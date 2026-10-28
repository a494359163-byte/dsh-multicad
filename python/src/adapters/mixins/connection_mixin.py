"""
Connection mixin for AutoCAD adapter.

Handles connection, disconnection, and validation methods.
"""

import logging
import sys
import time
from typing import TYPE_CHECKING, Any

if sys.platform == "win32":
    import win32com.client
    import pythoncom
    import pywintypes
else:
    raise ImportError("AutoCAD adapter requires Windows OS with COM support")

from core import CADConnectionError

if TYPE_CHECKING:
    from core.config import CADConfig

logger = logging.getLogger(__name__)

# HRESULTs raised while the CAD application is busy (redrawing, loading,
# showing a dialog). Retrying is the documented way to handle them.
_BUSY_HRESULTS = {0x80010001, 0x8001010A}  # CALL_REJECTED, CALL_REJECTED(busy)
_BUSY_HINTS = (
    "rejected by callee",
    "被调用方拒绝",
    "call was rejected",
    "server busy",
    "服务器忙",
    "系统忙",
)


def _is_cad_busy(error: Exception) -> bool:
    """Return True if this COM error just means CAD was busy and can be retried."""
    candidates = {getattr(error, "hresult", None)}
    args = getattr(error, "args", None)
    if args and isinstance(args[0], int):
        candidates.add(args[0])

    for hr in candidates:
        if isinstance(hr, int) and (hr & 0xFFFFFFFF) in _BUSY_HRESULTS:
            return True

    text = str(error).lower()
    return any(hint in text for hint in _BUSY_HINTS)


class ConnectionMixin:
    """Mixin for connection management."""

    if TYPE_CHECKING:
        # Tell type checker this mixin is used with CADAdapterProtocol
        cad_type: str
        config: "CADConfig"
        application: Any
        document: Any

        def _wait_for(
            self, condition: Any, timeout: float = 20.0, interval: float = 0.1
        ) -> bool: ...

    def connect(self, only_if_running: bool = False) -> bool:
        """Connect to the CAD application via COM, initializing COM for this thread.

        Tries to attach to an already-running instance first. If none is found
        and ``only_if_running`` is False, launches a new instance.

        Args:
            only_if_running: When True, return False instead of launching a new
                CAD instance if none is currently running.

        Returns:
            True if the connection was established successfully.

        Raises:
            CADConnectionError: If COM initialization fails or the ProgID is invalid.
        """
        try:
            logger.info(f"Connecting to {self.cad_type}...")

            # Initialize COM for this thread
            # CoInitialize() may raise if already initialized, which is fine
            try:
                pythoncom.CoInitialize()
            except Exception as e:
                logger.debug(
                    f"CoInitialize: {e} (may already be initialized for thread)"
                )

            # Try to get existing instance
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    self.application = win32com.client.GetActiveObject(
                        self.config.prog_id
                    )
                    logger.info(
                        f"{self.cad_type} instance found (active via GetActiveObject)"
                    )
                    break
                except Exception as e:
                    if attempt == max_retries - 1:
                        logger.debug(
                            f"GetActiveObject for {self.config.prog_id} failed after {max_retries} attempts: {e}"
                        )
                    else:
                        pythoncom.CoInitialize()  # Re-init just in case
                        import time

                        time.sleep(0.5)
                        continue

                # Start new instance
                if only_if_running:
                    logger.debug(
                        f"{self.cad_type} not running and only_if_running=True. Skipping launch."
                    )
                    return False

                logger.info(f"{self.cad_type} not running, starting new instance...")
                try:
                    self.application = win32com.client.Dispatch(self.config.prog_id)
                except pywintypes.com_error as com_err:
                    error_code = com_err.args[0] if com_err.args else None
                    if error_code == -2147221005:
                        error_msg = (
                            f"Invalid ProgID '{self.config.prog_id}'. "
                            f"Either {self.cad_type.upper()} is not installed or the ProgID is incorrect. "
                            f"Check config.json and ensure the application is installed."
                        )
                    else:
                        error_msg = str(com_err)
                    logger.error(
                        f"Failed to create {self.cad_type} instance: {error_msg}"
                    )
                    raise CADConnectionError(self.cad_type, error_msg)

                if self.application is not None:
                    # Try to make application visible (not all CAD types support this)
                    try:
                        self.application.Visible = True
                    except (pywintypes.com_error, AttributeError) as e:
                        logger.debug(
                            f"{self.cad_type} doesn't support Visible property or it's read-only: {e}"
                        )
                # Dispatch returns as soon as the COM server is registered, not
                # when the application can actually answer calls. Wait for a
                # real response before touching Documents.
                ready = self._wait_for(
                    self._is_application_ready,
                    timeout=self.config.startup_wait_time,
                )
                logger.info(
                    f"New {self.cad_type} instance started "
                    f"(ready={ready}, waited up to {self.config.startup_wait_time}s)"
                )

            # Get active document or create new. AutoCAD rejects these calls
            # while it is still loading ("Call was rejected by callee"), so they
            # go through the busy-retry helper.
            if self.application is not None:
                # Standard AutoCAD/ZWCAD/BricsCAD/GstarCAD handling
                doc_count = self._com_retry(
                    "Documents.Count", lambda: self.application.Documents.Count
                )
                if doc_count > 0:
                    self.document = self._com_retry(
                        "ActiveDocument", lambda: self.application.ActiveDocument
                    )
                    logger.info("Using existing active document")
                else:
                    self.document = self._com_retry(
                        "Documents.Add", lambda: self.application.Documents.Add()
                    )
                    logger.info("Created new document")

            # Validate connection
            if not self._validate_document():
                raise CADConnectionError(self.cad_type, "Document validation failed")

            logger.info(f"✓ Successfully connected to {self.cad_type}")

            return True

        except pywintypes.com_error as e:
            error_msg = f"COM error: {str(e)}"
            logger.error(f"Failed to connect to {self.cad_type}: {error_msg}")
            raise CADConnectionError(self.cad_type, error_msg)
        except Exception as e:
            logger.error(f"Failed to connect to {self.cad_type}: {e}")
            raise CADConnectionError(self.cad_type, str(e))

    def _com_retry(
        self,
        operation: str,
        func: Any,
        attempts: int = 6,
        delay: float = 0.25,
    ) -> Any:
        """Run a COM call, retrying while CAD reports that it is busy.

        AutoCAD rejects calls outright while it is loading, redrawing or showing
        a dialog, which is where the "Call was rejected by callee" failures in
        the logs come from. Retrying with a growing delay rides that out.

        Args:
            operation: Label used in debug logs.
            func: Zero-argument callable performing the COM call.
            attempts: Maximum number of attempts.
            delay: Base delay between attempts, in seconds (grows linearly).

        Returns:
            Whatever ``func`` returns.

        Raises:
            pywintypes.com_error: If the error is not a busy error, or every
                attempt failed.
        """
        last_error: Exception | None = None

        for attempt in range(attempts):
            try:
                return func()
            except pywintypes.com_error as e:
                last_error = e
                if attempt == attempts - 1 or not _is_cad_busy(e):
                    raise
                logger.debug(
                    f"{self.cad_type} busy during {operation}, "
                    f"retry {attempt + 1}/{attempts}"
                )
                time.sleep(delay * (attempt + 1))

        raise last_error  # pragma: no cover - final attempt always re-raises

    def is_installed(self) -> bool:
        """Return True if this CAD's COM ProgID is registered on this machine."""
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CLASSES_ROOT, rf"{self.config.prog_id}\CLSID"
            ):
                return True
        except OSError:
            return False

    def disconnect(self) -> bool:
        """Disconnect from CAD application with COM cleanup."""
        try:
            if self.application:
                self.application = None
                self.document = None
            pythoncom.CoUninitialize()
            logger.info(f"Disconnected from {self.cad_type}")
            return True
        except Exception as e:
            logger.error(f"Error disconnecting: {e}")
            return False

    def __enter__(self):
        """Enter context: connect to CAD application.

        Allows using the adapter as a context manager:
            with AutoCADAdapter("autocad") as adapter:
                adapter.draw_line((0,0), (10,10))
                # Auto-disconnect on exit

        Returns:
            Self (the adapter instance)

        Raises:
            CADConnectionError: If connection fails
        """
        if not self.connect():
            raise CADConnectionError(
                self.cad_type, "Connection failed during context manager initialization"
            )
        return self

    def __exit__(self, _exc_type, _exc_val, _exc_tb) -> None:
        """Exit context: disconnect from CAD application.

        Args:
            _exc_type: Exception type if raised
            _exc_val: Exception value if raised
            _exc_tb: Exception traceback if raised
        """
        self.disconnect()

    def is_connected(self) -> bool:
        """Check if connected to CAD application."""
        try:
            return (
                self.application is not None
                and self.document is not None
                and self._validate_document()
            )
        except Exception:
            return False

    def _is_application_ready(self) -> bool:
        """Return True once the CAD application answers a COM call.

        ``Dispatch`` succeeds as soon as the COM server is registered, which is
        long before AutoCAD has finished loading and can serve the object model.
        Reading ``Documents.Count`` is the cheapest call that fails until then.
        """
        try:
            application = self.application
            if application is None:
                return False
            _ = application.Documents.Count
            return True
        except Exception:
            return False

    def _validate_document(self) -> bool:
        """Validate that document is accessible."""
        try:
            if self.document is None:
                return False
            _ = self.document.Name
            return True
        except Exception:
            return False

    def check_document_change(self) -> bool:
        """
        Check if the active document in the CAD application has changed.
        If it has, update self.document to the new active document.

        Returns:
            bool: True if the document changed, False otherwise.
        """
        try:
            if not self.application:
                return False

            # If no documents are open, there's nothing to check
            if self.application.Documents.Count == 0:
                if self.document is not None:
                    self.document = None
                    return True
                return False

            active_doc = self.application.ActiveDocument

            # If we didn't have a document before, but now we do
            if self.document is None:
                self.document = active_doc
                return True

            # Compare names
            if self.document.Name != active_doc.Name:
                self.document = active_doc
                logger.info(f"Active document changed to: {active_doc.Name}")
                return True

            return False
        except Exception as e:
            # Silently catch COM errors during polling
            logger.debug(f"Error checking document change: {e}")
            return False

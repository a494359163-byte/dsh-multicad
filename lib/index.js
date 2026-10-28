import { cpSync, existsSync, mkdirSync, appendFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

/** Cordis plugin name used by loader diagnostics. */
export const name = 'multicad-setup'

const pkgDir = dirname(dirname(fileURLToPath(import.meta.url)))
const stateDir = join(process.env.LOCALAPPDATA ?? pkgDir, 'dsh-multicad')

function note(message) {
  try {
    mkdirSync(stateDir, { recursive: true })
    appendFileSync(join(stateDir, 'plugin.log'), `${new Date().toISOString()} ${message}\n`)
  } catch {
    // logging must never break plugin loading
  }
}

/**
 * Stage the bundled launcher and Python server into a stable, user-level
 * directory. The MCP row in `cordis.patch.yml` starts
 * `%LOCALAPPDATA%\dsh-multicad\bin\launch.cmd`, so it never depends on where
 * this package is installed. The launcher builds (and repairs) a private
 * virtual environment on first use.
 */
export const apply = () => {
  note(`apply start pkgDir=${pkgDir}`)
  try {
    mkdirSync(stateDir, { recursive: true })
    cpSync(join(pkgDir, 'bin'), join(stateDir, 'bin'), { recursive: true, force: true })
    cpSync(join(pkgDir, 'python'), join(stateDir, 'python'), { recursive: true, force: true })
  } catch (error) {
    note(`staging failed: ${error?.message ?? error}`)
    throw error
  }
  const launcher = join(stateDir, 'bin', 'launch.cmd')
  note(`apply done launcher=${launcher} exists=${existsSync(launcher)}`)
}

# dsh-multicad

把 **AutoCAD / 中望 ZWCAD / 浩辰 GstarCAD / BricsCAD** 接进 DeepSeek Harness 的 MCP 连接器插件。

内置 [multiCAD-mcp](https://github.com/AnCode666/multiCAD-mcp)，提供 7 个统一工具、覆盖 56 条 CAD 命令：画线/圆/矩形/多段线/样条/表格、图层管理、图块、实体选择与变换、导出 Excel/JSON、存 DWG/DXF/PDF。

## 安装

```bash
dsh plugin add dsh-multicad
```

装完**完全退出 DSH 再打开**，工具会以 `mcp__multicad__*` 出现。不需要单独安装 multiCAD-mcp，也不需要手动配 Python 环境。

## 它怎么工作

插件是一个 DSH bundle，包含四样东西：

1. **Python 源码**（`python/`）：内置的 multiCAD-mcp 服务端；
2. **启动器**（`bin/run.ps1` + `bin/setup.ps1`）：运行时按 `%LOCALAPPDATA%` 定位环境，缺了就建、坏了就修；
3. **环境**：首次启动在 `%LOCALAPPDATA%\dsh-multicad\venv` 建私有 venv 并装依赖（需联网，几分钟）；
4. **挂载**：`cordis.patch.yml` 往 DSH 里插一条 MCP 客户端记录，启动 `bin/run.ps1`。

所有路径都在运行时解析，跟用户名、安装位置无关。venv 被删掉后，下次启动会自动重建。

日志：

- `%LOCALAPPDATA%\dsh-multicad\plugin.log` —— 插件加载与铺文件
- `%LOCALAPPDATA%\dsh-multicad\setup.log` —— 环境安装
- `<项目>\logs\multicad_mcp.log` —— 服务端日志

## 前提

- Windows
- 本机装了 AutoCAD 2018+、ZWCAD 2020+、GstarCAD 2020+ 或 BricsCAD 21+
- PATH 上有 Python 3.10+（`py -3` 或 `python` 能跑）
- CAD 必须和 DSH 用同一个 Windows 用户、同样权限级别运行

想用自己已有的 Python 环境，可不装依赖：

```powershell
setx MULTICAD_PYTHON "E:\your-venv\Scripts\python.exe"
```

## 工具

`mcp__multicad__*` 一共 7 个：`manage_session`、`draw_entities`、`manage_layers`、`manage_entities`、`manage_blocks`、`manage_files`、`export_data`。

## 排错

| 现象 | 处理 |
|---|---|
| 工具没出现 | 看 `plugin.log` 和 `setup.log`；确认 PATH 上有 Python 3.10+ |
| 连不上 CAD | 确认 CAD 已打开、非管理员运行、与 DSH 同用户 |
| 首次启动很慢 | 正常，正在装依赖；之后秒开 |

## License

Apache-2.0。内置的 multiCAD-mcp 版权归其作者所有，见 `NOTICE`。

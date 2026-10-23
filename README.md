# PolyXRD GetCIF

**CIF 检索与获取小工具** —— PolyXRD 家族成员。单文件 exe，双击即用。

![logo](resources/logo-horizontal.png)

## 版本与发布形态

| 形态 | 文件 | 体积 | 注册机制 | 适用 |
|---|---|---|---|---|
| **标准版**（单文件） | `PolyXRD-GetCIF.exe` | ~106 MB | ✅ | 检索 / 预览 / 下载全功能；**不含 3D 预览**（matplotlib/numpy 已裁剪 + Qt 未用模块精简） |
| **Plus 版**（单文件） | `PolyXRD-GetCIF-Plus.exe` | ~269 MB | ✅ | 含**应用内 3D 结构展示**（对称操作展开渲染）+ 完整 Qt，为后续功能扩展预留 |
| **内部评估版**（单文件） | `PolyXRD-GetCIF-Internal.exe` | ~269 MB | ❌ 停用 | 内部评估自用：Plus 基底（含 3D），无注册提示/注册码入口，状态栏右侧固定显示「内部评估版本」 |
| **安装包**（Setup） | `PolyXRD-GetCIF-Setup.exe` / `PolyXRD-GetCIF-Plus-Setup.exe` | ~100/270 MB | ✅ | 正常安装流程：可选安装位置、开始菜单/桌面快捷方式、带卸载；onedir 版启动免自解压；装后每次启动检查注册（同单文件版） |

标准版 / Plus 版 / 安装包：未注册每次启动提示版权信息，注册后状态栏右侧显示单位部门名称；
**内部评估版**注册机制整体停用。两个单文件版检索能力完全一致（COD / 本地库 / polyDB / xinDB / AMCSD / MP / Atomly）；
标准版预览窗会提示升级 Plus。

## 功能

- **多数据源检索**，左侧检索条件 / 右侧结果列表：
  | 数据源 | 说明 | 默认 |
  |---|---|---|
  | COD（联网） | Crystallography Open Database，无需凭证 | ✅ 开启 |
  | COD 本地库 | SQLite 检索索引（兼容 PolyXRD 全库 `cod_index.sqlite`） | 配置后开启 |
  | polyDB 外挂库 | PolyXRD v4 目录容器（`meta.json` + `index.sqlite`）；CIF 按 `cif_rel` 相对数据根目录解析 | 配置后开启 |
  | xinDB 库 | XinMatch v3 单文件（`.xinDB`）；仅元数据检索，不含 CIF 原文 | 配置后开启 |
  | AMCSD（联网） | rruff.geo.arizona.edu，无需凭证 | 手动开启 |
  | Materials Project | 需免费 API Key（materialsproject.org） | 配置后开启 |
  | Atomly | 需 Token（atomly.net 登录后 localStorage 取 `userToken`） | 配置后开启 |
- **检索条件**：化学式、元素、名称/关键词、空间群、晶系（本地库）、晶胞参数 a/b/c/α/β/γ
- **候选预览**：双击结果行弹出预览窗 —— 结构信息、CIF 全文、3D 结构展示（Plus 版）、下载/另存
- **三语界面**：中文 / English / 日本語（菜单即时切换）
- **注册机制**：未注册每次启动提示版权信息；输入注册码后状态栏右侧显示注册单位
- **帮助菜单**：版权与许可（双许可说明）· 关于
- **明亮模式界面**：与家族工具一致的浅色接口（PolyXRD 青色强调）

## 注册机制

复用 PolyXRD 家族统一注册机制（与 PolyXRD-Reg 注册机算法一致）；**内部评估版（Internal）整体停用注册机制**，不受本节约束：

| 场景 | 行为 |
|---|---|
| 未注册，每次打开软件 | 弹窗：「本软件未注册，版权所有，禁止用于商业用途。如需注册请联系 sshztx@outlook.com」 |
| 点「确定」 | 关闭弹窗，软件正常使用；下次打开依旧提示 |
| 点「输入注册码」 | 打开注册对话框，粘贴注册码 → 校验通过即注册成功，以后不再提示 |
| 帮助菜单 | 固定包含「输入注册码 (&R)…」 |
| 注册成功后 | 状态栏最下面一排最右侧（右对齐）显示「已注册：\<单位部门名称\>」；未注册显示「未注册」 |

- 注册码由**开发方**根据用户提供的「单位部门名称」生成（PolyXRD-Reg 注册机 / `make_reg_code.py`），用户在软件内「帮助 → 输入注册码」粘贴后即完成注册；
- 注册码格式 `PXRD1-XXXX-XXXX-...`：Base32 编码的「单位部门名称 + HMAC 签名」，软件端离线校验真伪并还原单位名，**无需联网、无需机器码**，同一注册码可在同一单位的多台电脑使用；
- 注册状态保存于 `%APPDATA%\PolyXRD\GetCIF\registration.json`，每次启动重新校验，手改文件伪造「已注册」无效。

## 开发运行

```bash
# 依赖（PolyXRD venv 已齐备）
pip install -r requirements.txt

# 启动
set PYTHONPATH=src
python -m getcif.gui

# 离屏冒烟
QT_QPA_PLATFORM=offscreen python -m getcif.gui --smoke --no-splash
```

## 打包全版本

```bat
build.bat
:: 产物: dist\PolyXRD-GetCIF.exe                 （标准版 onefile，去3D+裁剪Qt）
::       dist\PolyXRD-GetCIF-Plus.exe            （Plus 版 onefile，含3D+全量Qt）
::       dist\PolyXRD-GetCIF-Internal.exe        （内部评估版 onefile，Plus基底+无注册）
::       dist\PolyXRD-GetCIF\                    （标准版 onedir，供安装包）
::       dist\PolyXRD-GetCIF-Plus\               （Plus 版 onedir，供安装包）
::       installer\Output\PolyXRD-GetCIF-Setup.exe       （标准版安装包）
::       installer\Output\PolyXRD-GetCIF-Plus-Setup.exe  （Plus 版安装包）
```

构建脚本为纯 ASCII + CRLF（cmd 在 cp65001 下解析含全角字符的批处理行可能错位）；
安装包需要 Inno Setup 6（未安装时自动跳过 Setup 步骤）。

## 配置存储

`%APPDATA%\PolyXRD\GetCIF\settings.toml`（数据源开关、凭证、索引路径、语言）；
其中 `[local]` 节含 `db_path`（COD 索引）、`polydb_path`（polyDB 目录）、`xindb_path`（xinDB 文件）、`cod_root`（数据根目录）；
注册状态 `%APPDATA%\PolyXRD\GetCIF\registration.json`；
CIF 下载默认目录 `%APPDATA%\PolyXRD\GetCIF\downloads`。

## 数据源致谢

COD · AMCSD/RRUFF · Materials Project · Atomly 的公开数据服务。
本地库格式兼容 PolyXRD（polyDB v1）与 XinMatch（xinDB v3）的外挂数据库。

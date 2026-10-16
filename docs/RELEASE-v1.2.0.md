# PolyXRD GetCIF v1.2.0

**CIF 检索与获取小工具** —— PolyXRD 家族成员。单文件 exe 或安装包，双击即用，无需安装。

![logo](resources/logo-horizontal.png)

## 📦 发布形态（按需下载其一即可）

| 形态 | 资产 | 体积 | 注册机制 | 适用 |
|---|---|---|---|---|
| **标准版** | `PolyXRD-GetCIF.exe` | ~106 MB | ✅ | 单文件免安装；检索 / 预览 / 下载全功能，无 3D |
| **Plus 版** | `PolyXRD-GetCIF-Plus.exe` | ~269 MB | ✅ | 单文件免安装；含**应用内 3D 结构展示** + 完整 Qt |
| **内部评估版** | `PolyXRD-GetCIF-Internal.exe` | ~269 MB | ❌ 停用 | 内部评估自用；Plus 基底（含 3D），状态栏右侧固定显示「内部评估版本」 |
| **标准版安装包** | `PolyXRD-GetCIF-Setup.exe` | ~40-60 MB | ✅ | 正常安装流程（可选安装位置、快捷方式、卸载） |
| **Plus 版安装包** | `PolyXRD-GetCIF-Plus-Setup.exe` | ~100-120 MB | ✅ | 同上（含 3D） |

单文件版首次启动解压需数秒；安装包装入本机磁盘后**启动免自解压**，更快。

## ✨ v1.2.0 更新

### 内部评估版（Internal）

- Plus 基底（含 3D 预览 + 全量 Qt），单文件 exe；
- **注册机制整体停用**：无未注册启动提示、帮助菜单无「输入注册码」；
- 主窗口状态栏最下面一排最右侧（右对齐）固定显示「内部评估版本」（三语随界面语言切换）；
- 由 `PolyXRD-GetCIF-Internal.spec` 打包时注入标记文件实现，运行时 `utils/build_variant.py` 判定，源码测试可用 `POLYXRD_GETCIF_INTERNAL=1` 强制。

### Setup 安装包（Inno Setup 6）

- 标准 / Plus 各一个安装包；**可在安装向导中选择安装位置**（默认 `%LOCALAPPDATA%\Programs\PolyXRD\GetCIF[-Plus]`，按用户级安装、无需管理员权限）；
- 显示许可协议（LICENSE-CN）→ 可选创建桌面快捷方式 → 开始菜单快捷方式 + 卸载入口；
- 完整卸载支持（控制面板「应用和功能」可卸载）；
- 安装的是 **onedir 目录版**（非 onefile 自解压），启动更快；
- 装后每次启动检查注册情况，行为与单文件版完全一致（未注册提示 / 输入注册码 / 状态栏右侧显示注册单位）。

### 其他

- 语言切换后，状态栏右侧注册状态文案即时随界面语言刷新（v1.1.0 需重启或触发注册事件后才刷新）。

## 📥 安装（Setup 版）

1. 下载 `PolyXRD-GetCIF-Setup.exe`（或 Plus 版）；
2. 双击运行 → 接受许可 → **选择安装位置**（默认即可）→ 勾选是否创建桌面快捷方式 → 安装；
3. 完成后从开始菜单 / 桌面 / 安装向导「运行」启动；
4. 卸载：Windows「设置 → 应用」或开始菜单「Uninstall PolyXRD GetCIF」。

## ✅ 发布前验证

- 离线自检 38 项全过（CIF 解析 / MP structure→CIF / 本地库过滤 / 3D / 注册机制 11 项 / **内部评估版链路** / GUI 冒烟）
- 内部评估版链路：注册管理器未创建、帮助菜单无注册入口、状态栏「内部评估版本」右对齐贴右端、en/ja/zh 三语切换同步
- 5 个构建产物 + 2 个安装包全部产出；单文件版离屏冒烟 EXIT=0；安装包静默安装到指定目录后运行冒烟 EXIT=0 并可正常静默卸载

运行 `tests/run_checks.py`（`--online` 附加联网检查）可复现以上验证；
`tests/_interactive_reg_check.py` / `tests/_internal_edition_check.py` 分别复现注册与内部版链路。

## 📄 许可

双许可（学术 / 商业），详见 LICENSE 与 LICENSE-CN。

## 🙏 数据源致谢

COD · AMCSD/RRUFF · Materials Project · Atomly 的公开数据服务。

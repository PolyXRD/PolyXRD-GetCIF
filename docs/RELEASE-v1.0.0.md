# PolyXRD GetCIF v1.0.0

**CIF 检索与获取小工具** —— PolyXRD 家族成员。单文件 exe，双击即用，无需安装。

![logo](resources/logo-horizontal.png)

## 📦 两个版本（按需下载其一即可）

| 版本 | 资产 | 体积 | 适用 |
|---|---|---|---|
| **标准版** | `PolyXRD-GetCIF.exe` | ~106 MB | 只需检索 / 预览 / 下载 CIF；轻量（无 3D，Qt 已精简） |
| **Plus 版** | `PolyXRD-GetCIF-Plus.exe` | ~269 MB | 需要**应用内 3D 结构展示**（对称操作展开渲染）；保留完整 Qt 便于后续功能扩展 |

两个版本检索能力完全一致；标准版预览窗会提示升级 Plus。

## ✨ 功能

- **多数据源检索**（左侧检索条件 / 右侧结果列表）：
  | 数据源 | 说明 | 默认 |
  |---|---|---|
  | COD（联网） | Crystallography Open Database，无需凭证 | ✅ 开启 |
  | COD 本地库 | SQLite 检索索引（兼容 PolyXRD 全库 `cod_index.sqlite`） | 配置后开启 |
  | AMCSD（联网） | rruff.geo.arizona.edu，无需凭证 | 手动开启 |
  | Materials Project | 需免费 API Key（materialsproject.org） | 配置后开启 |
  | Atomly | 需 Token（atomly.net 登录后 localStorage 取 `userToken`） | 配置后开启 |
- **检索条件**：化学式、元素、名称/关键词、空间群、晶系（本地库）、晶胞参数 a/b/c/α/β/γ
- **候选预览**：双击结果行弹出预览窗 —— 结构信息、CIF 全文、3D 结构展示（Plus 版）、下载/另存
- **三语界面**：中文 / English / 日本語（菜单即时切换）
- **PolyXRD 主题**：与家族一致的 logo、splash、深海军蓝 + 青色配色

## 📥 安装

1. 下载下方 Assets 中任一版本的 exe（单文件免安装）；
2. 双击运行。首次启动解压需数秒，属正常现象；
3. 配置保存在 `%APPDATA%\PolyXRD\GetCIF\settings.toml`，下载的 CIF 默认存于 `%APPDATA%\PolyXRD\GetCIF\downloads`。

## ✅ 发布前验证

- 离线自检 24 项全过：CIF 解析（对称操作数值验证 / esd 剥离 / 分号多行块）、MP structure→CIF、本地库六类条件过滤、3D 渲染、GUI 离屏冒烟
- 在线实测：COD 检索 `SiO2`（247 条命中）→ CIF 下载 → 解析 → 3D 渲染全链路通过
- 双版本产物离屏冒烟均 EXIT=0（标准版 111,606,058 字节 / Plus 版 282,033,656 字节）

运行 `tests/run_checks.py`（`--online` 附加联网检查）可复现以上验证。

## 📄 许可

双许可（学术 / 商业），详见 LICENSE 与 LICENSE-CN。

## 🙏 数据源致谢

COD · AMCSD/RRUFF · Materials Project · Atomly 的公开数据服务。

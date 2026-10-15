# PolyXRD GetCIF

**CIF 检索与获取小工具** —— PolyXRD 家族成员。单文件 exe，双击即用。

![logo](resources/logo-horizontal.png)

## 功能

- **多数据源检索**，左侧检索条件 / 右侧结果列表：
  | 数据源 | 说明 | 默认 |
  |---|---|---|
  | COD（联网） | Crystallography Open Database，无需凭证 | ✅ 开启 |
  | COD 本地库 | SQLite 检索索引（兼容 PolyXRD 全库 `cod_index.sqlite`） | 配置后开启 |
  | AMCSD（联网） | rruff.geo.arizona.edu，无需凭证 | 手动开启 |
  | Materials Project | 需免费 API Key（materialsproject.org） | 配置后开启 |
  | Atomly | 需 Token（atomly.net 登录后 localStorage 取 `userToken`） | 配置后开启 |
- **检索条件**：化学式、元素、名称/关键词、空间群、晶系（本地库）、晶胞参数 a/b/c/α/β/γ
- **候选预览**：双击结果行弹出预览窗 —— 结构信息、CIF 全文、**3D 结构展示**（对称操作展开）、下载/另存
- **三语界面**：中文 / English / 日本語（菜单即时切换）
- **PolyXRD 主题**：与家族一致的 logo、splash、深海军蓝 + 青色配色

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

## 打包单 exe

```bat
build.bat
:: 产物: dist\PolyXRD-GetCIF.exe
```

## 配置存储

`%APPDATA%\PolyXRD\GetCIF\settings.toml`（数据源开关、凭证、索引路径、语言）；
CIF 下载默认目录 `%APPDATA%\PolyXRD\GetCIF\downloads`。

## 数据源致谢

COD · AMCSD/RRUFF · Materials Project · Atomly 的公开数据服务。

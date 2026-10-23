# PolyXRD GetCIF v1.4.0

**CIF 检索与获取小工具** —— PolyXRD 家族成员。单文件 exe 或安装包，双击即用，无需安装。

![logo](resources/logo-horizontal.png)

## 📦 本版本发布形态

本版本沿用 v1.3.0 起的收敛口径，**仅发布以下两个资产**：

| 资产 | 体积 | 注册机制 | 适用 |
|---|---|---|---|
| `PolyXRD-GetCIF-Internal.exe` | ~234 MB | ❌ 停用 | **内部评估版**：Plus 基底（含应用内 3D 结构展示 + 完整 Qt），状态栏**水平居中**固定显示「内部评估版本」（加粗红字，字号不变） |
| `PolyXRD-GetCIF-Plus-Setup.exe` | ~100-120 MB | ✅ | **Plus 版安装包**：正常安装流程（可选安装位置 / 快捷方式 / 卸载），含 3D + 完整 Qt，启动免自解压 |

> 标准单文件版、Plus 单文件版、标准安装包不在本 release 发布范围内。
> 单文件版首次启动解压需数秒；安装包装入本机磁盘后启动免自解压，更快。

## ✨ v1.4.0 更新

### 本地库：列表式多库挂载（对齐 PolyXRD v4.0.0 / XinMatch v2.0.0）

PolyXRD v4.0.0 与 XinMatch v2.0.0 都把外挂库从「一类一个槽位」改成「想挂几个挂几个」
（COD-Inorg + COD-Full 是两份互不包含的库；3COD 拆成 COD / PCOD / TCOD 三份）。
本版把数据源设置里的本地库同步成**列表**：

- polyDB、xinDB 各一张列表，**一行 = 一个已挂载的库**；可添加、可移除、可单选某行卸下；
- 每行直接显示库状态：变体 / 库标识、物相数、体积、建库或快照日期；不可用时给出可读原因，
  悬停看明细（路径、峰口径、建库时间、缺失段等）；
- 添加时可指向**库本体**，也可指向**装着若干库的父目录**（如 `PolyXRD-DataBase\polydb`、
  `XinMatch-DataBase\data`），自动展开其中所有 `.polyDB` / `.xinDB`；
- 检索时逐库查询后合并，候选 `provenance` 末尾标明所属库；同 `eid` 跨库重复只保留一份；
- 状态栏「已启用」提示会带库数量（如 `polyDB 外挂库 ×2`），避免误以为只挂了第一份。

配置持久化：`settings.toml [local]` 新增 `polydb_paths` / `xindb_paths`（换行分隔）。
**老配置无需迁移**：原 `polydb_path` / `xindb_path` 读取时自动并入列表首位，写入时同步为列表首项。

### 兼容最新库格式

| 项 | 处理 |
|---|---|
| polyDB v1（20261021 版 `entries` 含 `tier` / `dup_group` / `cif_rel` / `src_mtime` / `row_idx` + FTS5） | 只取标量列，新旧 v1 库通用；`meta.sections` 声明了 `bytes` 才校验大小（挡住拷贝中断的半成品），未声明不判死 |
| xinDB v3（`meta` 新增 `library_kind` / `data_date` / `top_k` / `build_tool` / `peak_convention`） | 读出并在界面展示；`schema_version` 缺失时按表结构判定（早期构建有漏写），写了必须是 3 |
| 旧版 XinMatch 库（`entries` + `peaks`） | 明确报「旧版 XinMatch 库，请用 XinMatch ≥ 2.0 重建为 .xinDB v3」，不再只报缺表 |
| polyDB 的 CIF 相对路径 | 按**候选所属库**的 `meta.json` 解析，候选根依次为：设置里的「数据根目录」→ 环境变量 `XRD_DATA_ROOT` → `meta.source.root` → 库目录；每个根再覆盖 `COD` / `PCOD` / `TCOD` 与 `inorg_cif/<lib>` 子目录。取不回时提示已查找了几个根，指明该配哪里 |

> 修的是实打实的坑：`cif_rel` 形如 `1/00/00/1000003.cif`，实际文件在
> `<数据根>/COD/1/00/00/...`，而建库机写进 `meta.source.root` 的路径常常已经失效
> （数据根迁到 `sync-COD` 之后尤其如此）。旧逻辑只试「数据根目录 / 库目录 / 库父目录」，
> 对这类布局一律取不回 CIF。

### 内部评估版状态栏提示：真正居中

- 旧实现用 `QStatusBar.addWidget()` 放提示，而 `showMessage()`（本窗口每次检索、每次设置保存
  都会调用）**会临时隐藏这类普通控件** —— 结果这条提示实际几乎永远看不见；
- 改为 `addPermanentWidget()` + 两侧弹性占位，提示稳定**水平居中**；颜色由砖红 `#C0392B`
  改为**纯红 `#FF0000`**，加粗保持不变，**字号沿用全局 QSS 未作调整**；
- 自检里加了回归项：`showMessage()` 之后断言提示仍可见，并校验标签中心与状态栏中心偏差 ≤ 24 px。

## ✅ 发布前验证

- 离线自检 **72 项全过**（v1.3.0 为 62 项，本版新增 10 项多库用例）：
  CIF 解析 / MP structure→CIF / COD 本地库 / **polyDB 12 项** / **xinDB 10 项** /
  **多库挂载 10 项**（两条路径都生效、父目录自动展开、候选标注所属库、兼容旧单路径配置、
  xinDB 目录展开与库标识读取、两库结果合并）/ 主题与帮助菜单 / 3D 渲染 / 注册机制 /
  内部评估版链路（含居中与可见性回归）/ GUI 离屏冒烟；
- 另用**真实库**联调（不入自检、不依赖本机路径）：`COD-Inorg-20261021.polyDB`（77,500 相）
  + `COD-Full-20261021.polyDB`（521,361 相）自动展开为 2 行；`COD/PCOD/TCOD-Inorg-20261020.xinDB`
  （78,036 / 1,061,953 / 46,846 相）自动展开为 3 行；SiO₂ 检索两库结果合并，polyDB 候选的
  CIF 按 `cif_rel` 成功取回；
- 自检在独立临时配置目录中进行（`POLYXRD_GETCIF_CONFIG_DIR`），不读写用户真实 `settings.toml`。

## 📄 许可

双许可（学术 / 商业），详见 LICENSE 与 LICENSE-CN；帮助菜单「版权与许可」可随时查看精简说明。

## 🙏 数据源致谢

COD · AMCSD/RRUFF · Materials Project · Atomly 的公开数据服务。
本地库格式兼容 PolyXRD（polyDB v1）与 XinMatch（xinDB v3）。

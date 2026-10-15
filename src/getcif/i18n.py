"""轻量三语支持（中文源语言 + English / 日本語）。

约定与 PolyXRD 家族一致：中文原文即 key，未收录字符串原样透传。
语言持久化在 settings.toml ``[ui] language``。
"""
from __future__ import annotations

from getcif.core import config

SUPPORTED_LANGUAGES: dict[str, str] = {
    "zh": "中文",
    "en": "English",
    "ja": "日本語",
}

_current_language = "zh"

_TRANSLATIONS: dict[str, dict[str, str]] = {
    # ---- 菜单 ----
    "文件 (&F)": {"en": "&File", "ja": "ファイル(&F)"},
    "设置 (&S)": {"en": "&Settings", "ja": "設定(&S)"},
    "数据源设置…": {"en": "Data Sources…", "ja": "データソース設定…"},
    "语言 (&L)": {"en": "&Language", "ja": "言語(&L)"},
    "退出 (&Q)": {"en": "&Quit", "ja": "終了(&Q)"},
    "帮助 (&H)": {"en": "&Help", "ja": "ヘルプ(&H)"},
    "关于 {} (&A)": {"en": "About {} (&A)", "ja": "{} について(&A)"},
    "界面语言已切换：{}": {"en": "UI language switched: {}", "ja": "表示言語を切り替えました: {}"},
    # ---- 检索条件面板 ----
    "检索条件": {"en": "Search Criteria", "ja": "検索条件"},
    "化学式": {"en": "Formula", "ja": "化学式"},
    "元素": {"en": "Elements", "ja": "元素"},
    "名称 / 关键词": {"en": "Name / Keyword", "ja": "名称 / キーワード"},
    "空间群": {"en": "Space Group", "ja": "空間群"},
    "晶系（仅本地库过滤）": {"en": "Crystal System (local filter)", "ja": "結晶系（ローカル検索のみ）"},
    "晶胞参数（可选）": {"en": "Lattice Parameters (optional)", "ja": "格子定数（任意）"},
    "a (Å)": {"en": "a (Å)", "ja": "a (Å)"},
    "b (Å)": {"en": "b (Å)", "ja": "b (Å)"},
    "c (Å)": {"en": "c (Å)", "ja": "c (Å)"},
    "α (°)": {"en": "α (°)", "ja": "α (°)"},
    "β (°)": {"en": "β (°)", "ja": "β (°)"},
    "γ (°)": {"en": "γ (°)", "ja": "γ (°)"},
    "结果数上限": {"en": "Max results", "ja": "最大件数"},
    "检索 (&S)": {"en": "Search (&S)", "ja": "検索(&S)"},
    "清空 (&C)": {"en": "Clear (&C)", "ja": "クリア(&C)"},
    "如 SiO2 / CaMg(CO3)2": {"en": "e.g. SiO2 / CaMg(CO3)2", "ja": "例: SiO2 / CaMg(CO3)2"},
    "如 Ti,O 或 Ti O": {"en": "e.g. Ti,O or Ti O", "ja": "例: Ti,O または Ti O"},
    "如 Quartz / Rutile": {"en": "e.g. Quartz / Rutile", "ja": "例: Quartz / Rutile"},
    "如 Pnma / R-3c / 62": {"en": "e.g. Pnma / R-3c / 62", "ja": "例: Pnma / R-3c / 62"},
    "请输入至少一个检索条件": {"en": "Enter at least one search criterion", "ja": "検索条件を 1 つ以上入力してください"},
    "已清空检索条件": {"en": "Search criteria cleared", "ja": "検索条件をクリアしました"},
    "输入有误：{}": {"en": "Invalid input: {}", "ja": "入力エラー: {}"},
    "没有已启用的数据源，请在「设置 → 数据源设置」中配置": {
        "en": "No data source enabled; configure in Settings → Data Sources",
        "ja": "有効なデータソースがありません。設定 → データソース設定で構成してください",
    },
    # ---- 结果表 ----
    "检索结果": {"en": "Search Results", "ja": "検索結果"},
    "来源": {"en": "Source", "ja": "ソース"},
    "编号": {"en": "ID", "ja": "ID"},
    "晶胞 a/b/c (Å)": {"en": "Cell a/b/c (Å)", "ja": "格子 a/b/c (Å)"},
    "体积 (Å³)": {"en": "Volume (Å³)", "ja": "体積 (Å³)"},
    "预览 / 下载": {"en": "Preview / Download", "ja": "プレビュー / ダウンロード"},
    "双击行打开 CIF 预览": {"en": "Double-click a row to preview CIF", "ja": "行をダブルクリックで CIF プレビュー"},
    "候选 {} 条": {"en": "{} candidates", "ja": "候補 {} 件"},
    "未找到匹配的结构": {"en": "No matching structures found", "ja": "該当する構造が見つかりません"},
    "（部分数据源不可用，结果不完整）": {"en": " (some sources unavailable)", "ja": "（一部のデータソースが利用不可）"},
    # ---- 状态 ----
    "就绪 —— 输入检索条件后点击「检索」": {"en": "Ready — enter criteria and click Search", "ja": "準備完了 — 条件を入力して「検索」をクリック"},
    "正在检索…": {"en": "Searching…", "ja": "検索中…"},
    "检索完成：{} 条候选": {"en": "Search finished: {} candidates", "ja": "検索完了: 候補 {} 件"},
    "检索完成：无候选": {"en": "Search finished: no candidates", "ja": "検索完了: 候補なし"},
    "检索失败：{}": {"en": "Search failed: {}", "ja": "検索失敗: {}"},
    "检索中：{}": {"en": "Searching: {}", "ja": "検索中: {}"},
    "已启用：{}": {"en": "Enabled: {}", "ja": "有効: {}"},
    "取消 (&X)": {"en": "Cancel (&X)", "ja": "キャンセル(&X)"},
    "（尚未检索）": {"en": "(not searched yet)", "ja": "（未検索）"},
    # ---- 数据源名 ----
    "COD（联网）": {"en": "COD (online)", "ja": "COD（オンライン）"},
    "COD 本地库": {"en": "COD Local", "ja": "COD ローカル"},
    "AMCSD（联网）": {"en": "AMCSD (online)", "ja": "AMCSD（オンライン）"},
    "MP（联网）": {"en": "MP (online)", "ja": "MP（オンライン）"},
    "Atomly（联网）": {"en": "Atomly (online)", "ja": "Atomly（オンライン）"},
    # ---- 预览对话框 ----
    "CIF 预览": {"en": "CIF Preview", "ja": "CIF プレビュー"},
    "结构信息": {"en": "Structure Info", "ja": "構造情報"},
    "CIF 内容": {"en": "CIF Content", "ja": "CIF 内容"},
    "3D 结构": {"en": "3D Structure", "ja": "3D 構造"},
    "空间群（H-M）": {"en": "Space Group (H-M)", "ja": "空間群（H-M）"},
    "晶胞参数": {"en": "Lattice Parameters", "ja": "格子定数"},
    "晶胞体积": {"en": "Cell Volume", "ja": "格子体積"},
    "下载 CIF (&D)": {"en": "&Download CIF", "ja": "CIF をダウンロード(&D)"},
    "另存为…": {"en": "Save As…", "ja": "名前を付けて保存…"},
    "下载中…": {"en": "Downloading…", "ja": "ダウンロード中…"},
    "CIF 下载失败：{}": {"en": "CIF download failed: {}", "ja": "CIF ダウンロード失敗: {}"},
    "已保存：{}": {"en": "Saved: {}", "ja": "保存しました: {}"},
    "保存失败：{}": {"en": "Save failed: {}", "ja": "保存に失敗: {}"},
    "保存 CIF 文件": {"en": "Save CIF File", "ja": "CIF ファイルを保存"},
    "CIF 文件 (*.cif);;所有文件 (*)": {"en": "CIF Files (*.cif);;All Files (*)", "ja": "CIF ファイル (*.cif);;すべてのファイル (*)"},
    "该数据源不提供 CIF 下载": {"en": "This source does not provide CIF download", "ja": "このソースは CIF ダウンロードに対応していません"},
    "正在获取 CIF…": {"en": "Fetching CIF…", "ja": "CIF を取得中…"},
    "无法解析 CIF，3D 预览不可用": {"en": "Cannot parse CIF; 3D preview unavailable", "ja": "CIF を解析できず、3D プレビューは利用できません"},
    "尚无 CIF 内容，请先下载": {"en": "No CIF content yet; download first", "ja": "CIF が未取得です。先にダウンロードしてください"},
    "3D 预览不可用": {"en": "3D preview unavailable", "ja": "3D プレビューは利用できません"},
    "原子数": {"en": "Atoms", "ja": "原子数"},
    "化学式": {"en": "Formula", "ja": "化学式"},
    "元素": {"en": "Elements", "ja": "元素"},
    # ---- 设置对话框 ----
    "数据源设置": {"en": "Data Source Settings", "ja": "データソース設定"},
    "启用（联网检索 CIF，默认开启）": {"en": "Enable (online CIF search; on by default)", "ja": "有効化（オンライン CIF 検索、デフォルト ON）"},
    "启用（配置检索索引后生效）": {"en": "Enable (active after index configured)", "ja": "有効化（インデックス設定後に有効）"},
    "启用（无需配置，配置完成后勾选开启）": {"en": "Enable (no credentials needed; check to turn on)", "ja": "有効化（認証情報不要、チェックで ON）"},
    "API Key（materialsproject.org 免费注册获取；配置后可开启）": {
        "en": "API Key (free at materialsproject.org; enable after entering)",
        "ja": "API Key（materialsproject.org で無料取得；入力後に有効化可）",
    },
    "Token（atomly.net 登录后获取；配置后可开启）": {
        "en": "Token (from atomly.net login; enable after entering)",
        "ja": "Token（atomly.net ログイン後に取得；入力後に有効化可）",
    },
    "检索索引（cod_index.sqlite，兼容 PolyXRD 全库索引）": {
        "en": "Search index (cod_index.sqlite; PolyXRD full-index compatible)",
        "ja": "検索インデックス（cod_index.sqlite、PolyXRD 互換）",
    },
    "COD 数据根目录（可选，用于解析相对路径的 CIF 文件）": {
        "en": "COD data root (optional; resolves relative CIF paths)",
        "ja": "COD データルート（任意、相対パス CIF の解決用）",
    },
    "网络超时（秒）": {"en": "Network timeout (s)", "ja": "ネットワークタイムアウト（秒）"},
    "浏览…": {"en": "Browse…", "ja": "参照…"},
    "确定 (&O)": {"en": "&OK", "ja": "OK(&O)"},
    "取消 (&C)": {"en": "&Cancel", "ja": "キャンセル(&C)"},
    "说明：COD 联网检索默认开启；AMCSD 无需凭证；MP 需要 API Key；Atomly 需要 Token。本地库需指向 SQLite 检索索引。": {
        "en": "Note: COD online search is on by default; AMCSD needs no credentials; MP needs an API Key; Atomly needs a Token. The local library points to a SQLite search index.",
        "ja": "メモ: COD オンライン検索はデフォルト ON。AMCSD は認証不要。MP は API Key、Atomly は Token が必要。ローカル庫は SQLite インデックスを指定。",
    },
    "设置已保存": {"en": "Settings saved", "ja": "設定を保存しました"},
    "选择检索索引文件": {"en": "Select search index file", "ja": "検索インデックスを選択"},
    "SQLite 数据库 (*.sqlite *.db);;所有文件 (*)": {
        "en": "SQLite Database (*.sqlite *.db);;All Files (*)",
        "ja": "SQLite データベース (*.sqlite *.db);;すべてのファイル (*)",
    },
    "选择目录": {"en": "Select Folder", "ja": "フォルダーを選択"},
    # ---- 关于 ----
    "关于": {"en": "About", "ja": "バージョン情報"},
    "CIF 检索与获取小工具": {"en": "CIF Search & Fetch Tool", "ja": "CIF 検索・取得ツール"},
    "数据源：COD · AMCSD · Materials Project · Atomly · 本地库": {
        "en": "Sources: COD · AMCSD · Materials Project · Atomly · Local",
        "ja": "データソース: COD · AMCSD · Materials Project · Atomly · ローカル",
    },
    "关闭": {"en": "Close", "ja": "閉じる"},
    "确定": {"en": "OK", "ja": "OK"},
}


def current_language() -> str:
    return _current_language


def set_language(lang: str) -> None:
    global _current_language
    _current_language = lang if lang in SUPPORTED_LANGUAGES else "zh"


def tr(text: str) -> str:
    """翻译一条 UI 文案（中文原样返回；未收录透传，绝不抛异常）。"""
    entry = _TRANSLATIONS.get(text)
    if entry is None:
        return text
    return entry.get(_current_language) or text


def init_language() -> str:
    set_language(config.load_language())
    return current_language()

"""本地库列表控件（v1.4.0）：列表式多库挂载的通用界面部件。

PolyXRD v4.0.0 / XinMatch v2.0.0 都把外挂库从"一类一个槽位"改成"想挂几个挂
几个"，本工具的数据源设置跟随同一交互：**一行 = 一个已挂载的库**，可增删、可
逐行看状态（物相数 / 变体 / 不可用原因），选中哪行就删哪行。

两种模式：
* ``dir``  —— 库是**目录**（polyDB）。添加时可指向库本体，也可指向装着若干
  ``.polyDB`` 的父目录（发布包解压后的常见布局），后者会展开成多行。
* ``file`` —— 库是**文件**（xinDB）。添加时可指向文件，也可指向目录（批量
  展开其中的 ``.xinDB``）。

探测只在「加载 / 手动刷新 / 添加」时发生，且只读 meta（不读数组段、不扫峰），
因此挂 50 万相的库也不会卡。
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from getcif.adapters.locallib import discover
from getcif.i18n import tr
from getcif.ui.theme import ACCENT_TX, DANGER, TEXT_DIM

#: 列表项上挂「是否可用」的自定义 role（UserRole 已用于路径）
_ROLE_OK = Qt.ItemDataRole.UserRole + 1


class LibraryListGroup(QWidget):
    """一张「本地库列表」卡片：启用开关 + 列表 + 添加/移除/刷新。

    Args:
        kind: ``"polydb"`` / ``"xindb"``，决定发现规则与探测函数。
        describer: 探测函数，入参为路径，返回带 ``ok`` / ``reason`` /
            ``label`` / ``summary()`` / ``detail()`` 的对象。
        title: 卡片标题。
        subtitle: 标题下的一行说明。
        mode: ``"dir"`` 或 ``"file"``。
        open_title: 文件/目录选择对话框标题。
        name_filter: 文件模式的过滤器字符串。
    """

    def __init__(self, kind: str, describer: Callable[[Path], object], title: str,
                 subtitle: str, mode: str, open_title: str,
                 name_filter: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.kind = kind
        self.mode = mode
        self._describer = describer
        self._open_title = open_title
        self._name_filter = name_filter or tr("所有文件 (*)")
        if kind == "polydb":
            self._filter = ""
        else:
            self._filter = self._name_filter
        self._build(title, subtitle)

    # ------------------------------------------------------------------
    def _build(self, title: str, subtitle: str) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        head = QHBoxLayout()
        self.enable_check = QCheckBox(title)
        self.enable_check.setStyleSheet("font-weight: 600; color: %s;" % ACCENT_TX)
        head.addWidget(self.enable_check)
        head.addStretch(1)
        self.count_label = QLabel("")
        self.count_label.setObjectName("dimLabel")
        head.addWidget(self.count_label)
        root.addLayout(head)

        note = QLabel(subtitle)
        note.setObjectName("dimLabel")
        note.setWordWrap(True)
        root.addWidget(note)

        self.list_widget = QListWidget()
        self.list_widget.setMinimumHeight(96)
        self.list_widget.setAlternatingRowColors(True)
        self.list_widget.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list_widget.setWordWrap(False)
        root.addWidget(self.list_widget, 1)

        row = QHBoxLayout()
        add_button = QPushButton(tr("添加…") if self.mode == "dir" else tr("添加文件…"))
        add_button.clicked.connect(self._on_add)
        if self.mode == "file":
            add_dir_button = QPushButton(tr("从目录添加…"))
            add_dir_button.clicked.connect(self._on_add_dir)
            row.addWidget(add_button)
            row.addWidget(add_dir_button)
        else:
            row.addWidget(add_button)
        remove_button = QPushButton(tr("移除"))
        remove_button.clicked.connect(self._on_remove)
        rescan_button = QPushButton(tr("重新探测"))
        rescan_button.clicked.connect(self.refresh)
        hint = QLabel(tr("可挂多个库；每行一个，选中后点「移除」卸下"))
        hint.setObjectName("dimLabel")
        row.addWidget(remove_button)
        row.addWidget(rescan_button)
        row.addStretch(1)
        row.addWidget(hint)
        root.addLayout(row)

    # ------------------------------------------------------------------
    # 对外接口
    # ------------------------------------------------------------------
    def setEnabledState(self, enabled: bool) -> None:
        """设置启用开关（不触发探测）。"""
        self.enable_check.setChecked(bool(enabled))

    def isEnabledSource(self) -> bool:
        return self.enable_check.isChecked()

    def paths(self) -> list[str]:
        """当前列表里的库路径（用户视角的"配置项"，可直接落盘）。"""
        out: list[str] = []
        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)
            text = str(item.data(Qt.ItemDataRole.UserRole) or "")
            if text:
                out.append(text)
        return out

    def load(self, paths: list[str]) -> None:
        """按配置里的路径填充列表（每条路径可能展开成多行）。"""
        expanded: list[str] = []
        for text in paths or []:
            found = discover(self.kind, text)
            if found:
                expanded.extend(str(p) for p in found)
            else:
                expanded.append(str(text))     # 路径不存在也保留，好让用户看见并删掉
        self._fill(expanded)

    def refresh(self) -> None:
        """重新探测所有已挂载的库（状态 / 概况可能已变）。"""
        self._fill(self.paths())

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------
    def _fill(self, paths: list[str]) -> None:
        seen: set[str] = set()
        unique: list[str] = []
        for text in paths:
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            unique.append(text)
        self.list_widget.clear()
        usable = 0
        for text in unique:
            info = self._describe(Path(text))
            ok = bool(getattr(info, "ok", False))
            usable += 1 if ok else 0
            self._add_row(text, info, ok)
        self._update_count(len(unique), usable)

    def _describe(self, path: Path) -> object:
        try:
            return self._describer(path)
        except Exception as exc:  # noqa: BLE001 —— 探测失败不该炸界面
            class _Bad:
                ok = False
                reason = str(exc)
                label = path.name

                def summary(self_inner) -> str:      # noqa: N805
                    return "不可用：%s" % str(exc)

                def detail(self_inner) -> str:       # noqa: N805
                    return f"路径：{path}\n状态：不可用：{exc}"
            return _Bad()

    def _add_row(self, text: str, info: object, ok: bool) -> None:
        label = str(getattr(info, "label", "") or Path(text).name)
        summary = ""
        if hasattr(info, "summary"):
            try:
                summary = str(info.summary())
            except Exception:  # noqa: BLE001
                summary = ""
        if ok:
            item_text = f"● {label}    {summary}"
        else:
            reason = str(getattr(info, "reason", "") or "未知原因")
            item_text = f"▲ {label}    {tr('不可用')}：{_reason_text(reason)}"
        item = QListWidgetItem(item_text)
        item.setData(Qt.ItemDataRole.UserRole, text)
        item.setData(_ROLE_OK, ok)
        detail = ""
        if hasattr(info, "detail"):
            try:
                detail = str(info.detail())
            except Exception:  # noqa: BLE001
                detail = ""
        item.setToolTip(detail or text)
        item.setForeground(QColor(TEXT_DIM if ok else DANGER))
        self.list_widget.addItem(item)

    def _update_count(self, total: int, usable: int) -> None:
        if total == 0:
            self.count_label.setText(tr("未挂载"))
            return
        if usable == total:
            self.count_label.setText(tr("已挂载 {} 个").format(total))
        else:
            self.count_label.setText(
                tr("已挂载 {} 个（{} 个不可用）").format(total, total - usable))

    # ---- 交互 ----
    def _on_add(self) -> None:
        paths: list[str] = []
        if self.mode == "dir":
            path = QFileDialog.getExistingDirectory(self, self._open_title, "")
            if path:
                paths = [path]
        else:
            file_path, _ = QFileDialog.getOpenFileName(
                self, self._open_title, "", self._filter)
            if file_path:
                paths = [file_path]
        self._mount(paths)

    def _on_add_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, self._open_title, "")
        if path:
            self._mount([path])

    def _mount(self, paths: list[str]) -> None:
        """把选定路径展开成库并追加到列表（已存在的自动去重）。"""
        if not paths:
            return
        current = self.paths()
        for text in paths:
            found = discover(self.kind, text)
            if found:
                current.extend(str(p) for p in found)
            else:
                current.append(str(text))
        self._fill(current)

    def _on_remove(self) -> None:
        items = self.list_widget.selectedItems()
        if not items:
            return
        for item in items:
            self.list_widget.takeItem(self.list_widget.row(item))
        self._update_count(self.list_widget.count(), self._usable_count())

    def _usable_count(self) -> int:
        count = 0
        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)
            if bool(item.data(_ROLE_OK)):
                count += 1
        return count


#: probe 的机器可读原因 → 用户看得懂的一句话
_REASON_TEXT: dict[str, str] = {
    "file_not_found": "路径不存在",
    "not_a_directory": "不是目录",
    "not_a_file": "不是文件",
    "not_sqlite": "不是 SQLite 数据库",
    "bad_meta": "meta.json 无法解析",
    "missing:meta.json": "缺少 meta.json（不是 polyDB 目录）",
    "missing:index.sqlite": "缺少 index.sqlite",
    "missing_table:entries": "缺少 entries 表",
    "missing_table:meta": "缺少 meta 表",
    "missing_table:peak_chunks": "缺少 peak_chunks 表（不是 xinDB v3）",
    "missing_column:cif_rel": "entries 表缺少 cif_rel 列（旧版 polyDB）",
}


def _reason_text(reason: str) -> str:
    """把 ``probe`` 的短标记翻成人话（未收录的原样显示，便于排查）。"""
    reason = str(reason or "").strip()
    if not reason:
        return "未知原因"
    if reason in _REASON_TEXT:
        return tr(_REASON_TEXT[reason])
    if reason.startswith("unsupported_schema:"):
        return tr("schema 版本不受支持：{}").format(reason.split(":", 1)[1])
    if reason.startswith("bad_format:"):
        return tr("meta.json 的 format 不是 polyDB（{}）").format(reason.split(":", 1)[1])
    if reason.startswith("legacy_schema:"):
        return tr("旧版 XinMatch 库（entries/peaks），请用 XinMatch ≥ 2.0 重建为 .xinDB v3")
    if reason.startswith("size_mismatch:"):
        return tr("段文件大小与 meta.json 不符（拷贝可能中断）：{}").format(
            reason.split(":", 1)[1])
    if reason.startswith("missing:"):
        return tr("缺少文件：{}").format(reason.split(":", 1)[1])
    if reason.startswith("open_failed:"):
        return tr("打开失败：{}").format(reason.split(":", 1)[1])
    return reason


__all__ = ["LibraryListGroup"]

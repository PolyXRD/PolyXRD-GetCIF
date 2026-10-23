"""右侧检索结果表。"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from getcif.core.schema import Candidate
from getcif.i18n import tr

_SOURCE_LABELS = {
    "cod": "COD（联网）",
    "cod_local": "COD 本地库",
    "amcsd": "AMCSD（联网）",
    "mp": "MP（联网）",
    "atomly": "Atomly（联网）",
    "polydb": "polyDB 外挂库",
    "xindb": "xinDB 库",
}


class ResultTable(QWidget):
    """候选结构列表（双击行 → 预览信号）。"""

    preview_requested = Signal(object)  # Candidate

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.candidates: list[Candidate] = []
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        header_row = QHBoxLayout()
        self.title_label = QLabel(tr("检索结果"))
        self.title_label.setStyleSheet("font-weight:600; color:#1783B0;")
        self.count_label = QLabel("")
        self.count_label.setObjectName("dimLabel")
        header_row.addWidget(self.title_label)
        header_row.addStretch(1)
        header_row.addWidget(self.count_label)
        root.addLayout(header_row)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            tr("来源"), tr("编号"), tr("化学式"), tr("空间群"),
            tr("晶胞 a/b/c (Å)"), tr("体积 (Å³)"),
        ])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(26)
        self.table.setShowGrid(False)
        self.table.itemDoubleClicked.connect(self._on_double_click)
        root.addWidget(self.table, 1)

        hint = QLabel(tr("双击行打开 CIF 预览"))
        hint.setObjectName("dimLabel")
        root.addWidget(hint)

    def _on_double_click(self, item) -> None:
        row = item.row()
        if 0 <= row < len(self.candidates):
            self.preview_requested.emit(self.candidates[row])

    # ------------------------------------------------------------------
    def set_results(self, candidates: list[Candidate], partial: bool) -> None:
        self.candidates = list(candidates)
        table = self.table
        table.setRowCount(len(self.candidates))
        for row, cand in enumerate(self.candidates):
            source_text = tr(_SOURCE_LABELS.get(cand.source, cand.source))
            values = [
                source_text,
                cand.source_id,
                cand.formula or "-",
                cand.space_group or "-",
                cand.lattice.summary(),
                f"{cand.lattice.volume:.1f}" if cand.lattice.volume else "-",
            ]
            for column, text in enumerate(values):
                item = QTableWidgetItem(text)
                if column in (1, 5):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row, column, item)
        suffix = tr("（部分数据源不可用，结果不完整）") if partial else ""
        self.count_label.setText(tr("候选 {} 条").format(len(candidates)) + suffix)

    def clear_results(self, message: str = "") -> None:
        self.candidates = []
        self.table.setRowCount(0)
        self.count_label.setText(message)

    def selected_candidate(self) -> Optional[Candidate]:
        row = self.table.currentRow()
        if 0 <= row < len(self.candidates):
            return self.candidates[row]
        return None

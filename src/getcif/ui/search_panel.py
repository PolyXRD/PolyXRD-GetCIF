"""左侧检索条件面板。"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from getcif.core.schema import SearchQuery
from getcif.i18n import tr

CRYSTAL_SYSTEMS = ["", "三斜", "单斜", "正交", "四方", "三方", "六方", "立方"]


class SearchPanel(QWidget):
    """检索条件输入区（化学式 / 元素 / 名称 / 空间群 / 晶系 / 晶胞参数）。"""

    search_requested = Signal()
    clear_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        # ---- 基本条件 ----
        basic_box = QGroupBox(tr("检索条件"))
        form = QFormLayout(basic_box)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(6)

        self.formula_edit = QLineEdit()
        self.formula_edit.setPlaceholderText(tr("如 SiO2 / CaMg(CO3)2"))
        self.formula_edit.returnPressed.connect(self.search_requested.emit)
        form.addRow(tr("化学式"), self.formula_edit)

        self.elements_edit = QLineEdit()
        self.elements_edit.setPlaceholderText(tr("如 Ti,O 或 Ti O"))
        self.elements_edit.returnPressed.connect(self.search_requested.emit)
        form.addRow(tr("元素"), self.elements_edit)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText(tr("如 Quartz / Rutile"))
        self.name_edit.returnPressed.connect(self.search_requested.emit)
        form.addRow(tr("名称 / 关键词"), self.name_edit)

        self.sg_edit = QLineEdit()
        self.sg_edit.setPlaceholderText(tr("如 Pnma / R-3c / 62"))
        self.sg_edit.returnPressed.connect(self.search_requested.emit)
        form.addRow(tr("空间群"), self.sg_edit)

        self.system_combo = QComboBox()
        self.system_combo.addItems(CRYSTAL_SYSTEMS)
        form.addRow(tr("晶系（仅本地库过滤）"), self.system_combo)
        root.addWidget(basic_box)

        # ---- 晶胞参数 ----
        cell_box = QGroupBox(tr("晶胞参数（可选）"))
        grid = QGridLayout(cell_box)
        grid.setSpacing(6)
        self.cell_spins: dict[str, QDoubleSpinBox] = {}
        for row, key in enumerate(("a", "b", "c")):
            label = QLabel(tr(f"{key} (Å)"))
            spin = QDoubleSpinBox()
            spin.setRange(0.0, 9999.0)
            spin.setDecimals(3)
            spin.setSpecialValueText("—")
            self.cell_spins[key] = spin
            grid.addWidget(label, row, 0)
            grid.addWidget(spin, row, 1)
        for row, key in enumerate(("alpha", "beta", "gamma")):
            label = QLabel(tr(f"{'αβγ'[row]} (°)"))
            spin = QDoubleSpinBox()
            spin.setRange(0.0, 180.0)
            spin.setDecimals(2)
            spin.setSpecialValueText("—")
            self.cell_spins[key] = spin
            grid.addWidget(label, row, 2)
            grid.addWidget(spin, row, 3)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        root.addWidget(cell_box)

        # ---- 限制 + 按钮 ----
        limit_row = QHBoxLayout()
        limit_label = QLabel(tr("结果数上限"))
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(5, 200)
        self.limit_spin.setValue(50)
        limit_row.addWidget(limit_label)
        limit_row.addWidget(self.limit_spin)
        limit_row.addStretch(1)
        root.addLayout(limit_row)

        button_row = QHBoxLayout()
        self.search_button = QPushButton(tr("检索 (&S)"))
        self.search_button.setObjectName("primary")
        self.search_button.clicked.connect(self.search_requested.emit)
        self.clear_button = QPushButton(tr("清空 (&C)"))
        self.clear_button.clicked.connect(self._on_clear)
        button_row.addWidget(self.search_button, 1)
        button_row.addWidget(self.clear_button)
        root.addLayout(button_row)
        root.addStretch(1)

    # ------------------------------------------------------------------
    def _on_clear(self) -> None:
        self.formula_edit.clear()
        self.elements_edit.clear()
        self.name_edit.clear()
        self.sg_edit.clear()
        self.system_combo.setCurrentIndex(0)
        for spin in self.cell_spins.values():
            spin.setValue(spin.minimum())
        self.clear_requested.emit()

    def build_query(self) -> tuple[Optional[SearchQuery], str]:
        """收集表单 → SearchQuery；无任何条件时返回 (None, 原因)。"""
        query = SearchQuery(
            formula=self.formula_edit.text().strip(),
            elements=self.elements_edit.text().strip(),
            name=self.name_edit.text().strip(),
            space_group=self.sg_edit.text().strip(),
            crystal_system=self.system_combo.currentText().strip(),
            limit=self.limit_spin.value(),
        )
        for key, spin in self.cell_spins.items():
            value = spin.value()
            if value > spin.minimum():
                setattr(query, key, value)
        if not query.has_condition():
            return None, tr("请输入至少一个检索条件")
        return query, ""

    def set_searching(self, searching: bool) -> None:
        self.search_button.setEnabled(not searching)
        self.search_button.setText(tr("检索中…") if searching else tr("检索 (&S)"))

    def retranslate_ui(self) -> None:
        # 简化处理：文案主要在构造时固定；语言切换后重建窗口更彻底
        pass

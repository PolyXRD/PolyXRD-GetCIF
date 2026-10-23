"""PolyXRD-GetCIF 明亮模式主题（v1.3.0 起，与家族工具一致）。

配色思路：窗口 / 面板走浅色灰蓝（``#F2F5F8`` 底、``#FFFFFF`` 面板），
强调色沿用 PolyXRD 家族青 ``#22A7DD``（ splash 同源）；用于文字的
强调色压深为 ``#1783B0``，保证浅底上的对比度。
"""
from __future__ import annotations

#: 主题色板（浅色；强调色取自 splash：青 #22A7DD / #4FC3F7）
BG        = "#F2F5F8"   # 窗口底
BG_PANEL  = "#FFFFFF"   # 面板底
BG_INPUT  = "#FFFFFF"   # 输入框底
BG_HOVER  = "#E4EEF6"   # 悬停 / 交替行
BORDER    = "#C9D6E2"   # 描边
TEXT      = "#1F2937"   # 主文字
TEXT_DIM  = "#5B6B7C"   # 次要文字
ACCENT    = "#22A7DD"   # 主按钮 / 强调
ACCENT_TX = "#1783B0"   # 浅底上的强调文字（压深保证可读）
DANGER    = "#C0392B"
OK        = "#1E8E5A"


def build_qss() -> str:
    """全局 QSS（明亮模式）。"""
    return f"""
QWidget {{
    background: {BG};
    color: {TEXT};
    font-size: 13px;
}}
QMainWindow {{ background: {BG}; }}

QGroupBox {{
    background: {BG_PANEL};
    border: 1px solid {BORDER};
    border-radius: 8px;
    margin-top: 12px;
    padding: 10px 8px 8px 8px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 4px;
    color: {ACCENT_TX};
    background: {BG};
}}

QLabel {{ background: transparent; }}
QLabel#dimLabel {{ color: {TEXT_DIM}; font-size: 12px; }}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {BG_INPUT};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 4px 6px;
    selection-background-color: {ACCENT};
    selection-color: #FFFFFF;
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border: 1px solid {ACCENT};
}}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox QAbstractItemView {{
    background: {BG_PANEL};
    border: 1px solid {BORDER};
    selection-background-color: {BG_HOVER};
    selection-color: {ACCENT_TX};
}}

QPushButton {{
    background: {BG_PANEL};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 5px 14px;
}}
QPushButton:hover {{ background: {BG_HOVER}; border-color: {ACCENT}; }}
QPushButton:pressed {{ background: {BG}; }}
QPushButton:disabled {{ color: {TEXT_DIM}; background: {BG}; }}
QPushButton#primary {{
    background: {ACCENT};
    border: 1px solid {ACCENT};
    color: #FFFFFF;
    font-weight: 600;
}}
QPushButton#primary:hover {{ background: {ACCENT_TX}; border-color: {ACCENT_TX}; }}
QPushButton#primary:disabled {{ background: {BORDER}; border-color: {BORDER}; color: #FFFFFF; }}

QTableWidget {{
    background: {BG_PANEL};
    border: 1px solid {BORDER};
    border-radius: 6px;
    gridline-color: #E2E8F0;
    selection-background-color: #BEE3F2;
    selection-color: #10394F;
    alternate-background-color: #F7FAFC;
}}
QTableWidget::item {{ padding: 3px 6px; }}
QHeaderView::section {{
    background: #EDF2F7;
    color: #44546A;
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 5px 6px;
    font-weight: 600;
}}

QTabWidget::pane {{
    background: {BG_PANEL};
    border: 1px solid {BORDER};
    border-radius: 6px;
}}
QTabBar::tab {{
    background: {BG};
    color: {TEXT_DIM};
    padding: 6px 14px;
    border: 1px solid {BORDER};
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}}
QTabBar::tab:selected {{ background: {BG_PANEL}; color: {ACCENT_TX}; font-weight: 600; }}

QTextEdit, QPlainTextEdit {{
    background: {BG_PANEL};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    font-family: "Consolas", "Microsoft YaHei", monospace;
    font-size: 12px;
    selection-background-color: {ACCENT};
    selection-color: #FFFFFF;
}}

QProgressBar {{
    background: {BG_INPUT};
    border: 1px solid {BORDER};
    border-radius: 5px;
    text-align: center;
    color: {TEXT};
}}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 4px; }}

QScrollBar:vertical {{
    background: {BG}; width: 10px; border: none; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {BORDER}; border-radius: 5px; min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: {ACCENT}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: {BG}; height: 10px; border: none; margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER}; border-radius: 5px; min-width: 24px;
}}
QScrollBar::handle:horizontal:hover {{ background: {ACCENT}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

QMenu {{
    background: {BG_PANEL};
    border: 1px solid {BORDER};
    padding: 4px;
}}
QMenu::item {{ padding: 5px 24px; border-radius: 4px; }}
QMenu::item:selected {{ background: {BG_HOVER}; color: {ACCENT_TX}; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 4px 8px; }}

QCheckBox {{ spacing: 6px; }}
QCheckBox::indicator {{
    width: 15px; height: 15px;
    border: 1px solid {BORDER};
    border-radius: 4px;
    background: {BG_INPUT};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
    image: none;
}}

QStatusBar {{
    background: {BG_PANEL};
    border-top: 1px solid {BORDER};
    color: {TEXT_DIM};
}}
QDialog {{ background: {BG}; }}
QToolTip {{
    background: #FFFBE6;
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 4px;
}}
"""

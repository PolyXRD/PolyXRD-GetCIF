"""PolyXRD 主题（延续 splash 深海军蓝 + 青色调）。"""

#: 主题色板（取自 splash-screen.png：深海军蓝底 + 青色晶体）
BG        = "#0B1524"   # 窗口底
BG_PANEL  = "#101E31"   # 面板底
BG_INPUT  = "#16273D"   # 输入框底
BG_HOVER  = "#1C314B"
BORDER    = "#24405E"
TEXT      = "#D7E7F5"
TEXT_DIM  = "#8FB6D9"
ACCENT    = "#22A7DD"   # 主按钮 / 强调
ACCENT_HI = "#4FC3F7"
DANGER    = "#E06C5A"
OK        = "#57C08A"


def build_qss() -> str:
    """全局 QSS。"""
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
    color: {ACCENT_HI};
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
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border: 1px solid {ACCENT_HI};
}}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox QAbstractItemView {{
    background: {BG_PANEL};
    border: 1px solid {BORDER};
    selection-background-color: {BG_HOVER};
}}

QPushButton {{
    background: {BG_INPUT};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 5px 14px;
}}
QPushButton:hover {{ background: {BG_HOVER}; border-color: {ACCENT}; }}
QPushButton:pressed {{ background: {BG}; }}
QPushButton:disabled {{ color: {TEXT_DIM}; background: {BG_PANEL}; }}
QPushButton#primary {{
    background: {ACCENT};
    border: 1px solid {ACCENT};
    color: #FFFFFF;
    font-weight: 600;
}}
QPushButton#primary:hover {{ background: {ACCENT_HI}; border-color: {ACCENT_HI}; }}
QPushButton#primary:disabled {{ background: {BG_HOVER}; border-color: {BORDER}; color: {TEXT_DIM}; }}

QTableWidget {{
    background: {BG_PANEL};
    border: 1px solid {BORDER};
    border-radius: 6px;
    gridline-color: {BORDER};
    selection-background-color: {BG_HOVER};
    selection-color: {ACCENT_HI};
    alternate-background-color: {BG_INPUT};
}}
QTableWidget::item {{ padding: 3px 6px; }}
QHeaderView::section {{
    background: {BG_INPUT};
    color: {TEXT_DIM};
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
QTabBar::tab:selected {{ background: {BG_PANEL}; color: {ACCENT_HI}; font-weight: 600; }}

QTextEdit, QPlainTextEdit {{
    background: {BG_PANEL};
    border: 1px solid {BORDER};
    border-radius: 6px;
    font-family: "Consolas", "Microsoft YaHei", monospace;
    font-size: 12px;
    selection-background-color: {ACCENT};
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
QMenu::item:selected {{ background: {BG_HOVER}; color: {ACCENT_HI}; }}
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
    border-color: {ACCENT_HI};
    image: none;
}}

QStatusBar {{
    background: {BG_PANEL};
    border-top: 1px solid {BORDER};
    color: {TEXT_DIM};
}}
QDialog {{ background: {BG}; }}
QToolTip {{
    background: {BG_PANEL};
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 4px;
}}
"""

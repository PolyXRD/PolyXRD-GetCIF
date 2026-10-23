"""关于对话框（延续 PolyXRD 品牌：logo + 版本 + 数据源声明）。"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from getcif import __app_name__, __version__
from getcif.i18n import tr
from getcif.utils.edition import get_edition
from getcif.utils.resources import get_logo_horizontal_path


class AboutDialog(QDialog):
    def __init__(self, parent: Optional[QDialog] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("关于"))
        self.setFixedWidth(460)

        root = QVBoxLayout(self)
        root.setSpacing(10)

        logo_path = get_logo_horizontal_path()
        if logo_path:
            logo = QLabel()
            logo.setPixmap(QPixmap(logo_path).scaledToWidth(
                320, Qt.TransformationMode.SmoothTransformation))
            logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
            root.addWidget(logo)

        title = QLabel(f"{__app_name__} {get_edition()} v{__version__}")
        title.setStyleSheet("font-size:16px; font-weight:700; color:#1783B0;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)

        subtitle = QLabel(tr("CIF 检索与获取小工具"))
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color:#333F4E;")
        root.addWidget(subtitle)

        sources = QLabel(tr("数据源：COD · AMCSD · Materials Project · Atomly · 本地库"))
        sources.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sources.setWordWrap(True)
        sources.setStyleSheet("color:#5B6B7C; font-size:11px;")
        root.addWidget(sources)

        family = QLabel("PolyXRD Family · PolyXRD Team © 2026")
        family.setAlignment(Qt.AlignmentFlag.AlignCenter)
        family.setStyleSheet("color:#8A97A5; font-size:11px;")
        root.addWidget(family)

        close_button = QPushButton(tr("关闭"))
        close_button.setObjectName("primary")
        close_button.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(close_button)
        row.addStretch(1)
        root.addLayout(row)

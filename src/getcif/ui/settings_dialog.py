"""数据源设置对话框：COD（默认开）/ 本地库 / AMCSD / MP / Atomly + 超时。"""
from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from getcif.core import config
from getcif.i18n import tr


class SettingsDialog(QDialog):
    """设置（菜单 → 设置 → 数据源设置）。"""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("数据源设置"))
        self.setMinimumWidth(560)
        self._build_ui()
        self._load()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(8)

        note = QLabel(tr("说明：COD 联网检索默认开启；AMCSD 无需凭证；MP 需要 API Key；Atomly 需要 Token。本地库需指向 SQLite 检索索引。"))
        note.setWordWrap(True)
        note.setObjectName("dimLabel")
        root.addWidget(note)

        # ---- COD 联网 ----
        self.cod_check = QCheckBox(tr("启用（联网检索 CIF，默认开启）"))
        root.addWidget(self.cod_check)

        # ---- AMCSD ----
        self.amcsd_check = QCheckBox(tr("启用（无需配置，配置完成后勾选开启）"))
        root.addWidget(self.amcsd_check)

        # ---- MP ----
        self.mp_check = QCheckBox(tr("API Key（materialsproject.org 免费注册获取；配置后可开启）"))
        self.mp_edit = QLineEdit()
        self.mp_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.mp_edit.setPlaceholderText("X-API-KEY")
        self.mp_check.clicked.connect(lambda checked: self._validate_mp(checked))
        root.addWidget(self.mp_check)
        root.addWidget(self.mp_edit)

        # ---- Atomly ----
        self.atomly_check = QCheckBox(tr("Token（atomly.net 登录后获取；配置后可开启）"))
        self.atomly_edit = QLineEdit()
        self.atomly_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.atomly_edit.setPlaceholderText("userToken (localStorage)")
        self.atomly_check.clicked.connect(lambda checked: self._validate_atomly(checked))
        root.addWidget(self.atomly_check)
        root.addWidget(self.atomly_edit)

        # ---- 本地库 ----
        self.local_check = QCheckBox(tr("启用（配置检索索引后生效）"))
        root.addWidget(self.local_check)

        db_row = QHBoxLayout()
        self.db_edit = QLineEdit()
        self.db_edit.setPlaceholderText(tr("检索索引（cod_index.sqlite，兼容 PolyXRD 全库索引）"))
        db_browse = QPushButton(tr("浏览…"))
        db_browse.clicked.connect(self._browse_db)
        db_row.addWidget(self.db_edit, 1)
        db_row.addWidget(db_browse)
        root.addLayout(db_row)

        root_row = QHBoxLayout()
        self.root_edit = QLineEdit()
        self.root_edit.setPlaceholderText(tr("COD 数据根目录（可选，用于解析相对路径的 CIF 文件）"))
        root_browse = QPushButton(tr("浏览…"))
        root_browse.clicked.connect(self._browse_root)
        root_row.addWidget(self.root_edit, 1)
        root_row.addWidget(root_browse)
        root.addLayout(root_row)

        # ---- 超时 ----
        form = QFormLayout()
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(5, 120)
        self.timeout_spin.setSuffix(" s")
        form.addRow(tr("网络超时（秒）"), self.timeout_spin)
        root.addLayout(form)

        root.addStretch(1)

        # ---- 按钮 ----
        button_row = QHBoxLayout()
        ok_button = QPushButton(tr("确定 (&O)"))
        ok_button.setObjectName("primary")
        ok_button.clicked.connect(self._save)
        cancel_button = QPushButton(tr("取消 (&C)"))
        cancel_button.clicked.connect(self.reject)
        button_row.addStretch(1)
        button_row.addWidget(ok_button)
        button_row.addWidget(cancel_button)
        root.addLayout(button_row)

    # ------------------------------------------------------------------
    def _load(self) -> None:
        self.cod_check.setChecked(config.source_enabled("cod"))
        self.amcsd_check.setChecked(config.source_enabled("amcsd"))
        self.local_check.setChecked(config.source_enabled("local"))
        self.mp_check.setChecked(config.source_enabled("mp"))
        self.atomly_check.setChecked(config.source_enabled("atomly"))
        self.mp_edit.setText(config.mp_api_key())
        self.atomly_edit.setText(config.atomly_token())
        self.db_edit.setText(config.cod_local_db())
        self.root_edit.setText(config.cod_local_root())
        self.timeout_spin.setValue(config.net_timeout())

    def _validate_mp(self, checked: bool) -> None:
        if checked and not self.mp_edit.text().strip():
            QMessageBox.information(
                self, tr("数据源设置"),
                tr("API Key（materialsproject.org 免费注册获取；配置后可开启）"),
            )
            self.mp_check.setChecked(False)

    def _validate_atomly(self, checked: bool) -> None:
        if checked and not self.atomly_edit.text().strip():
            QMessageBox.information(
                self, tr("数据源设置"),
                tr("Token（atomly.net 登录后获取；配置后可开启）"),
            )
            self.atomly_check.setChecked(False)

    def _browse_db(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, tr("选择检索索引文件"), self.db_edit.text() or "",
            tr("SQLite 数据库 (*.sqlite *.db);;所有文件 (*)"),
        )
        if path:
            self.db_edit.setText(path)

    def _browse_root(self) -> None:
        path = QFileDialog.getExistingDirectory(self, tr("选择目录"), self.root_edit.text() or "")
        if path:
            self.root_edit.setText(path)

    # ------------------------------------------------------------------
    def _save(self) -> None:
        mp_key = self.mp_edit.text().strip()
        atomly_token = self.atomly_edit.text().strip()
        mp_ok = self.mp_check.isChecked() and bool(mp_key)
        atomly_ok = self.atomly_check.isChecked() and bool(atomly_token)
        local_ok = self.local_check.isChecked() and bool(self.db_edit.text().strip())

        config.set_source_enabled("cod", self.cod_check.isChecked())
        config.set_source_enabled("amcsd", self.amcsd_check.isChecked())
        config.set_source_enabled("mp", mp_ok)
        config.set_source_enabled("atomly", atomly_ok)
        config.set_source_enabled("local", local_ok)
        config.save("credentials", {"mp_api_key": mp_key, "atomly_token": atomly_token})
        config.save("local", {
            "db_path": self.db_edit.text().strip(),
            "cod_root": self.root_edit.text().strip(),
        })
        config.set_net_timeout(self.timeout_spin.value())
        self.accept()

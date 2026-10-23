"""数据源设置对话框：COD（默认开）/ AMCSD / MP / Atomly / 本地库（COD 索引 · polyDB · xinDB）+ 超时。

v1.4.0：本地库改为**列表式多库挂载**（与 PolyXRD v4.0.0 / XinMatch v2.0.0 一致），
polyDB 与 xinDB 各一张列表，一行一个库，可增删、可看状态。
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from getcif.adapters.polydb import describe_library as describe_polydb
from getcif.adapters.xindb import describe_library as describe_xindb
from getcif.core import config
from getcif.i18n import tr
from getcif.ui.library_list import LibraryListGroup


class SettingsDialog(QDialog):
    """设置（菜单 → 设置 → 数据源设置）。"""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("数据源设置"))
        self.setMinimumWidth(680)
        self.resize(760, 800)
        self._build_ui()
        self._load()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        outer.addWidget(scroll, 1)

        page = QWidget()
        scroll.setWidget(page)
        root = QVBoxLayout(page)
        root.setContentsMargins(14, 12, 14, 8)
        root.setSpacing(8)

        note = QLabel(tr("说明：COD 联网检索默认开启；AMCSD 无需凭证；MP 需要 API Key；Atomly 需要 Token。本地库支持三种格式：COD 检索索引（cod_index.sqlite）、polyDB 外挂库目录（PolyXRD v4，可挂多个）、xinDB 库文件（XinMatch v3，仅元数据检索，可挂多个）。"))
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

        # ---- 本地库：COD 检索索引 ----
        self.local_check = QCheckBox(tr("COD 本地索引（cod_index.sqlite，兼容 PolyXRD 全库索引）"))
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
        self.root_edit.setPlaceholderText(tr("数据根目录（可选，解析本地索引与 polyDB 的相对 CIF 路径）"))
        root_browse = QPushButton(tr("浏览…"))
        root_browse.clicked.connect(self._browse_root)
        root_row.addWidget(self.root_edit, 1)
        root_row.addWidget(root_browse)
        root.addLayout(root_row)

        # ---- 本地库：polyDB 外挂库（PolyXRD v4）多库列表 ----
        self.polydb_group = LibraryListGroup(
            kind="polydb",
            describer=describe_polydb,
            title=tr("polyDB 外挂库（PolyXRD v4 目录容器：meta.json + index.sqlite）"),
            subtitle=tr("添加 .polyDB 目录；也可直接选上层目录，自动展开其中所有 .polyDB。CIF 原文按各库 meta.json 的相对路径解析。"),
            mode="dir",
            open_title=tr("选择 polyDB 目录（可多选其上层目录自动展开）"),
        )
        root.addWidget(self.polydb_group)

        # ---- 本地库：xinDB（XinMatch v3）多库列表 ----
        self.xindb_group = LibraryListGroup(
            kind="xindb",
            describer=describe_xindb,
            title=tr("xinDB 库（XinMatch v3 单文件；仅元数据检索，不含 CIF 原文）"),
            subtitle=tr("添加 .xinDB 文件；也可选上层目录，自动展开其中所有 .xinDB。"),
            mode="file",
            open_title=tr("选择 xinDB 库文件"),
            name_filter=tr("xinDB 数据库 (*.xinDB *.db);;所有文件 (*)"),
        )
        root.addWidget(self.xindb_group)

        # ---- 超时 ----
        form = QHBoxLayout()
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(5, 120)
        self.timeout_spin.setSuffix(" s")
        form.addWidget(QLabel(tr("网络超时（秒）")))
        form.addWidget(self.timeout_spin)
        form.addStretch(1)
        root.addLayout(form)

        root.addStretch(1)

        # ---- 按钮（固定在对话框底部，不随内容滚动）----
        footer = QWidget()
        button_row = QHBoxLayout(footer)
        button_row.setContentsMargins(14, 8, 14, 12)
        ok_button = QPushButton(tr("确定 (&O)"))
        ok_button.setObjectName("primary")
        ok_button.clicked.connect(self._save)
        cancel_button = QPushButton(tr("取消 (&C)"))
        cancel_button.clicked.connect(self.reject)
        button_row.addStretch(1)
        button_row.addWidget(ok_button)
        button_row.addWidget(cancel_button)
        outer.addWidget(footer)

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

        polydb_paths = config.polydb_paths()
        self.polydb_group.load(polydb_paths)
        self.polydb_group.setEnabledState(
            config.source_enabled("polydb") or bool(polydb_paths))
        xindb_paths = config.xindb_paths()
        self.xindb_group.load(xindb_paths)
        self.xindb_group.setEnabledState(
            config.source_enabled("xindb") or bool(xindb_paths))

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
        polydb_paths = self.polydb_group.paths()
        xindb_paths = self.xindb_group.paths()
        polydb_ok = self.polydb_group.isEnabledSource() and bool(polydb_paths)
        xindb_ok = self.xindb_group.isEnabledSource() and bool(xindb_paths)

        config.set_source_enabled("cod", self.cod_check.isChecked())
        config.set_source_enabled("amcsd", self.amcsd_check.isChecked())
        config.set_source_enabled("mp", mp_ok)
        config.set_source_enabled("atomly", atomly_ok)
        config.set_source_enabled("local", local_ok)
        config.set_source_enabled("polydb", polydb_ok)
        config.set_source_enabled("xindb", xindb_ok)
        config.save("credentials", {"mp_api_key": mp_key, "atomly_token": atomly_token})
        config.save("local", {
            "db_path": self.db_edit.text().strip(),
            "cod_root": self.root_edit.text().strip(),
        })
        config.save_polydb_paths(polydb_paths)
        config.save_xindb_paths(xindb_paths)
        config.set_net_timeout(self.timeout_spin.value())
        self.accept()

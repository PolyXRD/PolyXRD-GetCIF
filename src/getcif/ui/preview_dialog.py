"""候选 CIF 预览对话框：结构信息 + CIF 内容 + 3D 展示 + 下载/另存。"""
from __future__ import annotations

import pathlib
import threading
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from getcif.core import config
from getcif.adapters.base import AdapterError
from getcif.cifparse import parse_cif
from getcif.core.schema import Candidate
from getcif.i18n import tr
from getcif.viz3d import Viewer3D


class PreviewDialog(QDialog):
    """候选结构预览（双击结果行弹出）。"""

    #: 后台下载线程 → 主线程回传 (ok, text_or_error)
    _cif_fetched = Signal(bool, str)

    def __init__(self, candidate: Candidate, timeout: int = 30,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.candidate = candidate
        self.timeout = timeout
        self._worker: Optional[threading.Thread] = None
        self._progress: Optional[QProgressDialog] = None
        self._cif_fetched.connect(self._on_cif_fetched)
        self._build_ui()
        self._maybe_auto_fetch()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        cand = self.candidate
        self.setWindowTitle(f"{tr('CIF 预览')} — {cand.candidate_id}")
        self.resize(880, 660)

        root = QVBoxLayout(self)
        root.setSpacing(8)

        # ---- 信息头 ----
        info_box = QWidget()
        form = QFormLayout(info_box)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(4)

        def _value_label(text: str) -> QLabel:
            label = QLabel(text)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            label.setStyleSheet("color:#333F4E;")
            return label

        lattice = cand.lattice
        cell_text = lattice.summary() or "—"
        rows = [
            (tr("来源"), f"{cand.provenance or cand.source}"),
            (tr("化学式"), cand.formula or "—"),
            (tr("空间群（H-M）"), cand.space_group or "—"),
            (tr("晶胞参数"), cell_text),
            (tr("晶胞体积"), f"{lattice.volume:.2f} Å³" if lattice.volume else "—"),
            (tr("元素"), ", ".join(sorted(cand.elements)) or "—"),
        ]
        for name, value in rows:
            name_label = QLabel(name)
            name_label.setStyleSheet("color:#5B6B7C; font-weight:600;")
            form.addRow(name_label, _value_label(value))
        root.addWidget(info_box)

        # ---- 选项卡：CIF 内容 / 3D ----
        self.tabs = QTabWidget()
        self.cif_view = QTextEdit()
        self.cif_view.setReadOnly(True)
        self.cif_view.setFont(QFont("Consolas", 9))
        self.cif_view.setPlaceholderText(tr("尚无 CIF 内容，请先下载"))
        self.tabs.addTab(self.cif_view, tr("CIF 内容"))

        self.viewer = Viewer3D(self)
        if self.viewer.widget is not None:
            self.tabs.addTab(self.viewer.widget, tr("3D 结构"))
        else:
            fallback = QLabel(self.viewer.last_message or tr("3D 预览不可用"))
            fallback.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tabs.addTab(fallback, tr("3D 结构"))
        root.addWidget(self.tabs, 1)

        # ---- 按钮行 ----
        button_row = QHBoxLayout()
        self.download_button = QPushButton(tr("下载 CIF (&D)"))
        self.download_button.setObjectName("primary")
        self.download_button.clicked.connect(self._download_and_save)
        self.save_button = QPushButton(tr("另存为…"))
        self.save_button.clicked.connect(self._save_as)
        close_button = QPushButton(tr("关闭"))
        close_button.clicked.connect(self.reject)
        button_row.addWidget(self.download_button)
        button_row.addWidget(self.save_button)
        button_row.addStretch(1)
        button_row.addWidget(close_button)
        root.addLayout(button_row)

        if cand.cif_content:
            self._show_cif(cand.cif_content)

    # ------------------------------------------------------------------
    def _maybe_auto_fetch(self) -> None:
        """无 CIF 内容时后台自动取回（MP/本地即取即显；在线库弹进度）。"""
        if self.candidate.cif_content:
            return
        self._fetch_cif(show_progress=True)

    def _fetch_cif(self, show_progress: bool = True) -> None:
        from getcif.adapters import create_adapters

        adapter = next((a for a in create_adapters(self.timeout)
                        if a.name == self.candidate.source), None)
        if adapter is None:
            self._on_cif_fetched(False, tr("该数据源不提供 CIF 下载"))
            return
        self.download_button.setEnabled(False)
        self.download_button.setText(tr("下载中…"))
        if show_progress:
            self._progress = QProgressDialog(tr("正在获取 CIF…"), "", 0, 0, self)
            self._progress.setWindowModality(Qt.WindowModality.WindowModal)
            self._progress.setCancelButton(None)
            self._progress.setMinimumDuration(0)
            self._progress.show()

        def _run() -> None:
            try:
                text = adapter.download_cif(self.candidate)
                ok = bool(text and "data_" in text)
                self._cif_fetched.emit(ok, text if ok else (text or "CIF 内容为空"))
            except AdapterError as exc:
                self._cif_fetched.emit(False, exc.reason)
            except Exception as exc:  # noqa: BLE001
                self._cif_fetched.emit(False, str(exc))

        self._worker = threading.Thread(target=_run, daemon=True)
        self._worker.start()

    def _on_cif_fetched(self, ok: bool, text: str) -> None:
        if self._progress is not None:
            self._progress.close()
            self._progress = None
        self.download_button.setEnabled(True)
        self.download_button.setText(tr("下载 CIF (&D)"))
        if ok:
            self._show_cif(text)
        else:
            QMessageBox.warning(self, tr("CIF 预览"), tr("CIF 下载失败：{}").format(text))

    # ------------------------------------------------------------------
    def _show_cif(self, text: str) -> None:
        self.candidate.cif_content = text
        self.cif_view.setPlainText(text)
        index = self.tabs.indexOf(self.cif_view)
        if index >= 0:
            self.tabs.setCurrentIndex(index)
        # 解析并渲染 3D
        try:
            cif = parse_cif(text)
            formula = cif.formula or self.candidate.formula
            code = cif.database_code or self.candidate.source_id
            self.viewer.set_cif(cif, label=f"{formula} {code}".strip())
        except Exception as exc:  # noqa: BLE001
            self.viewer.clear(f"3D 渲染失败：{exc}")

    # ------------------------------------------------------------------
    def _download_and_save(self) -> None:
        """下载（若未取得）并保存到默认下载目录。"""
        if not self.candidate.cif_content:
            self._fetch_cif(show_progress=True)
            return

        default_dir = config.load_last_save_dir() or str(config.downloads_dir())
        filename = f"{self.candidate.candidate_id.replace(':', '_')}.cif"
        path = pathlib.Path(default_dir) / filename
        try:
            path.write_text(self.candidate.cif_content, encoding="utf-8")
            config.save_last_save_dir(str(path.parent))
            QMessageBox.information(self, tr("保存 CIF 文件"), tr("已保存：{}").format(path))
        except OSError as exc:
            QMessageBox.critical(self, tr("保存 CIF 文件"), tr("保存失败：{}").format(exc))

    def _save_as(self) -> None:
        if not self.candidate.cif_content:
            self._fetch_cif(show_progress=True)
            return
        start_dir = config.load_last_save_dir() or str(config.downloads_dir())
        filename = f"{self.candidate.candidate_id.replace(':', '_')}.cif"
        path, _ = QFileDialog.getSaveFileName(
            self, tr("保存 CIF 文件"), str(pathlib.Path(start_dir) / filename),
            tr("CIF 文件 (*.cif);;所有文件 (*)"),
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(self.candidate.cif_content)
            config.save_last_save_dir(str(pathlib.Path(path).parent))
            QMessageBox.information(self, tr("保存 CIF 文件"), tr("已保存：{}").format(path))
        except OSError as exc:
            QMessageBox.critical(self, tr("保存 CIF 文件"), tr("保存失败：{}").format(exc))

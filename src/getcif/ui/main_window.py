"""主窗口：左侧检索条件 / 右侧检索结果 + 菜单（设置 / 语言 / 关于）。"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QIcon
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QSizePolicy,
    QSplitter,
    QWidget,
)

from getcif import __app_name__, __version__
from getcif.core import config
from getcif.core.schema import SearchQuery
from getcif.i18n import SUPPORTED_LANGUAGES, init_language, set_language, tr
from getcif.search import SearchWorker
from getcif.ui.about_dialog import AboutDialog
from getcif.ui.license_dialog import show_license
from getcif.ui.preview_dialog import PreviewDialog
from getcif.ui.result_table import ResultTable
from getcif.ui.search_panel import SearchPanel
from getcif.ui.settings_dialog import SettingsDialog
from getcif.ui.theme import DANGER, build_qss
from getcif.utils import registration
from getcif.utils.build_variant import is_internal_edition
from getcif.utils.resources import get_app_icon_path

_SOURCE_LABELS = {
    "cod": "COD（联网）",
    "cod_local": "COD 本地库",
    "amcsd": "AMCSD（联网）",
    "mp": "MP（联网）",
    "atomly": "Atomly（联网）",
    "polydb": "polyDB 外挂库",
    "xindb": "xinDB 库",
}


class MainWindow(QMainWindow):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        init_language()
        # 内部评估版（Internal spec 注入标记）：停用注册机制，状态栏显示「内部评估版本」
        self._internal = is_internal_edition()
        self._reg: Optional[registration.RegistrationManager] = None
        if not self._internal:
            registration.set_language(config.load_language())
            self._reg = registration.RegistrationManager(
                __app_name__, config.app_config_dir() / "registration.json"
            )
        self.worker: Optional[SearchWorker] = None
        self._status_timer = QTimer(self)
        self._status_timer.setSingleShot(True)

        self.setWindowTitle(f"{__app_name__} v{__version__}")
        icon_path = get_app_icon_path()
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))
        self.resize(1180, 720)
        self.setStyleSheet(build_qss())

        self._build_menu()
        self._build_body()
        self._build_statusbar()
        self._update_source_hint()
        if self._reg is not None:
            # 未注册启动提示：窗口显示后弹出（QTimer 保证冒烟测试不阻塞）
            QTimer.singleShot(0, lambda: self._reg.startup_check(self))

    # ------------------------------------------------------------------
    def _build_menu(self) -> None:
        menu_bar = self.menuBar()

        # 设置菜单
        settings_menu = menu_bar.addMenu(tr("设置 (&S)"))
        datasource_action = QAction(tr("数据源设置…"), self)
        datasource_action.triggered.connect(self._open_settings)
        settings_menu.addAction(datasource_action)
        settings_menu.addSeparator()
        quit_action = QAction(tr("退出 (&Q)"), self)
        quit_action.triggered.connect(self.close)
        settings_menu.addAction(quit_action)

        # 语言菜单
        language_menu = menu_bar.addMenu(tr("语言 (&L)"))
        self._language_group = QActionGroup(self)
        self._language_group.setExclusive(True)
        self._language_actions: dict[str, QAction] = {}
        current = config.load_language()
        for code, native_name in SUPPORTED_LANGUAGES.items():
            action = QAction(native_name, self)
            action.setCheckable(True)
            action.setChecked(code == current)
            action.triggered.connect(lambda _checked, c=code: self._switch_language(c))
            self._language_group.addAction(action)
            language_menu.addAction(action)
            self._language_actions[code] = action

        # 帮助菜单
        help_menu = menu_bar.addMenu(tr("帮助 (&H)"))
        if self._reg is not None:
            self._reg.add_help_action(help_menu, self)
        license_action = QAction(tr("版权与许可 (&L)"), self)
        license_action.triggered.connect(self._on_license)
        help_menu.addAction(license_action)
        about_action = QAction(tr("关于 {} (&A)").format(__app_name__), self)
        about_action.triggered.connect(self._open_about)
        help_menu.addAction(about_action)

    def _build_body(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.search_panel = SearchPanel()
        self.search_panel.search_requested.connect(self._start_search)
        self.search_panel.clear_requested.connect(self._on_clear)

        self.result_table = ResultTable()
        self.result_table.preview_requested.connect(self._open_preview)

        splitter.addWidget(self.search_panel)
        splitter.addWidget(self.result_table)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([360, 800])
        self.setCentralWidget(splitter)

    def _build_statusbar(self) -> None:
        status_bar = self.statusBar()
        self.progress = QProgressBar()
        self.progress.setFixedWidth(160)
        self.progress.setRange(0, 0)  # busy
        self.progress.setVisible(False)
        status_bar.addPermanentWidget(self.progress)
        # 最下面一排最右侧（右对齐）：注册的单位部门名称 / 未注册；
        # 内部评估版：状态栏**居中**显示「内部评估版本」（加粗红字，字号不变）
        self._internal_label: Optional[QLabel] = None
        if self._reg is not None:
            self._reg.attach_status_label(status_bar, self)
        else:
            self._internal_label = QLabel(tr("内部评估版本"))
            self._internal_label.setAlignment(
                Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
            )
            # 仅加粗 + 红字，字号沿用全局 QSS（不调字号）
            self._internal_label.setStyleSheet(f"color: {DANGER}; font-weight: bold;")
            self._internal_label.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
            )
            status_bar.addWidget(self._internal_label, 1)
        self.set_status(tr("就绪 —— 输入检索条件后点击「检索」"))

    # ------------------------------------------------------------------
    def set_status(self, text: str) -> None:
        self.statusBar().showMessage(text, 0)

    def _flash_status(self, text: str, msec: int = 4000) -> None:
        self.set_status(text)
        self._status_timer.start(msec)

    # ---- 检索 ----
    def _start_search(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            return
        query, error = self.search_panel.build_query()
        if query is None:
            self._flash_status(error)
            QMessageBox.information(self, __app_name__, error)
            return
        if not self._any_source_enabled():
            QMessageBox.warning(self, __app_name__, tr("没有已启用的数据源，请在「设置 → 数据源设置」中配置"))
            return

        self.result_table.clear_results(tr("正在检索…"))
        self.search_panel.set_searching(True)
        self.progress.setVisible(True)
        self.set_status(tr("正在检索…"))

        self.worker = SearchWorker(query, timeout=config.net_timeout(), parent=self)
        self.worker.source_status.connect(self._on_source_status)
        self.worker.finished_all.connect(self._on_search_finished)
        self.worker.failed.connect(self._on_search_failed)
        self.worker.start()

    def _any_source_enabled(self) -> bool:
        return any(
            config.source_enabled(name)
            for name in ("cod", "amcsd", "mp", "atomly", "local", "polydb", "xindb")
        )

    def _on_source_status(self, source: str, status: str, detail: str) -> None:
        label = tr(_SOURCE_LABELS.get(source, source))
        if status == "querying":
            text = tr("检索中：{}").format(label)
        elif status == "hits":
            text = f"{label}: {detail}"
        elif status == "empty":
            text = f"{label}: {tr('未找到匹配的结构')}"
        elif status == "failed":
            text = f"{label}: {tr('检索失败：{}').format(detail)}"
        else:  # disabled
            text = f"{label}: {detail or tr('（尚未检索）')}"
        self.set_status(text)

    def _on_search_finished(self, candidates: list, partial: bool) -> None:
        self.search_panel.set_searching(False)
        self.progress.setVisible(False)
        self.result_table.set_results(candidates, partial)
        if candidates:
            self.set_status(tr("检索完成：{} 条候选").format(len(candidates)))
        else:
            self.set_status(tr("检索完成：无候选"))

    def _on_search_failed(self, reason: str) -> None:
        self.search_panel.set_searching(False)
        self.progress.setVisible(False)
        self.result_table.clear_results()
        self.set_status(tr("检索失败：{}").format(reason))

    def _on_clear(self) -> None:
        self.result_table.clear_results()
        self.set_status(tr("已清空检索条件"))

    def _open_preview(self, candidate) -> None:
        dialog = PreviewDialog(candidate, timeout=config.net_timeout(), parent=self)
        dialog.exec()

    # ---- 菜单动作 ----
    def _open_settings(self) -> None:
        dialog = SettingsDialog(self)
        if dialog.exec():
            self._update_source_hint()
            self._flash_status(tr("设置已保存"))

    def _update_source_hint(self) -> None:
        enabled = [tr(_SOURCE_LABELS[name]) for name in _SOURCE_LABELS
                   if config.source_enabled(name)]
        if enabled:
            self.set_status(tr("已启用：{}").format(" · ".join(enabled)))

    def _switch_language(self, code: str) -> None:
        set_language(code)
        config.save_language(code)
        registration.set_language(code)
        # 状态栏右侧文案随语言刷新
        if self._reg is not None:
            self._reg.refresh()
        elif self._internal_label is not None:
            self._internal_label.setText(tr("内部评估版本"))
        # 重建菜单与中央部件，让全部文案立即切换
        self.menuBar().clear()
        self._build_menu()
        central = self.centralWidget()
        if central is not None:
            central.setParent(None)  # type: ignore[arg-type]
        self._build_body()
        self._update_source_hint()
        self._flash_status(tr("界面语言已切换：{}").format(SUPPORTED_LANGUAGES.get(code, code)))

    def _open_about(self) -> None:
        AboutDialog(self).exec()

    def _on_license(self) -> None:
        """显示版权 / 许可对话框（与「关于」并列）。"""
        show_license(self)

    # ------------------------------------------------------------------
    def closeEvent(self, event) -> None:  # noqa: N802
        if self.worker is not None and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(2000)
        event.accept()

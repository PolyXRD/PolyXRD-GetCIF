"""PolyXRD-GetCIF 桌面 GUI 入口。

用法::

    python -m getcif.gui                 # 正常启动（带启动画面）
    python -m getcif.gui --no-splash     # 跳过启动画面
    QT_QPA_PLATFORM=offscreen python -m getcif.gui --smoke
                                         # 离屏冒烟：构造主窗口后立即退出

要点（与 PolyXRD / CifCalc 同源经验）：
    * 窗口图标只取 PNG（Qt6 内建解码，避免启动阶段加载 qico 插件）；
    * 打包为窗口应用后 stderr 无处可去 —— 顶层异常落盘 crash.log 并弹窗提示。
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Optional

from getcif import __app_name__, __version__

logger = logging.getLogger("getcif.gui")

EXIT_OK = 0
EXIT_ERROR = 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="getcif-gui",
        description=f"{__app_name__} v{__version__} —— CIF 检索与获取小工具",
    )
    parser.add_argument("--no-splash", action="store_true", help="不显示启动画面")
    parser.add_argument("--smoke", action="store_true",
                        help="离屏冒烟：构造主窗口后立即退出（不进入事件循环）")
    parser.add_argument("--verbose", "-v", action="store_true", help="输出 DEBUG 日志")
    parser.add_argument("--log-file", dest="log_file", metavar="PATH",
                        help="把日志同时写入指定文件")
    parser.add_argument("--version", action="version", version=f"{__app_name__} v{__version__}")
    return parser


def _install_crash_handler() -> None:
    """顶层异常落盘（``console=False`` 打包版异常不可见）。"""
    import traceback

    def _hook(exc_type, exc_value, exc_tb) -> None:
        text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        try:
            from getcif.core.config import app_config_dir

            log_dir = app_config_dir() / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            target = log_dir / "crash.log"
            target.write_text(text, encoding="utf-8", newline="\n")
            path_hint = str(target)
        except Exception:  # noqa: BLE001
            path_hint = "(无法写入日志文件)"
        logger.error("未捕获异常：\n%s", text)
        # offscreen / 冒烟环境弹窗无意义且会阻塞（无人点击），跳过
        if os.environ.get("QT_QPA_PLATFORM", "").lower() == "offscreen":
            return
        try:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.critical(None, "程序异常", f"发生未处理的异常，详情见：\n{path_hint}")
        except Exception:  # noqa: BLE001
            pass

    sys.excepthook = _hook


def _setup_logging(level: int, log_file: Optional[str]) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        handlers=handlers)


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    _install_crash_handler()
    _setup_logging(logging.DEBUG if args.verbose else logging.INFO, args.log_file)
    logger.info("启动 %s v%s", __app_name__, __version__)

    if args.smoke:
        # 冒烟模式：禁用未注册启动弹窗（无人点击，且会阻塞离屏测试）
        os.environ["POLYXRD_REG_NO_PROMPT"] = "1"

    try:
        from PySide6.QtGui import QIcon, QPixmap
        from PySide6.QtWidgets import QApplication, QSplashScreen
    except Exception as exc:  # noqa: BLE001
        logger.error("PySide6 不可用，无法启动图形界面：%s", exc)
        return EXIT_ERROR

    try:
        from getcif.ui.main_window import MainWindow
        from getcif.utils.resources import get_app_icon_path, get_splash_screen_path
    except Exception as exc:  # noqa: BLE001
        logger.error("界面模块加载失败：%s", exc)
        return EXIT_ERROR

    app = QApplication(sys.argv[:1] if argv is None else argv)
    app.setApplicationName(__app_name__)
    app.setApplicationVersion(__version__)
    app.setOrganizationName("PolyXRD Team")

    icon_path = get_app_icon_path()
    if icon_path:
        app.setWindowIcon(QIcon(icon_path))

    splash = None
    if not args.no_splash and not args.smoke:
        splash_path = get_splash_screen_path()
        if splash_path:
            pixmap = QPixmap(splash_path)
            if not pixmap.isNull():
                splash = QSplashScreen(pixmap)
                splash.show()
                app.processEvents()

    try:
        window = MainWindow()
    except Exception as exc:  # noqa: BLE001
        logger.error("主窗口构造失败：%s", exc)
        if splash is not None:
            splash.close()
        return EXIT_ERROR

    if args.smoke:
        logger.info("GUI 冒烟测试通过：MainWindow 已构造（%s）", window.windowTitle())
        window.close()
        return EXIT_OK

    window.show()
    if splash is not None:
        splash.finish(window)
    return app.exec()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

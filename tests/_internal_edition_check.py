# -*- coding: utf-8 -*-
"""内部评估版（POLYXRD_GETCIF_INTERNAL=1）主窗口行为验证：

* 注册机制整体停用（无 RegistrationManager、无「输入注册码」菜单项）；
* 状态栏**居中**显示「内部评估版本」（加粗红字，字号不变）；
* 语言切换后该文案同步三语。

用法：python tests/_internal_edition_check.py  （自身设 offscreen 环境变量）
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["POLYXRD_GETCIF_INTERNAL"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from getcif.utils.build_variant import is_internal_edition

app = QApplication([])

assert is_internal_edition(), "env var force failed"
print("[PASS] 环境变量强制内部模式")

from getcif.ui.main_window import MainWindow  # noqa: E402

window = MainWindow()
window.show()
assert window._internal is True
assert window._reg is None
print("[PASS] 内部模式：注册管理器未创建（无启动提示 / 无输入注册码菜单）")

# 帮助菜单不应包含「输入注册码」
menu_texts = []
for action in window.menuBar().actions():
    if action.menu() is not None:
        menu_texts += [a.text() for a in action.menu().actions()]
assert not any("注册" in t for t in menu_texts), menu_texts
print("[PASS] 帮助菜单无「输入注册码」入口")

# 状态栏：**居中**显示「内部评估版本」（加粗红字，字号不变）
bar = window.statusBar()
for _ in range(10):
    app.processEvents()
label = window._internal_label
assert label is not None
assert label.text() == "内部评估版本", label.text()
assert label.alignment() & Qt.AlignmentFlag.AlignCenter
print("[PASS] 状态栏显示「内部评估版本」（居中）")

# 样式：红字 + 加粗（字号沿用全局 QSS，不改）
from getcif.ui.theme import DANGER  # noqa: E402

sheet = label.styleSheet()
assert DANGER in sheet, sheet
assert "font-weight: bold" in sheet, sheet
print(f"[PASS] 标签样式：红色 {DANGER} + 加粗")

# 几何：标签横向占满状态栏，文本居中（标签中心 ≈ 状态栏中心）
left = label.mapTo(bar, label.rect().topLeft()).x()
center = left + label.width() / 2.0
bar_center = bar.width() / 2.0
assert abs(center - bar_center) <= 24, (center, bar_center, left, label.width())
print(f"[PASS] 标签横向居中（中心 {center:.0f}，状态栏中心 {bar_center:.0f}）")

# 语言切换 → 三语文案同步
window._switch_language("en")
assert window._internal_label.text() == "Internal Evaluation Edition", (
    window._internal_label.text()
)
window._switch_language("ja")
assert window._internal_label.text() == "内部評価版", window._internal_label.text()
window._switch_language("zh")
assert window._internal_label.text() == "内部评估版本"
print("[PASS] 语言切换：en / ja / zh 三语文案同步")

window.close()
print("内部评估版链路全部通过")

# -*- coding: utf-8 -*-
"""一次性交互验证：离屏环境下自动点击，完整走一遍
「启动未注册提示 → 输入注册码 → 注册成功 → 状态栏刷新」链路。"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QApplication, QDialog, QLineEdit, QMessageBox, QPushButton

from getcif.utils import registration

app = QApplication([])
UNIT = "交互测试大学材料学院"
CODE = registration.generate_code(UNIT)


def _click_button(widget, text):
    for b in widget.findChildren(QPushButton):
        if b.text() == text:
            b.click()
            return True
    return False


def make_autopilot():
    """重复扫描活动模态窗：提示框点「输入注册码」/ 信息框点「确定」(或 OK) / 对话框填码确定。"""
    state = {"done": False}

    def tick():
        w = app.activeModalWidget()
        if w is None:
            return
        if isinstance(w, QMessageBox):
            if _click_button(w, "输入注册码"):
                return
            # 信息框：确定（Qt 内置翻译缺失时标准按钮显示为 OK）
            if not _click_button(w, "确定"):
                _click_button(w, "OK")
            return
        if isinstance(w, QDialog) and w.findChild(QLineEdit) is not None:
            w.findChild(QLineEdit).setText(CODE)
            _click_button(w, "确定")
            return

    timer = QTimer(app)
    timer.timeout.connect(tick)
    timer.start(30)
    return timer


# ---- 场景 1：帮助菜单 → 输入注册码 ----
with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp) / "registration.json"
    timer = make_autopilot()
    state = registration.prompt_for_code(None, path, "PolyXRD-GetCIF")
    timer.stop()
    assert state is not None and state.registered, f"prompt_for_code 失败: {state}"
    assert state.unit == UNIT, state.unit
    assert registration.load_state(path).registered
    print(f"[PASS] 对话框输入注册码 → 已注册：{state.unit}")

    # ---- 场景 2：启动未注册提示 → 输入注册码 ----
    # 离屏守卫会跳过启动弹窗（冒烟测试所需），这里临时绕过以验证交互链路
    registration._prompt_skipped = lambda: False
    path2 = Path(tmp) / "reg2.json"
    timer = make_autopilot()
    state2 = registration.startup_prompt(None, path2, "PolyXRD-GetCIF")
    timer.stop()
    assert state2.registered and state2.unit == UNIT, f"startup_prompt 失败: {state2}"
    assert registration.load_state(path2).registered
    print(f"[PASS] 启动提示 → 输入注册码 → 已注册：{state2.unit}")

    # ---- 场景 3：已注册后再启动 → 静默无提示 ----
    state3 = registration.startup_prompt(None, path2, "PolyXRD-GetCIF")
    assert state3.registered and state3.unit == UNIT
    print("[PASS] 已注册后启动静默（无提示）")

    # ---- 场景 4：未注册点「确定」→ 关闭且仍正常返回未注册态 ----
    path3 = Path(tmp) / "reg3.json"

    def click_ok():
        w = app.activeModalWidget()
        if w is not None and isinstance(w, QMessageBox):
            _click_button(w, "确定")

    QTimer.singleShot(100, click_ok)
    state4 = registration.startup_prompt(None, path3, "PolyXRD-GetCIF")
    assert not state4.registered
    print("[PASS] 未注册点「确定」→ 关闭提示，软件可正常使用")
    registration._prompt_skipped = lambda: os.environ.get("QT_QPA_PLATFORM", "").lower() == "offscreen"

print("交互链路全部通过")

# ---------------------------------------------------------------------------
# 场景 5：真实主窗口启动链路（MainWindow + QTimer 启动提示 + 状态栏标签）
# APPDATA 重定向到临时目录，避免污染真实配置；离屏 + autopilot 自动点击。
# ---------------------------------------------------------------------------
import tempfile as _tempfile

_tmp = _tempfile.mkdtemp()
os.environ["APPDATA"] = _tmp  # getcif.core.config 在调用时读取，重定向后再建窗口

from getcif.ui.main_window import MainWindow  # noqa: E402

window = MainWindow()
window.show()
print("[PASS] MainWindow 构造并显示（未注册态）", flush=True)
assert not window._reg.state.registered
assert window._reg.label(window).text() == "未注册"

timer = make_autopilot()
# 离屏守卫会让启动提示静默跳过（冒烟测试所需）；这里临时绕过以验证真实弹窗链路
registration._prompt_skipped = lambda: False
QTimer.singleShot(15000, app.quit)  # 兜底超时
app.exec()
timer.stop()
registration._prompt_skipped = lambda: os.environ.get("QT_QPA_PLATFORM", "").lower() == "offscreen"

state = window._reg.state
label_text = window._reg.label(window).text()
assert state.registered and state.unit == UNIT, f"主窗口注册失败: {state}"
assert label_text == f"已注册：{UNIT}", label_text
print(f"[PASS] 主窗口启动提示 → 注册成功 → 状态栏显示「{label_text}」")

# ---- 场景 6：标签右对齐，且是状态栏最右侧的控件 ----
# 注意：离屏环境下 app.exec() 返回后窗口会被判定为不可见、布局不再刷新，
# 此时读到的是过期几何。重新 show() 触发一次重排后再断言。
window.show()
app.processEvents()

label = window._reg.label(window)
bar = window.statusBar()
assert label.alignment() & Qt.AlignmentFlag.AlignRight, label.alignment()
print("[PASS] 标签右对齐（AlignRight）")

# 标签右端应贴近状态栏右端。
# 注意：状态栏右下角有系统缩放手柄（size grip，约 20~30px），
# Qt 会自动把常驻控件排到手柄左侧，因此这里留出该余量。
label_right = label.mapTo(bar, label.rect().topRight()).x()
label_left = label.mapTo(bar, label.rect().topLeft()).x()
GRIP_MARGIN = 40
assert label_right >= bar.width() - GRIP_MARGIN, (
    f"标签右端未贴住状态栏右端: {label_right} / {bar.width()}"
)
print(f"[PASS] 标签位于状态栏最右侧（右端 {label_right}，状态栏宽 {bar.width()}，已扣除缩放手柄余量）")

# 进度条默认隐藏、不参与布局；仅在可见时校验「它在注册标签左侧」
if window.progress.isVisible():
    progress_right = window.progress.mapTo(bar, window.progress.rect().topRight()).x()
    assert progress_right <= label_left + 1, (
        f"进度条未在标签左侧: {progress_right} > {label_left}"
    )
    print("[PASS] 进度条在注册标签左侧（注册标签为最右常驻控件）")
else:
    print("[PASS] 进度条当前隐藏，跳过左右位置校验")

# 进度条可见时同样应在标签左侧（注册标签始终是最右常驻控件）
window.progress.setVisible(True)
window.show()
app.processEvents()
progress_right = window.progress.mapTo(bar, window.progress.rect().topRight()).x()
label_left = label.mapTo(bar, label.rect().topLeft()).x()
assert progress_right <= label_left + 1, f"进度条可见时未在标签左侧: {progress_right} > {label_left}"
print("[PASS] 进度条可见时仍在注册标签左侧")
window.progress.setVisible(False)

# 注册状态落盘到重定向后的 APPDATA
saved = registration.load_state(Path(_tmp) / "PolyXRD" / "GetCIF" / "registration.json")
assert saved.registered and saved.unit == UNIT
print("[PASS] 注册状态已持久化（%APPDATA%/PolyXRD/GetCIF/registration.json）")

window.close()
print("主窗口链路全部通过")

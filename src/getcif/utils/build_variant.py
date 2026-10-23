# -*- coding: utf-8 -*-
"""构建变体检测：内部评估版（Internal）vs 正式发布版（Release）。

**内部评估版**：打包时由 ``PolyXRD-GetCIF-Internal.spec`` 向包内注入标记文件
``_internal_edition.marker``，运行时据此判定。内部评估版行为差异：

* 注册机制整体停用 —— 无未注册启动提示、无「输入注册码」菜单项；
* 主窗口状态栏**居中**固定显示「内部评估版本」（加粗红字，字号不变）。

正式发布版（默认）不包含该标记文件，注册机制照常工作。
源码运行 / 测试时可用环境变量 ``POLYXRD_GETCIF_INTERNAL=1`` 强制内部模式。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

#: 内部评估版标记文件名（由 Internal spec 打进包根目录）
MARKER_NAME = "_internal_edition.marker"


def is_internal_edition() -> bool:
    """当前是否为内部评估版构建。"""
    if os.environ.get("POLYXRD_GETCIF_INTERNAL") == "1":
        return True
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", "") or str(Path(sys.executable).parent)
        return (Path(base) / MARKER_NAME).exists()
    return False

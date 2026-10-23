"""应用内 3D 结构预览（matplotlib 3D，PolyXRD-CifCalc Tier A 同款实现思路）。

晶胞边框 + 原子位点（元素配色 / 半径），对称操作展开，周期性包裹进胞内。
"""
from __future__ import annotations

import math
from typing import Any, Optional

from getcif.cifparse import CifData
from getcif.viz_elements import element_color, element_radius

_MAX_SITES = 800          # 绘制上限：超出后抽样
_CELL_COLOR = "#22A7DD"   # PolyXRD 主题青色（与 splash 呼应）
_BG_COLOR = "#FFFFFF"     # 明亮模式：3D 视口跟随浅色界面
_TEXT_COLOR = "#333F4E"
_TEXT_DIM = "#5B6B7C"


class Viewer3D:
    """matplotlib 3D 预览控件（持有 QWidget，可嵌入布局）。"""

    def __init__(self, parent: Any = None, figure_size: tuple = (4.0, 3.4)) -> None:
        self.figure_size = figure_size
        self.widget: Any = None
        self.figure: Any = None
        self.axes: Any = None
        self.canvas: Any = None
        self.last_message = ""
        self._build(parent)

    def _build(self, parent: Any) -> None:
        try:
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
            from matplotlib.figure import Figure
        except Exception as exc:  # noqa: BLE001
            from getcif.i18n import tr
            from getcif.utils.edition import STANDARD, get_edition

            if get_edition() == STANDARD:
                self.last_message = f"{tr('标准版不含 3D 预览')}\n{tr('如需 3D 结构展示，请使用 PolyXRD-GetCIF-Plus')}"
            else:
                self.last_message = f"3D 预览依赖缺失：{exc}"
            return
        self.figure = Figure(figsize=self.figure_size, facecolor=_BG_COLOR)
        self.axes = self.figure.add_subplot(111, projection="3d", facecolor=_BG_COLOR)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setStyleSheet(f"background:{_BG_COLOR};")
        self.widget = self.canvas

    # ------------------------------------------------------------------
    def _cell_matrix(self, cell: dict[str, float]):
        """晶胞参数 → 列向量基矢矩阵 (3x3, Å)。"""
        a, b, c = cell.get("a", 0), cell.get("b", 0), cell.get("c", 0)
        alpha = math.radians(cell.get("alpha", 90))
        beta = math.radians(cell.get("beta", 90))
        gamma = math.radians(cell.get("gamma", 90))
        va = [a, 0.0, 0.0]
        vb = [b * math.cos(gamma), b * math.sin(gamma), 0.0]
        cx = c * math.cos(beta)
        cy = c * (math.cos(alpha) - math.cos(beta) * math.cos(gamma)) / max(math.sin(gamma), 1e-9)
        cz2 = c * c - cx * cx - cy * cy
        cz = math.sqrt(max(cz2, 0.0))
        vc = [cx, cy, cz]
        return [va, vb, vc]

    def clear(self, message: str = "") -> None:
        self.last_message = message
        if self.axes is None:
            return
        self.axes.clear()
        self.axes.set_axis_off()
        self.axes.set_facecolor(_BG_COLOR)
        if message:
            self.axes.text2D(0.5, 0.5, message, transform=self.axes.transAxes,
                             ha="center", va="center", color=_TEXT_DIM, fontsize=9)
        self._refresh()

    def _refresh(self) -> None:
        if self.canvas is not None:
            self.canvas.draw_idle()

    def set_cif(self, cif: Optional[CifData], label: str = "") -> bool:
        """渲染 CIF 数据（失败返回 False，占位文案写入 last_message）。"""
        if self.axes is None:
            return False
        if cif is None or not cif.sites or cif.cell.get("a", 0) <= 0:
            self.clear("无法解析 CIF，3D 预览不可用")
            return False
        self.last_message = ""
        try:
            self._render(cif, label)
            return True
        except Exception as exc:  # noqa: BLE001
            self.clear(f"3D 渲染失败：{exc}")
            return False

    def _render(self, cif: CifData, label: str) -> None:
        import numpy as np

        axes = self.axes
        axes.clear()
        axes.set_facecolor(_BG_COLOR)

        basis = np.array(self._cell_matrix(cif.cell))  # 行 = 基矢
        origin = np.zeros(3)

        # ---- 晶胞边框 ----
        corners_frac = np.array([
            [0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0],
            [0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1],
        ])
        corners = corners_frac @ basis
        edges = [(0, 1), (1, 2), (2, 3), (3, 0),
                 (4, 5), (5, 6), (6, 7), (7, 4),
                 (0, 4), (1, 5), (2, 6), (3, 7)]
        for start, end in edges:
            points = corners[[start, end]]
            axes.plot(points[:, 0], points[:, 1], points[:, 2],
                      color=_CELL_COLOR, linewidth=1.1, alpha=0.9)

        # ---- 原子（对称操作展开 + 周期包裹）----
        ops = cif.symmetry_ops or [((1, 0, 0), (0, 0, 0),
                                    (0, 1, 0), (0, 0, 0),
                                    (0, 0, 1), (0, 0, 0))]
        rendered: list[tuple[float, float, float, str]] = []
        for site in cif.sites:
            element = str(site.get("element") or site.get("label") or "X")
            fx, fy, fz = float(site.get("x", 0)), float(site.get("y", 0)), float(site.get("z", 0))
            for op in ops:
                r = (op[0] * fx + op[1] * fy + op[2] * fz + op[3],
                     op[4] * fx + op[5] * fy + op[6] * fz + op[7],
                     op[8] * fx + op[9] * fy + op[10] * fz + op[11])
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        for dz in (-1, 0, 1):
                            gx, gy, gz = r[0] + dx, r[1] + dy, r[2] + dz
                            if -0.02 <= gx <= 1.02 and -0.02 <= gy <= 1.02 and -0.02 <= gz <= 1.02:
                                rendered.append((gx, gy, gz, element))
        if len(rendered) > _MAX_SITES:
            step = len(rendered) / _MAX_SITES
            rendered = [rendered[int(i * step)] for i in range(_MAX_SITES)]

        # 按深度排序后绘制（近似球遮挡）
        centers = np.array([[p[0], p[1], p[2]] for p in rendered]) @ basis
        radii = np.array([element_radius(p[3]) for p in rendered]) * 0.45
        order = np.argsort(centers[:, 2] + centers[:, 1] * 0.3)
        for index in order:
            x, y, z = centers[index]
            element = rendered[index][3]
            axes.scatter([x], [y], [z],
                         s=max(12.0, float(radii[index]) ** 2 * 220),
                         c=element_color(element), edgecolors="#FFFFFF",
                         linewidths=0.4, depthshade=True, zorder=3)

        # ---- 视角 / 标注 ----
        all_points = np.vstack([corners, centers]) if len(centers) else corners
        padding = 1.5
        axes.set_xlim(all_points[:, 0].min() - padding, all_points[:, 0].max() + padding)
        axes.set_ylim(all_points[:, 1].min() - padding, all_points[:, 1].max() + padding)
        axes.set_zlim(all_points[:, 2].min() - padding, all_points[:, 2].max() + padding)
        axes.set_box_aspect((1, 1, 1))
        axes.view_init(elev=18, azim=-58)
        axes.xaxis.set_pane_color((0, 0, 0, 0))
        axes.yaxis.set_pane_color((0, 0, 0, 0))
        axes.zaxis.set_pane_color((0, 0, 0, 0))
        axes.set_xticks([]), axes.set_yticks([]), axes.set_zticks([])
        for axis in (axes.xaxis, axes.yaxis, axes.zaxis):
            axis.line.set_color((0, 0, 0, 0))

        shown_elements = sorted({p[3].capitalize() for p in rendered})
        title_bits = [bit for bit in (label, f"atoms={len(rendered)}") if bit]
        axes.set_title(" · ".join(title_bits), color=_TEXT_COLOR, fontsize=9, pad=2)
        if shown_elements:
            legend_labels = [f"{e}" for e in shown_elements][:10]
            axes.text2D(0.02, 0.02, "  ".join(legend_labels),
                        transform=axes.transAxes, color=_TEXT_DIM, fontsize=7)
        self._refresh()


__all__ = ["Viewer3D"]

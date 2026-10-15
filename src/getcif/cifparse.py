"""轻量 CIF 解析（预览 / 3D 渲染用）。

只解析预览所需字段：晶胞参数、对称操作（列表形式）或 P1、原子分数坐标、
化学式、数据库编号。不解析完整 CIF 语义，也不依赖 pymatgen。

另提供 ``cif_from_structure``：把 Materials Project 的 structure dict
合成最小 CIF 文本。
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Optional

from getcif.viz_elements import element_color, element_radius

_TAG_VALUE_RE = re.compile(r"^(_\S+)\s+(.*)$")
_DATA_RE = re.compile(r"^data_", re.IGNORECASE)


@dataclass
class CifData:
    """解析出的 CIF 预览数据。"""

    cell: dict[str, float] = field(default_factory=dict)
    formula: str = ""
    space_group: str = ""
    database_code: str = ""
    symmetry_ops: list[tuple[tuple[float, float, float], tuple[float, float, float]]] = field(
        default_factory=list
    )
    sites: list[dict] = field(default_factory=list)  # {label, element, x, y, z, occupancy}
    title: str = ""
    authors: list[str] = field(default_factory=list)
    raw: str = ""

    @property
    def volume(self) -> float:
        cell = self.cell
        if not all(cell.get(k) for k in ("a", "b", "c", "alpha", "beta", "gamma")):
            return 0.0
        a, b, c = cell["a"], cell["b"], cell["c"]
        ca = math.cos(math.radians(cell["alpha"]))
        cb = math.cos(math.radians(cell["beta"]))
        cg = math.cos(math.radians(cell["gamma"]))
        factor = 1 + 2 * ca * cb * cg - ca * ca - cb * cb - cg * cg
        if factor <= 0:
            return 0.0
        return a * b * c * math.sqrt(factor)


# ----------------------------------------------------------------------
# 解析
# ----------------------------------------------------------------------
def _parse_op_text(text: str) -> Optional[tuple[tuple[float, float, float], tuple[float, float, float]]]:
    """``x, y, z`` / ``-y, x-y, z+1/3`` → (旋转 3x3 行, 平移)。"""
    parts = [p.strip() for p in text.replace("'", "").replace('"', "").split(",")]
    if len(parts) != 3:
        return None
    rot_rows = []
    shift = [0.0, 0.0, 0.0]
    try:
        for row_index, expr in enumerate(parts):
            expr = expr.replace(" ", "").lower()
            coeffs = [0.0, 0.0, 0.0]
            # 逐项拆解：±2x / ±x / ±x/2 / ±1/3 / ±0.25 等
            for term in re.findall(r"[+-]?[^+-]+", expr):
                sign = -1.0 if term.startswith("-") else 1.0
                term = term.lstrip("+-")
                if not term:
                    continue
                var_match = re.match(r"([0-9*. ]*/?[0-9*. ]*)\*?([xyz])", term)
                if var_match:
                    coef_text, axis = var_match.groups()
                    axis_index = "xyz".index(axis)
                    if coef_text in ("", ".", "1"):
                        coeffs[axis_index] += sign
                    elif "/" in coef_text:
                        num, _, den = coef_text.partition("/")
                        num_val = 1.0 if num in ("", ".") else float(num.replace("*", ""))
                        den_val = float(den)
                        if den_val:
                            coeffs[axis_index] += sign * num_val / den_val
                    else:
                        coeffs[axis_index] += sign * float(coef_text.replace("*", ""))
                else:
                    if "/" in term:
                        num, _, den = term.partition("/")
                        shift[row_index] += sign * float(num) / float(den)
                    else:
                        shift[row_index] += sign * float(term)
            rot_rows.append(tuple(coeffs))
    except (ValueError, ZeroDivisionError):
        return None
    return (rot_rows[0], rot_rows[1], rot_rows[2]), tuple(shift)


def _safe_eval_op(text: str) -> Optional[tuple[tuple[float, float, float], tuple[float, float, float]]]:
    """兜底：受限 eval 探点拟合解析对称操作（``x,-y,z+1/2`` 等自由格式）。"""
    parts = [p.strip() for p in text.replace("'", "").replace('"', "").split(",")]
    if len(parts) != 3:
        return None
    rot: list[tuple[float, float, float]] = []
    shift: list[float] = []
    try:
        for expr in parts:
            code = compile(expr.strip().lower(), "<symop>", "eval")

            def _eval(x: float, y: float, z: float) -> float:
                return float(eval(code, {"__builtins__": {}}, {"x": x, "y": y, "z": z}))  # noqa: S307

            base = _eval(0.317, 0.423, 0.191)
            row = []
            for axis_index, axis in enumerate("xyz"):
                point = [0.317, 0.423, 0.191]
                point[axis_index] += 0.25
                row.append((_eval(*point) - base) / 0.25)
            shift.append(base - sum(coef * p for coef, p in zip(row, (0.317, 0.423, 0.191))))
            rot.append((row[0], row[1], row[2]))
    except Exception:  # noqa: BLE001
        return None
    return (rot[0], rot[1], rot[2]), tuple(shift)


def parse_cif(text: str) -> CifData:
    """解析 CIF 文本 → :class:`CifData`（宽松容错，失败字段留空）。

    状态机要点：
    * loop 头（连续 ``_tag`` 行）之后出现**任何数据行**即进入数据区；
    * 数据区中再次出现 ``_tag`` 行 ⇒ 该 loop 结束（CIF 规范），按单值标签处理；
    * ``;`` 开头的行进入多行文本块，直到下一个 ``;`` 行结束。
    """
    data = CifData(raw=text)
    lines = text.splitlines()

    i = 0
    loop_tags: list[str] = []
    loop_rows: list[list[str]] = []
    in_loop_header = False
    loop_data_started = False
    in_semicolon = False
    current_tag = ""
    current_value_lines: list[str] = []

    def _flush_tag_value() -> None:
        nonlocal current_tag, current_value_lines
        if not current_tag:
            current_value_lines = []
            return
        value = "\n".join(current_value_lines).strip()
        _assign_single(data, current_tag, value)
        current_tag = ""
        current_value_lines = []

    def _flush_loop() -> None:
        nonlocal loop_tags, loop_rows, in_loop_header, loop_data_started
        if loop_tags:
            _assign_loop(data, loop_tags, loop_rows)
        loop_tags, loop_rows = [], []
        in_loop_header = False
        loop_data_started = False

    while i < len(lines):
        raw = lines[i]
        line = raw.strip()

        # ---- 多行文本块（; ... ;）----
        if in_semicolon:
            if line.startswith(";"):
                _flush_tag_value()
                in_semicolon = False
            else:
                current_value_lines.append(raw)
            i += 1
            continue

        if not line or line.startswith("#"):
            i += 1
            continue

        lowered = line.lower()
        if lowered.startswith("loop_"):
            _flush_tag_value()
            _flush_loop()
            in_loop_header = True
            i += 1
            continue

        if lowered.startswith("data_") or lowered.startswith("global_"):
            _flush_tag_value()
            _flush_loop()
            i += 1
            continue

        if line.startswith("_"):
            parts = line.split(None, 1)
            tag = parts[0]
            rest = parts[1].strip() if len(parts) > 1 else ""

            if in_loop_header and not loop_data_started:
                # loop 头标签
                loop_tags.append(tag)
                if rest:  # 标签行带值（罕见）：视作首行数据
                    loop_rows.append(_split_cif_tokens(rest))
                    loop_data_started = True
                i += 1
                continue

            # loop 数据区中出现新标签 ⇒ loop 结束；按单值标签处理
            _flush_loop()
            current_tag = tag
            if rest.startswith(";"):
                # 值从下一行开始（行尾分号块）
                current_value_lines = []
                in_semicolon = True
                i += 1
                continue
            if rest:
                _assign_single(data, tag, _unquote(rest))
                current_tag = ""
                i += 1
                continue
            # 值在下一行：检查是否分号块
            nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
            if nxt.startswith(";"):
                current_value_lines = []
                in_semicolon = True
                i += 2
                continue
            if nxt and not nxt.startswith("_") and not nxt.lower().startswith("loop_")                     and not nxt.lower().startswith("data_"):
                _assign_single(data, tag, _unquote(nxt))
                current_tag = ""
                i += 2
                continue
            _flush_tag_value()
            i += 1
            continue

        # ---- 数据行 ----
        if loop_tags:
            loop_rows.append(_split_cif_tokens(line))
            loop_data_started = True
        i += 1

    _flush_tag_value()
    _flush_loop()

    # 无对称操作 → P1（恒等操作）
    if not data.symmetry_ops:
        data.symmetry_ops = [(((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
                              (0.0, 0.0, 0.0))]  # type: ignore[list-item]
    # 规范对称操作结构 → 12 元组（r11..r33 + t1..t3）
    normalized: list[tuple] = []
    for op in data.symmetry_ops:
        if isinstance(op, tuple) and len(op) == 2:
            rot, shift = op
            normalized.append((
                rot[0][0], rot[0][1], rot[0][2], shift[0],
                rot[1][0], rot[1][1], rot[1][2], shift[1],
                rot[2][0], rot[2][1], rot[2][2], shift[2],
            ))
    data.symmetry_ops = normalized  # type: ignore[assignment]
    return data


def _unquote(text: str) -> str:
    text = text.strip()
    if len(text) >= 2 and text[0] in "'\"" and text[-1] == text[0]:
        return text[1:-1]
    return text


def _split_cif_tokens(line: str) -> list[str]:
    """按 CIF 词法切分（支持引号包裹）。"""
    tokens: list[str] = []
    for match in re.finditer(r"'([^']*)'|\"([^\"]*)\"|(\S+)", line):
        tokens.append(next(g for g in match.groups() if g is not None))
    return tokens


def _assign_single(data: CifData, tag: str, value: str) -> None:
    tag = tag.lower()
    number = _parse_number(value)
    try:
        if tag in ("_cell_length_a",):
            if number is not None:
                data.cell["a"] = number
        elif tag in ("_cell_length_b",):
            if number is not None:
                data.cell["b"] = number
        elif tag in ("_cell_length_c",):
            if number is not None:
                data.cell["c"] = number
        elif tag in ("_cell_angle_alpha",):
            if number is not None:
                data.cell["alpha"] = number
        elif tag in ("_cell_angle_beta",):
            if number is not None:
                data.cell["beta"] = number
        elif tag in ("_cell_angle_gamma",):
            if number is not None:
                data.cell["gamma"] = number
        elif tag in ("_cell_volume",):
            if number is not None:
                data.cell.setdefault("volume", number)
        elif tag in ("_chemical_formula_sum", "_chemical_formula_structural"):
            data.formula = _unquote(value) or data.formula
        elif tag in ("_symmetry_space_group_name_h-m", "_space_group_name_h-m_alt",
                     "_space_group_name_h-m", "_symmetry_space_group_name_h-m_alt"):
            data.space_group = _unquote(value) or data.space_group
        elif tag in ("_space_group_it_number", "_symmetry_int_tables_number"):
            data.space_group = data.space_group or f"#{value}"
        elif tag in ("_database_code_cod", "_database_code_amcsd", "_database_code_mp",
                     "_database_code_atomly", "_database_code"):
            data.database_code = data.database_code or value
        elif tag in ("_atom_sites_Cartn_transform_matrix_11",):
            pass
        elif tag == "_citation_title":
            data.title = data.title or _unquote(value)
        elif tag == "_publ_author_name":
            data.authors.append(_unquote(value))
    except (TypeError, ValueError):
        pass


def _parse_number(text: str) -> Optional[float]:
    """解析 CIF 数值（剥离不确定度后缀：``0.255(8)`` → 0.255）。"""
    cleaned = re.sub(r"\(\d+\)", "", str(text).strip())
    try:
        return float(cleaned)
    except (TypeError, ValueError):
        return None


def _assign_loop(data: CifData, tags: list[str], rows: list[list[str]]) -> None:
    tags_lower = [t.lower() for t in tags]
    # 对称操作列表
    op_tags = {"_symmetry_equiv_pos_as_xyz", "_space_group_symop_operation_xyz"}
    op_indexes = [i for i, t in enumerate(tags_lower) if t in op_tags]
    if op_indexes:
        for row in rows:
            if len(row) > op_indexes[0]:
                text = row[op_indexes[0]]
                op = _parse_op_text(text) or _safe_eval_op(text)
                if op is not None:
                    data.symmetry_ops.append(op)  # type: ignore[arg-type]
        return
    # 原子位点
    site_map = {}
    for alias, key in (
        ("_atom_site_label", "label"),
        ("_atom_site_type_symbol", "element"),
        ("_atom_site_fract_x", "x"),
        ("_atom_site_fract_y", "y"),
        ("_atom_site_fract_z", "z"),
        ("_atom_site_occupancy", "occupancy"),
    ):
        if alias in tags_lower:
            site_map[key] = tags_lower.index(alias)
    if "x" not in site_map or "y" not in site_map or "z" not in site_map:
        return
    for row in rows:
        if len(row) < len(tags):
            continue
        coords = [_parse_number(row[site_map[axis]]) for axis in ("x", "y", "z")]
        if any(v is None for v in coords):
            continue
        try:
            element = str(row[site_map["element"]]) if "element" in site_map else ""
            label = str(row[site_map["label"]]) if "label" in site_map else element
            element = element or label
            match = re.match(r"[A-Za-z]{1,2}", element)
            element = match.group(0) if match else element
            occupancy = 1.0
            if "occupancy" in site_map:
                occ = _parse_number(row[site_map["occupancy"]])
                occupancy = occ if occ is not None else 1.0
            data.sites.append({
                "label": label,
                "element": element[:2].capitalize() if element[:1].isalpha() else element,
                "x": coords[0], "y": coords[1], "z": coords[2],
                "occupancy": occupancy,
            })
        except (TypeError, ValueError, IndexError):
            continue


# ----------------------------------------------------------------------
# MP structure dict → CIF 文本
# ----------------------------------------------------------------------
def cif_from_structure(structure: dict, material_id: str = "") -> str:
    """Materials Project structure dict → 最小 P1 CIF 文本。"""
    lattice = structure.get("lattice") or {}
    sites = structure.get("sites") or []
    lines = [
        f"data_{material_id or 'mp_structure'}",
        "_audit_creation_method 'PolyXRD-GetCIF (MP structure)'",
        f"_cell_length_a {lattice.get('a', 0)}",
        f"_cell_length_b {lattice.get('b', 0)}",
        f"_cell_length_c {lattice.get('c', 0)}",
        f"_cell_angle_alpha {lattice.get('alpha', 90)}",
        f"_cell_angle_beta {lattice.get('beta', 90)}",
        f"_cell_angle_gamma {lattice.get('gamma', 90)}",
        f"_cell_volume {lattice.get('volume', 0)}",
        "_symmetry_space_group_name_H-M 'P 1'",
        "_space_group_name_H-M_alt 'P 1'",
        "loop_",
        "_symmetry_equiv_pos_as_xyz",
        "'x, y, z'",
        "loop_",
        "_atom_site_label",
        "_atom_site_type_symbol",
        "_atom_site_fract_x",
        "_atom_site_fract_y",
        "_atom_site_fract_z",
        "_atom_site_occupancy",
    ]
    for index, site in enumerate(sites, start=1):
        species_list = site.get("species") or []
        element = str(species_list[0].get("element", "X")) if species_list else "X"
        abc = site.get("abc") or (0, 0, 0)
        occ = species_list[0].get("occu", 1.0) if species_list else 1.0
        lines.append(
            f"{element}{index} {element} {abc[0]:.6f} {abc[1]:.6f} {abc[2]:.6f} {occ:.4f}"
        )
    return "\n".join(lines) + "\n"


__all__ = ["CifData", "cif_from_structure", "element_color", "element_radius", "parse_cif"]

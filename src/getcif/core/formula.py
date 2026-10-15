"""化学式辅助：COD 库格式归一化、元素提取。"""
from __future__ import annotations

import re

_ELEMENT_TOKEN_RE = re.compile(r"([A-Z][a-z]?)(\d*\.?\d*)")
_HM_TOKEN_RE = re.compile(r"[A-Za-z]+|\d+|[-/]")


def normalize_cod_formula(formula: str) -> str:
    """把化学式归一化为 COD 检索格式：元素按字母序、空格分隔、计数 1 省略。

    ``SiO2`` → ``O2 Si``；``Mg(OH)2`` → ``H2 Mg O2``。解析失败原样返回。
    """
    text = str(formula or "").strip()
    if not text:
        return ""

    for _ in range(5):  # 展开嵌套括号
        def _expand(match: re.Match) -> str:
            inner, times = match.group(1), match.group(2)
            factor = int(times) if times else 1
            parts = []
            for element, count in _ELEMENT_TOKEN_RE.findall(inner):
                n = int(float(count)) if count else 1
                parts.append(f"{element}{n * factor}")
            return " ".join(parts)

        expanded = re.sub(r"\(([A-Za-z0-9]+)\)(\d*)", _expand, text)
        if expanded == text:
            break
        text = expanded

    counts: dict[str, int] = {}
    for element, count in _ELEMENT_TOKEN_RE.findall(text):
        if not element:
            continue
        n = int(float(count)) if count else 1
        counts[element] = counts.get(element, 0) + n
    if not counts:
        return text
    return " ".join(
        f"{element}{counts[element] if counts[element] != 1 else ''}"
        for element in sorted(counts)
    )


def normalize_formula_display(formula: str) -> str:
    """展示用归一化：``O2 Si`` / ``Si O2`` → ``SiO2``（Hill 排序近似）。"""
    text = str(formula or "").strip()
    if not text:
        return ""
    counts: dict[str, int] = {}
    for element, count in _ELEMENT_TOKEN_RE.findall(text):
        if not element:
            continue
        n = int(float(count)) if count else 1
        counts[element] = counts.get(element, 0) + n
    if not counts:
        return text
    ordered = sorted(counts)
    if "C" in ordered:  # Hill 规则：C 在前，H 次之
        ordered = ["C"] + [e for e in ordered if e not in ("C", "H")] + (
            ["H"] if "H" in ordered else []
        )
    return "".join(
        f"{e}{counts[e] if counts[e] != 1 else ''}" for e in ordered if counts[e] > 0
    )


def spaced_hm_symbol(symbol: str) -> str:
    """H-M 符号转空格分隔形式：``Fm-3m`` → ``F m -3 m``。"""
    text = str(symbol or "").strip()
    if not text or " " in text:
        return text
    return " ".join(_HM_TOKEN_RE.findall(text))


def split_elements(text: str) -> list[str]:
    """``Ti, O`` / ``Ti O`` / ``TiO`` → ["Ti", "O"]（宽松解析，非法 token 忽略）。"""
    raw = str(text or "").replace(",", " ").replace(";", " ").split()
    result: list[str] = []
    for token in raw:
        for element, _count in _ELEMENT_TOKEN_RE.findall(token):
            if element and element not in result:
                result.append(element)
    return result

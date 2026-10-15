"""检索条件与候选结构的数据模型（轻量 dataclass，无重依赖）。"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SearchQuery:
    """统一的检索条件（各适配器按需取用）。"""

    formula: str = ""
    elements: str = ""          # 逗号/空格分隔元素，如 "Ti,O"
    name: str = ""              # 矿物名 / 关键词
    space_group: str = ""       # H-M 符号或编号
    crystal_system: str = ""    # 本地过滤用（在线库多数不支持）
    a: float | None = None
    b: float | None = None
    c: float | None = None
    alpha: float | None = None
    beta: float | None = None
    gamma: float | None = None
    limit: int = 50

    def has_condition(self) -> bool:
        text = (self.formula + self.elements + self.name + self.space_group).strip()
        if text:
            return True
        lattice = (self.a, self.b, self.c, self.alpha, self.beta, self.gamma)
        return any(v is not None for v in lattice)


@dataclass
class LatticeParams:
    a: float = 0.0
    b: float = 0.0
    c: float = 0.0
    alpha: float = 0.0
    beta: float = 0.0
    gamma: float = 0.0
    volume: float = 0.0

    def is_empty(self) -> bool:
        return not (self.a > 0 and self.b > 0 and self.c > 0)

    def summary(self) -> str:
        if self.is_empty():
            return ""
        text = f"{self.a:.3f} / {self.b:.3f} / {self.c:.3f}"
        if self.alpha > 0 and self.beta > 0 and self.gamma > 0:
            text += f" · {self.alpha:.1f}/{self.beta:.1f}/{self.gamma:.1f}"
        return text


@dataclass
class Candidate:
    """归一化的候选结构条目。"""

    source: str = ""            # cod / cod_local / amcsd / mp / atomly
    source_id: str = ""
    formula: str = ""
    mineral_name: str = ""
    space_group: str = ""
    crystal_system: str = ""
    lattice: LatticeParams = field(default_factory=LatticeParams)
    elements: set[str] = field(default_factory=set)
    cif_url: str = ""
    cif_content: str = ""
    provenance: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def candidate_id(self) -> str:
        return f"{self.source}:{self.source_id}"

    def display_formula(self) -> str:
        return self.formula or "-"


def elements_from_formula(formula: str) -> set[str]:
    """从化学式粗提元素集合（``CaMg(CO3)2`` → {Ca, Mg, C, O}）。"""
    import re

    text = str(formula or "")
    # 去掉括号内容再扫元素 token
    simplified = re.sub(r"\([^)]*\)", "", text)
    tokens = re.findall(r"\b([A-Z][a-z]?)", simplified)
    return {t for t in tokens if t}


def parse_float(text: object) -> float | None:
    try:
        value = float(str(text).strip())
    except (TypeError, ValueError):
        return None
    return value if value == value else None  # 过滤 NaN

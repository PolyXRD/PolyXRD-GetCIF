"""检索控制器：后台线程顺序查询已启用的适配器，信号回传主线程。"""
from __future__ import annotations

import traceback
from typing import Optional

from PySide6.QtCore import QThread, Signal

from getcif.adapters import create_adapters
from getcif.adapters.base import AdapterError, BaseAdapter
from getcif.core.schema import Candidate, SearchQuery


class SearchWorker(QThread):
    """顺序查询所有启用数据源；逐源发射状态，结束时发射汇总结果。"""

    #: (source_name, status_text)  status: waiting/querying/hits/empty/failed/disabled
    source_status = Signal(str, str, str)
    finished_all = Signal(list, bool)   # candidates, partial（部分源失败）
    failed = Signal(str)

    def __init__(self, query: SearchQuery, timeout: int = 30, parent=None) -> None:
        super().__init__(parent)
        self.query = query
        self.timeout = timeout
        self._cancelled = False
        self.adapters = create_adapters(timeout)

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:  # noqa: C901
        all_candidates: list[Candidate] = []
        partial = False
        any_enabled = False

        for adapter in self.adapters:
            if self._cancelled:
                return
            if not adapter.is_available():
                self.source_status.emit(adapter.name, "disabled", adapter.availability_reason())
                continue
            any_enabled = True
            self.source_status.emit(adapter.name, "querying", "")
            try:
                candidates = adapter.search(self.query)
            except AdapterError as exc:
                partial = True
                self.source_status.emit(adapter.name, "failed", exc.reason)
                continue
            except Exception as exc:  # noqa: BLE001
                partial = True
                traceback.print_exc()
                self.source_status.emit(adapter.name, "failed", str(exc))
                continue
            if self._cancelled:
                return
            # 跨源去重（同 id 的 cod / cod_local 保留首个）
            deduped = []
            existing = {f"{c.source}:{c.source_id}" for c in all_candidates}
            for candidate in candidates:
                if candidate.candidate_id in existing:
                    continue
                existing.add(candidate.candidate_id)
                deduped.append(candidate)
            all_candidates.extend(deduped)
            status = "hits" if deduped else "empty"
            detail = f"{len(deduped)} 条" if deduped else ""
            self.source_status.emit(adapter.name, status, detail)

        if not any_enabled:
            self.failed.emit("没有已启用的数据源")
            return
        if self._cancelled:
            return
        self.finished_all.emit(all_candidates, partial)

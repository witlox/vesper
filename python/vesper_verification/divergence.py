"""
Divergence Detection and Storage for Vesper Verification
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class DivergenceRecord:
    """A record of a divergence between runtimes."""

    id: str
    node_id: str
    inputs: dict[str, Any]
    python_output: dict[str, Any]
    direct_output: dict[str, Any]
    diff: dict[str, Any]
    timestamp: str
    mode: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "node_id": self.node_id,
            "inputs": self.inputs,
            "python_output": self.python_output,
            "direct_output": self.direct_output,
            "diff": self.diff,
            "timestamp": self.timestamp,
            "mode": self.mode,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DivergenceRecord:
        """Create from dictionary."""
        return cls(
            id=data["id"],
            node_id=data["node_id"],
            inputs=data["inputs"],
            python_output=data["python_output"],
            direct_output=data["direct_output"],
            diff=data["diff"],
            timestamp=data["timestamp"],
            mode=data["mode"],
            metadata=data.get("metadata", {}),
        )


class DivergenceDatabase:
    """Storage and retrieval for divergence records."""

    def __init__(
        self,
        storage_path: Path | None = None,
        max_records_per_node: int = 1000,
    ) -> None:
        self.storage_path = storage_path
        self.max_records_per_node = max_records_per_node
        self._records: dict[str, list[DivergenceRecord]] = {}
        self._lock = asyncio.Lock()

        if storage_path:
            self._load_from_file()

    async def store(self, record: DivergenceRecord) -> None:
        """Store a divergence record."""
        async with self._lock:
            if record.node_id not in self._records:
                self._records[record.node_id] = []

            records = self._records[record.node_id]
            records.append(record)

            if len(records) > self.max_records_per_node:
                self._records[record.node_id] = records[-self.max_records_per_node :]

            if self.storage_path:
                self._save_to_file()

    async def get_by_node(
        self, node_id: str, limit: int = 100, offset: int = 0
    ) -> list[DivergenceRecord]:
        """Get divergences for a specific node."""
        async with self._lock:
            records = self._records.get(node_id, [])
            return list(reversed(records))[offset : offset + limit]

    async def get_by_time_range(
        self,
        start_time: datetime,
        end_time: datetime | None = None,
        node_id: str | None = None,
    ) -> list[DivergenceRecord]:
        """Get divergences within a time range."""
        if end_time is None:
            end_time = datetime.now(UTC)

        start_iso = start_time.isoformat()
        end_iso = end_time.isoformat()

        result: list[DivergenceRecord] = []

        async with self._lock:
            nodes = [node_id] if node_id else list(self._records.keys())
            for nid in nodes:
                for record in self._records.get(nid, []):
                    if start_iso <= record.timestamp <= end_iso:
                        result.append(record)

        return sorted(result, key=lambda r: r.timestamp, reverse=True)

    async def get_stats(self, node_id: str | None = None) -> dict[str, Any]:
        """Get statistics about stored divergences."""
        async with self._lock:
            if node_id:
                records = self._records.get(node_id, [])
                return self._compute_stats(records, node_id)
            else:
                all_stats = {}
                for nid, records in self._records.items():
                    all_stats[nid] = self._compute_stats(records, nid)
                return all_stats

    def _compute_stats(
        self, records: list[DivergenceRecord], node_id: str
    ) -> dict[str, Any]:
        """Compute statistics for a list of records."""
        if not records:
            return {
                "node_id": node_id,
                "total_divergences": 0,
                "by_mode": {},
                "most_common_diff_types": [],
            }

        by_mode: dict[str, int] = {}
        for record in records:
            by_mode[record.mode] = by_mode.get(record.mode, 0) + 1

        diff_types: dict[str, int] = {}
        for record in records:
            for diff in record.diff.get("differences", []):
                diff_type = diff.get("type", "unknown")
                diff_types[diff_type] = diff_types.get(diff_type, 0) + 1

        sorted_diff_types = sorted(
            diff_types.items(), key=lambda x: x[1], reverse=True
        )[:5]

        return {
            "node_id": node_id,
            "total_divergences": len(records),
            "by_mode": by_mode,
            "most_common_diff_types": [
                {"type": t, "count": c} for t, c in sorted_diff_types
            ],
            "oldest": records[0].timestamp if records else None,
            "newest": records[-1].timestamp if records else None,
        }

    async def clear(self, node_id: str | None = None) -> int:
        """Clear divergence records."""
        async with self._lock:
            if node_id:
                count = len(self._records.get(node_id, []))
                self._records.pop(node_id, None)
            else:
                count = sum(len(r) for r in self._records.values())
                self._records.clear()

            if self.storage_path:
                self._save_to_file()
            return count

    def _load_from_file(self) -> None:
        """Load records from file storage."""
        if not self.storage_path or not self.storage_path.exists():
            return
        try:
            with open(self.storage_path) as f:
                data = json.load(f)
            for node_id, records_data in data.items():
                self._records[node_id] = [
                    DivergenceRecord.from_dict(r) for r in records_data
                ]
            logger.info(
                f"Loaded {sum(len(r) for r in self._records.values())} divergence records"
            )
        except Exception as e:
            logger.error(f"Failed to load divergence records: {e}")

    def _save_to_file(self) -> None:
        """Save records to file storage."""
        if not self.storage_path:
            return
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                node_id: [r.to_dict() for r in records]
                for node_id, records in self._records.items()
            }
            with open(self.storage_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save divergence records: {e}")

"""
Backends for Vesper Runtime
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class OperationResult:
    """Result of a backend operation."""

    success: bool
    data: Any | None = None
    error: str | None = None


class Backend(ABC):
    """Abstract base class for backends."""

    @abstractmethod
    async def execute(self, operation: str, params: dict[str, Any]) -> OperationResult:
        pass


class InMemoryBackend(Backend):
    """In-memory backend for testing."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}
        self._operations: list[dict[str, Any]] = []

    async def execute(self, operation: str, params: dict[str, Any]) -> OperationResult:
        self._operations.append({"operation": operation, "params": params})
        try:
            if operation == "get":
                return self._get(params)
            elif operation == "set":
                return self._set(params)
            elif operation == "delete":
                return self._delete(params)
            elif operation == "list":
                return self._list(params)
            elif operation == "exists":
                return self._exists(params)
            else:
                return OperationResult(
                    success=False, error=f"Unknown operation: {operation}"
                )
        except Exception as e:
            return OperationResult(success=False, error=str(e))

    def _get(self, params: dict[str, Any]) -> OperationResult:
        collection = params.get("collection", "default")
        key: str = params.get("key", "")
        if collection not in self._data:
            return OperationResult(success=True, data=None)
        data = self._data[collection].get(key)
        return OperationResult(success=True, data=data)

    def _set(self, params: dict[str, Any]) -> OperationResult:
        collection = params.get("collection", "default")
        key: str = params.get("key", "")
        value = params.get("value")
        if collection not in self._data:
            self._data[collection] = {}
        self._data[collection][key] = value
        return OperationResult(success=True, data=value)

    def _delete(self, params: dict[str, Any]) -> OperationResult:
        collection = params.get("collection", "default")
        key: str = params.get("key", "")
        if collection in self._data and key in self._data[collection]:
            del self._data[collection][key]
        return OperationResult(success=True)

    def _list(self, params: dict[str, Any]) -> OperationResult:
        collection = params.get("collection", "default")
        if collection not in self._data:
            return OperationResult(success=True, data=[])
        keys = list(self._data[collection].keys())
        return OperationResult(success=True, data=keys)

    def _exists(self, params: dict[str, Any]) -> OperationResult:
        collection = params.get("collection", "default")
        key = params.get("key")
        exists = collection in self._data and key in self._data[collection]
        return OperationResult(success=True, data=exists)

    def get_operations(self) -> list[dict[str, Any]]:
        return list(self._operations)

    def clear(self) -> None:
        self._data.clear()
        self._operations.clear()


class MockBackend(Backend):
    """Mock backend for testing."""

    def __init__(self) -> None:
        self._responses: dict[str, OperationResult] = {}
        self._default_response = OperationResult(success=True, data=None)
        self._calls: list[dict[str, Any]] = []

    def set_response(self, operation: str, result: OperationResult) -> None:
        self._responses[operation] = result

    def set_default_response(self, result: OperationResult) -> None:
        self._default_response = result

    async def execute(self, operation: str, params: dict[str, Any]) -> OperationResult:
        self._calls.append({"operation": operation, "params": params})
        return self._responses.get(operation, self._default_response)

    def get_calls(self) -> list[dict[str, Any]]:
        return list(self._calls)

    def reset(self) -> None:
        self._responses.clear()
        self._calls.clear()

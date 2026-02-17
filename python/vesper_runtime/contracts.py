"""
Runtime Contract Checking for Vesper
"""

from __future__ import annotations

import operator
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


class ContractViolation(Exception):
    """Base exception for contract violations."""

    def __init__(
        self, message: str, contract: str, values: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message)
        self.contract = contract
        self.values = values or {}


class PreconditionViolation(ContractViolation):
    """Raised when a precondition is violated."""

    pass


class PostconditionViolation(ContractViolation):
    """Raised when a postcondition is violated."""

    pass


class InvariantViolation(ContractViolation):
    """Raised when an invariant is violated."""

    pass


@dataclass
class ContractResult:
    """Result of contract evaluation."""

    passed: bool
    contract: str
    message: str | None = None
    values: dict[str, Any] | None = None


class ContractChecker:
    """Checks contracts at runtime."""

    OPERATORS: dict[str, Callable[[Any, Any], bool]] = {
        "==": operator.eq,
        "!=": operator.ne,
        "<": operator.lt,
        "<=": operator.le,
        ">": operator.gt,
        ">=": operator.ge,
    }

    def __init__(self) -> None:
        self._custom_functions: dict[str, Callable[..., Any]] = {}

    def register_function(self, name: str, func: Callable[..., Any]) -> None:
        self._custom_functions[name] = func

    def check_precondition(
        self, contract: str, inputs: dict[str, Any]
    ) -> ContractResult:
        try:
            result = self._evaluate(contract, inputs)
            if result:
                return ContractResult(passed=True, contract=contract)
            else:
                return ContractResult(
                    passed=False,
                    contract=contract,
                    message=f"Precondition failed: {contract}",
                    values=inputs,
                )
        except Exception as e:
            return ContractResult(
                passed=False,
                contract=contract,
                message=f"Error evaluating precondition: {e}",
                values=inputs,
            )

    def check_postcondition(
        self,
        contract: str,
        inputs: dict[str, Any],
        outputs: dict[str, Any],
        old_values: dict[str, Any] | None = None,
    ) -> ContractResult:
        context = {**inputs, **outputs}
        if old_values:
            context["_old"] = old_values
        try:
            result = self._evaluate(contract, context)
            if result:
                return ContractResult(passed=True, contract=contract)
            else:
                return ContractResult(
                    passed=False,
                    contract=contract,
                    message=f"Postcondition failed: {contract}",
                    values=context,
                )
        except Exception as e:
            return ContractResult(
                passed=False,
                contract=contract,
                message=f"Error evaluating postcondition: {e}",
                values=context,
            )

    def check_invariant(self, contract: str, state: dict[str, Any]) -> ContractResult:
        try:
            result = self._evaluate(contract, state)
            if result:
                return ContractResult(passed=True, contract=contract)
            else:
                return ContractResult(
                    passed=False,
                    contract=contract,
                    message=f"Invariant violated: {contract}",
                    values=state,
                )
        except Exception as e:
            return ContractResult(
                passed=False,
                contract=contract,
                message=f"Error evaluating invariant: {e}",
                values=state,
            )

    def enforce_preconditions(
        self, contracts: list[str], inputs: dict[str, Any]
    ) -> None:
        for contract in contracts:
            result = self.check_precondition(contract, inputs)
            if not result.passed:
                raise PreconditionViolation(
                    result.message or f"Precondition failed: {contract}",
                    contract=contract,
                    values=result.values,
                )

    def enforce_postconditions(
        self,
        contracts: list[str],
        inputs: dict[str, Any],
        outputs: dict[str, Any],
        old_values: dict[str, Any] | None = None,
    ) -> None:
        for contract in contracts:
            result = self.check_postcondition(contract, inputs, outputs, old_values)
            if not result.passed:
                raise PostconditionViolation(
                    result.message or f"Postcondition failed: {contract}",
                    contract=contract,
                    values=result.values,
                )

    def _evaluate(self, contract: str, context: dict[str, Any]) -> bool:
        contract = " ".join(contract.split())

        if " OR " in contract:
            parts = contract.split(" OR ", 1)
            return self._evaluate(parts[0], context) or self._evaluate(
                parts[1], context
            )

        if " AND " in contract:
            parts = contract.split(" AND ", 1)
            return self._evaluate(parts[0], context) and self._evaluate(
                parts[1], context
            )

        if contract.startswith("NOT "):
            return not self._evaluate(contract[4:], context)

        if " IS NOT NULL" in contract:
            var_name = contract.replace(" IS NOT NULL", "").strip()
            value = self._get_value(var_name, context)
            return value is not None

        if " IS NULL" in contract:
            var_name = contract.replace(" IS NULL", "").strip()
            value = self._get_value(var_name, context)
            return value is None

        if " IN " in contract:
            match = re.match(r"(.+)\s+IN\s+\[(.+)\]", contract)
            if match:
                var_name = match.group(1).strip()
                values_str = match.group(2)
                value = self._get_value(var_name, context)
                allowed = self._parse_list(values_str)
                return value in allowed

        if " CONTAINS " in contract:
            parts = contract.split(" CONTAINS ", 1)
            container = self._get_value(parts[0].strip(), context)
            item = self._parse_value(parts[1].strip(), context)
            return item in container

        for op_str, op_func in self.OPERATORS.items():
            if op_str in contract:
                parts = contract.split(op_str, 1)
                left = self._parse_value(parts[0].strip(), context)
                right = self._parse_value(parts[1].strip(), context)
                return op_func(left, right)

        if contract.lower() == "true":
            return True
        if contract.lower() == "false":
            return False

        value = self._get_value(contract, context)
        return bool(value)

    def _get_value(self, path: str, context: dict[str, Any]) -> Any:
        if path.startswith("old(") and path.endswith(")"):
            inner_path = path[4:-1]
            return self._get_value(inner_path, context.get("_old", {}))

        if "(" in path and path.endswith(")"):
            match = re.match(r"(\w+)\((.+)\)", path)
            if match:
                func_name = match.group(1)
                args_str = match.group(2)
                if func_name in self._custom_functions:
                    args = [
                        self._parse_value(a.strip(), context)
                        for a in args_str.split(",")
                    ]
                    return self._custom_functions[func_name](*args)

        parts = path.split(".")
        value: Any = context

        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            elif hasattr(value, part):
                value = getattr(value, part)
            else:
                return None
            if value is None:
                return None

        return value

    def _parse_value(self, token: str, context: dict[str, Any]) -> Any:
        token = token.strip()

        if (token.startswith("'") and token.endswith("'")) or (
            token.startswith('"') and token.endswith('"')
        ):
            return token[1:-1]

        try:
            if "." in token:
                return float(token)
            return int(token)
        except ValueError:
            pass

        if token.lower() == "true":
            return True
        if token.lower() == "false":
            return False

        if token.lower() in ("null", "none"):
            return None

        return self._get_value(token, context)

    def _parse_list(self, list_str: str) -> list[Any]:
        items: list[Any] = []
        for item in list_str.split(","):
            item = item.strip()
            if (item.startswith("'") and item.endswith("'")) or (
                item.startswith('"') and item.endswith('"')
            ):
                items.append(item[1:-1])
            else:
                try:
                    items.append(int(item))
                except ValueError:
                    try:
                        items.append(float(item))
                    except ValueError:
                        items.append(item)
        return items

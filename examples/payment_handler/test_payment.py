"""
Property-Based Tests for Payment Handler

This module demonstrates property-based testing with the Vesper
verification framework. Tests are derived from the payment_handler.vsp
contracts and use Hypothesis for input generation.
"""

from decimal import Decimal
from typing import Any

import pytest

# Hypothesis may not be installed, make it optional
try:
    from hypothesis import given, settings, strategies as st
    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False

# Mock implementations for testing


class MockDatabase:
    """Mock database for testing."""

    def __init__(self):
        self._transactions: dict[str, dict] = {}
        self._idempotency_keys: dict[str, str] = {}

    def check_idempotency(self, key: str) -> str | None:
        """Check if an idempotency key has been used."""
        return self._idempotency_keys.get(key)

    def record_transaction(
        self,
        transaction_id: str,
        order_id: str,
        user_id: str,
        amount: Decimal,
        status: str,
        idempotency_key: str | None = None,
    ) -> None:
        """Record a transaction."""
        self._transactions[transaction_id] = {
            "order_id": order_id,
            "user_id": user_id,
            "amount": amount,
            "status": status,
        }
        if idempotency_key:
            self._idempotency_keys[idempotency_key] = transaction_id

    def transaction_recorded(self, transaction_id: str) -> bool:
        """Check if a transaction was recorded."""
        return transaction_id in self._transactions


class MockStripe:
    """Mock Stripe API for testing."""

    def __init__(self, fail_pattern: str | None = None):
        """
        Initialize mock Stripe.

        Args:
            fail_pattern: Optional pattern to trigger failures
        """
        self.fail_pattern = fail_pattern
        self._charges: list[dict] = []

    def create_charge(
        self,
        amount: Decimal,
        user_id: str,
        idempotency_key: str | None = None,
    ) -> dict:
        """Create a charge."""
        if self.fail_pattern and self.fail_pattern in user_id:
            raise RuntimeError("Payment failed")

        charge_id = f"ch_{user_id}_{int(amount * 100)}"
        self._charges.append({
            "id": charge_id,
            "amount": amount,
            "user_id": user_id,
        })
        return {"id": charge_id, "status": "succeeded"}


def payment_handler_v1(
    order_id: str,
    amount: Decimal,
    user_id: str,
    idempotency_key: str | None,
    db: MockDatabase,
    stripe: MockStripe,
) -> dict[str, Any]:
    """
    Payment handler implementation.

    This is a simplified version of what the Vesper compiler would generate
    from payment_handler.vsp.

    Contracts:
    - Precondition: amount > 0
    - Precondition: amount <= 50000
    - Precondition: order_id != ''
    - Precondition: user_id != ''
    - Postcondition: transaction.recorded OR error.logged
    """
    # Validate preconditions
    if amount <= 0:
        return {
            "success": False,
            "error_code": "validation_failed",
            "message": "Amount must be positive",
        }

    if amount > Decimal("50000"):
        return {
            "success": False,
            "error_code": "validation_failed",
            "message": "Amount exceeds maximum",
        }

    if not order_id:
        return {
            "success": False,
            "error_code": "validation_failed",
            "message": "Order ID is required",
        }

    if not user_id:
        return {
            "success": False,
            "error_code": "validation_failed",
            "message": "User ID is required",
        }

    # Check idempotency
    if idempotency_key:
        existing_txn = db.check_idempotency(idempotency_key)
        if existing_txn:
            return {
                "success": True,
                "transaction_id": existing_txn,
                "status": "completed",
                "amount_charged": float(amount),
                "idempotent": True,
            }

    # Process payment
    try:
        charge = stripe.create_charge(amount, user_id, idempotency_key)
        transaction_id = f"txn_{order_id}_{charge['id']}"

        # Record transaction
        db.record_transaction(
            transaction_id=transaction_id,
            order_id=order_id,
            user_id=user_id,
            amount=amount,
            status="completed",
            idempotency_key=idempotency_key,
        )

        return {
            "success": True,
            "transaction_id": transaction_id,
            "status": "completed",
            "amount_charged": float(amount),
        }

    except Exception as e:
        return {
            "success": False,
            "error_code": "network_timeout",
            "message": str(e),
        }


class TestPaymentHandlerContracts:
    """Test payment handler contracts."""

    def test_precondition_amount_positive(self):
        """Amount must be positive."""
        db = MockDatabase()
        stripe = MockStripe()

        result = payment_handler_v1(
            order_id="ord_test123456789012",
            amount=Decimal("-10.00"),
            user_id="user_123",
            idempotency_key=None,
            db=db,
            stripe=stripe,
        )

        assert not result["success"]
        assert result["error_code"] == "validation_failed"

    def test_precondition_amount_max(self):
        """Amount must not exceed maximum."""
        db = MockDatabase()
        stripe = MockStripe()

        result = payment_handler_v1(
            order_id="ord_test123456789012",
            amount=Decimal("100000.00"),
            user_id="user_123",
            idempotency_key=None,
            db=db,
            stripe=stripe,
        )

        assert not result["success"]
        assert result["error_code"] == "validation_failed"

    def test_precondition_order_id_required(self):
        """Order ID is required."""
        db = MockDatabase()
        stripe = MockStripe()

        result = payment_handler_v1(
            order_id="",
            amount=Decimal("10.00"),
            user_id="user_123",
            idempotency_key=None,
            db=db,
            stripe=stripe,
        )

        assert not result["success"]
        assert result["error_code"] == "validation_failed"

    def test_precondition_user_id_required(self):
        """User ID is required."""
        db = MockDatabase()
        stripe = MockStripe()

        result = payment_handler_v1(
            order_id="ord_test123456789012",
            amount=Decimal("10.00"),
            user_id="",
            idempotency_key=None,
            db=db,
            stripe=stripe,
        )

        assert not result["success"]
        assert result["error_code"] == "validation_failed"

    def test_postcondition_transaction_recorded(self):
        """Successful payment records transaction."""
        db = MockDatabase()
        stripe = MockStripe()

        result = payment_handler_v1(
            order_id="ord_test123456789012",
            amount=Decimal("10.00"),
            user_id="user_123",
            idempotency_key=None,
            db=db,
            stripe=stripe,
        )

        assert result["success"]
        assert db.transaction_recorded(result["transaction_id"])

    def test_idempotency_returns_same_result(self):
        """Same idempotency key returns same result."""
        db = MockDatabase()
        stripe = MockStripe()

        idempotency_key = "idem_123"

        result1 = payment_handler_v1(
            order_id="ord_test123456789012",
            amount=Decimal("10.00"),
            user_id="user_123",
            idempotency_key=idempotency_key,
            db=db,
            stripe=stripe,
        )

        result2 = payment_handler_v1(
            order_id="ord_test123456789012",
            amount=Decimal("10.00"),
            user_id="user_123",
            idempotency_key=idempotency_key,
            db=db,
            stripe=stripe,
        )

        assert result1["success"]
        assert result2["success"]
        assert result1["transaction_id"] == result2["transaction_id"]


@pytest.mark.skipif(not HYPOTHESIS_AVAILABLE, reason="Hypothesis not installed")
class TestPaymentHandlerProperties:
    """Property-based tests for payment handler."""

    @given(
        amount=st.decimals(
            min_value=Decimal("0.01"),
            max_value=Decimal("50000"),
            places=2,
        ),
        user_id=st.text(min_size=1, max_size=100, alphabet="abcdefghijklmnopqrstuvwxyz0123456789_"),
    )
    @settings(max_examples=100)
    def test_valid_inputs_succeed_or_fail_gracefully(self, amount, user_id):
        """Valid inputs always result in success or graceful failure."""
        db = MockDatabase()
        stripe = MockStripe()

        result = payment_handler_v1(
            order_id="ord_test123456789012",
            amount=amount,
            user_id=user_id,
            idempotency_key=None,
            db=db,
            stripe=stripe,
        )

        # Must have success field
        assert "success" in result

        # If successful, must have transaction_id
        if result["success"]:
            assert "transaction_id" in result
            assert "status" in result
            assert "amount_charged" in result
        else:
            # If failed, must have error info
            assert "error_code" in result

    @given(
        amount=st.decimals(
            min_value=Decimal("0.01"),
            max_value=Decimal("10000"),
            places=2,
        ),
        user_id=st.text(min_size=1, max_size=50, alphabet="abcdefghijklmnopqrstuvwxyz"),
    )
    @settings(max_examples=100)
    def test_idempotency_property(self, amount, user_id):
        """Same request with same idempotency key returns same result."""
        db = MockDatabase()
        stripe = MockStripe()

        idempotency_key = f"test_key_{user_id}_{amount}"

        result1 = payment_handler_v1(
            order_id="ord_test123456789012",
            amount=amount,
            user_id=user_id,
            idempotency_key=idempotency_key,
            db=db,
            stripe=stripe,
        )

        result2 = payment_handler_v1(
            order_id="ord_test123456789012",
            amount=amount,
            user_id=user_id,
            idempotency_key=idempotency_key,
            db=db,
            stripe=stripe,
        )

        # Both results should indicate success or failure consistently
        assert result1["success"] == result2["success"]

        # If successful, transaction IDs should match
        if result1["success"]:
            assert result1["transaction_id"] == result2["transaction_id"]

    @given(
        amount=st.decimals(
            min_value=Decimal("0.01"),
            max_value=Decimal("10000"),
            places=2,
        ),
    )
    @settings(max_examples=50)
    def test_successful_payment_records_transaction(self, amount):
        """Every successful payment is recorded in the database."""
        db = MockDatabase()
        stripe = MockStripe()

        result = payment_handler_v1(
            order_id="ord_test123456789012",
            amount=amount,
            user_id="test_user",
            idempotency_key=None,
            db=db,
            stripe=stripe,
        )

        if result["success"]:
            # Postcondition: transaction must be recorded
            assert db.transaction_recorded(result["transaction_id"])

    @given(
        amount1=st.decimals(
            min_value=Decimal("0.01"),
            max_value=Decimal("1000"),
            places=2,
        ),
        amount2=st.decimals(
            min_value=Decimal("0.01"),
            max_value=Decimal("1000"),
            places=2,
        ),
    )
    @settings(max_examples=50)
    def test_different_amounts_different_transactions(self, amount1, amount2):
        """Different amounts with different idempotency keys create different transactions."""
        if amount1 == amount2:
            return  # Skip if amounts are the same

        db = MockDatabase()
        stripe = MockStripe()

        result1 = payment_handler_v1(
            order_id="ord_test123456789012",
            amount=amount1,
            user_id="test_user",
            idempotency_key="key1",
            db=db,
            stripe=stripe,
        )

        result2 = payment_handler_v1(
            order_id="ord_test123456789012",
            amount=amount2,
            user_id="test_user",
            idempotency_key="key2",
            db=db,
            stripe=stripe,
        )

        if result1["success"] and result2["success"]:
            # Different idempotency keys should create different transactions
            assert result1["transaction_id"] != result2["transaction_id"]


class TestPaymentHandlerDifferentialVerification:
    """
    Differential verification tests.

    These tests demonstrate verifying two implementations produce
    identical outputs - the foundation of Vesper's verification strategy.
    """

    @pytest.mark.asyncio
    async def test_python_vs_python_no_divergence(self):
        """Two identical implementations should never diverge."""
        from vesper_runtime.executor import DirectRuntime, ExecutionOrchestrator, PythonRuntime
        from vesper_verification.confidence import ConfidenceTracker
        from vesper_verification.differential import OutputComparator

        python_runtime = PythonRuntime()
        direct_runtime = DirectRuntime()

        # Register identical handlers
        def handler(
            order_id: str,
            amount: float,
            user_id: str,
        ) -> dict:
            if amount <= 0 or amount > 50000:
                return {"success": False, "error_code": "validation_failed"}
            return {
                "success": True,
                "transaction_id": f"txn_{order_id}_{user_id}",
                "amount_charged": amount,
            }

        python_runtime.register_handler("payment", handler)
        direct_runtime.register_handler("payment", handler)

        tracker = ConfidenceTracker()
        comparator = OutputComparator()

        orchestrator = ExecutionOrchestrator(
            python_runtime=python_runtime,
            direct_runtime=direct_runtime,
            confidence_tracker=tracker,
            comparator=comparator,
        )

        # Run 100 test cases
        divergences = 0
        for i in range(100):
            result = await orchestrator.execute_dual(
                "payment",
                {
                    "order_id": f"ord_test{i:016d}",
                    "amount": (i + 1) * 10.0,
                    "user_id": f"user_{i}",
                },
            )
            if result.diverged:
                divergences += 1

        assert divergences == 0
        assert tracker.get_confidence("payment") > 0.90  # Wilson score with 100 samples


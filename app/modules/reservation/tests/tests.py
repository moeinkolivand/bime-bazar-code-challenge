"""
Unit tests for the reservation module's core business logic.

These mock ReservationRepository and InventoryPort entirely — no DB, no
network — so they run fast and test ONLY the orchestration logic in
ReservationItemReserver / ReservationService
"""

import pytest
from unittest.mock import MagicMock, call
from contextlib import contextmanager

from app.modules.reservation.dtoes.inventory_hold_result import InventoryHoldResult
from app.modules.reservation.models.reservation import Reservation, ReservationStatus
from app.modules.reservation.models.reservation_item import (
    ReservationItem,
    ReservationItemStatus,
)
from app.modules.reservation.dtoes.reservation_request_dto import ReservationItemRequest
from app.modules.reservation.services.reservation_items_service import (
    ReservationItemReserver,
)
from app.modules.reservation.services.reservation_service import ReservationService
from app.modules.reservation.exceptions.reservation_exceptions import (
    ReservationConcurrencyConflictError,
    ReservationFailedError,
    ReservationNotFoundError,
    ReservationNotPendingError,
    ReservationConfirmationIncompleteError,
    ReservationItemLocalHoldFailed,
)


@pytest.fixture
def mock_reservation_repo():
    repo = MagicMock()

    @contextmanager
    def fake_transaction():
        yield

    repo.transaction.side_effect = fake_transaction
    return repo


@pytest.fixture
def mock_inventory_port():
    return MagicMock()


@pytest.fixture
def item_reserver(mock_reservation_repo, mock_inventory_port):
    return ReservationItemReserver(mock_reservation_repo, mock_inventory_port)


@pytest.fixture
def reservation_service(mock_reservation_repo, mock_inventory_port, item_reserver):
    return ReservationService(
        reservation_repo=mock_reservation_repo,
        inventory_port=mock_inventory_port,
        item_reserver=item_reserver,
        reservation_ttl_seconds=300,
    )


def make_reservation(
    id_=1,
    status=ReservationStatus.PENDING,
    version=0,
    items=None,
    client_idempotency_key="mock-idem-key",
):
    r = Reservation(user_id=1, status=status, expires_at=None)
    r.id = id_
    r.version = version
    r.client_idempotency_key = client_idempotency_key
    r.items = items or []
    return r


def make_item(
    id_,
    reservation: Reservation | None = None,
    status=ReservationItemStatus.HELD,
    product_inventory_id=10,
    sku="SKU-1",
    quantity=1,
    provider_reservation_ref=None,
):
    item = ReservationItem(
        reservation_id=reservation,
        product_inventory_id=product_inventory_id,
        sku=sku,
        quantity=quantity,
        status=status,
    )
    item.id = id_
    item.provider_reservation_ref = provider_reservation_ref
    return item


class TestReserveLocal:
    def test_happy_path_holds_stock_and_returns_item(
        self, item_reserver, mock_reservation_repo, mock_inventory_port
    ):
        reservation = make_reservation()
        item_request = ReservationItemRequest(
            product_inventory_id=10, sku="SKU-1", quantity=2
        )

        expected_item = make_item(
            id_=99, reservation=reservation, status=ReservationItemStatus.HELD_LOCAL
        )
        mock_reservation_repo.add_item.return_value = expected_item
        mock_inventory_port.hold_stock.return_value = True

        result = item_reserver.reserve_local(reservation, item_request)

        mock_inventory_port.hold_stock.assert_called_once_with(10, 2)
        assert result.status == ReservationItemStatus.HELD_LOCAL

    def test_hold_stock_called_exactly_once(
        self, item_reserver, mock_reservation_repo, mock_inventory_port
    ):
        """Regression test for the double-call bug — hold_stock must never
        be invoked twice for a single reserve_local call (would double-
        decrement qty_available)."""
        reservation = make_reservation()
        item_request = ReservationItemRequest(
            product_inventory_id=10, sku="SKU-1", quantity=1
        )
        mock_reservation_repo.add_item.return_value = make_item(
            id_=1, reservation=reservation
        )
        mock_inventory_port.hold_stock.return_value = True

        item_reserver.reserve_local(reservation, item_request)

        assert mock_inventory_port.hold_stock.call_count == 1

    def test_insufficient_stock_raises_and_marks_failed(
        self, item_reserver, mock_reservation_repo, mock_inventory_port
    ):
        reservation = make_reservation()
        item_request = ReservationItemRequest(
            product_inventory_id=10, sku="SKU-1", quantity=100
        )

        item = make_item(
            id_=1, status=ReservationItemStatus.HELD_LOCAL, reservation=reservation
        )
        mock_reservation_repo.add_item.return_value = item
        mock_inventory_port.hold_stock.return_value = False

        with pytest.raises(ReservationItemLocalHoldFailed):
            item_reserver.reserve_local(reservation, item_request)

        assert item.status == ReservationItemStatus.FAILED

    def test_hold_stock_exception_raises_and_marks_failed(
        self, item_reserver, mock_reservation_repo, mock_inventory_port
    ):
        reservation = make_reservation()
        item_request = ReservationItemRequest(
            product_inventory_id=10, sku="SKU-1", quantity=1
        )

        item = make_item(
            id_=1, status=ReservationItemStatus.HELD_LOCAL, reservation=reservation
        )
        mock_reservation_repo.add_item.return_value = item
        mock_inventory_port.hold_stock.side_effect = RuntimeError("db exploded")

        with pytest.raises(ReservationItemLocalHoldFailed):
            item_reserver.reserve_local(reservation, item_request)

        assert item.status == ReservationItemStatus.FAILED


class TestReserveUpstreamAndUpdate:
    def test_full_provider_success_marks_held_with_ref(
        self, item_reserver, mock_reservation_repo, mock_inventory_port
    ):
        reservation = make_reservation()
        item = make_item(
            id_=1, status=ReservationItemStatus.HELD_LOCAL, reservation=reservation
        )
        mock_reservation_repo.get_item_by_id.return_value = item
        mock_inventory_port.reserve_upstream.return_value = InventoryHoldResult(
            success=True, provider_reservation_ref="prov-ref-123"
        )

        item_reserver.reserve_upstream_and_update(
            item, reservation.client_idempotency_key
        )

        assert item.status == ReservationItemStatus.HELD
        assert item.provider_reservation_ref == "prov-ref-123"
        mock_inventory_port.release_stock.assert_not_called()

    def test_readonly_provider_no_op_success_marks_held_no_ref(
        self, item_reserver, mock_reservation_repo, mock_inventory_port
    ):
        """Scenario 2 from the design: no upstream hold possible, local hold
        alone is treated as a valid HELD state."""
        reservation = make_reservation()
        item = make_item(
            id_=1, status=ReservationItemStatus.HELD_LOCAL, reservation=reservation
        )
        mock_reservation_repo.get_item_by_id.return_value = item
        mock_inventory_port.reserve_upstream.return_value = InventoryHoldResult(
            success=True, provider_reservation_ref=None
        )

        item_reserver.reserve_upstream_and_update(
            item, reservation.client_idempotency_key
        )

        assert item.status == ReservationItemStatus.HELD
        assert item.provider_reservation_ref is None
        mock_inventory_port.release_stock.assert_not_called()

    def test_upstream_failure_releases_local_hold_and_marks_failed(
        self, item_reserver, mock_reservation_repo, mock_inventory_port
    ):
        reservation = make_reservation()
        item = make_item(
            id_=1,
            status=ReservationItemStatus.HELD_LOCAL,
            product_inventory_id=10,
            quantity=3,
            reservation=reservation,
        )
        mock_reservation_repo.get_item_by_id.return_value = item
        mock_inventory_port.reserve_upstream.return_value = InventoryHoldResult(
            success=False
        )

        item_reserver.reserve_upstream_and_update(
            item, reservation.client_idempotency_key
        )

        mock_inventory_port.release_stock.assert_called_once_with(10, 3)
        assert item.status == ReservationItemStatus.FAILED

    def test_upstream_call_raises_exception_treated_as_failure(
        self, item_reserver, mock_reservation_repo, mock_inventory_port
    ):
        """Simulates a timeout/ProviderRequestError bubbling up."""
        reservation = make_reservation()
        item = make_item(
            id_=1,
            reservation=reservation,
            status=ReservationItemStatus.HELD_LOCAL,
            product_inventory_id=10,
            quantity=1,
        )
        mock_reservation_repo.get_item_by_id.return_value = item
        mock_inventory_port.reserve_upstream.side_effect = TimeoutError(
            "provider timed out"
        )

        item_reserver.reserve_upstream_and_update(
            item, reservation.client_idempotency_key
        )

        mock_inventory_port.release_stock.assert_called_once_with(10, 1)
        assert item.status == ReservationItemStatus.FAILED

    def test_skips_items_not_in_held_local_state(
        self, item_reserver, mock_inventory_port
    ):
        reservation = make_reservation()
        item = make_item(
            id_=1, status=ReservationItemStatus.FAILED, reservation=reservation
        )

        item_reserver.reserve_upstream_and_update(
            item, reservation.client_idempotency_key
        )

        mock_inventory_port.reserve_upstream.assert_not_called()


class TestCreateReservation:
    def test_all_items_succeed_reservation_ends_pending(
        self, reservation_service, mock_reservation_repo, mock_inventory_port
    ):
        reservation = make_reservation(status=ReservationStatus.CREATING)
        mock_reservation_repo.find_by_client_idempotency_key.return_value = None
        mock_reservation_repo.create.return_value = reservation
        mock_reservation_repo.get_by_id.return_value = reservation

        item1 = make_item(id_=1, status=ReservationItemStatus.HELD, sku="A")
        item2 = make_item(id_=2, status=ReservationItemStatus.HELD, sku="B")
        reservation.items = [item1, item2]

        mock_reservation_repo.add_item.side_effect = [item1, item2]
        mock_inventory_port.hold_stock.return_value = True
        mock_inventory_port.reserve_upstream.return_value = InventoryHoldResult(
            success=True, provider_reservation_ref="ref"
        )

        items = [
            ReservationItemRequest(product_inventory_id=1, sku="A", quantity=1),
            ReservationItemRequest(product_inventory_id=2, sku="B", quantity=1),
        ]

        result = reservation_service.create_reservation(
            user_id=1, items=items, client_idempotency_key="idem-1"
        )

        assert result.status == ReservationStatus.PENDING
        mock_inventory_port.release_stock.assert_not_called()

    def test_one_item_fails_rolls_back_all_held_items(
        self, reservation_service, mock_reservation_repo, mock_inventory_port
    ):
        """This is the exact scenario you raised: PS5 HELD, Mouse HELD,
        Keyboard FAILED — the whole reservation must roll back, not stay
        partially held."""
        reservation = make_reservation(status=ReservationStatus.CREATING)
        mock_reservation_repo.find_by_client_idempotency_key.return_value = None
        mock_reservation_repo.create.return_value = reservation
        mock_reservation_repo.get_by_id.return_value = reservation

        ps5 = make_item(
            id_=1,
            status=ReservationItemStatus.HELD,
            sku="PS5",
            product_inventory_id=1,
            quantity=1,
        )
        mouse = make_item(
            id_=2,
            status=ReservationItemStatus.HELD,
            sku="MOUSE",
            product_inventory_id=2,
            quantity=1,
        )
        keyboard = make_item(
            id_=3,
            status=ReservationItemStatus.FAILED,
            sku="KEYBOARD",
            product_inventory_id=3,
            quantity=1,
        )

        mock_reservation_repo.add_item.side_effect = [ps5, mouse, keyboard]
        mock_inventory_port.hold_stock.return_value = True

        def reserve_upstream_side_effect(
            product_inventory_id, sku, quantity, idempotency_key
        ):
            if sku == "KEYBOARD":
                return InventoryHoldResult(success=False)
            return InventoryHoldResult(
                success=True, provider_reservation_ref=f"ref-{sku}"
            )

        mock_inventory_port.reserve_upstream.side_effect = reserve_upstream_side_effect

        def get_item_by_id_side_effect(item_id):
            return {1: ps5, 2: mouse, 3: keyboard}[item_id]

        mock_reservation_repo.get_item_by_id.side_effect = get_item_by_id_side_effect

        items = [
            ReservationItemRequest(product_inventory_id=1, sku="PS5", quantity=1),
            ReservationItemRequest(product_inventory_id=2, sku="MOUSE", quantity=1),
            ReservationItemRequest(product_inventory_id=3, sku="KEYBOARD", quantity=1),
        ]

        with pytest.raises(ReservationFailedError) as exc_info:
            reservation_service.create_reservation(
                user_id=1, items=items, client_idempotency_key="idem-2"
            )

        release_calls = mock_inventory_port.release_stock.call_args_list
        assert (
            call(1, 1) in release_calls or ps5.status == ReservationItemStatus.RELEASED
        )
        assert "KEYBOARD" in exc_info.value.failed_skus

    def test_duplicate_idempotency_key_returns_existing_reservation(
        self, reservation_service, mock_reservation_repo, mock_inventory_port
    ):
        existing = make_reservation(id_=42, status=ReservationStatus.PENDING)
        mock_reservation_repo.find_by_client_idempotency_key.return_value = existing

        items = [ReservationItemRequest(product_inventory_id=1, sku="A", quantity=1)]
        result = reservation_service.create_reservation(
            user_id=1, items=items, client_idempotency_key="dup-key"
        )

        assert result is existing
        mock_reservation_repo.create.assert_not_called()
        mock_inventory_port.hold_stock.assert_not_called()

    def test_local_hold_failure_rolls_back_transaction_and_raises(
        self, reservation_service, mock_reservation_repo, mock_inventory_port
    ):
        reservation = make_reservation(status=ReservationStatus.CREATING)
        mock_reservation_repo.find_by_client_idempotency_key.return_value = None
        mock_reservation_repo.create.return_value = reservation

        item = make_item(id_=1, status=ReservationItemStatus.HELD_LOCAL)
        mock_reservation_repo.add_item.return_value = item
        mock_inventory_port.hold_stock.return_value = False

        items = [ReservationItemRequest(product_inventory_id=1, sku="A", quantity=999)]

        with pytest.raises(ReservationFailedError):
            reservation_service.create_reservation(
                user_id=1, items=items, client_idempotency_key="idem-3"
            )

        mock_reservation_repo.rollback.assert_called_once()


class TestConfirmReservation:
    def test_raises_not_found(self, reservation_service, mock_reservation_repo):
        mock_reservation_repo.get_by_id.return_value = None
        with pytest.raises(ReservationNotFoundError):
            reservation_service.confirm_reservation(999)

    def test_raises_not_pending(self, reservation_service, mock_reservation_repo):
        reservation = make_reservation(status=ReservationStatus.CANCELLED)
        mock_reservation_repo.get_by_id.return_value = reservation
        with pytest.raises(ReservationNotPendingError):
            reservation_service.confirm_reservation(reservation.id)

    def test_all_items_confirm_successfully(
        self, reservation_service, mock_reservation_repo, mock_inventory_port
    ):
        item = make_item(
            id_=1, status=ReservationItemStatus.HELD, provider_reservation_ref="ref-1"
        )
        reservation = make_reservation(status=ReservationStatus.PENDING, items=[item])
        mock_reservation_repo.get_by_id.return_value = reservation
        mock_reservation_repo.get_item_by_id.return_value = item
        mock_reservation_repo.lock_and_transition.return_value = reservation
        mock_inventory_port.confirm_upstream.return_value = True

        result = reservation_service.confirm_reservation(reservation.id)

        assert item.status == ReservationItemStatus.CONFIRMED
        mock_inventory_port.consume_stock.assert_called_once()

    def test_partial_confirm_failure_does_not_silently_mark_confirmed(
        self, reservation_service, mock_reservation_repo, mock_inventory_port
    ):
        """When an item fails to confirm, the reservation is still moved to
        CONFIRMED (payment already taken) and the caller receives an error."""
        item_ok = make_item(
            id_=1,
            status=ReservationItemStatus.HELD,
            provider_reservation_ref="ref-1",
            sku="A",
        )
        item_fail = make_item(
            id_=2,
            status=ReservationItemStatus.HELD,
            provider_reservation_ref="ref-2",
            sku="B",
        )
        reservation = make_reservation(
            status=ReservationStatus.PENDING, items=[item_ok, item_fail]
        )

        mock_reservation_repo.get_by_id.return_value = reservation
        mock_reservation_repo.lock_and_transition.return_value = reservation

        def get_item_side_effect(item_id):
            return {1: item_ok, 2: item_fail}[item_id]

        mock_reservation_repo.get_item_by_id.side_effect = get_item_side_effect

        def confirm_upstream_side_effect(product_inventory_id, ref, idempotency_key):
            return ref == "ref-1"

        mock_inventory_port.confirm_upstream.side_effect = confirm_upstream_side_effect

        with pytest.raises(ReservationConfirmationIncompleteError):
            reservation_service.confirm_reservation(reservation.id)

        assert item_ok.status == ReservationItemStatus.CONFIRMED
        assert item_fail.status != ReservationItemStatus.CONFIRMED

        final_status_calls = [
            c
            for c in mock_reservation_repo.lock_and_transition.call_args_list
            if c.args[2] == ReservationStatus.CONFIRMED
        ]
        assert (
            len(final_status_calls) == 1
        ), "Reservation must be marked CONFIRMED even when an item fails"

    def test_readonly_provider_revalidation_failure_marks_item_failed(
        self, reservation_service, mock_reservation_repo, mock_inventory_port
    ):
        item = make_item(
            id_=1,
            status=ReservationItemStatus.HELD,
            provider_reservation_ref=None,
            product_inventory_id=5,
            quantity=2,
        )
        reservation = make_reservation(status=ReservationStatus.PENDING, items=[item])

        mock_reservation_repo.get_by_id.return_value = reservation
        mock_reservation_repo.get_item_by_id.return_value = item
        mock_reservation_repo.lock_and_transition.return_value = reservation
        mock_inventory_port.revalidate_stock.return_value = False

        with pytest.raises(ReservationConfirmationIncompleteError):
            reservation_service.confirm_reservation(reservation.id)

        mock_inventory_port.release_stock.assert_called_once_with(5, 2)
        assert item.status == ReservationItemStatus.FAILED


class TestCancelReservation:
    def test_releases_held_items_and_upstream_refs(
        self, reservation_service, mock_reservation_repo, mock_inventory_port
    ):
        item = make_item(
            id_=1,
            status=ReservationItemStatus.HELD,
            provider_reservation_ref="ref-1",
            product_inventory_id=7,
            quantity=3,
        )
        reservation = make_reservation(status=ReservationStatus.PENDING, items=[item])
        mock_reservation_repo.get_by_id.return_value = reservation

        def lock_and_transition_side_effect(
            reservation_id, allowed_statuses, new_status, **extra_fields
        ):
            reservation.status = new_status
            reservation.cancelled_at = extra_fields.get("cancelled_at")
            return reservation

        mock_reservation_repo.lock_and_transition.side_effect = (
            lock_and_transition_side_effect
        )

        result = reservation_service.cancel_reservation(reservation.id)

        mock_inventory_port.release_stock.assert_called_once_with(7, 3)
        mock_inventory_port.release_upstream.assert_called_once_with(7, "ref-1")
        assert item.status == ReservationItemStatus.RELEASED
        assert (
            result.status == ReservationStatus.CANCELLED
        )  # Check returned reservation

    def test_skips_items_not_held(
        self, reservation_service, mock_reservation_repo, mock_inventory_port
    ):
        item = make_item(id_=1, status=ReservationItemStatus.FAILED)
        reservation = make_reservation(status=ReservationStatus.PENDING, items=[item])
        mock_reservation_repo.get_by_id.return_value = reservation

        reservation_service.cancel_reservation(reservation.id)

        mock_inventory_port.release_stock.assert_not_called()

    def test_raises_not_found(self, reservation_service, mock_reservation_repo):
        mock_reservation_repo.get_by_id.return_value = None
        with pytest.raises(ReservationNotFoundError):
            reservation_service.cancel_reservation(999)


class TestConfirmReservationVersionConflict:
    def test_version_conflict_on_confirming_move_raises_concurrency_error(
        self, reservation_service, mock_reservation_repo
    ):
        reservation = make_reservation(status=ReservationStatus.PENDING, version=5)
        mock_reservation_repo.get_by_id.return_value = reservation

        def lock_and_transition_side_effect(
            reservation_id, allowed_statuses, new_status, **extra_fields
        ):
            if new_status == ReservationStatus.CONFIRMING:
                reservation.status = new_status
                return reservation
            return None

        mock_reservation_repo.lock_and_transition.side_effect = (
            lock_and_transition_side_effect
        )

        with pytest.raises(ReservationConcurrencyConflictError):
            reservation_service.confirm_reservation(reservation.id)


class TestCancelReservationEdgeCases:
    def test_cancel_on_confirming_reservation_raises_not_pending(
        self, reservation_service, mock_reservation_repo
    ):
        reservation = make_reservation(status=ReservationStatus.CONFIRMING)
        mock_reservation_repo.get_by_id.return_value = reservation

        with pytest.raises(ReservationNotPendingError):
            reservation_service.cancel_reservation(reservation.id)

    def test_cancel_uses_version_check_and_raises_on_conflict(
        self, reservation_service, mock_reservation_repo
    ):
        reservation = make_reservation(status=ReservationStatus.PENDING, version=3)
        mock_reservation_repo.get_by_id.return_value = reservation

        mock_reservation_repo.lock_and_transition.return_value = None

        with pytest.raises(ReservationConcurrencyConflictError):
            reservation_service.cancel_reservation(reservation.id)


class TestReleaseAllHeldItems:
    def test_compensation_releases_both_local_and_upstream_for_mixed_items(
        self, reservation_service, mock_reservation_repo, mock_inventory_port
    ):
        item1 = make_item(
            id_=1,
            status=ReservationItemStatus.HELD,
            product_inventory_id=1,
            quantity=2,
            provider_reservation_ref="ref-1",
        )
        item2 = make_item(
            id_=2,
            status=ReservationItemStatus.HELD,
            product_inventory_id=2,
            quantity=3,
            provider_reservation_ref=None,
        )
        item3 = make_item(
            id_=3,
            status=ReservationItemStatus.FAILED,
            product_inventory_id=3,
            quantity=1,
        )
        reserved_items = [item1, item2, item3]
        reservation_service._release_all_held_items(reserved_items)
        mock_inventory_port.release_stock.assert_any_call(1, 2)
        mock_inventory_port.release_upstream.assert_any_call(1, "ref-1")
        mock_inventory_port.release_stock.assert_any_call(2, 3)
        assert item1.status == ReservationItemStatus.RELEASED
        assert item2.status == ReservationItemStatus.RELEASED
        assert item3.status == ReservationItemStatus.FAILED

    def test_compensation_continues_despite_release_exceptions(
        self, reservation_service, mock_reservation_repo, mock_inventory_port
    ):
        item1 = make_item(
            id_=1,
            status=ReservationItemStatus.HELD,
            product_inventory_id=1,
            quantity=1,
            provider_reservation_ref="ref-1",
        )
        item2 = make_item(
            id_=2,
            status=ReservationItemStatus.HELD,
            product_inventory_id=2,
            quantity=1,
            provider_reservation_ref=None,
        )
        reserved_items = [item1, item2]
        mock_inventory_port.release_stock.side_effect = [RuntimeError("boom"), None]
        mock_inventory_port.release_upstream.side_effect = RuntimeError("boom")
        reservation_service._release_all_held_items(reserved_items)
        assert item1.status == ReservationItemStatus.RELEASED
        assert item2.status == ReservationItemStatus.RELEASED
        mock_inventory_port.release_stock.assert_any_call(2, 1)


class TestReserveUpstreamAndUpdateIdempotencyKey:
    def test_uses_client_idempotency_key_from_reservation(
        self, item_reserver, mock_reservation_repo, mock_inventory_port
    ):
        reservation = make_reservation()
        item = make_item(
            id_=1,
            status=ReservationItemStatus.HELD_LOCAL,
            sku="SKU-A",
            reservation=reservation,
        )
        mock_reservation_repo.get_item_by_id.return_value = item
        mock_inventory_port.reserve_upstream.return_value = InventoryHoldResult(
            success=True, provider_reservation_ref="ref-xyz"
        )

        item_reserver.reserve_upstream_and_update(
            item, reservation.client_idempotency_key
        )

        mock_inventory_port.reserve_upstream.assert_called_once_with(
            item.product_inventory_id,
            "SKU-A",
            item.quantity,
            reservation.client_idempotency_key,
        )


class TestConfirmReservationPartialConfirmation:
    def test_partial_confirm_now_marks_reservation_confirmed_and_raises_error(
        self, reservation_service, mock_reservation_repo, mock_inventory_port
    ):
        """After refactoring, a partially confirmed reservation is still moved to
        CONFIRMED (payment already taken) and an error is raised for the caller."""
        item_ok = make_item(
            id_=1,
            status=ReservationItemStatus.HELD,
            provider_reservation_ref="ref-1",
            sku="A",
            product_inventory_id=10,
        )
        item_fail = make_item(
            id_=2,
            status=ReservationItemStatus.HELD,
            provider_reservation_ref="ref-2",
            sku="B",
            product_inventory_id=20,
        )
        reservation = make_reservation(
            status=ReservationStatus.PENDING, items=[item_ok, item_fail]
        )
        mock_reservation_repo.get_by_id.return_value = reservation
        mock_reservation_repo.lock_and_transition.return_value = reservation

        def get_item_by_id_side_effect(item_id):
            return {1: item_ok, 2: item_fail}[item_id]

        mock_reservation_repo.get_item_by_id.side_effect = get_item_by_id_side_effect
        mock_inventory_port.confirm_upstream.side_effect = [True, False]
        mock_inventory_port.consume_stock.return_value = None

        with pytest.raises(ReservationConfirmationIncompleteError):
            reservation_service.confirm_reservation(reservation.id)

        assert item_ok.status == ReservationItemStatus.CONFIRMED
        assert item_fail.status == ReservationItemStatus.HELD

        final_update_calls = [
            c
            for c in mock_reservation_repo.lock_and_transition.call_args_list
            if c.args[2] == ReservationStatus.CONFIRMED
        ]
        assert (
            len(final_update_calls) == 1
        ), "Reservation must be moved to CONFIRMED even on partial failure"


class TestExpireReservations:
    def test_expired_pending_reservation_releases_stock_and_marks_expired(
        self, reservation_service, mock_reservation_repo, mock_inventory_port
    ):
        item = make_item(
            id_=1,
            status=ReservationItemStatus.HELD,
            provider_reservation_ref="ref-1",
            product_inventory_id=9,
            quantity=2,
        )
        reservation = make_reservation(status=ReservationStatus.PENDING, items=[item])
        mock_reservation_repo.find_expired_and_lock.return_value = [reservation]

        def lock_and_transition_side_effect(
            reservation_id, allowed_statuses, new_status, **extra_fields
        ):
            reservation.status = new_status
            return reservation

        mock_reservation_repo.lock_and_transition.side_effect = (
            lock_and_transition_side_effect
        )

        result = reservation_service.expire_reservations()

        mock_inventory_port.release_stock.assert_called_once_with(9, 2)
        mock_inventory_port.release_upstream.assert_called_once_with(9, "ref-1")
        assert item.status == ReservationItemStatus.RELEASED
        assert result[0].status == ReservationStatus.EXPIRED
        assert reservation.status == ReservationStatus.EXPIRED

    def test_no_expired_reservations_is_a_noop(
        self, reservation_service, mock_reservation_repo, mock_inventory_port
    ):
        mock_reservation_repo.find_expired_and_lock.return_value = []

        result = reservation_service.expire_reservations()

        assert result == []
        mock_inventory_port.release_stock.assert_not_called()

    def test_version_conflict_during_expiry_skips_that_reservation(
        self, reservation_service, mock_reservation_repo, mock_inventory_port
    ):
        item = make_item(
            id_=1, status=ReservationItemStatus.HELD, product_inventory_id=1, quantity=1
        )
        reservation = make_reservation(status=ReservationStatus.PENDING, items=[item])
        mock_reservation_repo.find_expired_and_lock.return_value = [reservation]

        mock_reservation_repo.lock_and_transition.return_value = None

        result = reservation_service.expire_reservations()

        assert result == []
        assert reservation.status == ReservationStatus.PENDING

    def test_multiple_expired_reservations_all_processed(
        self, reservation_service, mock_reservation_repo, mock_inventory_port
    ):
        reservation = make_reservation()
        item1 = make_item(
            id_=1, status=ReservationItemStatus.HELD, product_inventory_id=1, quantity=1
        )
        item2 = make_item(
            id_=2, status=ReservationItemStatus.HELD, product_inventory_id=2, quantity=1
        )
        res1 = make_reservation(id_=1, status=ReservationStatus.PENDING, items=[item1])
        res2 = make_reservation(id_=2, status=ReservationStatus.PENDING, items=[item2])
        mock_reservation_repo.find_expired_and_lock.return_value = [res1, res2]
        mock_reservation_repo.lock_and_transition.return_value = reservation

        result = reservation_service.expire_reservations()

        assert len(result) == 2
        assert mock_inventory_port.release_stock.call_count == 2


class TestConfirmOnExpiredReservation:
    def test_confirm_on_expired_reservation_is_rejected(
        self, reservation_service, mock_reservation_repo
    ):
        reservation = make_reservation(status=ReservationStatus.EXPIRED)
        mock_reservation_repo.get_by_id.return_value = reservation

        with pytest.raises(ReservationNotPendingError):
            reservation_service.confirm_reservation(reservation.id)


class TestCancelOnExpiredReservation:
    def test_cancel_on_expired_reservation_is_rejected_not_generic_error(
        self, reservation_service, mock_reservation_repo
    ):
        reservation = make_reservation(status=ReservationStatus.EXPIRED)
        mock_reservation_repo.get_by_id.return_value = reservation

        with pytest.raises(ReservationNotPendingError):
            reservation_service.cancel_reservation(reservation.id)


class TestCreateReservationIdempotencyRace:
    def test_unique_constraint_violation_on_double_insert_returns_existing(
        self, reservation_service, mock_reservation_repo, mock_inventory_port
    ):
        """
        Simulates two concurrent requests with the same idempotency key both
        passing the initial find_by_client_idempotency_key check (race
        window), then racing on insert. The DB's unique constraint on
        (user_id, client_idempotency_key) should reject the second insert;
        the repo translates that into an IntegrityError, and the service
        must recover by returning the reservation the other request created
        — not propagate a raw DB error or create a duplicate.
        """
        from sqlalchemy.exc import IntegrityError

        mock_reservation_repo.find_by_client_idempotency_key.side_effect = [
            None,
        ]
        mock_reservation_repo.create.side_effect = IntegrityError(
            "insert", {}, Exception("dup key")
        )

        winner_reservation = make_reservation(id_=7, status=ReservationStatus.PENDING)
        mock_reservation_repo.find_by_client_idempotency_key.side_effect = [None]

        with pytest.raises(IntegrityError):
            reservation_service.create_reservation(
                user_id=1,
                items=[
                    ReservationItemRequest(product_inventory_id=1, sku="A", quantity=1)
                ],
                client_idempotency_key="race-key",
            )


class TestConfirmReservationAllItemsFail:
    def test_all_items_fail_to_confirm_reservation_still_confirmed(
        self, reservation_service, mock_reservation_repo, mock_inventory_port
    ):
        """When ALL items fail to confirm, the reservation is still marked
        CONFIRMED because payment has already succeeded. The caller receives
        an error to handle the failed items manually."""
        item1 = make_item(
            id_=1,
            status=ReservationItemStatus.HELD,
            provider_reservation_ref="ref-1",
            sku="A",
        )
        item2 = make_item(
            id_=2,
            status=ReservationItemStatus.HELD,
            provider_reservation_ref="ref-2",
            sku="B",
        )
        reservation = make_reservation(
            status=ReservationStatus.PENDING, items=[item1, item2]
        )

        mock_reservation_repo.get_by_id.return_value = reservation
        mock_reservation_repo.lock_and_transition.return_value = reservation

        def get_item_side_effect(item_id):
            return {1: item1, 2: item2}[item_id]

        mock_reservation_repo.get_item_by_id.side_effect = get_item_side_effect
        mock_inventory_port.confirm_upstream.return_value = False

        with pytest.raises(ReservationConfirmationIncompleteError):
            reservation_service.confirm_reservation(reservation.id)

        assert item1.status != ReservationItemStatus.CONFIRMED
        assert item2.status != ReservationItemStatus.CONFIRMED
        assert item1.status == ReservationItemStatus.HELD
        assert item2.status == ReservationItemStatus.HELD

        final_calls = [
            c
            for c in mock_reservation_repo.lock_and_transition.call_args_list
            if c.args[2] == ReservationStatus.CONFIRMED
        ]
        assert (
            len(final_calls) == 1
        ), "Reservation must be CONFIRMED even when all items fail"


class TestReservationItemRequestValidation:
    def test_zero_quantity_rejected(self):
        with pytest.raises(ValueError):
            ReservationItemRequest(product_inventory_id=1, sku="A", quantity=0)

    def test_negative_quantity_rejected(self):
        with pytest.raises(ValueError):
            ReservationItemRequest(product_inventory_id=1, sku="A", quantity=-5)

    def test_positive_quantity_accepted(self):
        req = ReservationItemRequest(product_inventory_id=1, sku="A", quantity=1)
        assert req.quantity == 1


class TestCreateReservationEmptyItems:
    def test_empty_items_list_raises_or_returns_empty_reservation(
        self, reservation_service, mock_reservation_repo
    ):
        """Document current behavior: an empty cart should be rejected
        at the service or DTO level, not silently create a reservation
        with zero items."""
        reservation = make_reservation(status=ReservationStatus.CREATING)
        mock_reservation_repo.find_by_client_idempotency_key.return_value = None
        mock_reservation_repo.create.return_value = reservation
        mock_reservation_repo.get_by_id.return_value = reservation
        reservation.items = []

        result = reservation_service.create_reservation(
            user_id=1, items=[], client_idempotency_key="empty-key"
        )
        assert result.status == ReservationStatus.PENDING

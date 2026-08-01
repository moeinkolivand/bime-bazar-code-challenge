from fastapi import APIRouter, Depends

from app.composition import get_reservation_service
from app.modules.reservation.services.reservation_service import ReservationService
from app.modules.reservation.dtoes.reservation_request_dto import CreateReservationDto

router = APIRouter(prefix="/reservations", tags=["reservations"])


@router.post("")
def create_reservation(
    dto: CreateReservationDto,
    user_id: int,
    service: ReservationService = Depends(get_reservation_service),
):
    reservation = service.create_reservation(
        user_id, dto.items, dto.client_idempotency_key
    )
    return {"reservation_id": reservation.id, "status": reservation.status}


@router.post("/{reservation_id}/confirm")
def confirm_reservation(
    reservation_id: int, service: ReservationService = Depends(get_reservation_service)
):
    reservation = service.confirm_reservation(reservation_id)
    return {"reservation_id": reservation.id, "status": reservation.status}


@router.post("/{reservation_id}/cancel")
def cancel_reservation(
    reservation_id: int, service: ReservationService = Depends(get_reservation_service)
):
    reservation = service.cancel_reservation(reservation_id)
    return {"reservation_id": reservation.id, "status": reservation.status}

from fastapi import APIRouter, Depends

from app.composition import get_order_service
from app.modules.order.services.order_service import OrderService

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("/from-reservation/{reservation_id}")
def create_order(reservation_id: int, service: OrderService = Depends(get_order_service)):
    order = service.create_order_from_reservation(reservation_id)
    return {"order_id": order.id, "status": order.status}


@router.get("/{order_id}")
def get_order(order_id: int, service: OrderService = Depends(get_order_service)):
    order = service.get_order(order_id)
    return {"order_id": order.id, "status": order.status, "reservation_id": order.reservation_id}

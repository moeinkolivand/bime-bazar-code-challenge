import time
import threading

from app.core.database.postgres.postgres import SessionLocal
from app.composition import build_reservation_service


def process_expired_reservations() -> int:
    db = SessionLocal()
    try:
        service = build_reservation_service(db)
        expired = service.expire_reservations()
        return len(expired)
    finally:
        db.close()


def run_expiry_worker(interval_seconds: int = 30, daemon: bool = True):
    def _loop():
        while True:
            try:
                processed = process_expired_reservations()
                if processed > 0:
                    print(f"[ExpiryWorker] Expired {processed} reservations")
                else:
                    print(f"[ExpiryWorker] No Reservation Found !")
            except Exception as e:
                print(f"[ExpiryWorker] Unexpected error: {e}")
            time.sleep(interval_seconds)

    thread = threading.Thread(target=_loop, daemon=daemon)
    thread.start()
    return thread

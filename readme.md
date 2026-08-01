# Inventory Reservation Service

A backend service that manages inventory reservations during e-commerce checkout: temporarily holding stock while a user completes payment, confirming it into a final order on success, and releasing it on cancellation or timeout.

Inventory can come from multiple sources — the platform's own warehouse, or external providers with differing capabilities (some support holding stock upstream, others only expose a read-only stock check). The service is built so business logic never depends on which kind of provider it's talking to.

For the reasoning behind the design decisions, trade-offs, and how the system holds up under growth, see:

- **[ARCHITECTURE.md](./ARCHITECTURE.md)** — domain model, reservation lifecycle, provider abstraction, concurrency strategy, known limitations
- **[SCALABILITY.md](./SCALABILITY.md)** — bottlenecks, what breaks first, scaling stages

This README covers what's needed to run the service and use the API.

---

## Tech Stack

- **FastAPI** — HTTP API
- **PostgreSQL** (via SQLAlchemy 2.0 + `psycopg`) — primary datastore, source of truth for reservations and inventory
- **Redis** — currently used for OTP storage (auth), with a fallback to Postgres if Redis is unavailable
- **Alembic** — database migrations
- **httpx** — outbound HTTP calls to external inventory providers
- **pytest** — unit tests

---

## Project Structure

```
app/
├── core/                    # DB sessions, Redis client, JWT, settings
├── modules/
│   ├── user/                 # Auth (OTP login) — out of scope of the reservation task itself
│   ├── product/               # Product model
│   ├── inventory/            # Inventory levels, providers, provider registry, resilience layer
│   │   ├── providers/
│   │   │   ├── interfaces/          # StockCheckable / Reservable capability interfaces
│   │   │   ├── provider_implementation/  # internal / warehouse / marketplace clients
│   │   │   └── shared/               # RetryPolicy, CircuitBreaker, RestTransport, CallLogger
│   │   └── ...
│   ├── reservation/          # Reservation + ReservationItem lifecycle, the core of this service
│   │   ├── services/          # ReservationService, ReservationItemReserver
│   │   ├── repositories/      # Row-locking, status transitions
│   │   ├── tests/             # Unit test suite
│   │   └── ...
│   └── order/                 # Order creation from a confirmed reservation
├── seed.py                   # Populates sample products, providers, and inventory
└── main.py                   # App wiring, router + exception handler registration
alembic/                      # Migrations
```

---

## Getting Started

### 1. Environment variables

Create a `.env` file in the project root (not committed — see `.gitignore`):

```env
POSTGRES_USER=fastapi_user
POSTGRES_PASSWORD=secret_password
POSTGRES_DB=fastapi_db
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

JWT_SECRET_KEY=change-me
RESERVATION_TTL_SECONDS=300
```

All of these have defaults in `app/core/conf/config.py` for local development — the `.env` file lets you override them, and is required as-is for `docker-compose` since it reads `POSTGRES_*` / `REDIS_*` directly.

### 2. Run with Docker Compose

```bash
docker compose up --build
```

This starts Postgres, Redis, and the API on `http://localhost:8000`.

> **Note:** the `Dockerfile` currently points `pip install` at a private mirror index (`archive.ito.gov.ir`). If you're running this outside that network, drop the `--index-url` flag from the two `pip install` lines in `Dockerfile` so it falls back to the default PyPI index.

### 3. Run migrations

```bash
alembic upgrade head
```

(If running inside Docker: `docker compose exec fastapi alembic upgrade head`.)

### 4. Seed sample data

```bash
python -m app.seed
```

This creates three inventory providers (`internal`, `warehouse_provider`, `marketplace_seller_x`) and a few sample products so you can exercise the reservation flow end-to-end without wiring up real provider credentials.

### 5. Run locally without Docker

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Requires a running Postgres and Redis reachable via the host/port values in your `.env`.

---

## Running Tests

```bash
pip install pytest
pytest app/modules/reservation/tests/tests.py -v
```

The suite is fully mocked (no DB, no network) and covers the reservation/item lifecycle, concurrency conflicts, idempotency, and partial-failure handling — see the **Testing** section of [ARCHITECTURE.md](./ARCHITECTURE.md) for a full breakdown of what's covered and what isn't.

---

## API Reference

All routes are prefixed with `/api/v1`. Requests carry a verified `user_id` — auth is out of scope for this service (see Assumptions in ARCHITECTURE.md).

### Auth

| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/login` | Request an OTP for a phone number |
| `POST` | `/auth/verify-otp` | Verify OTP and receive a session/token |

### Reservations

| Method | Path | Description |
|---|---|---|
| `POST` | `/reservations?user_id={id}` | Create a reservation for a list of items. Idempotent via `client_idempotency_key` in the body. |
| `POST` | `/reservations/{reservation_id}/confirm` | Confirm a pending reservation after payment succeeds — consumes inventory and creates an order. |
| `POST` | `/reservations/{reservation_id}/cancel` | Cancel a pending reservation and release held inventory. |

**Create reservation — example body:**
```json
{
  "items": [
    { "product_inventory_id": 1, "sku": "SONY-WH-XM5-BLK", "quantity": 1 }
  ],
  "client_idempotency_key": "a-client-generated-uuid"
}
```

### Orders

| Method | Path | Description |
|---|---|---|
| `POST` | `/orders/from-reservation/{reservation_id}` | Create the final order from a confirmed reservation. |
| `GET` | `/orders/{order_id}` | Fetch an order's status. |

### Misc

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness check. |

Interactive docs (Swagger UI) are available at `/docs` once the app is running.

---

## Reservation Lifecycle

```
CREATING → PENDING_LOCAL → PENDING → CONFIRMING → CONFIRMED
                                 │
                                 ├──► CANCELLED
                                 └──► EXPIRED
```

Each `ReservationItem` tracks its own finer-grained status (`HELD_LOCAL → HELD → CONFIRMED / FAILED / RELEASED`), independent of the parent reservation's status — see [ARCHITECTURE.md](./ARCHITECTURE.md) for the full flow and why this split exists.

---

## Known Limitations

Briefly, since the full reasoning lives in the docs above:

- Read-only inventory providers (no upstream hold API) carry a small, structural oversell risk between the confirm-time stock check and consuming stock — see **Known Limitations** in ARCHITECTURE.md.
- Resilience (retry/circuit-breaker) state is currently per-process; it doesn't survive across multiple horizontally-scaled instances — see **Per-Instance Resilience State** in SCALABILITY.md.
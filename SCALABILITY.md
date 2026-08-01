## Overview

The current implementation is designed to prioritize **correctness**, **consistency**, and **maintainability** over extreme scalability.

Inventory reservation is a business-critical operation where overselling is unacceptable. Therefore, several design decisions intentionally favor strong consistency even if they reduce maximum throughput.

The architecture is suitable for a medium-sized e-commerce platform and provides clear evolution paths as traffic increases.

---

# Current Scalability Characteristics

The service scales well for:

- Multiple application instances
- Moderate inventory contention
- Multiple inventory providers
- Thousands of concurrent checkout sessions

The application itself is stateless, allowing horizontal scaling by simply adding more application instances behind a load balancer.

The primary shared state resides in the database.

---

# Primary Bottlenecks

As traffic grows, several bottlenecks will appear before the application servers become the limiting factor.

## 1. Database Contention

The first scalability bottleneck is inventory updates.

Each reservation acquires a pessimistic lock on inventory rows.

Under heavy demand for popular products:

```
User A
    │
    ▼
Locks Inventory Row
    │
User B waits
    │
User C waits
    │
User D waits
```

This reduces throughput for highly contested inventory.

### Why this trade-off?

Overselling inventory is more expensive than temporarily reducing throughput.

The system deliberately favors correctness over maximum concurrency.

---

## 2. Synchronous Provider Calls

Reservation creation currently communicates directly with external inventory providers.

Slow providers increase API latency.

```
Reservation Request

↓

Local Reservation

↓

External Provider

↓

Client Response
```

A provider timeout directly impacts checkout response time.

---

## 3. Reservation Expiration

Expired reservations eventually accumulate.

As reservation volume grows, expiration processing becomes increasingly expensive.

Without periodic cleanup:

- reserved inventory remains locked
- database tables grow continuously
- queries become slower

---

## 4. Database Growth

Several tables continuously grow:

- Reservations
- Reservation Items
- Orders
- Inventory Events (future)

Historical reservation data is valuable for auditing but increases storage and query costs over time.

---

# Scaling Strategy

Rather than redesigning the system immediately, the architecture supports incremental improvements.

---

# Stage 1 — Horizontal API Scaling

The application is stateless.

Multiple application instances can be deployed behind a load balancer.

```
                Load Balancer
             /        |        \
            /         |         \
        API 1      API 2      API 3
               |
            PostgreSQL
```

No application-level changes are required.

---

# Stage 2 — Background Workers

Reservation expiration should move to a dedicated background worker.

Responsibilities include:

- releasing expired reservations
- notifying providers
- cleaning temporary resources

This prevents user requests from performing maintenance work.

---

# Stage 3 — Reliable Provider Communication

Provider communication currently happens synchronously.

As provider count grows, asynchronous communication becomes preferable.

A production system would introduce the Outbox Pattern.

```
Transaction

↓

Reservation Saved

↓

Outbox Event

↓

Background Worker

↓

Provider API
```

Benefits:

- eliminates dual-write problems
- supports retries
- isolates provider failures
- improves response time

---

# Stage 4 — Retry and Resiliency

External providers are inherently unreliable.

Provider operations should include:

- exponential backoff
- retry limits
- circuit breakers
- dead-letter queues

This improves availability without affecting local consistency.

---

# Stage 5 — Read Optimization

Reservation operations are write-heavy.

Other operations such as:

- product availability
- reservation lookup
- order history

are read-heavy.

Read replicas can reduce pressure on the primary database while preserving transactional integrity for writes.

---

# Database Scaling

The current design assumes a single PostgreSQL instance.

As data volume grows:

## Partitioning

Reservation tables can be partitioned by creation date.

Benefits:

- faster cleanup
- smaller indexes
- improved query performance

---

## Index Optimization

Critical indexes include:

- Reservation ID
- User ID
- Reservation Status
- Expiration Time
- Product ID

These support the most common lookup patterns.

---

# Inventory Contention

Popular products naturally generate lock contention.

Potential future improvements include:

- inventory sharding
- warehouse-level inventory partitioning
- optimistic locking for low-contention products
- reservation queues for flash sales

These optimizations increase throughput while maintaining correctness.

---

# Provider Scaling

The Provider Registry allows new providers to be added without modifying reservation logic.

As provider count increases:

- each provider remains independently deployable
- provider-specific authentication stays isolated
- failures remain localized

This prevents business logic from becoming tightly coupled to provider implementations.

---

# Observability

As traffic grows, monitoring becomes essential.

Recommended metrics include:

### Reservation Metrics

- reservations created
- reservations confirmed
- reservations cancelled
- reservation failures
- expired reservations

### Inventory Metrics

- available inventory
- reserved inventory
- inventory lock wait time

### Provider Metrics

- request latency
- success rate
- timeout rate
- retry count

These metrics allow operational bottlenecks to be identified before they affect users.

---

# Trade-offs

Several deliberate trade-offs favor simplicity over maximum scalability.

## Pessimistic Locking

Pros:

- prevents overselling
- simple reasoning
- strong consistency

Cons:

- reduced throughput under heavy contention

Given the business domain, correctness outweighs raw performance.

---

## Synchronous Provider Calls

Pros:

- simpler implementation
- immediate consistency
- easier debugging

Cons:

- higher response latency
- provider failures affect checkout

A production system would migrate this responsibility to asynchronous processing.

---

## Modular Monolith

Pros:

- simpler deployment
- transactional consistency
- easier development

Cons:

- entire application scales together
- larger deployment units

The modular boundaries intentionally make future service extraction straightforward if required.

---

# What Breaks First?

If traffic increased significantly, components would likely reach their limits in the following order:

1. Database row locking on high-demand inventory
2. Slow or unavailable external providers
3. Reservation expiration processing
4. Database storage and index growth
5. API server CPU and memory

Understanding this order helps prioritize optimization efforts where they provide the greatest benefit.

---

# Future Evolution

If the platform reached very large scale, the architecture could evolve toward an event-driven system:

```
Checkout

↓

Reservation Service

↓

Outbox

↓

Message Broker

↓

Inventory Workers

↓

Provider Workers

↓

Order Service
```

This architecture improves resilience, supports independent scaling of components, and isolates failures while preserving the existing domain model.

The current implementation intentionally stops short of this complexity because the assignment prioritizes correctness, clean design, and maintainability over operating a distributed system.
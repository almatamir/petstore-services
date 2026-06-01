# Interview Guide — Cloud Assignment 4: Pet Store CI/CD

> Course: Cloud Computing and SE | Team: Alma Tamir + Amit Cohen

---

## What This Project Actually Is

A **microservices pet store system** with three Flask services, two MongoDB instances, and a three-stage GitHub Actions CI/CD pipeline. Two independent pet store instances manage inventory; a third service handles purchases across both stores. Everything runs in Docker containers behind an Nginx reverse proxy, with Kubernetes manifests ready for production deployment.

**One-liner for interviews:**
> "A multi-service REST API for pet inventory and ordering, containerized with Docker, orchestrated with Docker Compose and Kubernetes, fronted by Nginx, persisted in MongoDB, and fully automated with a three-stage GitHub Actions CI/CD pipeline."

---

## Cloud Technologies — What Each One Is and Why We Used It

### Containers & Docker

**What is a container?**
A container is a lightweight, isolated process that packages an application together with everything it needs to run — code, runtime, libraries, environment variables. It runs on the host OS kernel directly (unlike a VM which emulates an entire machine), so it starts in milliseconds and uses far less memory.

**Container vs Virtual Machine:**
| | Container | Virtual Machine |
|--|-----------|----------------|
| Startup | Milliseconds | Minutes |
| Size | Megabytes | Gigabytes |
| Isolation | Process-level | Full OS |
| Overhead | Very low | High |

**Docker image vs Docker container:**
- An **image** is the blueprint — a read-only snapshot of the app and its dependencies, built from a Dockerfile.
- A **container** is a running instance of an image. You can run many containers from the same image.

In this project: both pet stores run from the same `pet-store:latest` image. The image is built once; two containers run from it with different environment variables.

**Why Docker here?**
> "Docker guarantees that what passes CI tests is exactly what runs in production — same OS libraries, same Python version, same dependencies. Without Docker, 'it works on my machine' is a real problem."

---

### Microservices

**What is a microservice?**
A microservice is a small, independently deployable service with a single responsibility. Services communicate over the network (HTTP in this project) instead of calling each other's functions directly.

**This project has 2 microservices:**

| Microservice | Responsibility | Instances |
|-------------|---------------|-----------|
| **pet-store** | Manages inventory: pet types and individual pets | 2 (store1 and store2) |
| **pet-order** | Handles purchases across stores, records transactions | 1 |

**Important:** pet-store1 and pet-store2 are not two different microservices — they are **two instances of the same microservice**, running the same code with different configuration (different `STORE_ID`, different MongoDB collection). This is a key benefit of microservices: deploy the same service multiple times with different configs.

**Why microservices over a single monolith?**
> "Each service has one job and can be deployed, scaled, and updated independently. If the purchase logic needs to change, I update pet-order without touching pet-store. If store1 gets more traffic, I can scale just that instance. The trade-off is network calls between services instead of function calls — slower and less reliable, but the independence is worth it at scale."

---

### Docker Compose

**What it does:**
Docker Compose defines and runs multi-container applications from a single `docker-compose.yml` file. Instead of manually starting each container with long `docker run` commands, one `docker compose up -d` starts everything — with the right network, environment variables, and dependency order.

**In this project it manages:**
- 2 MongoDB containers
- 2 pet-store containers
- 1 pet-order container
- 1 Nginx container
- 1 shared bridge network connecting them all

**Why not just run containers manually?**
> "Docker Compose gives you reproducibility — the same command on any machine starts the exact same system. It also handles networking automatically: all services can reach each other by name (e.g. `pet-store1:8000`) without any manual IP configuration."

---

### Nginx

**What it is:** A high-performance web server used here as a **reverse proxy**.

**What reverse proxy means:**
The client talks to Nginx on port 80. Nginx forwards the request to the right backend service and sends the response back. The client never knows which backend it talked to.

```
Client → nginx:80/store1/pet-types → pet-store1:8000/pet-types
Client → nginx:80/orders/purchases → pet-order:8080/purchases
```

**What Nginx adds:**
- **Single entry point** — one port instead of three
- **Path-based routing** — routes by URL prefix
- **Load balancing** — if you run 3 replicas of pet-store1, Nginx distributes requests across them automatically
- **TLS termination** — HTTPS is decrypted once at Nginx; internal traffic stays plain HTTP

> "Nginx is the front door. Everything goes through it. In production it would also handle SSL certificates and rate limiting."

---

### Kubernetes

**What it is:** A container orchestration platform. Docker Compose is for one machine; Kubernetes manages containers across a **cluster** of many machines.

**What Kubernetes does automatically:**
- Restarts crashed containers
- Spreads containers across healthy nodes
- Updates containers with zero downtime (rolling updates)
- Scales replicas up and down
- Routes traffic to healthy pods only

**Key concepts in this project:**

**Deployment** — tells Kubernetes "run N copies of this container, and if one crashes, restart it"
```yaml
spec:
  replicas: 1          # run 1 copy
  template:            # this is the pod blueprint
    spec:
      containers:
        - image: pet-store:latest
```

**Service (ClusterIP)** — gives a Deployment a stable DNS name inside the cluster. `pet-store1` always resolves to the correct pod, even if that pod restarts and gets a new IP.

**ConfigMap** — non-secret configuration injected as environment variables. Changing a ConfigMap doesn't require rebuilding the image.

**Secret** — same as ConfigMap but for sensitive values (API keys, passwords). Values are base64-encoded and access-controlled.

**Ingress** — the Kubernetes equivalent of Nginx in docker-compose. Routes external HTTP traffic to internal Services by path.

**Why Kubernetes over Docker Compose?**
> "Docker Compose is great for one machine. Kubernetes manages a cluster — if a node goes down, Kubernetes moves the containers to a healthy node automatically. It also handles scaling: `kubectl scale deployment pet-store1 --replicas=3` and Nginx load-balances across all three instantly."

---

### MongoDB — Collections & Data Persistence

**How MongoDB is structured in this project:**

We run **two separate MongoDB instances** (two containers/pods), each responsible for a different concern:

```
mongodb-stores (container)
└── database: petstore
    ├── collection: pet_store_1   ← pet-store1's inventory
    ├── collection: pet_store_2   ← pet-store2's inventory
    ├── collection: counters_1    ← ID counter for store 1
    └── collection: counters_2    ← ID counter for store 2

mongodb-purchases (container)
└── database: petstore
    └── collection: transactions  ← all purchase records
```

Both stores share one MongoDB instance but write to **different collections** — controlled by the `COLLECTION_NAME` environment variable. Same database engine, completely separate data. The purchase service has its own MongoDB instance entirely, so a failure in store inventory never affects transaction records.

---

**Why a plain Deployment loses data on restart — simple explanation:**

Think of a container like a whiteboard. Every time you start a new container from an image, you get a **blank whiteboard**. Anything MongoDB writes to disk during the container's life is written on that whiteboard. When the container stops or crashes, Kubernetes throws the whiteboard away and gives the new container a fresh blank one.

```
Container starts  →  MongoDB writes data to /data/db  →  Container crashes
                                                               ↓
                                               New container starts with empty /data/db
                                               All data is gone
```

**The fix — PersistentVolumeClaim:**

Instead of writing to the container's internal whiteboard, MongoDB writes to an **external disk** that lives outside the container. If the container is thrown away, the disk survives and gets attached to the next container.

```
Container starts  →  PVC (external disk) attached at /data/db
                  →  MongoDB writes data there
                  →  Container crashes
                         ↓
               New container starts
               Same PVC reattached at /data/db
               All data is still there ✓
```

**StatefulSet vs Deployment:**
- **Deployment** — treats every pod as identical and replaceable. Fine for stateless services (Flask apps). Bad for databases.
- **StatefulSet** — gives each pod a stable name (`mongodb-stores-0`) and its own PVC. When the pod restarts, it always gets the same disk back.

> "A Deployment is like hiring a temp worker and not caring which desk they sit at. A StatefulSet is like assigning a permanent employee to a specific desk with a locked drawer — the drawer stays theirs even if they're away for a day."

---

## Architecture — Draw This and Explain It

```
        External Client
              |
           port 80
              |
   ┌──────────────────────────────────────┐
   │         nginx (reverse proxy)        │
   │  /store1/* → pet-store1:8000         │
   │  /store2/* → pet-store2:8000         │
   │  /orders/* → pet-order:8080          │
   │                                      │
   │   Docker bridge: petstore-network    │
   │                                      │
   │  pet-store1 & pet-store2             │
   │   (same image, different config)     │
   │       └── mongodb-stores (internal)  │
   │                                      │
   │  pet-order                           │
   │       ├── calls pet-stores via HTTP  │
   │       └── mongodb-purchases          │
   └──────────────────────────────────────┘

   pet-store ──► api-ninjas.com  (external animal taxonomy API)
```

**Say out loud:**
> The three services talk to each other over Docker's bridge network using service names like `http://pet-store1:8000`. MongoDB ports are only exposed internally — no external access. The pet stores both run the same Docker image but point at different MongoDB collections, configured entirely through environment variables.

---

## 5 Questions You Will Almost Certainly Get

### 1. "Walk me through the architecture."

> There are three services in a Docker Compose network. Two pet-store instances — running the same image, different configs — manage inventory for their respective store locations. They use a shared MongoDB instance but separate collections. A third service, pet-order, handles purchases: when someone buys a pet, it calls the appropriate pet store via HTTP, removes the pet from inventory, and saves the transaction in its own MongoDB database. The whole system builds and tests automatically with GitHub Actions on every push.

---

### 2. "Why microservices?"

> Each service has a single, clear responsibility. The two stores can be updated or scaled independently. The order service can change its purchase logic without touching store logic. The main trade-off is operational complexity — more containers to manage and inter-service HTTP calls instead of simple function calls. For this scale, Docker Compose handles that complexity well.

---

### 3. "Why MongoDB?"

> Pet types have different characteristics depending on the animal — dogs have a temperament field, other animals have group behavior. A flexible document schema handles that more naturally than forcing everything into the same relational columns. MongoDB also lets me embed the pet list directly inside each pet-type document, which matches how the data is read. The trade-off is weaker consistency guarantees compared to PostgreSQL, but for this use case that's fine.

---

### 4. "What was the biggest technical challenge?"

> Two things. First, passing Docker images between CI pipeline jobs — each GitHub Actions job runs on a fresh machine, so I had to `docker save` the images as `.tar` files, upload them as artifacts, then download and `docker load` them in the next job. Second, making the test job wait for all services to actually be ready before running pytest. I wrote a polling loop that checks four endpoints — the `/health` route on both stores, the order service, and nginx on port 80 — up to 30 times before allowing tests to start.

---

### 5. "If you had another month, what would you improve?"

 A few things:
> 1. Wire the Docker Compose `healthcheck` directive to the existing `/health` endpoints so `depends_on` waits for true service readiness instead of just container startup.
> 2. Add monitoring — Prometheus metrics and a Grafana dashboard, because right now there's zero visibility into request rates or errors.
> 3. Add retry logic and circuit breakers for inter-service HTTP calls — currently if a pet store is temporarily down during a purchase, the whole request fails with no retry.
> 4. Push Docker images to a registry (Docker Hub or ECR) so Kubernetes can pull them — right now the k8s manifests use `imagePullPolicy: Never` which only works with locally loaded images.
> 5. Add liveness and readiness probes to the Kubernetes Deployments so k8s knows when a pod is actually ready to serve traffic, not just running.

---

## CI/CD Pipeline — Know This Cold

```
Code Push → GitHub Actions

[build job]
  - docker build pet-store:latest
  - docker build pet-order:latest
  - docker save → upload as .tar artifacts
  - write log.txt (timestamp, team names, build results)

[test job]  (needs: build)
  - download image artifacts → docker load
  - docker compose up -d
  - wait for all 4 endpoints to respond: /health on both stores + order service, /store1/health through nginx
  - pytest assn4_tests.py — 9 integration tests against live containers
  - docker compose down

[query job]  (needs: test)
  - start containers again
  - populate test data (pet types + pets via API calls)
  - read query.txt → execute each GET query and POST purchase
  - write response.txt with status codes and JSON bodies
  - upload as artifact
```

**Key design point to mention:** Images are saved as `.tar` artifacts so the test and query jobs use the exact same images that were built — no rebuilding. This guarantees reproducibility.

**Test suite — 9 integration tests (`tests/assn4_tests.py`):**

| Test | What it verifies |
|------|-----------------|
| `test_00_health_checks` | All 4 endpoints respond before anything else runs (both stores + order service + nginx) |
| `test_01` | POST 3 pet-types to store1 → 201, IDs exist and are unique |
| `test_02` | POST 3 pet-types to store2 → 201, IDs exist and are unique |
| `test_03–07` | POST pets to various types → all return 201 |
| `test_08_purchase_removes_pet_from_store` | Buy a pet → count in store decreases by exactly 1 |

Tests run sequentially and share state via `pet_type_ids` dict — each test depends on the IDs created in previous tests. `test_00` acts as a gate: if any service isn't ready, the whole suite fails immediately with a clear message rather than cryptic errors in test_01.

---

## Nginx — Why and How

**What it does in this project:**
Nginx sits in front of all three services as a reverse proxy. It gives the system a single entry point on port 80 instead of exposing three separate ports.

```
Client → nginx:80
    /store1/* → pet-store1:8000  (strips /store1 prefix)
    /store2/* → pet-store2:8000  (strips /store2 prefix)
    /orders/* → pet-order:8080   (strips /orders prefix)
```

**How to explain it:**
> "Nginx acts as a reverse proxy — the client talks to one port and Nginx routes the request to the right service. It also forwards the real client IP via `X-Real-IP` so services can log who made the request. In production, Nginx would also handle TLS termination, so HTTPS is decrypted once at the edge and internal traffic stays plain HTTP."

**Why nginx and not just direct ports?**
> "Direct ports work for development, but in production you want a single entry point. Nginx also gives you load balancing for free — if I add replicas of pet-store1, Nginx distributes requests across them without any application code change."

---

## Kubernetes — Why and How

**What k8s adds over Docker Compose:**

| Feature | Docker Compose | Kubernetes |
|---------|---------------|------------|
| Restart crashed containers | No | Yes (restartPolicy) |
| Scale replicas | Manual | `kubectl scale` or HPA |
| Rolling updates | No | Built-in, zero downtime |
| Secret management | `.env` file | `Secret` objects |
| Service discovery | Docker DNS | kube-dns |
| Health checks | Basic | Liveness + readiness probes |

**File structure:**
```
k8s/
  namespace.yaml      — isolates all resources under "petstore"
  configmap.yaml      — non-secret config (URLs, DB names)
  secrets.yaml        — sensitive values (API key, owner secret)
  mongo.yaml          — two MongoDB StatefulSets + headless Services + PersistentVolumeClaims
  pet-store.yaml      — pet-store1 and pet-store2 Deployments + Services
  pet-order.yaml      — pet-order Deployment + Service
  ingress.yaml        — nginx Ingress routes external traffic to services
```

**How to deploy:**
```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets.yaml      # fill in real values first
kubectl apply -f k8s/mongo.yaml
kubectl apply -f k8s/pet-store.yaml
kubectl apply -f k8s/pet-order.yaml
kubectl apply -f k8s/ingress.yaml
```

**Key concepts to explain:**

*ConfigMap vs Secret:*
> "Non-sensitive config (service URLs, DB name) goes in a ConfigMap. Sensitive values (API key, auth secret) go in a Secret. Both are injected as environment variables — the application code doesn't change, only where the values come from."

*ClusterIP Service:*
> "Each Deployment gets a ClusterIP Service, which gives it a stable internal DNS name. `pet-store1` resolves to the correct pod IP even if the pod restarts and gets a new IP. The Ingress is the only thing exposed externally."

*Ingress:*
> "The Ingress replaces Nginx in Docker Compose. It's the same concept — one external entry point, path-based routing to backend services — but managed by Kubernetes instead of a config file."

*Why two Deployments for pet-store instead of one?*
> "Both stores use the same Docker image, but need different environment variables — STORE_ID, COLLECTION_NAME. So they're two separate Deployments pointing at the same image, differentiated only by their env vars."

*Why StatefulSet for MongoDB and not Deployment?*
> "MongoDB needs persistent storage — if the pod restarts, data can't disappear. A plain Deployment treats pods as disposable; a StatefulSet gives each pod its own PersistentVolumeClaim so the same disk reattaches on restart. Both MongoDB instances in this project use StatefulSets with 1Gi PVCs for exactly this reason."

---

## Purchase Flow & Rollback — Know This Well

This is one of the most interesting technical decisions in the project.

**The problem (what the original code did):**
```
1. delete pet from store  ← if step 2 fails, pet is gone with no record
2. save transaction to DB
```

**The fix (what the code does now):**
```
1. save transaction to DB  ← if this fails, return 500, pet still available
2. delete pet from store   ← if this fails, compensate by deleting the transaction
```

**How to explain it in an interview:**
> "I identified a data consistency issue in the purchase flow. The original code deleted the pet first, then recorded the transaction. If the database write failed, the pet was lost with no record. I fixed it by saving the transaction first — if that fails, we return 500 and the pet is still available. If the pet deletion then fails, we delete the transaction we just saved as a compensating action. This is the basic idea behind the saga pattern for distributed transactions."

**If they ask "why not use a database transaction?"**
> "The pet and the transaction live in different MongoDB instances — the pet is in mongodb-stores and the transaction in mongodb-purchases. MongoDB transactions don't span across separate instances, so a true atomic transaction isn't possible here. The saga pattern with compensating actions is the right approach for this kind of distributed operation."

---

## Code Design — What You'd Improve (Strong Interview Topic)

You don't need the code to exist to talk about good design. These are patterns you *identified* in the codebase and would apply next — interviewers respect this more than half-implemented refactors.

| Pattern | Where you'd apply it | Why |
|---------|---------------------|-----|
| **Full repository pattern** | `db.py` has the `PetStoreDB` class but it still returns raw dicts. A full repository would return typed objects and hide MongoDB-specific code completely | Would make unit testing possible without a real database — swap in an in-memory fake |
| **Model classes** | Replace raw dicts with `Pet` and `PetType` dataclasses | Every field becomes explicit and typed. No guessing what keys a dict might have. |
| **Generic filter builder** | The `GET /pet-types` filter chain in `pets.py` | Six separate `if` blocks, one per field. A dict of `{field: predicate}` means adding a new filter is one line. |
| **HTTP client wrapper** | Wrap the api-ninjas.com call in an `AnimalAPIClient` class | Hides URL and auth details. In tests, you inject a fake client — no real network calls. |
| **Centralized error handling** | Custom exception hierarchy + single Flask error handler | Right now each route formats its own error response. One handler means consistent format everywhere. |

> **How to say it in an interview:** "The current code works and is correct. If I were continuing the project, I'd extract the database layer, introduce typed models, and centralize error handling — these three changes would make it significantly easier to test and extend."

---

## Services in Detail

### pet-store (2 files — separated by responsibility)

| File | Responsibility |
|------|---------------|
| `db.py` | `PetStoreDB` class — all MongoDB reads, writes, and ID generation |
| `pets.py` | Flask routes — HTTP handling, validation, business logic |

`pets.py` imports `PetStoreDB` from `db.py` and creates one instance: `db = PetStoreDB(MONGO_URI, DB_NAME, COLLECTION_NAME, STORE_ID)`. Routes call `db.find_by_id()`, `db.save()` etc. — they have no idea how MongoDB works internally.

Key implementation details:
- On `POST /pet-types`: calls api-ninjas.com to fetch real animal taxonomy (family, genus, lifespan, temperament/attributes)
- `PetStoreDB` is generic — same class, any collection. Adding store 3 = one new instance with different config, zero new code
- ID generation uses a MongoDB atomic counter (`find_one_and_update` with `$inc`) — safe under concurrent requests

### pet-order (pet_order.py)
- `POST /purchases`: finds available pet (random if not specified), saves transaction first, then deletes pet (saga pattern)
- `GET /transactions`: protected by `OwnerPC: <OWNER_SECRET>` header; supports filtering by purchaser, pet-type, store, purchase-id
- Discovers stores dynamically from `PET_STORE_N_URL` env vars — adding a third store requires zero code changes
- **Does not touch MongoDB stores directly** — always goes through the pet-store REST API to delete pets

---

## API Quick Reference

### Pet Store (`:5001` and `:5002`)

| Method | Endpoint | Returns |
|--------|----------|---------|
| POST | `/pet-types` | 201 with taxonomy from external API |
| GET | `/pet-types` | 200 array (filterable by id, type, family, genus, lifespan, hasAttribute) |
| GET | `/pet-types/{id}` | 200 or 404 |
| DELETE | `/pet-types/{id}` | 204 (fails if pets exist) |
| POST | `/pet-types/{id}/pets` | 201 (optional birthdate DD-MM-YYYY, picture-url) |
| GET | `/pet-types/{id}/pets` | 200 (filterable by birthdateGT, birthdateLT) |
| GET/PUT/DELETE | `/pet-types/{id}/pets/{name}` | 200/204/404 |

### Pet Order (`:5003`)

| Method | Endpoint | Notes |
|--------|----------|-------|
| POST | `/purchases` | `purchaser` + `pet-type` required; `store`/`pet-name` optional |
| GET | `/transactions` | Requires `OwnerPC: <OWNER_SECRET>` header |

**Validation rules worth knowing:**
- Client cannot send `purchase-id` (server generates it — UUID truncated to 8 chars)
- `pet-name` requires `store` to also be provided
- Unknown fields in request body → 400

---

## Security — Especially Relevant for CyberArk

**What's in place:**
- MongoDB ports are internal only (`expose` not `ports`) — not reachable from outside Docker network
- All secrets (`NINJA_API_KEY`, `OWNER_SECRET`) are injected via environment variables — never hardcoded in source code
- A `.env.example` documents required secrets; `.gitignore` ensures the real `.env` is never committed
- `/transactions` requires a custom auth header whose value comes from `OWNER_SECRET` env var
- `docker-compose.yml` uses `${NINJA_API_KEY}` and `${OWNER_SECRET}` — values come from the local `.env` file at runtime

**Remaining gaps (be honest about these):**
- Auth header is a simple shared secret, not cryptographically signed — would replace with JWT in production
- No HTTPS/TLS between services (acceptable inside a private Docker network, not acceptable over the internet)
- No rate limiting or request authentication on the pet-store endpoints themselves

---

## Trade-offs — For Strong Interviewers

| Decision | Why | What I'd change |
|----------|-----|-----------------|
| MongoDB over PostgreSQL | Flexible schema for varying animal attributes | PostgreSQL for stronger consistency if data model stabilized |
| Microservices over monolith | Independent deployability, separation of concerns | Monolith is simpler for small teams; microservices need more infra |
| Shared mongodb-stores | Simpler operations, one container | Separate DB per store for true isolation and independent scaling |
| Synchronous HTTP between services | Simple, easy to debug | Add retry logic and circuit breakers for production |
| Filesystem for pet images | Easy to implement | Object storage (S3) — images are lost on container restart |
| Repository pattern adds a layer | Testable, decoupled from DB | More files, more indirection — overkill for a two-endpoint service |
| Dataclasses over dicts | Explicit fields, type safety, self-documenting | Small overhead; for very simple data a dict is fine |
| N-store env var convention | No code change needed to add stores | Relies on naming convention — easy to misconfigure |

---

## Live Demo Script

If asked to demo (copy `.env.example` → `.env`, fill in values, then `docker compose up -d && sleep 10`):

```bash
# Create a pet type (calls external API)
curl -X POST localhost:5001/pet-types \
  -H "Content-Type: application/json" \
  -d '{"type":"Golden Retriever"}'

# Add a pet
curl -X POST localhost:5001/pet-types/1/pets \
  -H "Content-Type: application/json" \
  -d '{"name":"Buddy","birthdate":"14-05-2020"}'

# Filter by family
curl "localhost:5001/pet-types?family=Canidae"

# Purchase a pet (removes from store)
curl -X POST localhost:5003/purchases \
  -H "Content-Type: application/json" \
  -d '{"purchaser":"Bob","pet-type":"Golden Retriever","store":1}'

# Verify pet is gone
curl localhost:5001/pet-types/1/pets

# View transaction log (auth required — value is your OWNER_SECRET from .env)
curl -H "OwnerPC: $(grep OWNER_SECRET .env | cut -d= -f2)" localhost:5003/transactions
```

---

## Key Numbers

| Item | Value |
|------|-------|
| Services | 3 (pet-store1, pet-store2, pet-order) |
| MongoDB instances | 2 (stores + purchases) |
| Host ports | 5001, 5002, 5003 |
| CI pipeline stages | 3 (build → test → query) |
| External API | api-ninjas.com Animals v1 |
| Python version | 3.10 |
| MongoDB version | 6.0 |
| pet-store source files | 2 (db.py — database layer, pets.py — routes) |
| k8s manifests | 7 (namespace, configmap, secrets, mongo, pet-store, pet-order, ingress) |
| Auth header key | `OwnerPC` (value from `OWNER_SECRET` env var) |
| Date format | `DD-MM-YYYY` or `"NA"` |
| Secrets management | `.env` file (never committed) — see `.env.example` |

---

*Know the purchase flow, the CI pipeline stages, and why services are separated — those three topics cover 80% of technical questions. The design patterns section (repository, filter builder, error handling) is your differentiator — it shows you think beyond "make it work."*

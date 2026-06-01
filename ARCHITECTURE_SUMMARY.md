# Pet Store Project — Simple Architecture & Workflow

A short guide to what runs where and how requests move through the system.

---

## What is this project?

Two small **Flask** APIs work together:

| Service | Job |
|---------|-----|
| **pet-store** | Keeps inventory: pet types and individual pets in MongoDB |
| **pet-order** | Handles **purchases**: picks a pet from a store, saves the sale, removes the pet from inventory |

You run **two copies** of pet-store (`store1` and `store2`). Each has its own MongoDB collection. Purchases are stored in a **second** MongoDB.

**Nginx** is the front door: one URL (port 80) routes traffic to the right service by path.

---

## Big picture (local Docker)

```
You (browser / tests)
        │
        ▼  port 80
    ┌─────────┐
    │  Nginx  │  paths: /store1/  /store2/  /orders/
    └────┬────┘
         │
    ┌────┴────┬────────────┐
    ▼         ▼            ▼
 store1    store2      pet-order
 :5001     :5002        :5003
    │         │            │
    └────┬────┘            │ calls stores over HTTP
         ▼                 ▼
   mongodb-stores    mongodb-purchases
   (inventory)       (transactions)
```

- All containers talk on a private Docker network (`petstore-network`).
- MongoDB is **not** exposed to your laptop—only the apps can reach it.

---

## How Nginx routes URLs

| You call | Goes to |
|----------|---------|
| `http://localhost/store1/...` | pet-store1 |
| `http://localhost/store2/...` | pet-store2 |
| `http://localhost/orders/...` | pet-order |

Nginx strips the prefix (`/store1`, etc.) before forwarding, so the apps still see normal paths like `/pet-types`.

---

## Typical workflows

### 1. Manage inventory (pet-store)

1. Client sends REST request to `/store1/` or `/store2/` (via Nginx) or directly to ports 5001 / 5002.
2. **pet-store** reads/writes its collection in **mongodb-stores**.
3. When you **add a pet type**, the service may call the external **API Ninjas Animals API** (needs `NINJA_API_KEY`) to fill in family, genus, lifespan, etc.

Main ideas:

- **Pet types** = categories (e.g. “Golden Retriever”).
- **Pets** = actual animals under a type (name, birthdate, etc.).

### 2. Buy a pet (pet-order)

1. Client `POST /orders/purchases` (through Nginx).
2. **pet-order** chooses a store (or uses the one you asked for), finds an available pet.
3. **Order of steps (saga):**
   - Save transaction in **mongodb-purchases** first.
   - Then delete the pet from the store via HTTP.
4. If something fails after the save, you avoid “sold” pets still showing in the store without a record (or the reverse).

### 3. List all transactions (owner only)

- `GET /orders/transactions` needs header `OwnerPC` = value of `OWNER_SECRET`.
- Only **pet-order** checks this; stores do not.

---

## Secrets & config

| Secret / setting | Used by | Purpose |
|------------------|---------|---------|
| `NINJA_API_KEY` | pet-store | Animals API enrichment |
| `OWNER_SECRET` | pet-order | Protect transaction list |

**Local Docker:** copy `.env.example` → `.env` and fill values. Docker Compose injects them.

**Kubernetes:** template `k8s/secrets.yaml` has placeholders. For real deploys use your local file `k8s/secret-local.yaml` (gitignored) with real keys, then `kubectl apply -f k8s/secret-local.yaml`.

Non-secret settings (Mongo hostnames, store URLs) live in `k8s/configmap.yaml`.

---

## Folder map (what to open)

| Path | What it is |
|------|------------|
| `pet-store/` | Store API (`pets.py`, `db.py`) |
| `pet-order/` | Order API (`pet_order.py`) |
| `nginx/nginx.conf` | Path routing rules |
| `docker-compose.yml` | Run everything locally |
| `k8s/` | Kubernetes manifests (namespace, mongo, apps, ingress) |
| `tests/assn4_tests.py` | Integration tests against running containers |
| `.github/workflows/assignment4.yml` | CI: build → test → query job |
| `query.txt` | Queries run in the CI “query” job |

---

## Local workflow (step by step)

1. **Secrets:** `cp .env.example .env` and edit.
2. **Build images:**
   ```bash
   docker build -t pet-store:latest ./pet-store
   docker build -t pet-order:latest ./pet-order
   ```
3. **Start stack:** `docker compose up -d`
4. **Use API:** port 80 (Nginx) or direct 5001 / 5002 / 5003.
5. **Test:** `cd tests && pytest -v assn4_tests.py`
6. **Stop:** `docker compose down`

---

## Kubernetes workflow (step by step)

Same apps, packaged for a cluster:

1. `kubectl apply -f k8s/namespace.yaml`
2. `kubectl apply -f k8s/configmap.yaml`
3. Apply secrets (`k8s/secret-local.yaml` locally, not the placeholder template)
4. `kubectl apply -f k8s/mongo.yaml` — MongoDB with persistent disks
5. `kubectl apply -f k8s/pet-store.yaml` — two store deployments
6. `kubectl apply -f k8s/pet-order.yaml`
7. `kubectl apply -f k8s/ingress.yaml` — same path idea as Nginx (`/store1`, `/store2`, `/orders`)

Images must exist on the cluster nodes (or in a registry); manifests use `imagePullPolicy: IfNotPresent`.

---

## CI/CD (GitHub Actions) in one line

On every push: **build** Docker images → **test** (compose up, health checks, pytest) → **query** (load data, run `query.txt`, save `response.txt`).

Images are saved as `.tar` artifacts between jobs so tests use the exact same build.

---

## Mental model (3 sentences)

1. **Two stores** = two databases collections, same code, different `STORE_ID` / `COLLECTION_NAME`.
2. **One order service** talks to both stores and its own purchases database.
3. **Nginx (or Ingress)** is only routing—you always hit the right microservice by URL path.

---

## Quick reference — important ports (Docker)

| What | Port |
|------|------|
| Nginx (main entry) | 80 |
| pet-store1 direct | 5001 |
| pet-store2 direct | 5002 |
| pet-order direct | 5003 |

For more API detail (every endpoint), see `README.md`.

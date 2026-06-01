# Pet Store Microservices

A microservices-based REST API for pet inventory management, containerized with Docker, fronted by Nginx, and fully automated through a GitHub Actions CI/CD pipeline.

---

## Architecture

```
                        External Client
                              │
                           port 80
                              │
                     ┌────────────────┐
                     │     Nginx      │
                     │ (reverse proxy)│
                     └───────┬────────┘
              /store1/*      │      /store2/*      /orders/*
         ┌─────────────┐     │     ┌─────────────┐     ┌─────────────────┐
         │  pet-store1 │     │     │  pet-store2 │     │    pet-order    │
         │   :5001     │     │     │   :5002     │     │     :5003       │
         └──────┬──────┘     │     └──────┬──────┘     └────────┬────────┘
                │            │            │                      │ HTTP
                └────────────┴────────────┘             ┌───────┴───────┐
                             │                           ▼               ▼
                             ▼                    pet-store1      pet-store2
                    ┌─────────────────┐
                    │  mongodb-stores │
                    └─────────────────┘
                    ┌─────────────────────┐
                    │  mongodb-purchases  │
                    └─────────────────────┘
```

All services communicate over an internal Docker bridge network (`petstore-network`). MongoDB ports are never exposed outside the network.

---

## Services

### Pet Store (`pet-store/`)

Manages pet type inventory for a single store instance. Two replicas run as `pet-store1` and `pet-store2`, each backed by its own MongoDB collection. Database access is encapsulated in a `PetStoreDB` class (`db.py`); routes live in `pets.py`.

| Method | Path | Description |
|--------|------|-------------|
| POST | `/pet-types` | Add a new pet type (enriched via Animals API) |
| GET | `/pet-types` | List pet types (filterable by `id`, `type`, `family`, `genus`, `lifespan`, `hasAttribute`) |
| GET | `/pet-types/:id` | Get a specific pet type |
| DELETE | `/pet-types/:id` | Delete a pet type (only if no pets assigned) |
| POST | `/pet-types/:id/pets` | Add a pet to a type |
| GET | `/pet-types/:id/pets` | List pets (filterable by `birthdateGT`, `birthdateLT`) |
| GET | `/pet-types/:id/pets/:name` | Get a specific pet |
| PUT | `/pet-types/:id/pets/:name` | Update a pet |
| DELETE | `/pet-types/:id/pets/:name` | Remove a pet |
| GET | `/health` | Health check |

### Pet Order (`pet-order/`)

Handles purchases across both stores. Randomly selects an available pet if no specific one is requested, saves the transaction first, then removes the pet from store inventory (saga pattern — prevents data loss if either step fails).

Supports any number of stores: add `PET_STORE_N_URL` environment variables and no code changes are needed.

| Method | Path | Description |
|--------|------|-------------|
| POST | `/purchases` | Purchase a pet (optionally specify `store` and `pet-name`) |
| GET | `/transactions` | List all transactions (requires `OwnerPC` header) |
| GET | `/health` | Health check |

---

## Tech Stack

| Technology | Role |
|------------|------|
| **Flask** | REST API framework for both services |
| **MongoDB 6.0** | Persistence — two separate instances (stores and purchases) |
| **Docker** | Containerization — same image runs as multiple store instances |
| **Docker Compose** | Local orchestration, networking, secret injection |
| **Nginx** | Reverse proxy — single entry point on port 80, path-based routing |
| **Kubernetes** | Production manifests in `k8s/` — StatefulSets, PVCs, Ingress |
| **GitHub Actions** | CI/CD pipeline: build → test → query |
| **Pytest** | Integration tests against live containers |

---

## Setup

**Requirements:** Docker, Docker Compose

### 1. Configure secrets

```bash
cp .env.example .env
# Edit .env and fill in:
#   NINJA_API_KEY=your_api_ninjas_key
#   OWNER_SECRET=your_owner_secret
```

### 2. Build images

```bash
docker build -t pet-store:latest ./pet-store
docker build -t pet-order:latest ./pet-order
```

### 3. Start all services

```bash
docker compose up -d
```

Services are available at:

| Service | Direct port | Via Nginx |
|---------|-------------|-----------|
| Pet Store 1 | `http://localhost:5001` | `http://localhost:80/store1/` |
| Pet Store 2 | `http://localhost:5002` | `http://localhost:80/store2/` |
| Pet Order | `http://localhost:5003` | `http://localhost:80/orders/` |

### 4. Run tests

```bash
pip install pytest requests
cd tests && pytest -v assn4_tests.py
```

---

## Environment Variables

| Variable | Service | Description |
|----------|---------|-------------|
| `NINJA_API_KEY` | pet-store | API key for the Animals API — enriches pet types with taxonomy data |
| `OWNER_SECRET` | pet-order | Value for the `OwnerPC` auth header on `GET /transactions` |
| `MONGO_URI` | both | MongoDB connection string |
| `STORE_ID` | pet-store | Store instance identifier (`1` or `2`) |
| `COLLECTION_NAME` | pet-store | MongoDB collection to use (`pet_store_1` or `pet_store_2`) |
| `PET_STORE_N_URL` | pet-order | URL for store N — add more to scale horizontally |

Secrets are loaded from a `.env` file at runtime. See `.env.example` for required values. The `.env` file is gitignored and never committed.

---

## CI/CD Pipeline

The GitHub Actions workflow (`.github/workflows/assignment4.yml`) runs on every push with three sequential jobs:

```
Code Push
    │
    ▼
[build]
  docker build pet-store:latest
  docker build pet-order:latest
  docker save → upload as .tar artifacts
  write log.txt
    │
    ▼
[test]
  docker load artifacts
  docker compose up -d
  poll /health on all services + nginx until ready
  pytest assn4_tests.py (9 integration tests)
  docker compose down
    │
    ▼
[query]
  docker compose up -d
  populate test data
  execute query.txt entries → response.txt
  upload artifacts
```

Images are passed between jobs as `.tar` artifacts — no rebuilding, guaranteed reproducibility.

---

## Kubernetes

Production-ready manifests are in `k8s/`. MongoDB uses `StatefulSet` with `PersistentVolumeClaims` so data survives pod restarts.

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets.yaml   # fill in real values first
kubectl apply -f k8s/mongo.yaml
kubectl apply -f k8s/pet-store.yaml
kubectl apply -f k8s/pet-order.yaml
kubectl apply -f k8s/ingress.yaml
```

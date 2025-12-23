# NGO Automation MVP - Backend

FastAPI backend with PostgreSQL for managing organizations and projects.

## Features

- ✅ RESTful API with 14 endpoints
- ✅ 2 database tables (Organizations, Projects)
- ✅ CRUD operations for both entities
- ✅ Automatic API documentation (Swagger UI)
- ✅ Docker containerization
- ✅ PostgreSQL database with SQLAlchemy ORM
- ✅ Pydantic validation
- ✅ Cascade delete (org → projects)

## Quick Start

### 1. Prerequisites

- Docker Desktop installed
- Git installed

### 2. Setup

```bash
# Clone repository
git clone <your-repo>
cd project1

# Copy environment variables
cp .env.example .env
```

### 3. Run

```bash
# Start containers
docker-compose up --build

# Wait for:
# ✅ PostgreSQL ready
# ✅ Backend started
# ✅ "Uvicorn running on http://0.0.0.0:8000"
```

### 4. Test

Open browser: **http://localhost:8000/docs**

Try these endpoints in order:
1. `GET /health` → Should return `{"status": "ok"}`
2. `POST /organizations` → Create test organization
3. `GET /organizations` → List all organizations
4. `POST /projects` → Create test project
5. `GET /projects` → List all projects

## API Endpoints

### Organizations (5 endpoints)
- `POST /organizations` - Create organization
- `GET /organizations` - List all (paginated)
- `GET /organizations/{id}` - Get one with projects
- `PUT /organizations/{id}` - Update
- `DELETE /organizations/{id}` - Delete (cascade)

### Projects (6 endpoints)
- `POST /projects` - Create project
- `GET /projects` - List all (paginated)
- `GET /projects/{id}` - Get one with organization
- `GET /organizations/{id}/projects` - Get org's projects
- `PUT /projects/{id}` - Update
- `DELETE /projects/{id}` - Delete

### Utilities (3 endpoints)
- `GET /` - API info
- `GET /health` - Health check
- `GET /docs` - Swagger UI

## Project Structure

```
project1/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI app, endpoints
│   ├── models.py        # SQLAlchemy ORM models
│   ├── schemas.py       # Pydantic validators
│   ├── crud.py          # Database operations
│   ├── database.py      # DB connection
│   └── config.py        # Settings
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env
└── README.md
```

## Database Schema

**Organizations Table:**
- id (PK)
- name (unique)
- email (unique)
- country
- description
- is_active
- created_at, updated_at

**Projects Table:**
- id (PK)
- name
- description
- organization_id (FK)
- status
- is_active
- created_at, updated_at

**Relationship:** 1 Organization → Many Projects (cascade delete)

## Technology Stack

- **Backend:** FastAPI 0.109.0
- **Database:** PostgreSQL 15
- **ORM:** SQLAlchemy 2.0.23
- **Validation:** Pydantic 2.5.2
- **Server:** Uvicorn 0.27.0
- **Container:** Docker + docker-compose

## Development

### Run locally (without Docker)

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start PostgreSQL (separate terminal)
# Update DATABASE_URL in .env to localhost

# Run server
uvicorn app.main:app --reload
```

### Stop containers

```bash
docker-compose down

# Remove volumes (deletes data!)
docker-compose down -v
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Port 8000 in use | `docker-compose down`, change port |
| Database error | `docker-compose down -v`, rebuild |
| Swagger not loading | Check logs: `docker-compose logs backend` |

## Documentation

- [API Reference](docs/API.md) - Complete REST API documentation
- [Deployment Guide](docs/DEPLOYMENT.md) - Production deployment instructions

## Next Steps

- [ ] Add authentication (JWT) - Phase 2
- [ ] Add tests (pytest) - Phase 2
- [ ] Add filtering/search - Phase 2
- [ ] Deploy to production - Phase 2
- [ ] Add RAG Copilot (embeddings, vector search, LLM queries) - Phase 3

## License

MIT

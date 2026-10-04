.PHONY: help install backend frontend seed test clean docker docker-down reset

help:
	@echo "Contract Lifecycle & Approval Management"
	@echo ""
	@echo "Targets:"
	@echo "  install      Install backend + frontend deps"
	@echo "  backend      Run FastAPI backend on :8000"
	@echo "  frontend     Run Next.js frontend on :3000"
	@echo "  seed         Seed demo data"
	@echo "  test         Run backend tests"
	@echo "  migrate      Apply Alembic migrations"
	@echo "  docker       Start full stack via docker compose"
	@echo "  docker-down  Stop the stack"
	@echo "  reset        Drop all data and rebuild (DESTRUCTIVE)"
	@echo "  worker       Start the Celery worker"
	@echo "  beat         Start the Celery beat scheduler"

install:
	cd backend && python -m pip install -r requirements.txt
	cd frontend && npm install --legacy-peer-deps

migrate:
	cd backend && alembic upgrade head

seed:
	cd backend && python scripts/seed.py

backend:
	cd backend && uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

worker:
	cd backend && celery -A app.workers.celery_app.celery_app worker --loglevel=info -Q contracts

beat:
	cd backend && celery -A app.workers.celery_app.celery_app beat --loglevel=info

test:
	cd backend && python -m pytest tests/ -v

docker:
	docker compose up --build

docker-down:
	docker compose down

reset:
	docker compose down -v
	docker compose up --build

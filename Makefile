.PHONY: help dev-backend dev-frontend test lint install-backend install-frontend docker-build docker-up docker-down

help:
	@echo "Available targets:"
	@echo "  make dev-backend   - Run the FastAPI backend with uvicorn reload on port 8000"
	@echo "  make dev-frontend  - Run Vite development server on port 5173"
	@echo "  make test          - Run backend unit tests with pytest"
	@echo "  make lint          - Lint backend with ruff and frontend with typescript"
	@echo "  make install       - Install backend and frontend dependencies"
	@echo "  make docker-build  - Build Docker containers"
	@echo "  make docker-up     - Start Docker containers in detached mode"
	@echo "  make docker-down   - Stop and remove Docker containers"

dev-backend:
	python -m uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && npm run dev

test:
	python -m pytest backend/tests

lint:
	python -m ruff check backend
	cd frontend && npm run lint

install-backend:
	python -m pip install -r backend/requirements.txt

install-frontend:
	cd frontend && npm install

install: install-backend install-frontend

docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down

.PHONY: dev dev-backend dev-frontend docker-dev test

dev:
	bash scripts/dev.sh

dev-backend:
	venv/bin/python -m uvicorn architect.api_server:app --host 127.0.0.1 --port 8000

dev-frontend:
	cd frontend && npm run dev -- --host 127.0.0.1 --port 5173

docker-dev:
	docker compose up --build

test:
	venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v

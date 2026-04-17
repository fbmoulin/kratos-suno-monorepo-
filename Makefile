.PHONY: help dev test lint build clean prompt-lab install

help:
	@echo "Kratos Suno Prompt - comandos disponíveis:"
	@echo ""
	@echo "  make install      - Instala dependências backend + frontend"
	@echo "  make dev          - Sobe tudo via docker-compose"
	@echo "  make test         - Roda testes do backend"
	@echo "  make lint         - Roda ruff no backend"
	@echo "  make prompt-lab   - Roda Prompt Lab (A/B testing)"
	@echo "  make clean        - Remove artifacts"
	@echo ""

install:
	cd backend && pip install -r requirements.txt
	cd frontend && npm install

dev:
	docker compose -f docker-compose.dev.yml up --build

dev-detached:
	docker compose -f docker-compose.dev.yml up --build -d

dev-stop:
	docker compose -f docker-compose.dev.yml down

test:
	cd backend && pytest tests/ -v

test-cov:
	cd backend && pytest tests/ --cov=app --cov-report=html

lint:
	cd backend && ruff check app/ tests/

lint-fix:
	cd backend && ruff check --fix app/ tests/

prompt-lab:
	cd backend && python -m prompt_lab.run \
		--prompts v1_baseline \
		--test-cases prompt_lab/test_cases/artists.json \
		--output prompt_lab/results/

prompt-lab-interactive:
	cd backend && python -m prompt_lab.run --prompts v1_baseline --interactive

build-frontend:
	cd frontend && npm run build

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name node_modules -exec rm -rf {} + 2>/dev/null || true
	rm -rf backend/prompt_lab/results/*.json backend/prompt_lab/results/*.csv 2>/dev/null || true

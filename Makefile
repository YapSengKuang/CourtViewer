.PHONY: up down migrate seed test crawl api

up:
	docker compose up -d

down:
	docker compose down

migrate:
	alembic -c db/alembic.ini upgrade head

seed:
	python -m golfdb.seed

test:
	cd db && pytest
	cd scraper && pytest
	cd api && pytest

crawl:
	cd scraper && scrapy crawl example_platform

api:
	uvicorn tee_api.main:app --reload --port 8000

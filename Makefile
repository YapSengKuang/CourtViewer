.PHONY: up down migrate seed test crawl

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

crawl:
	cd scraper && scrapy crawl example_platform

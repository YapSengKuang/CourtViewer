.PHONY: up down migrate seed test

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

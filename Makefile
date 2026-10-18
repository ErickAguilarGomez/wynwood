.PHONY: up down logs seed test lint check observability

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f web worker

seed:
	docker compose exec web python manage.py seed_demo --refresh-images

test:
	docker compose run --rm --entrypoint python web manage.py test

lint:
	.venv/bin/ruff check accounts bookings config core observability payments properties

check:
	DJANGO_SECRET_KEY=$$(openssl rand -hex 32) docker compose run --rm --entrypoint python -e DJANGO_DEBUG=False -e DJANGO_SECURE_SSL_REDIRECT=True -e DJANGO_SECRET_KEY web manage.py check --deploy

observability:
	docker compose -f compose.yaml -f compose.observability.yaml up -d

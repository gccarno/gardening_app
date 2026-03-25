.PHONY: run install lint test

install:
	uv sync

run:
	FLASK_APP=apps/api/wsgi.py FLASK_DEBUG=1 uv run flask run

lint:
	uv run ruff check .

test:
	uv run pytest

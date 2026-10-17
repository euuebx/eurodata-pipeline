.PHONY: install run-api ingest test lint
install:
	python -m pip install -e '.[dev]'
run-api:
	uvicorn eurodata_pipeline.api:app --reload
ingest:
	python -m eurodata_pipeline.cli --verbose
test:
	pytest -q
lint:
	ruff check src tests

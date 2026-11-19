.PHONY: demo api test ingest clean benchmark golden openapi

demo:
	python scripts/build_sample.py
	python -m app.api.main

api:
	python -m app.api.main

test:
	pytest -q

ingest:
	python -m app.ingest.cli

clean:
	rm -f mf.db

benchmark:
	python scripts/benchmark_api.py

golden:
	python scripts/golden_validation.py

openapi:
	python scripts/export_openapi.py

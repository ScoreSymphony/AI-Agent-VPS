.PHONY: validate validate-deployment test quality compose-check check-upstreams

validate:
	python scripts/validate_baseline.py

validate-deployment:
	python scripts/validate_deployment.py

test:
	pytest -q

compose-check:
	docker compose --profile upstream-smoke config --quiet

quality: validate validate-deployment test

check-upstreams:
	python scripts/upstream/check_updates.py

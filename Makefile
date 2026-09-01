.PHONY: validate test check-upstreams

validate:
	python scripts/validate_baseline.py

test:
	pytest

check-upstreams:
	python scripts/upstream/check_updates.py

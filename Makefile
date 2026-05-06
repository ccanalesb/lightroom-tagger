.PHONY: dev dev-down check-core-sizes

check-core-sizes:
	bash scripts/check_core_file_sizes.sh

dev:
	bash ./scripts/dev-down.sh || true
	bash ./scripts/dev-up.sh

dev-down:
	bash ./scripts/dev-down.sh


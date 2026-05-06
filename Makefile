.PHONY: validate validate-registry validate-governance-console

validate: validate-registry validate-governance-console

validate-registry:
	python3 scripts/validate_prototype_studio.py --repo-root .

validate-governance-console:
	npm --prefix apps/governance-operations-console run check

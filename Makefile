.PHONY: test validate validate-registry validate-governance-console-architecture

validate: test validate-registry validate-governance-console-architecture

test:
	python3 -m unittest discover -s tests

validate-registry:
	python3 scripts/validate_prototype_studio.py --repo-root .

validate-governance-console-architecture:
	python3 scripts/validate_governance_console_architecture.py

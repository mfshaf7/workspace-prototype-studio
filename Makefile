.PHONY: test validate validate-registry validate-landing validate-maturity validate-closure validate-governance-console-architecture

validate: test validate-registry validate-landing validate-maturity validate-closure validate-governance-console-architecture

test:
	python3 -m unittest discover -s tests

validate-registry:
	python3 scripts/validate_prototype_studio.py --repo-root .

validate-landing:
	python3 scripts/prototype_landing.py --repo-root . validate-all

validate-maturity:
	python3 scripts/prototype_maturity.py --repo-root . validate-all

validate-closure:
	python3 scripts/prototype_closure.py --repo-root . validate-all

validate-governance-console-architecture:
	python3 scripts/validate_governance_console_architecture.py

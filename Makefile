
.PHONY: docs

test:
	pytest tests --cov evm_contract_exporter --cov-report term-missing -s

docs:
	rm -r ./docs/source -f
	rm -r ./docs/_templates -f
	rm -r ./docs/_build -f
	sphinx-apidoc -o ./docs/source ./evm_contract_exporter

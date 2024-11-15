lint:
	ruff check .
	mypy .

test:
	pytest tests

test_cov:
	pytest --cov=pvm --cov-report=html tests
	python -m http.server 8000 --directory htmlcov

install_hooks:
	git config core.hooksPath .githooks
	chmod +x .githooks/*

setup: install_hooks
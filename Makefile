lint:
	ruff check .
	ruff format .
	ty check
	mypy .
test:
	pytest tests

test_cov:
	pytest --cov=pvm --cov-report=html tests
	
show_coverage:
	pytest --cov=pvm --cov-report=html tests
	python -m http.server 8000 --directory htmlcov

install_hooks:
	git config core.hooksPath .githooks
	chmod +x .githooks/*

clear_cache:
	python -c "from datasets.cache import clear_cache; clear_cache()"

download_olist:
	mkdir -p src/datasets/olist/raw
	uvx --from kaggle kaggle datasets download -d olistbr/brazilian-ecommerce -p src/datasets/olist/raw --unzip
	uv run python -m datasets.build_olist

setup: install_hooks
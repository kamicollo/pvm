test_cov:
	pytest --cov=pvm --cov-report=html tests
	python -m http.server 8000 --directory htmlcov
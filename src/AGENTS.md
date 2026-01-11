## Code rules

This repository should use best pythonic practices in its code, including fully typed code. Upon making changes to code, always use
* `make lint` to ensure code meets quality requirements. We use `ruff`, `mypy` and `ty` for linting.
* `make test` to run all unit tests. We use `pytest` for tests.
*  Ensure test coverage (use `make test_cov` to generate latest coverage information or rely on built-in VS code tools)

## High-level repository structure

The repository is organized as follows:

* `src/` - Main source code directory
    * `pvm/` - Core package containing the main application logic
* `tests/` - Test suite with unit and integration tests
* `docs/` - Documentation files
* `Makefile` - Build automation with common tasks (lint, test, etc.)
* `pyproject.toml` - Python project configuration and dependencies
* `README.md` - Project overview and getting started guide
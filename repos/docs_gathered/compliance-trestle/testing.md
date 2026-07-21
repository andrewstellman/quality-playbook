# Testing Conventions

Trestle's test suite is organized under `tests/` and uses pytest as the test runner, with parallel execution via `pytest-xdist` and random ordering via `pytest-randomly`.

## Test Directory Layout

```
tests/
  __init__.py
  conftest.py              # Shared pytest fixtures and configuration
  test_utils.py            # Helper utilities shared across tests
  trestle/
    __init__.py
    cli_test.py            # Integration tests for the top-level CLI
    main_test.py           # Entry-point tests
    core/
      __init__.py
      base_model_test.py
      control_io_test.py
      crm/                 # CRM subsystem tests
      draw_io_test.py
      err_test.py
      generator_test.py
      jinja/               # Jinja authoring tests
      markdown/            # Markdown processing tests
      models/              # Action/element/plan tests
      parser_test.py
      profile_resolver_test.py
      remote/              # Remote cache tests
      repository_test.py
      ssp_io_test.py
      utils_test.py
      valid_values_test.py
      validator_helper_test.py
      commands/            # Per-command integration tests
    misc/                  # Miscellaneous tests
    parsing/               # Parsing tests
    tasks/                 # Task tests (one subdirectory per task)
    transforms/            # Transformer tests
    utils/                 # Utility tests
  data/                    # Test fixture data (OSCAL JSON/YAML files, markdown, drawio)
  functionality/           # Functional/integration tests
  manual_tests/            # Tests that require manual setup or external services
```

## pytest Configuration

`pyproject.toml` defines:

```toml
[tool.pytest.ini_options]
minversion = "6.2"
testpaths = ["tests"]
```

The `hatch-test` environment adds:

```toml
parallel = true
randomize = true
```

so `hatch test` runs the suite with `-n auto` (parallel workers) and random ordering. The `[[tool.hatch.envs.hatch-test.matrix]]` section defines a matrix over `python = ["3.10", "3.11", "3.12"]`, so `hatch test` can run against multiple Python versions.

## conftest.py and Fixtures

`tests/conftest.py` provides shared fixtures. Key patterns used across the test suite:

- **Temporary trestle workspace**: most tests that exercise commands or the repository API create a temporary directory, call `trestle init`, and work within it. The `tmp_path` fixture from pytest provides an isolated directory per test.
- **Sample OSCAL models**: fixtures load JSON/YAML files from `tests/data/` using `load_validate_model_path` or `ModelUtils.load_distributed` to obtain in-memory OSCAL model objects.
- **Mocking remote resources**: tests for the remote cache subsystem patch `requests.get` or `paramiko` to avoid network access.

## Test Data

`tests/data/` contains a corpus of OSCAL JSON and YAML files, markdown templates, and drawio fixtures. These cover all eight OSCAL model types, valid and intentionally invalid variants, split and unsplit forms, and various markdown template formats. Test tasks and transformers have corresponding data directories under `tests/trestle/tasks/`.

## Test Conventions

- Tests are named `<module>_test.py` (trestle follows the `<name>_test` suffix convention, not the `test_<name>` prefix).
- Each test file imports only from `trestle.*` public APIs unless testing internal behavior explicitly.
- `assert` is used freely in tests (Ruff rule S101 is ignored in `tests/**/*.py`).
- Hardcoded test credentials in test data files are accepted (S105/S106 ignored in tests).
- Temporary file paths are accepted (S108 ignored in tests).
- Tests that exercise the plugin discovery path are marked with `# pragma: nocover` comments where the plugin path cannot be activated in the core test suite (plugins must be separately installed packages).

## Coverage

Coverage is measured with `coverage[toml]` and reported via SonarCloud. The `[tool.coverage.run]` section enables `relative_files = true` for compatible path reporting in CI. The `hatch test` command collects coverage automatically when run via `hatch test --cover`.

## Linting and Static Analysis

The `hatch-static-analysis` environment sets `config-path = "none"`, delegating static analysis to Ruff (configured in `[tool.ruff]`). The `trestle/oscal/` directory is excluded from Ruff to avoid linting generated code. Type checking uses mypy with the `pydantic.mypy` plugin; the `[[tool.mypy.overrides]]` section disables mypy errors in `trestle.oscal.*` for the same reason.

Pre-commit hooks (configured via `.pre-commit-config.yaml`) enforce formatting and linting before commits. The CI workflow (`python-test.yml`) runs the full test suite and coverage reporting on every pull request.

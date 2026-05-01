# Repository Guidelines

## Project Structure & Module Organization

This repository contains a FastAPI demo service and an AutoFix agent workflow.

- `web_service/` contains the application code. `app.py` builds the FastAPI app, `api/routes/` defines HTTP endpoints, `services/` holds business logic, `repositories/` holds data access, and `core/` contains config, logging, and error handling.
- `agent/` contains the CLI workflow, LLM client, prompts, fix-record writer, and tool modules under `agent/tools/`.
- `tests/` contains pytest acceptance tests for the service.
- `scripts/trigger_bug.py` reproduces known demo failures.
- `logs/` and `fix_records/` are runtime output locations. Do not commit local logs or generated records unless intentionally documenting a run.

## Build, Test, and Development Commands

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Run the API locally:

```bash
python -m uvicorn web_service.app:app --reload
```

Run the full test suite:

```bash
python -m pytest tests/
```

Trigger demo failures after the server is running:

```bash
python scripts/trigger_bug.py divide
python scripts/trigger_bug.py user
```

Run the AutoFix workflow:

```bash
python -m agent.main --max-attempts 3
```

## Coding Style & Naming Conventions

Use Python 3 with 4-space indentation and type annotations for new or changed functions. Keep modules focused by layer: route handlers should stay thin, service modules should own business rules, and repository modules should isolate data access. Use `snake_case` for functions, variables, modules, and test names. Prefer explicit imports from local packages, as seen in `tests/test_service.py`.

## Testing Guidelines

Tests use `pytest`, `pytest.anyio`, and `httpx.AsyncClient` against the ASGI app. Add tests in `tests/` with names matching `test_*.py` and functions named `test_<behavior>`. For API fixes, assert both status code and response JSON. Run `python -m pytest tests/` before submitting changes. Targeted tests may be run with pytest node IDs, for example:

```bash
python -m pytest tests/test_service.py::test_user_not_found_should_return_404
```

## Commit & Pull Request Guidelines

Recent history uses short imperative or descriptive commit messages, sometimes in Chinese, such as `complete first version of six tools` or `修复pytest路径查询失败的问题`. Keep commits focused and describe the behavior changed.

Pull requests should include a concise summary, test results, linked issue or bug context when applicable, and screenshots or log excerpts only when they clarify runtime behavior. Never include `.env`, tokens, or private webhook URLs.

## Security & Configuration Tips

Copy `.env.example` to `.env` for local credentials. Keep `.env` local and avoid printing secrets in logs, fix records, PR descriptions, or test output.

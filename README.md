# AutoFix Agent Demo

Stage 1 web target for the Feishu AI campus challenge.

## Structure

```text
web_service/
  app.py                    # FastAPI application factory
  api/
    router.py               # API router composition
    routes/                 # HTTP endpoint layer
  core/
    config.py               # Shared paths and service constants
    error_handlers.py       # Structured exception logging
    logging.py              # Error-log logger setup
  repositories/             # In-memory data access for demo cases
  services/                 # Business logic intentionally containing bugs
tests/
  test_service.py           # Repair acceptance tests
scripts/
  trigger_bug.py            # Demo helper for triggering bug cases
```

## Run the service

```bash
uvicorn web_service.app:app --reload
```

## Trigger bugs

```bash
curl 'http://127.0.0.1:8000/divide?a=10&b=0'
curl 'http://127.0.0.1:8000/users/999'
```

Runtime exceptions are written to `logs/error.log` as structured bug blocks.

## Run tests

```bash
pytest tests/
```

The initial service intentionally fails the two bug-case tests. The AutoFix
Agent should repair the service until all tests pass.

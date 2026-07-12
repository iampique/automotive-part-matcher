# Contributing

Thanks for your interest in improving Automotive Connector Matcher.

## Getting started

1. Fork and clone the repository.
2. Follow the [setup guide](docs/setup.md) to run backend and frontend locally.
3. Copy `backend/.env.example` → `backend/.env` and fill in your own keys. **Never commit `.env` files or API keys.**

## Development workflow

- Create a branch for your change.
- Prefer small, focused pull requests.
- Match existing code style in `backend/` and `frontend/`.
- Update docs when behavior or setup steps change.

## Tests

From `backend/` with the virtualenv active:

```bash
pytest tests/ -v
```

Neo4j integration tests need `NEO4J_URI` and `NEO4J_PASSWORD` set; see [docs/testing.md](docs/testing.md).

## Pull requests

- Describe what changed and why.
- Note any new env vars or migration steps.
- Confirm no secrets, credentials, or personal machine paths are included.

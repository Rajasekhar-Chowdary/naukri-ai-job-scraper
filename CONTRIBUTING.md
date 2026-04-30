# Contributing to Dream Hunt

Thank you for your interest in contributing!

## Development Setup

1. Fork the repo and clone it
2. Install dependencies: `pip install -r requirements.txt`
3. Install pre-commit hooks: `pre-commit install`
4. Copy config: `cp config/profile_config.example.json config/profile_config.json`
5. Run tests: `pytest tests/ -v`

## Git Workflow

We follow a standard Git Flow:

```
main    → production releases (protected)
develop → integration branch
feature/* → new features
fix/*   → bug fixes
```

1. Create a feature branch from `develop`
2. Make your changes
3. Run `pytest`, `black`, `flake8`, `mypy`
4. Open a PR to `develop`
5. After review, it merges to `develop`
6. Releases are merged from `develop` → `main`

## Code Standards

- **Black** for formatting (line length 120)
- **isort** for import sorting
- **flake8** for linting
- **mypy** for type checking (optional but preferred)
- All new code must have tests

## Security

- NEVER commit `config/profile_config.json` (it's gitignored)
- NEVER commit secrets, API keys, or passwords
- Use environment variables from `.env` for sensitive config
- Run `bandit -r src/` before submitting PRs

## Questions?

Open an issue or start a discussion.

# Contributing

Thanks for your interest in improving `async-scrapekit`.

By participating, you agree to uphold our [Code of Conduct](CODE_OF_CONDUCT.md).

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Checks before opening a PR

```bash
ruff check src tests examples
pytest
```

## Guidelines

1. **Ethics first** — do not add features that bypass robots.txt by default,
   rotate proxies to evade blocks, solve CAPTCHAs, or defeat auth/anti-abuse.
2. Keep the public API typed and documented.
3. Prefer unit tests with `respx` / `httpx` mocks; never require live network in CI.
4. Match existing module boundaries (`client`, `robots`, `rate_limit`, `retry`, etc.).

## Commit style

Use clear, imperative subjects, for example:

- `Add per-host crawl-delay awareness`
- `Fix JSONL append mode creating empty parent dirs`

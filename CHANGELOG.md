# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-09-04

Initial public portfolio release of **async-scrapekit** — a polite, typed async scraping toolkit.

### Added

- `AsyncScrapeClient` context manager on top of `httpx.AsyncClient`
- robots.txt evaluation via `urllib.robotparser` (default on; opt-out only with `allow_disallowed=True`)
- Per-host rate limiting (concurrency + requests-per-second)
- Retries with exponential backoff and full jitter for transient network/HTTP failures
- BeautifulSoup helpers for title, text, links, and CSS field extraction
- JSONL and CSV export helpers for structured pipelines
- pydantic-settings configuration (`SCRAPEKIT_*` env vars) with honest default User-Agent
- Demo CLI (`scrapekit`) with host allowlist (`httpbin.org`, `example.com`) and Rich optional output
- Typed public API + `py.typed` marker
- Offline fixture example plus optional live httpbin demo
- GitHub Actions CI (ruff + pytest, no live network; respx mocks)
- Community hygiene: MIT license, CONTRIBUTING, SECURITY, Code of Conduct

### Security

- Defaults favor authorized, robots-respecting collection
- Intentionally omits proxy rotation for evasion, CAPTCHA bypass, and auth circumvention

# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `Settings.max_response_bytes` (default 10 MiB) and `ResponseTooLargeError` so
  oversized scrape responses are rejected instead of loaded into extraction.
- Config tests for boolean and numeric `SCRAPEKIT_*` environment overrides.
- Robots edge tests for HTTP 5xx fail-open, per-origin parser cache, and missing crawl-delay.
- Extract tests for title fallback to headings and skipping `mailto:` / `javascript:` links.
- Extract tests for skipping `data:` / `vbscript:` / `tel:` href schemes (case-insensitive).
- Retry tests for 408/425/502/504 statuses, timeout/protocol exceptions, non-transient re-raise,
  persistent retryable-result exhaustion, `RetryExhaustedError.last_exception`, and `on_retry`.
- SSRF offline coverage for IPv6 loopback/ULA/link-local, `*.localhost`, and URL userinfo rejection.

### Changed

- Linked the changelog from the README so release history is easy to find.
- Clarified that polite defaults (robots + per-host limits) are the production path, not optional niceties.
- Documented secrets / `.env` handling in `SECURITY.md` and tightened `.env.example` guidance.

### Security

- Cap response bodies at `max_response_bytes` (Content-Length and loaded body),
  documented in `SECURITY.md` and `.env.example`.
- Demo CLI allowlist now requires `http`/`https`, compares hostname (ports OK), and rejects
  null bytes plus non-HTTP schemes (`file://`, `ftp://`, etc.) before any fetch.
- `AsyncScrapeClient` blocks loopback, private, link-local, and cloud-metadata hosts by
  default (`block_private_hosts=True`), including redirect targets via an httpx request
  hook. Opt out only for intentional intranet scrapes.
- SSRF checks also reject URL userinfo and treat `metadata.goog` as a blocked hostname.
- `extract_links` skips `data:`, `vbscript:`, and `tel:` hrefs (plus existing `javascript:` /
  `mailto:`) so those schemes do not appear in exported link lists.
- `to_csv` neutralizes spreadsheet formula prefixes (`=`, `+`, `-`, `@`, tab, CR) in
  string cells by prefixing `'`, so scraped text cannot run as a formula when the
  export is opened in Excel or Sheets. Opt out with `escape_formulas=False`.

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

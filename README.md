# async-scrapekit

**A small, serious async scraping toolkit** that demonstrates production judgment: polite defaults, typed APIs, and zero "evasion" features.

Built for portfolio review by [muhammad-a-dev](https://github.com/muhammad-a-dev) — showing how an Upwork-oriented Python engineer approaches scraping that agencies can trust.

> **Ethics (read this first)**  
> Only scrape sites you are **authorized** to scrape. Respect `robots.txt`, Terms of Service, and rate limits.  
> Do **not** bypass CAPTCHAs, authentication, paywalls, or anti-abuse systems.  
> This library's **default behavior respects robots.txt and per-host rate limits**.  
> It intentionally does **not** provide proxy rotation for evasion, CAPTCHA bypass, or auth bypass.

---

## Problem

Most scraping snippets on the internet optimize for "get the HTML at all costs." In real client work that creates legal and operational risk: ignored robots rules, stampeded origin servers, brittle retries, and undocumented User-Agents.

Agencies need the opposite: a **small toolkit** that makes the polite path the easy path.

## Solution

`async-scrapekit` wraps [`httpx.AsyncClient`](https://www.python-httpx.org/) with:

| Concern | Behavior |
| --- | --- |
| robots.txt | Evaluated via `urllib.robotparser` before each fetch |
| Opt-out | Disallowed URLs only if you pass `allow_disallowed=True` explicitly |
| Rate limits | Per-host concurrency + requests-per-second |
| Retries | Exponential backoff **with full jitter** for transient errors |
| Identity | Configurable User-Agent via env / `pydantic-settings` |
| Extraction | BeautifulSoup helpers for title, text, links, CSS fields |
| Export | JSONL and CSV writers for structured pipelines |
| CLI | Allowlisted demo crawl/export entrypoint |

## Features

- Async-first `AsyncScrapeClient` context manager
- Structured logging (`scrapekit.*` loggers)
- Typed public API + `py.typed`
- Settings from environment (`SCRAPEKIT_*`) or constructor overrides
- `fetch`, `fetch_many`, and `scrape` (fetch + extract)
- Retry on network/timeouts and HTTP 408/425/429/5xx
- Optional Rich-powered CLI (`pip install async-scrapekit[cli]`)

## Architecture

```
src/scrapekit/
  client.py       # AsyncScrapeClient orchestration
  robots.py       # robots.txt cache + can_fetch
  rate_limit.py   # per-host semaphore + spacing
  retry.py        # backoff + jitter helpers
  extract.py      # BeautifulSoup extraction
  export.py       # JSONL / CSV
  config.py       # pydantic-settings
  cli.py          # demo CLI (allowlisted hosts)
```

Request path:

1. Resolve settings (UA, limits, retries).
2. If `respect_robots` (default): load/cache robots.txt → deny unless allowed or `allow_disallowed=True`.
3. Acquire per-host rate-limit slot.
4. Perform HTTP request via httpx; retry transient failures.
5. Optionally parse HTML and export records.

## Install

```bash
# from a clone / local checkout
pip install -e ".[dev]"

# CLI extras (Rich)
pip install -e ".[cli]"
```

Python **3.11+** required.

## Quick start

```python
import asyncio
from scrapekit import AsyncScrapeClient, get_settings, to_jsonl

async def main() -> None:
    settings = get_settings(
        user_agent="MyAuthorizedBot/1.0 (+https://example.com/bot)",
        requests_per_second=1.0,
        max_concurrency_per_host=2,
    )
    async with AsyncScrapeClient(settings) as client:
        # Only use URLs you are authorized to scrape.
        page = await client.scrape(
            "https://example.com/",
            css_fields={"heading": "h1"},
        )
    to_jsonl([page], "out.jsonl")
    print(page.title, page.selected)

asyncio.run(main())
```

### Offline example (no network)

```bash
python examples/basic_usage.py
```

### Live httpbin demo (network)

```bash
python examples/basic_usage.py --live
```

### CLI

```bash
scrapekit https://httpbin.org/html -o page.jsonl --css heading=h1
```

The demo CLI only permits an allowlist (`httpbin.org`, `example.com`) unless you add `--allow-host`. Adding a host does **not** bypass robots.txt and does **not** grant legal permission — you must already be authorized.

To explicitly ignore a robots disallow (rare, authorized cases only):

```bash
scrapekit https://example.com/path --allow-disallowed
```

## Configuration

| Setting | Env var | Default |
| --- | --- | --- |
| User-Agent | `SCRAPEKIT_USER_AGENT` | `async-scrapekit/0.1 (+…)` |
| Concurrency / host | `SCRAPEKIT_MAX_CONCURRENCY_PER_HOST` | `2` |
| RPS / host | `SCRAPEKIT_REQUESTS_PER_SECOND` | `1.0` |
| Retries | `SCRAPEKIT_MAX_RETRIES` | `3` |
| Backoff base / cap | `SCRAPEKIT_BACKOFF_BASE` / `_CAP` | `0.5` / `30` |
| Timeout | `SCRAPEKIT_TIMEOUT` | `30` |
| Respect robots | `SCRAPEKIT_RESPECT_ROBOTS` | `true` |
| Allow disallowed | `SCRAPEKIT_ALLOW_DISALLOWED` | `false` |
| Log level | `SCRAPEKIT_LOG_LEVEL` | `INFO` |

See [`.env.example`](.env.example).

## Ethics & legal

This project is a **toolkit for authorized collection**, not a weapon for unauthorized scraping.

**You must:**

- Confirm you have the right to access the target (contract, ToS, robots, local law).
- Keep rate limits conservative; prefer site-provided APIs when available.
- Identify your bot with an honest User-Agent and contact URL when appropriate.

**This project will not add:**

- Proxy pools marketed for block evasion
- CAPTCHA solvers / anti-bot bypass
- Session/auth circumvention helpers

`allow_disallowed=True` exists for controlled environments (e.g., you own the site and robots is overly strict). It is an explicit foot-gun, logged as a warning, and defaults to **off**.

## Testing

CI runs **ruff** + **pytest** with **no live network** (httpx mocked via [respx](https://lundberg.github.io/respx/)).

```bash
pip install -e ".[dev]"
ruff check src tests examples
pytest -q
```

## License

[MIT](LICENSE) © Muhammad Ali

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).

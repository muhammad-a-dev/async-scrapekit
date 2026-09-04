"""Basic usage example for async-scrapekit.

This script demonstrates the public API. By default it runs an *offline*
demo that uses recorded HTML (no network). Pass ``--live`` to fetch from
httpbin.org — only do that if you are allowed to access that host.

Ethics reminder: only scrape sites you are authorized to scrape. Respect
robots.txt, Terms of Service, and rate limits. Do not bypass CAPTCHAs,
authentication, or anti-abuse systems.
"""

from __future__ import annotations

import argparse
import asyncio
import tempfile
from pathlib import Path

from scrapekit import AsyncScrapeClient, extract_page, get_settings, to_csv, to_jsonl

SAMPLE_HTML = """
<!doctype html>
<html>
  <head>
    <title>Offline Demo</title>
    <meta name="description" content="No network required">
  </head>
  <body>
    <h1>async-scrapekit</h1>
    <p>Polite async scraping toolkit.</p>
    <a href="/docs">Docs</a>
  </body>
</html>
"""


async def offline_demo() -> None:
    page = extract_page(
        SAMPLE_HTML,
        url="https://example.com/offline",
        css_fields={"heading": "h1"},
    )
    with tempfile.TemporaryDirectory() as tmp:
        jsonl_path = Path(tmp) / "demo.jsonl"
        csv_path = Path(tmp) / "demo.csv"
        to_jsonl([page], jsonl_path)
        to_csv([page.to_dict()], csv_path)
        print(f"Offline extract title={page.title!r} heading={page.selected['heading']}")
        print(f"Wrote {jsonl_path.name} and {csv_path.name}")


async def live_httpbin_demo() -> None:
    """Fetch https://httpbin.org/html with polite defaults.

    httpbin is commonly used for HTTP client demos. Still: only run this
    if network access is appropriate in your environment.
    """
    settings = get_settings(
        user_agent="async-scrapekit-example/0.1 (+https://github.com/muhammad-a-dev/async-scrapekit)",
        requests_per_second=1.0,
        max_concurrency_per_host=1,
    )
    async with AsyncScrapeClient(settings) as client:
        page = await client.scrape(
            "https://httpbin.org/html",
            css_fields={"heading": "h1"},
        )
    print(f"Live fetch title={page.title!r} selected={page.selected}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live",
        action="store_true",
        help="Fetch httpbin.org (requires network). Default is offline-only.",
    )
    args = parser.parse_args()
    if args.live:
        asyncio.run(live_httpbin_demo())
    else:
        asyncio.run(offline_demo())


if __name__ == "__main__":
    main()

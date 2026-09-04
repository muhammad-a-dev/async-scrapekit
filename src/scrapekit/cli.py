"""Command-line entrypoint for simple crawl/export demos.

Users must only scrape sites they are authorized to access.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from urllib.parse import urlparse

from scrapekit.client import AsyncScrapeClient, RobotsDisallowedError
from scrapekit.config import get_settings
from scrapekit.export import to_csv, to_jsonl

logger = logging.getLogger(__name__)

# Hard allowlist for the demo CLI — only these hosts may be targeted.
# Users building custom crawlers should enforce their own authorization checks.
DEFAULT_ALLOWLIST = frozenset(
    {
        "httpbin.org",
        "www.httpbin.org",
        "example.com",
        "www.example.com",
    }
)


def _host_allowed(url: str, allowlist: frozenset[str]) -> bool:
    host = urlparse(url).netloc.lower()
    if not host:
        return False
    return host in allowlist


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scrapekit",
        description=(
            "async-scrapekit demo CLI. Only scrape sites you are authorized to. "
            "Respects robots.txt and rate limits by default."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  scrapekit https://httpbin.org/html -o page.jsonl --css heading=h1\n"
            "  scrapekit https://example.com/ -o page.csv --format csv -v\n"
            "  scrapekit https://example.com/path --allow-disallowed  # authorized only"
        ),
    )
    parser.add_argument(
        "url",
        help="Target URL (must be on the demo allowlist unless --allow-host is used carefully).",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="output.jsonl",
        help="Output path (.jsonl or .csv).",
    )
    parser.add_argument(
        "--format",
        choices=("jsonl", "csv"),
        default=None,
        help="Export format (inferred from --output suffix if omitted).",
    )
    parser.add_argument(
        "--css",
        action="append",
        default=[],
        metavar="NAME=SELECTOR",
        help="CSS field extraction, e.g. --css title=h1 --css links=a",
    )
    parser.add_argument(
        "--allow-host",
        action="append",
        default=[],
        help=(
            "Add a host to the demo allowlist. You must still be legally authorized "
            "to scrape that host. Does NOT bypass robots.txt."
        ),
    )
    parser.add_argument(
        "--allow-disallowed",
        action="store_true",
        default=False,
        help=(
            "Explicitly allow URLs disallowed by robots.txt. "
            "Only use if you have authorization to ignore robots.txt."
        ),
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable DEBUG logging.",
    )
    return parser


def _parse_css_fields(raw: list[str]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for item in raw:
        if "=" not in item:
            raise SystemExit(f"Invalid --css value {item!r}; expected NAME=SELECTOR")
        name, selector = item.split("=", 1)
        fields[name.strip()] = selector.strip()
    return fields


def _resolve_format(output: str, fmt: str | None) -> str:
    if fmt:
        return fmt
    suffix = Path(output).suffix.lower()
    if suffix == ".csv":
        return "csv"
    return "jsonl"


async def _run(args: argparse.Namespace) -> int:
    allowlist = frozenset(DEFAULT_ALLOWLIST | {h.lower() for h in args.allow_host})
    if not _host_allowed(args.url, allowlist):
        print(
            f"Refusing to fetch {args.url!r}: host not on demo allowlist {sorted(allowlist)}.\n"
            "Pass --allow-host HOST only for sites you are authorized to scrape.",
            file=sys.stderr,
        )
        return 2

    settings = get_settings(
        log_level="DEBUG" if args.verbose else "INFO",
        allow_disallowed=args.allow_disallowed,
    )
    css_fields = _parse_css_fields(args.css)
    export_format = _resolve_format(args.output, args.format)

    try:
        from rich.console import Console

        console: object | None = Console()
    except ImportError:
        console = None

    async with AsyncScrapeClient(settings) as client:
        try:
            page = await client.scrape(args.url, css_fields=css_fields or None)
        except RobotsDisallowedError as exc:
            print(f"Blocked by robots.txt: {exc}", file=sys.stderr)
            return 3

    record = page.to_dict()
    if export_format == "csv":
        count = to_csv([record], args.output)
    else:
        count = to_jsonl([record], args.output)

    msg = f"Wrote {count} record(s) to {args.output}"
    if console is not None:
        console.print(f"[green]{msg}[/green]")  # type: ignore[attr-defined]
    else:
        print(msg)
    return 0


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    raise SystemExit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()

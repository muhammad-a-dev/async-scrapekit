"""async-scrapekit — polite async scraping toolkit."""

from __future__ import annotations

from scrapekit.client import AsyncScrapeClient, FetchResult, RobotsDisallowedError
from scrapekit.config import Settings, get_settings
from scrapekit.export import records_from_jsonl, to_csv, to_jsonl
from scrapekit.extract import ExtractedPage, extract_page, parse_html
from scrapekit.rate_limit import HostRateLimiter
from scrapekit.retry import RetryExhaustedError, compute_backoff, with_retries
from scrapekit.robots import RobotsChecker

__version__ = "0.1.0"

__all__ = [
    "AsyncScrapeClient",
    "ExtractedPage",
    "FetchResult",
    "HostRateLimiter",
    "RetryExhaustedError",
    "RobotsChecker",
    "RobotsDisallowedError",
    "Settings",
    "__version__",
    "compute_backoff",
    "extract_page",
    "get_settings",
    "parse_html",
    "records_from_jsonl",
    "to_csv",
    "to_jsonl",
    "with_retries",
]

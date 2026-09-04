"""HTML extraction helpers powered by BeautifulSoup."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag


@dataclass(slots=True)
class ExtractedPage:
    """Structured extraction result for a single HTML document."""

    url: str
    title: str | None = None
    text: str | None = None
    links: list[str] = field(default_factory=list)
    meta: dict[str, str] = field(default_factory=dict)
    selected: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "text": self.text,
            "links": list(self.links),
            "meta": dict(self.meta),
            "selected": dict(self.selected),
        }


def parse_html(html: str, *, features: str = "html.parser") -> BeautifulSoup:
    """Parse HTML into a BeautifulSoup document."""
    return BeautifulSoup(html, features)


def extract_title(soup: BeautifulSoup) -> str | None:
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    heading = soup.find(["h1", "h2"])
    if isinstance(heading, Tag):
        return heading.get_text(strip=True) or None
    return None


def extract_text(soup: BeautifulSoup, *, separator: str = "\n", strip: bool = True) -> str:
    """Return visible text with scripts/styles removed."""
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return soup.get_text(separator=separator, strip=strip)


def extract_links(
    soup: BeautifulSoup,
    *,
    base_url: str | None = None,
    absolute: bool = True,
) -> list[str]:
    """Collect href values from anchor tags."""
    links: list[str] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        if not isinstance(anchor, Tag):
            continue
        href = str(anchor.get("href", "")).strip()
        if not href or href.startswith(("#", "javascript:", "mailto:")):
            continue
        if absolute and base_url:
            href = urljoin(base_url, href)
        if href not in seen:
            seen.add(href)
            links.append(href)
    return links


def extract_meta(soup: BeautifulSoup) -> dict[str, str]:
    """Extract common meta name/property content pairs."""
    meta: dict[str, str] = {}
    for tag in soup.find_all("meta"):
        if not isinstance(tag, Tag):
            continue
        key = tag.get("name") or tag.get("property")
        content = tag.get("content")
        if key and content:
            meta[str(key)] = str(content)
    return meta


def select_text(soup: BeautifulSoup, css_selector: str) -> list[str]:
    """Return stripped text for every element matching *css_selector*."""
    return [el.get_text(strip=True) for el in soup.select(css_selector)]


def select_attrs(soup: BeautifulSoup, css_selector: str, attr: str) -> list[str]:
    """Return attribute values for elements matching *css_selector*."""
    values: list[str] = []
    for el in soup.select(css_selector):
        if isinstance(el, Tag) and el.has_attr(attr):
            raw = el.get(attr)
            if isinstance(raw, list):
                values.append(" ".join(str(v) for v in raw))
            elif raw is not None:
                values.append(str(raw))
    return values


def extract_page(
    html: str,
    *,
    url: str = "",
    css_fields: dict[str, str] | None = None,
    include_text: bool = True,
    include_links: bool = True,
) -> ExtractedPage:
    """High-level helper that returns a structured :class:`ExtractedPage`."""
    soup = parse_html(html)
    selected: dict[str, Any] = {}
    if css_fields:
        for name, selector in css_fields.items():
            selected[name] = select_text(soup, selector)

    return ExtractedPage(
        url=url,
        title=extract_title(soup),
        text=extract_text(soup) if include_text else None,
        links=extract_links(soup, base_url=url or None) if include_links else [],
        meta=extract_meta(soup),
        selected=selected,
    )

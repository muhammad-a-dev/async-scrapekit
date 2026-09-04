"""Tests for HTML extraction helpers."""

from __future__ import annotations

from scrapekit.extract import (
    extract_links,
    extract_meta,
    extract_page,
    extract_text,
    extract_title,
    parse_html,
    select_attrs,
    select_text,
)

SAMPLE = """
<html>
<head>
  <title>Demo Page</title>
  <meta name="description" content="A demo">
  <meta property="og:title" content="OG Demo">
</head>
<body>
  <h1>Hello</h1>
  <p>World</p>
  <a href="/about">About</a>
  <a href="https://example.com/contact">Contact</a>
  <a href="#top">Skip</a>
  <script>var x = 1;</script>
</body>
</html>
"""


def test_extract_title() -> None:
    soup = parse_html(SAMPLE)
    assert extract_title(soup) == "Demo Page"


def test_extract_text_strips_scripts() -> None:
    soup = parse_html(SAMPLE)
    text = extract_text(soup)
    assert "Hello" in text
    assert "World" in text
    assert "var x" not in text


def test_extract_links_absolute() -> None:
    soup = parse_html(SAMPLE)
    links = extract_links(soup, base_url="https://example.com/home")
    assert "https://example.com/about" in links
    assert "https://example.com/contact" in links
    assert all(not link.startswith("#") for link in links)


def test_extract_meta() -> None:
    soup = parse_html(SAMPLE)
    meta = extract_meta(soup)
    assert meta["description"] == "A demo"
    assert meta["og:title"] == "OG Demo"


def test_select_helpers() -> None:
    soup = parse_html(SAMPLE)
    assert select_text(soup, "h1") == ["Hello"]
    assert select_attrs(soup, "a", "href") == ["/about", "https://example.com/contact", "#top"]


def test_extract_page_with_css_fields() -> None:
    page = extract_page(
        SAMPLE,
        url="https://example.com/",
        css_fields={"headings": "h1"},
    )
    assert page.title == "Demo Page"
    assert page.selected["headings"] == ["Hello"]
    assert page.to_dict()["url"] == "https://example.com/"

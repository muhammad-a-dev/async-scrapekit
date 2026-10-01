"""extract_links skips non-navigable / dangerous href schemes."""

from __future__ import annotations

from scrapekit.extract import extract_links, parse_html


def test_extract_links_skips_dangerous_schemes_case_insensitive() -> None:
    soup = parse_html(
        """
        <a href="mailto:a@b.com">m</a>
        <a href="JavaScript:alert(1)">j</a>
        <a href="DATA:text/plain,hi">d</a>
        <a href="vbscript:msgbox(1)">v</a>
        <a href="tel:+15551212">t</a>
        <a href="#frag">frag</a>
        <a href="/ok">ok</a>
        """
    )
    links = extract_links(soup, base_url="https://example.com/")
    assert links == ["https://example.com/ok"]

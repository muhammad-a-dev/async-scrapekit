# Security Policy

## Supported versions

| Version | Supported |
| ------- | --------- |
| 0.1.x   | Yes       |

## Reporting a vulnerability

Please open a [GitHub Security Advisory](https://github.com/muhammad-a-dev/async-scrapekit/security/advisories/new)
or email the maintainer via the profile contact on GitHub.

Do **not** open a public issue for undisclosed security problems.

## Secrets and local config

- Copy [`.env.example`](.env.example) to `.env` for local overrides. Never commit `.env` or real credentials.
- This toolkit is designed so default scrapes need **no API keys**. If you inject tokens into a custom User-Agent, Authorization header, or downstream pipeline, treat them as secrets.
- Prefer environment variables or a secret manager over hard-coding credentials in examples or tests.
- Rotate any token that was pasted into chat, a ticket, or a public gist.

## Outbound URL safety

- The library client defaults to **blocking private network targets**: loopback,
  RFC1918 private ranges, link-local (including `169.254.169.254`), multicast,
  reserved addresses, and known cloud-metadata hostnames (`metadata.google.internal`,
  `metadata.goog`, and `*.localhost`).
- IPv6 loopback / ULA / link-local literals (for example `::1`, `fc00::/7`, `fe80::/10`)
  are blocked the same way as IPv4 private ranges.
- URLs that embed userinfo (`https://user:pass@host/`) are rejected so credentials
  are not sent or logged by accident.
- Redirects are checked too (httpx request hook) so a public URL cannot bounce
  into an internal endpoint.
- This also covers an `httpx.AsyncClient` you pass in with `client=`. The
  `ssrf_request_hook` is appended to that client's request hooks once, after
  any hooks it already has, so it checks the final URL of every hop. The hook
  stays on the client after `AsyncScrapeClient` closes. `ssrf_request_hook` is
  exported if you want the same check on clients you use elsewhere.
- Set `SCRAPEKIT_BLOCK_PRIVATE_HOSTS=false` or `block_private_hosts=False` only
  when you intentionally scrape intranet hosts you are authorized to reach.
  With the opt-out, an injected client is left untouched.
- The demo CLI still applies its own host allowlist on top of these checks.

## Response size limits

- Fetches reject bodies larger than `max_response_bytes` (default 10 MiB,
  override with `SCRAPEKIT_MAX_RESPONSE_BYTES`).
- When `Content-Length` is present and over the limit, the client raises
  `ResponseTooLargeError` before treating the body as usable scrape input.
- Bodies are streamed, and reading stops at the first chunk that pushes the
  total past the limit. When `Content-Length` is missing (chunked responses) or
  understates the size, at most one chunk past the cap is ever held in memory,
  and the rest of the body is never downloaded.
- The limit counts decoded bytes, after gzip, deflate, or brotli is undone, so a
  tiny compressed body that inflates to gigabytes (a compression bomb) is cut
  off too.
- robots.txt is streamed and only the first 500 KiB is read (the minimum
  RFC 9309 asks parsers to handle). Anything past that is ignored, and a rule
  cut off mid-line at the limit is dropped instead of evaluated, so a hostile
  origin cannot use a giant robots.txt to exhaust memory.

## Redirect limits

- The built-in client follows at most `max_redirects` redirects per fetch
  (default 10, override with `SCRAPEKIT_MAX_REDIRECTS`, allowed range 0 to 30).
  httpx alone allows 20.
- Redirect hops are followed inside httpx, so they do not pass through the
  per-host rate limiter or the robots.txt check. The cap keeps a redirect loop
  from turning one fetch into many requests against the same host.
- Going past the cap raises `httpx.TooManyRedirects`. It is not retried.
  Set `max_redirects=0` to refuse every redirect.
- An `httpx.AsyncClient` passed via `client=` keeps its own `max_redirects`.
  Set it on that client if you need a tighter limit.

## Extraction hygiene

- `extract_links` drops `javascript:`, `mailto:`, `data:`, `vbscript:`, and `tel:`
  hrefs (case-insensitive) so those values do not land in JSONL/CSV exports.
- `to_csv` prefixes string cells that start with `=`, `+`, `-`, `@`, tab, or
  carriage return with `'` (CSV formula injection). Scraped titles and text are
  untrusted, so this is on by default; numbers are not changed. Use
  `escape_formulas=False` only for CSVs that never reach a spreadsheet app.

## Scope notes

`async-scrapekit` is an HTTP client toolkit. It intentionally does **not** include:

- proxy rotation for evasion
- CAPTCHA solving or bypass
- authentication / paywall circumvention
- any feature designed to defeat anti-abuse controls

If you discover that a change would enable abusive scraping, please report it
so we can keep defaults polite and lawful.

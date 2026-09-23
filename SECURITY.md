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
  reserved addresses, and known cloud-metadata hostnames.
- Redirects are checked too (httpx request hook) so a public URL cannot bounce
  into an internal endpoint.
- Set `SCRAPEKIT_BLOCK_PRIVATE_HOSTS=false` or `block_private_hosts=False` only
  when you intentionally scrape intranet hosts you are authorized to reach.
- The demo CLI still applies its own host allowlist on top of these checks.

## Scope notes

`async-scrapekit` is an HTTP client toolkit. It intentionally does **not** include:

- proxy rotation for evasion
- CAPTCHA solving or bypass
- authentication / paywall circumvention
- any feature designed to defeat anti-abuse controls

If you discover that a change would enable abusive scraping, please report it
so we can keep defaults polite and lawful.

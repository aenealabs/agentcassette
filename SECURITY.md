# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| Latest  | Yes       |
| Older   | No        |

We support only the most recent released version. Please upgrade before reporting a vulnerability.

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Please report security issues privately through GitHub's [private vulnerability reporting](https://github.com/aenealabs/agentcassette/security/advisories/new): go to the repository's **Security** tab and click **Report a vulnerability**. This keeps the report confidential until a fix is released.

Include:
- A description of the vulnerability and its potential impact
- Steps to reproduce or a minimal proof-of-concept
- The agentcassette version and Python version affected

You can expect an acknowledgment within 48 hours and a resolution or mitigation plan within 14 days. We will credit you in the release notes unless you request otherwise.

## Scope

agentcassette records and replays intercepted calls to and from a JSON cassette file. The attack surface is limited to:

- Cassette files (`_cassette.py`) — these are plain JSON read from disk. Treat cassettes from untrusted sources with the same care as any untrusted JSON.
- Secrets captured into cassettes — use `redact()` or `record(..., redact=[...])` to scrub credentials before committing cassettes to version control.
- Supply-chain attacks via the package itself (we maintain zero dependencies to minimize this risk)

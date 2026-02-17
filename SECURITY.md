# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| main branch | Yes |
| Older commits | No |

## Reporting a Vulnerability

If you discover a security vulnerability in Wiii, please report it responsibly.

**Do NOT open a public GitHub issue for security vulnerabilities.**

### How to Report

1. Email: **security@wiii.lab** (or open a private security advisory on GitHub)
2. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

### What to Expect

- **Acknowledgment**: Within 48 hours of your report
- **Assessment**: We will evaluate the severity and impact within 7 days
- **Fix**: Critical vulnerabilities will be patched as quickly as possible
- **Disclosure**: We will coordinate with you on public disclosure timing

## Security Measures

Wiii implements the following security practices:

- **Authentication**: Dual auth (API Key + JWT) with timing-safe comparison (`hmac.compare_digest`)
- **Authorization**: Role-based access control (student, teacher, admin) with ownership checks
- **Input validation**: Pydantic models with field constraints (e.g., message max 10,000 chars)
- **Rate limiting**: Per-role rate limits via slowapi (Valkey-backed in production)
- **Sandboxing**: Filesystem and code execution tools run in restricted sandboxes
- **Error handling**: Generic error messages in HTTP responses; details logged server-side only
- **Secrets management**: Environment variables via `.env` — never committed to version control
- **Request tracing**: Auto-generated `X-Request-ID` for log correlation

## Scope

The following are **in scope** for security reports:

- Authentication/authorization bypasses
- SQL injection, XSS, SSRF, or other injection attacks
- Sensitive data exposure
- Sandbox escapes (filesystem tools, code execution)
- Privilege escalation

The following are **out of scope**:

- Denial of service via rate limiting (by design)
- Issues in third-party dependencies (report to their maintainers)
- Social engineering attacks
- Issues requiring physical access to the server

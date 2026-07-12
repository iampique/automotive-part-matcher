# Security Policy

## Reporting a vulnerability

Please **do not** open a public issue for security vulnerabilities.

Prefer one of:

1. [GitHub Security Advisories](https://github.com/iampique/automotive-part-matcher/security/advisories/new) for this repository
2. Email the maintainer privately via the contact method on their GitHub profile

Include steps to reproduce, impact, and any suggested fix if you have one.

## Secrets

- Never commit `.env`, API keys, passwords, or certificates.
- Use `backend/.env.example` and `frontend/.env.example` as templates only.
- If you accidentally expose a key, rotate it immediately with the provider.

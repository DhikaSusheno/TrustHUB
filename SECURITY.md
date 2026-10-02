# SECURITY.md

How to report a vulnerability in TrustHUB, and what is deliberately not
supported in this repository.

## Supported versions

This is a CALIBER 2026 Case 1 submission repository. It is not a released
product and carries no support commitment.

| Version | Supported |
|---|---|
| `main` | Yes |
| Older branches | No |

Fixes land on `main`. There is no backport policy.

## Reporting a vulnerability

Report privately through GitHub's private reporting on the Security tab of the
repository (**Security → Report a vulnerability**), not through a public issue.

Please include:

- What an attacker can do, not only which endpoint is involved.
- Steps to reproduce, with the request path and method if it is the proxy.
- Whether a token, a credential, or dataset content is involved.
- The commit SHA or the release you tested.

Expect an acknowledgement within 7 days. There is no bug bounty attached to
this repository.

### What to expect on timing

This is an academic submission maintained by a small team. Triage happens
between submissions. There is no guaranteed remediation window. If a report
needs a fix that only the submitting institution can make, you will be told
so rather than left waiting.

## Scope

The following are in scope:

- `backend/`, `security/`, and `frontend/` source.
- The CI workflows under `.github/workflows/`.
- Deployment and configuration documented in this repository.

The following are out of scope, and this is deliberate rather than an oversight:

- **The CALIBER dataset.** It is not committed to this repository. Its licence
  forbids redistribution, so there is no copy here to attack. Fetch it through
  `backend/plant/fetch_dataset.py`.
- **Third-party credentials.** `TRUSTHUB_API_TOKEN`, GitHub tokens, and LLM
  provider API keys are supplied by the operator at runtime and are never
  committed. A leaked key is rotated by whoever owns it, not by patching this
  code.
- **Generated local state.** `backend/plant/trusthub_plant.db`,
  `backend/.fernet_key`, and `trusthub_settings.json` are ignored by git and
  are per-machine.

## Known design constraints

These are known and documented, not undisclosed vulnerabilities. Reporting
them as new findings will not move them to the top of a queue.

### The proxy injects a server-side token

`frontend/app/backend/[...path]/route.ts` forwards requests to the FastAPI
backend and injects `TRUSTHUB_API_TOKEN` from the server environment, so the
token never reaches the browser bundle. That design means any client which can
reach the Next.js port can use those credentials.

What is done about it, in the proxy itself:

- Browser cross-site requests are rejected via `Sec-Fetch-Site`, so a foreign
  page cannot make a victim's browser drive the proxy (CORS blocks reading a
  response, not executing the request).
- Client `Authorization` headers are stripped rather than forwarded.
- Only the endpoints the TrustHUB interface actually calls are allowed, each
  with an explicit method allowlist, so credential-bearing routes such as
  `/api/github/*` and `/api/llm/providers*` are unreachable through the proxy.
- `..`, `.`, and empty path segments are rejected on the decoded path.

What cannot be fixed in that file: non-browser clients such as `curl` or a
local script that can reach the port still use the proxy, because the token is
injected server-side. That is inherent to a token-injecting proxy.

**Operator action required.** Bind Next.js to `localhost` rather than
`0.0.0.0`, or set `TRUSTHUB_PROXY_ALLOWED_ORIGINS` to the exact origins that
should be served.

### No authentication on the application itself

TrustHUB has no user accounts and no login. Its trust model applies to
document provenance, not to who is allowed to ask a question. Do not expose it
to an untrusted network.

### Sample data

The official dataset is labelled by its own authors as sample data. Trip set
points and costs are stated to be dummy training values. This is stated in the
product itself, on the landing page and the Dataset page, rather than in a
footnote.
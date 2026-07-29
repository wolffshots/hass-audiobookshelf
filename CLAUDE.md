# CLAUDE.md

Working notes for this repo. Written after the Audiobookshelf 2.36.0 compliance pass;
the aim is that the next server release can be handled the same way without rediscovering
the same traps.

This is a Home Assistant custom integration. It polls an Audiobookshelf server with a
single static admin credential and exposes counts as sensors. It is read-mostly: the only
write is the `remove_my_progress` service.

## Checking the integration against a new Audiobookshelf release

Release notes are a starting point, not evidence. They describe intent and routinely omit
schema changes. Verify against the tagged source.

The cheapest high-confidence check is comparing blob SHAs between tags — byte-identical
files cannot have changed, which settles most questions without reading any code:

```bash
gh api repos/advplyr/audiobookshelf/compare/vOLD...vNEW --jq '.files[].filename'
```

Then read the actual hunks for anything that did change, at
`https://raw.githubusercontent.com/advplyr/audiobookshelf/vNEW/server/...`.

### Endpoints this integration depends on

Check each of these on every server release. The first five back sensors; the rest back
the `remove_my_progress` service.

| Endpoint | Used for | Notes |
| --- | --- | --- |
| `GET /api/libraries` | library discovery | |
| `GET /api/users` | `count_users` | admin only, 403 otherwise |
| `GET /api/users/online` | `count_users_online` | admin only, 403 otherwise |
| `GET /api/sessions/open` | open + recent sessions | admin only, **404** (not 403) otherwise |
| `GET /api/libraries/{id}/stats` | per-library sensors | |
| `GET /api/me/sessions` | `count_auth_sessions` | added in 2.36.0; 404s on older servers |
| `GET /api/libraries/{id}/items` | service | paginated |
| `GET`/`DELETE /api/me/progress/...` | service | |

`/api/libraries/{id}/stats` omits `totalAuthors` for **podcast** libraries. `LibraryStats.total_authors`
must stay `int | None`. This is not hypothetical — it was confirmed against a real server
with a podcast library, and a required field there would break every poll.

## Authentication

Audiobookshelf 2.26.0 reworked auth. Three credential types now exist, and only some work
as a `Bearer` token:

- **API keys** (Settings > API Keys, 2.26.0+) — long-lived, the supported option. Recommend these.
- **Legacy user tokens** (Settings > Users) — still work, but the UI labels them "Legacy API
  Token" and warns of removal. Fallback for servers older than 2.26.0 only.
- **Refresh tokens** — rejected for API auth since 2.36.0. This integration never sends one.

The credential must belong to an **admin/root** user. `verify_config` uses
`get_admin_client_by_token` deliberately so a non-admin key is rejected at setup rather than
failing on every poll afterwards.

### The exception trap

This is the single easiest thing to get wrong here.

`aioaudiobookshelf` exceptions derive from `AbsError`, **not** `aiohttp.ClientError`. Catching
only `ClientError` silently misses all of them.

Worse, because this integration configures a static `token` with no refresh token, a 401 does
**not** raise `LoginError`. The library sees `auto_refresh=True`, tries to refresh, finds no
refresh token, and raises `TokenIsMissingError`. Both are `AbsAuthError`, so catch that:

- `AbsAuthError` -> `ConfigEntryAuthFailed` (triggers the reauth flow)
- other `AbsError` -> `UpdateFailed`

`NotFoundError` (HTTP 404) is *not* an `AbsAuthError` — that is what lets `count_auth_sessions`
degrade to `None` on pre-2.36.0 servers instead of prompting for reauth.

Note also that `_get` changed behaviour across library versions: 404 used to return `b""` and
now raises. Re-check this when bumping `aioaudiobookshelf`.

## Verifying a change

All three must be clean. `uvx` avoids touching the system Python:

```bash
uvx ruff@0.16.0 check .
```

```bash
uvx ruff@0.16.0 format --check .
```

```bash
uvx --prerelease=allow --with homeassistant==2025.1.4 --with aioaudiobookshelf==0.1.24 --with voluptuous --with pytest mypy@2.3.0 --config-file mypy.ini custom_components/audiobookshelf/ tests/
```

```bash
uvx --prerelease=allow --with homeassistant==2025.1.4 --with aioaudiobookshelf==0.1.24 pytest@9.1.1 tests/ -q -W ignore::DeprecationWarning
```

`--prerelease=allow` is required because `homeassistant` depends on a pre-release of
`aiohasupervisor`. Without it the resolve fails outright.

When bumping a pinned tool, run it against a pristine tree first (`git archive HEAD` into a
temp dir) so pre-existing findings are not mistaken for regressions.

Static checks are the real safety net here — the test suite is small and covers pure logic
only (config validation and response schemas). Anything touching Home Assistant runtime
behaviour is not covered and needs the live test below.

## Testing against a real server

Static analysis will not catch schema drift or auth behaviour. For anything touching
endpoints or authentication, test against an actual instance.

**Never put an API key in the conversation.** Have the user write it to a file and read it
from a script that prints only structural results. The key stays out of the transcript.

Two levels, in order:

1. **API smoke test** — authenticate, call every endpoint above, parse each response with the
   integration's *own* schema classes (import them; do not reimplement). Catches schema drift
   cheaply and needs no Home Assistant.
2. **Full Home Assistant run** — the only way to exercise the config flow, coordinator,
   entities and reauth. Home Assistant Core does not run on Windows; use WSL.

Reauth can only be verified by genuinely breaking the credential: configure a throwaway API
key, then delete it server-side while Home Assistant polls. Expect
`Auto refreshing tokens.` followed by `ConfigEntryAuthFailed`, then a reauth prompt, then
recovery without a restart. A pass here is worth more than any amount of reading, because
this path cannot be reasoned about reliably.

The user must drive Home Assistant onboarding and the config flow themselves — it involves
creating an account and entering a credential.

## Windows and WSL gotchas

These cost real time. All were hit in practice.

- **Git Bash mangles paths and variables** passed to `wsl`. It rewrites a leading `/mnt/c/...`
  to `C:/Program Files/Git/mnt/c/...` and strips `$VAR` even inside single quotes. Use the
  PowerShell tool for `wsl` invocations, and put anything non-trivial in a script file.
- **PowerShell strips single quotes** around arguments to native commands, so `bash -c '...'`
  fragments end up interpreted by the login shell (zsh here). Use double quotes.
- **`2>/dev/null` does not behave as expected** inside a PowerShell-invoked native command;
  output goes missing and looks like an empty result.
- **`pgrep -f foo` matches its own command line.** It will report a process running when
  nothing is. Verify with something independent, such as whether the port is still bound.
- **`pycares` 5.x breaks `aiodns` 3.2.0** (`Channel.getaddrinfo()` signature change), which
  breaks every DNS lookup in Home Assistant and surfaces as a bare "Unknown error occurred"
  in the config flow. Pinned via `pycares<5` in `requirements.txt`.

## Dependencies

`requirements.txt` is **CI and development only**. HACS ships `custom_components/audiobookshelf/`,
and `manifest.json` declares the only runtime requirement (`aioaudiobookshelf`, unpinned).

This matters for triaging Dependabot: advisories against `homeassistant` in `requirements.txt`
affect the Actions runner, not any user of the integration, and should be weighted accordingly.

Because `manifest.json` is unpinned, users always get the newest `aioaudiobookshelf`. Keep the
`requirements.txt` pin at that same version or CI tests something users never run.

## Releasing

Bump the version in **both** places — they are separate values and drift silently:

- `custom_components/audiobookshelf/const.py` -> `VERSION = "vX.Y.Z"` (with `v`)
- `custom_components/audiobookshelf/manifest.json` -> `"version": "X.Y.Z"` (without `v`)

`hacs.json` separately declares the minimum supported Home Assistant version.

Releases are cut from `main` after merge. Publishing a GitHub release triggers
`.github/workflows/release.yml`, which zips the component and attaches it — that asset is what
HACS installs, so confirm it exists on the release before considering it done.

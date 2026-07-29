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

Check each of these on every server release. The first six back sensors; the rest back
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

`POST /api/authorize` is not in the table because the library calls it, not this integration —
`get_admin_client_by_token` posts it to build the client. Its response carries
`serverSettings.version`, which the library exposes as `client.server_settings.version`. That is
where the device's `sw_version` comes from, so it costs no request of its own. It is only
refreshed when the client is rebuilt, so a server upgrade is not reflected until the entry
reloads.

Audiobookshelf exposes **no update-check endpoint**. `/api/check-for-update`, `/api/update`,
`/api/version` and `/api/server-settings` all 404 on 2.36.0; the web UI queries GitHub from the
browser. Anything reporting "an update is available" has to ask GitHub directly, which is why
this integration does not do it today.

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
`get_admin_client_by_token` deliberately so a non-admin key is rejected in the config flow
rather than failing on every poll afterwards.

`verify_config` is only reachable from the config flow now. It used to run again in
`async_setup_entry`, which duplicated a request on every restart and reload over its own
`ClientSession`; `async_config_entry_first_refresh` already gates setup. A non-admin key that
somehow reaches setup is caught by the coordinator, which handles `BadUserError` ahead of
`AbsAuthError` to say so specifically.

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

`BadUserError` (non-admin credential) *is* an `AbsAuthError`, so it must be caught before it if
you want a message that says so rather than a generic auth failure.

There is a third clause that is easy to leave out. Every `from_json` call raises **mashumaro**
exceptions on schema drift — `MissingField` (a `LookupError`) and `InvalidFieldValue` (a
`ValueError`) — and a non-JSON body raises `JSONDecodeError` (also a `ValueError`). None of
these are `AbsError` *or* `ClientError`. Without `except (ValueError, LookupError)` they escape
the coordinator entirely and Home Assistant logs a full traceback on every poll instead of a
clean `UpdateFailed`.

Note also that `_get` changed behaviour across library versions: 404 used to return `b""` and
now raises. Re-check this when bumping `aioaudiobookshelf`.

### Platform setup must not call the API

`sensor.py` used to call `/api/libraries` again during `async_setup_entry` to name its
per-library entities. A transient failure there is swallowed by the platform forward, so the
entry stayed `LOADED` with no entities — and because the coordinator only schedules a refresh
while it has listeners, **polling then stopped permanently**, with the integration still
showing as healthy. It took a restart or manual reload to recover.

The library list is now stashed on the coordinator by `library_stats()` and read from there.
Keep it that way: anything the sensor platform needs should come from data the first refresh
already fetched.

That list is also what makes new libraries appear without a reload — the platform registers a
coordinator listener that adds sensors for library ids it has not seen. It has to stay
idempotent, because it runs on every poll.

## Verifying a change

All four must be clean. `uvx` avoids touching the system Python:

```bash
uvx ruff@0.16.0 check .
```

```bash
uvx ruff@0.16.0 format --check .
```

```bash
uvx --python 3.12 --prerelease=allow --with homeassistant==2025.1.4 --with aioaudiobookshelf==0.1.24 --with voluptuous --with pytest mypy@2.3.0 --config-file mypy.ini custom_components/audiobookshelf/ tests/
```

```bash
uvx --python 3.12 --prerelease=allow --with homeassistant==2025.1.4 --with aioaudiobookshelf==0.1.24 pytest@9.1.1 tests/ -q -W ignore::DeprecationWarning
```

`--prerelease=allow` is required because `homeassistant` depends on a pre-release of
`aiohasupervisor`. Without it the resolve fails outright.

`--python 3.12` is not optional in practice. Once `uv` has cached a newer toolchain it will
re-resolve to it, and `homeassistant==2025.1.4` cannot build there — `orjson==3.10.12` has no
wheel for 3.14. Without the flag the same command works one day and fails the next.

CI runs exactly these, minus the pins, via `requirements.txt`. It lints and type-checks
`tests/` as well as the component, so a change that only passes locally because you scoped the
command narrower will still fail there.

When bumping a pinned tool, run it against a pristine tree first (`git archive HEAD` into a
temp dir) so pre-existing findings are not mistaken for regressions.

The test suite covers the coordinator's exception mapping, sensor value derivation and
availability, the `remove_my_progress` guards, and the v1 to v2 entity migration — all with
plain `pytest` and `unittest.mock`, no `hass` fixture. Do not reach for
`pytest-homeassistant-custom-component`: every release caps `pytest` at `<=8.3.4` and conflicts
with the pinned 9.1.1, and nothing here has needed it.

What is still *not* covered, and needs the live test below: the config flow as a flow, reauth
end to end, and anything that depends on Home Assistant actually wiring entities up.

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
  in the config flow. Pinned via `pycares<5` in `requirements.txt`. A one-off `uvx` command
  that imports the Home Assistant stack needs `--with 'pycares<5'` too, or it hits this.
- **`aiodns` refuses to run on Windows' default event loop.** `aiohttp` picks it as the
  resolver whenever it is installed, so any script importing the Home Assistant stack on the
  host dies with "aiodns needs a SelectorEventLoop on Windows" before doing anything. Call
  `asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())` first. Home
  Assistant itself only runs on Linux, so this is a host-scripting problem, not a real one.

## Dependencies

`requirements.txt` is **CI and development only**. HACS ships `custom_components/audiobookshelf/`,
and `manifest.json` declares the only runtime requirement (`aioaudiobookshelf`).

This matters for triaging Dependabot: advisories against `homeassistant` in `requirements.txt`
affect the Actions runner, not any user of the integration, and should be weighted accordingly.

`manifest.json` bounds `aioaudiobookshelf` to `>=0.1.24,<0.2` rather than leaving it open. The
coordinator reaches into `client._get()` in six places because the library exposes no public
accessor for these endpoints, and `_get`'s 404 behaviour has already changed once between
versions. Unbounded, a single upstream release would break every install at once with no code
change here. The cost is that a new minor has to be adopted deliberately: bump the bound and
the `requirements.txt` pin together, and re-read the exception trap section above.

Keep the `requirements.txt` pin at the newest version the bound allows, or CI tests something
users never run.

## Releasing

Bump the version in **both** places — they are separate values and used to drift silently:

- `custom_components/audiobookshelf/const.py` -> `VERSION = "vX.Y.Z"` (with `v`)
- `custom_components/audiobookshelf/manifest.json` -> `"version": "X.Y.Z"` (without `v`)

`release.yml` now checks both against the tag and fails the release if either disagrees, so
the drift is caught rather than shipped. `VERSION` has no remaining consumer in the code — it
was removed from `device_info`, where it was being reported as the *server's* version — but it
still has to be bumped, because the gate compares it to the tag.

`hacs.json` separately declares the minimum supported Home Assistant version.

Releases are cut from `main` after merge. Publishing a GitHub release triggers
`.github/workflows/release.yml`, which zips the component and attaches it to the release.

**That asset is not what HACS installs.** `hacs.json` does not set `zip_release`, so HACS
downloads the individual files under `custom_components/audiobookshelf/` at the tag and ignores
the archive entirely. The archive exists for the manual-install path in the README. Opting in
to `zip_release` would mean giving the asset a stable filename, which the current
`Audiobookshelf_$TAG.zip` is not.

## Config entry schema version

`ConfigFlow.VERSION` is **2**. It went from 1 when entity unique IDs and the device identifier
moved off the API URL (user-editable, so changing it orphaned everything) onto `entry.entry_id`.

Anything that changes the shape of a unique ID from now on needs a matching bump and a branch
in `async_migrate_entry`. The v1 migration is a pure prefix swap that keeps the rest of the key
byte for byte, which is deliberate — it is far easier to verify than a reformat, and the
trailing `_None_None` segments are invisible to users.

### Verifying a migration against a real instance

Install the *previous* release first, let it create its entities, then swap the component and
restart. Two traps make this look broken when it is not:

- **Registry writes during startup are deferred by 180 seconds.**
  `helpers/registry.py` picks `SAVE_DELAY_LONG` (180) rather than `SAVE_DELAY` (10) whenever
  `hass.state` is not `CoreState.running`, and a migration always runs before that. So
  `.storage/core.entity_registry` keeps the *old* values for three minutes while the in-memory
  registry is already correct — and restarting inside that window throws the change away.
  `core.config_entries` saves on its own schedule and updates promptly, so the version bump
  appearing without the entity rewrite is the expected intermediate state, not a failure.
  Stop the container with a generous grace period (`podman stop --time 90`) to force the final
  write, then read the file.
- **Omitting a field from `DeviceInfo` does not clear it.** The device registry keeps whatever
  is already stored, so removing `sw_version` only affects new installs. Clearing it for
  existing ones takes an explicit `sw_version=None` in `async_update_device`. This was found
  by testing the migration for real and is invisible to unit tests that only assert on what
  the integration passes.

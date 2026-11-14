# 2026-11-14 — LAN sharing (SHARE chip) for remote Hermes backends

## Status and scope

- Base revision / branch: `65779b9` (tag `pre-share-toggle` marks the rollback point).
- Local, committed or published: committed and pushed to `main`.
- Affected files/components: `dashboard/plugin_api.py` (share relay + `POST /share` + state fields),
  `desktop/plugin.js` (`SHARE` status-bar chip), installed copies under
  `%LOCALAPPDATA%/hermes/plugins/llamacpp-tuned/` and `.../desktop-plugins/llamacpp-tuned/`,
  per-machine `dashboard/settings.json` (share keys added, existing keys preserved).

## Reason / observed symptom

A second Hermes gateway (the NAS Docker backend) needs to use the local GGUF models served
by this machine, driven from a third device that connects to the NAS. The tuned proxy and
its router both bind `127.0.0.1`, so nothing here is reachable from another host; the plugin
had no supported way to expose the proxy to the LAN. Requirement: an easy in-app on/off
toggle that does not need admin per toggle.

## Changes

- Added a **SHARE** status-bar chip and `POST /share {enabled}` route. ON starts a LAN relay
  listener (`share_port`, default 8090) that forwards to `127.0.0.1:<port>` (the existing
  proxy), so remote requests still pass through the proxy's per-model serialization lock —
  the relay must never point at the router port (`port + 1`).
- New settings (all optional, OFF by default): `share` (persisted choice, re-applied on the
  next router start), `share_port` (8090), `share_bind` (`0.0.0.0`), `share_allow` (source-IP
  allowlist; empty = rely on the firewall), `share_token` (optional `Authorization: Bearer`
  check; empty = no auth).
- `_read_state()` now reports `share`, `share_port`, `share_allow`, `share_token_set`.
- The SHARE chip surfaces failures (red `SHARE !` + explanatory title, 5 s) instead of swallowing
  the promise error, so an unmounted route (gateway not restarted), a 409 (router off) or a
  read-back mismatch is visible rather than looking like a dead chip.
- Binding a socket needs no admin; inbound reachability is gated by a one-time OS firewall
  rule, so the toggle itself is non-admin.

## Unchanged behavior and hardware impact

- The local proxy on `127.0.0.1:8080` and the router on `:8081` are unchanged; the share relay
  is an additive listener that forwards to the proxy. Local Hermes use is unaffected when
  sharing is OFF.
- No model flags, presets, engine selection or machine settings were altered. The relay does
  not change token speeds or preset behavior.
- AMD/ROCm: no change — the relay is platform-neutral.
- RTX/CUDA: no change.

## Verification

| Command / scenario | Environment and model | Actual result | Evidence |
|---|---|---|---|
| `python -m py_compile dashboard/plugin_api.py` | dev venv, Python 3.14 | Pass | inline |
| `node --input-type=module --check < desktop/plugin.js` | Node ESM | Pass | inline |
| Relay forwarding (no token) to live proxy | RTX 3070, staged models | `200`, 7960-byte `/v1/models` | `share_selftest.py` |
| Relay bearer token: none / wrong / correct | same | `401` / `401` / `200` | `share_selftest.py` |
| Allowlist rejects non-listed peer | same | connection closed (`RemoteDisconnected`) | `share_selftest.py` |
| NAS host `curl http://192.168.0.192:8090/v1/models` | NAS `192.168.0.102` | `200` + model JSON | NAS shell |
| NAS container `docker exec hermes python … /v1/models` | NAS Docker container | `200` | NAS shell |
| SHARE chip render + click | packaged Desktop | **not yet tested** (needs gateway restart) | — |

## Migration and rollback

- The `POST /share` route is new backend code: it mounts only after the gateway process
  restarts (quit and relaunch the Desktop app). The chip needs a ⌘K → *Reload desktop
  plugins* (or the same relaunch). Until then the chip's POST hits an unmounted route and is
  silently swallowed.
- One-time OS firewall rule (already added on the dev machine, admin): inbound TCP 8090 from
  the remote gateway host. Without it the listener binds but inbound is dropped.
- Rollback: restore the `.bak` copies in `C:/Users/Martin/Documents/llamacpp-bench-2026-11/pre-share-toggle/`
  (plugin_api.py, plugin.js, settings.json), or check out tag `pre-share-toggle`. No model or
  runtime data is touched by rollback.

## Limits / remaining work

- The SHARE chip has not been exercised in the packaged Desktop (route is not yet mounted on
  the running gateway). Render/click verification is pending a restart.
- The NAS-side provider entry (`providers.tuned-local` with `base_url http://192.168.0.192:8090/v1`)
  is not yet registered; a real inference turn from the NAS has not been run.
- DHCP: `share_bind = 0.0.0.0` avoids pinning the IP, but the NAS provider uses the machine's
  LAN IP, so a reservation is recommended.
- Cold-load latency and Hermes' first-chunk watchdog still apply to remote callers; the plugin
  preloads on this machine but cannot preload on the NAS side.

## Approval / publication

Approved by the user and pushed to `main`. Changelog index updated.
approval per AGENTS.md.
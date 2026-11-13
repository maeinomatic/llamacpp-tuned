# Operations

## Current serving layout

The configured public port defaults to 8080; the plugin proxy serves clients there. The actual llama.cpp router uses configured port + 1 (8081 by default). Use the public endpoint for normal inference so requests receive residency coordination and keepalives.

Machine settings live in ignored `dashboard/settings.json`. Preserve each computer's engine path, backend selection and context caps. Do not copy a generated preset from a different machine.

## Updating and activation

1. Preserve local uncommitted work and take a named code/settings backup before an approved update.
2. Run regression tests and verify generated tunes before activation. Never infer running behavior solely from files on disk.
3. An already-mounted in-process Python API may retain old code after plugin rediscovery. If a gateway restart is needed, the user must run `hermes gateway restart` from a separate terminal. Do not restart the gateway hosting the current task or evade its guard.
4. After reconnecting, enable the LLM chip and verify both public/internal health endpoints and a real Qwen completion in an approved test window.

## Chip briefly loads, then returns OFF

The observed migration incident was a legacy direct-serving router that survived restart and still occupied public port 8080. Inspect the actual listener PID, executable, command line and model status. Stop only the verified stale instance after confirming it has no active model/child work. Do not terminate an unknown port owner or every llama-server process.

Port-conflict failure remains deliberate: the plugin does not automatically kill arbitrary listeners. See the [repair changelog incident record](../changelogs/2026-11-13-proxy-reliability-and-rocm-activation.md#5-activation-incident-environment-cleanup-not-another-code-change).

## Rollback

The repair's original code is preserved in branch `backup/pre-proxy-fdfadc0` and a separate machine backup. Current fixes remain uncommitted. Before rollback, save the current working-tree diff/untracked work and machine settings, then agree the exact files/revision to restore. Do not blindly switch/reset a dirty tree or overwrite ignored settings. A rollback is not permission to delete model data or change other profiles.

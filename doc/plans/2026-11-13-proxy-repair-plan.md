# Local repair plan — no commits or pushes

Backup branch: backup/pre-proxy-fdfadc0 (installed known-good code).
Repair branch/worktree: fix/proxy-rocm-compat at C:/Users/jup03/llama-local/plugin-work/llamacpp-tuned.
Machine backup: C:/Users/jup03/AppData/Local/hermes/backups/llamacpp-tuned-pre-proxy-fdfadc0.
Incoming base: 7ff3582, pulled fast-forward in repair worktree only.

## Coding / test gates

1. Preserve installed code and running router during implementation; do not write live settings, config.yaml, presets, model data, or desktop-plugin copies during unit/integration tests.
2. Use short RED -> GREEN regression-test cycles for: mode enable/disable/re-enable; specific chat routes before catch-all; incremental SSE; cold-load and prefill heartbeats; upstream failures; cancellation and cleanup; concurrent same/different model requests with models-max=1.
3. Retain all existing ROCm/ngram-model tuning behavior, engine resolution, guard hooks and idle-unload settings. Test actual staged-model preset equivalence separately, output redirected to scratch.
4. Fix proxy startup/shutdown/port contention and UNLOAD menu cleanup where required by tests. Keep changes confined to the plugin, tests and documentation.
5. Run the complete regression suite, syntax/diff checks and an independent review. No commit/push.
6. Exercise the repaired proxy with the real ROCm engine in an isolated runtime on temporary localhost ports, sequential dense and MoE loads, genuine streaming completion and tool-call smoke tests. Do not run a competing GPU model concurrently; inventory the existing router first. No inference output fabricated or inferred from model listings.
7. Apply verified source locally with machine overrides preserved. If safe live activation is not possible without restarting the serving gateway, leave installed activation pending and state that boundary explicitly. Do not call fully deployed until real end-to-end acceptance is verified.
8. Record exact rollback commands and final modified files/test results. No commits, pushes, publishing or remote mutations without explicit separate approval.

# Repository maintenance rules

These rules apply to work on llamacpp-tuned. Read [doc/README.md](doc/README.md) before changing behavior.

## Required changelog for every change

- Every bug fix, feature, refactor, configuration/default change, dependency change, deployment adjustment or documentation reorganization MUST add a Markdown entry to `doc/changelogs/` before the task is called complete. Documentation-only maintenance also needs an entry.
- Name entries `YYYY-MM-DD-short-description.md`, using the actual local date. Use a distinct descriptive suffix for separate changes on the same day. Do not invent a commit ID for uncommitted work.
- Use [the changelog template](doc/templates/changelog.md). Explain the symptom/reason, changes, unchanged behavior, hardware/backend impact, tests actually run, failures/limits, migration/rollback and commit/push status.
- Update the [changelog index](doc/changelogs/README.md) and relevant documentation links in the same task. Do not create loose `CHANGELOG_LOCAL.md`, `REPAIR_PLAN.md` or benchmark reports in the repository root.
- Keep published/historical entries intact; document later corrections in a linked new entry. An in-progress entry may be extended while that same task is being completed.

## Evidence and testing

- Keep measured performance reports under `doc/benchmarks/`, test reports under `doc/tests/`, compatibility assessments under `doc/compatibility/`, runbooks under `doc/operations/`, plans under `doc/plans/`, and reviews under `doc/reviews/`.
- Use [the benchmark template](doc/templates/benchmark.md). Record hardware, backend/build, exact model/quant, context, flags, workload, method and raw evidence. Never turn fixture results or short smoke tests into GPU/performance claims.
- Preserve failures and limitations. Label imported historical material and conflicting/stale conclusions instead of silently rewriting the original measurements.
- Use Qwen models as the default live test targets, not Ornith. Do not alter the user's chat/provider selection just to test an API.
- Run relevant tests before reporting completion. For Python/desktop changes: `python -m unittest discover -s tests -v`, `node tests/test_desktop.cjs`, `node --check desktop/plugin.js`, and `git diff --check`. Document skipped checks and why.
- Documentation-only edits do not require GPU inference. Verify local links, JSON evidence and archive hashes instead.

## Safety and portability

- Before changing shared backend/preset/engine/lifecycle behavior, read [this AMD machine's compatibility baseline](doc/compatibility/amd-890m-windows.md) and complete the [cross-machine checklist](doc/compatibility/cross-machine-checklist.md). Work from the RTX computer must preserve the AMD path, and vice versa; do not equate fixture validation with a real GPU test.
- Preserve each computer's ignored `dashboard/settings.json`, engine, models and hardware-specific tunes. Do not copy AMD engine paths/context caps to the CUDA machine.
- Do not store credentials, model weights, binaries or whole private session logs in `doc/`.
- Archived benchmark scripts may stop every llama-server or write fixed machine paths. Read them before execution; their presence is not permission to run them.
- Never restart the gateway hosting the current task from inside itself or evade its restart guard.
- Do not commit, push, publish or update another computer without explicit user approval. A request to fix code or write a changelog is not approval to commit or push.

## Completion checklist

- [ ] Requested work is implemented and relevant checks have real results.
- [ ] A new entry exists in `doc/changelogs/` and is linked in its index.
- [ ] Relevant reports/evidence and migration instructions are updated.
- [ ] Hardware-specific claims distinguish local runs, fixtures and untested remote behavior.
- [ ] No settings, model data, credentials or unrelated work were overwritten.
- [ ] Final response states what changed, verification and anything still unverified.

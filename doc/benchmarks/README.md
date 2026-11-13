# Benchmarks

## Available records

- [AMD Radeon 890M — historical paired sessions, 2026-11-11](amd-890m/2026-11-11/README.md): original report/setup notes, raw matrix and Qwen-variant results, script/input snapshots and caveats.
- [RTX 3070 — existing repository evidence and gaps](rtx-3070/README.md): where the CUDA claims originate, and what has not been copied or re-tested on this machine.

Live proxy activation and brief generated replies belong under [tests](../tests/README.md), not in performance tables. The [compatibility check](../compatibility/README.md) verifies generated CUDA flags, not CUDA throughput.

## New measurements

Use the [benchmark template](../templates/benchmark.md). Put each run under a hardware/backend folder and a measurement-date/scenario folder. Record exact model identity, engine build, settings and raw results; use paired same-session A/B measurements for performance comparisons.

Historical files are archived evidence, not instructions to run old launchers or change the current server. Prefer Qwen for new tests. Preserve original results and document corrections separately. Do not automatically start any archived script: some force-stop every llama-server process and write absolute machine paths.

## Desktop archive import

The [RTX 3070 index](rtx-3070/README.md) now links historical charts, cache-sweep JSONs, model-evaluation records with corrections, and import hashes.

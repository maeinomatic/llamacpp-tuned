# RTX 3070 benchmark evidence

## What is available locally

The repository's pre-existing [README tested setup](../../../README.md#tested-setup-development-machine) records RTX 3070 / CUDA benchmark claims. The imported preset generator also contains historical expert-cache measurements in its comments. These claims came with upstream revision `7ff3582`; they were not newly measured during the local AMD proxy repair.

For preserved cache sizes and a source/fixture compatibility assessment, see [compatibility](../../compatibility/README.md) and the [repair changelog](../../changelogs/2026-11-13-proxy-reliability-and-rocm-activation.md).

## Evidence gap

The other computer's raw CUDA benchmark files/logs are not present in this imported archive. No live RTX 3070 inference or performance benchmark was run during this work. Do not present AMD results, source comments or CUDA preset fixtures as a current RTX benchmark.

When those original records are made available, import them into a separate dated run folder with source hashes, actual hardware/build/model settings and the [benchmark template](../../templates/benchmark.md). Do not manufacture missing rows or silently treat historical throughput as current performance.

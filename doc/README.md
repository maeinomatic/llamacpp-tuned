# Documentation

## Start here

| Section | Contents |
|---|---|
| [Changelogs](changelogs/README.md) | Dated changes, verification, migration and rollback notes |
| [Benchmarks](benchmarks/README.md) | Hardware-separated performance reports and preserved raw results |
| [Tests](tests/README.md) | Automated regression checks and real-model smoke-test evidence |
| [Compatibility](compatibility/README.md) | AMD/ROCm versus RTX 3070/CUDA scope and limitations |
| [Operations](operations/README.md) | Activation, ports, settings preservation and safe troubleshooting |
| [Plans](plans/README.md) | Historical implementation/test plans, not proof of completion |
| [Reviews](reviews/README.md) | Historical failure findings and review evidence |
| [Templates](templates/README.md) | Required changelog and benchmark report structures |

## Documentation policy

[AGENTS.md](../AGENTS.md) makes a changelog entry mandatory for each change, including documentation-only maintenance. Entries belong in `doc/changelogs/`, not at the repository root. Add a new entry using the [template](templates/changelog.md), update the [index](changelogs/README.md), and record tests actually executed plus remaining limits.

## Evidence labels

- **Real-model smoke test:** actual inference on the named machine; not a throughput or long-context-quality benchmark.
- **Fixture/structural check:** source or explicit fixture validation; not a live CUDA test.
- **Historical benchmark:** earlier measurements, with their original hardware/session limitations.
- **Historical review/plan:** findings or intentions from that stage; may describe failures subsequently repaired.

The [provenance manifest](provenance.json) records original source paths and SHA-256 values for imported material. Original benchmark sources outside the repo were copied, not removed. The two loose root changelog/plan files were moved into their corresponding sections. No GGUFs, engines, credentials or full private session logs were imported.

The benchmark archive contains older broad recommendations and some inconsistent labels/conclusions. Read the [archive caveats](benchmarks/amd-890m/2026-11-11/README.md); do not treat the copied text as current verified advice.

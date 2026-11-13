# AMD Radeon 890M — archived benchmark sessions

**Historical evidence, imported on 2026-11-13; no performance benchmark was re-run during this import.** The original report labels its primary session 2026-11-11 and describes a follow-up paired session separately. Hardware/build metadata are recorded in the original report and setup notes; they have not been independently re-probed for this documentation task.

## Preserved sources

- [Original report](report-original.md), copied byte-for-byte from `C:/Users/jup03/llama-local/BENCHMARKS.md`.
- [Original setup notes](setup-notes-original.md), copied byte-for-byte from that directory's README.
- [Primary matrix raw results](results.json).
- [Qwen variant re-run raw results](variant-verification.json).
- [Matrix script snapshot](scripts/matrix_bench.py), [variant script snapshot](scripts/verify_unc.py) and [reproduction input](inputs/doc.txt).

Original files outside the repository were retained. Hashes and source paths are recorded in [the provenance manifest](../../../provenance.json). The scripts are historical machine-specific snapshots, not maintained portable test entry points.

## Important caveats and corrections to interpretation

1. The original report combines measurements and later notes. Some early conclusions conflict with its own later re-run tables. In particular, a universal ROCm-over-Vulkan ranking is not justified by the later base-decode session. Compare conditions within the same paired session.
2. The original report labels `Qwen3.5-9B` as MoE in places. That historical label must not be used to classify the actual GGUF; the plugin uses its header/profile. Likewise, censorship/quality recommendations and model-store inventories in the copied notes are historical claims, not current validation.
3. A blanket 'within 5%' statement in the report is stronger than all cells in the raw variant re-run support. Preserve the raw cells; do not propagate that claim without a correctly scoped calculation.
4. Context-copy/RAG gains are not ordinary-generation gains. A short tool-call JSON probe is not a complete agent/coding-quality benchmark.
5. The matrix script requests 300 output tokens for its chat workload; prose descriptions such as '250-word story' describe the prompt, not a guaranteed actual output length. Use raw `gen_n` when available.
6. The archived scripts contain a blanket `taskkill /IM llama-server.exe /F` helper and fixed output paths. **Do not execute them while the live plugin is running.** Future automation should target only processes it owns and require an approved test window.
7. Manual 4K/8K benchmark contexts and old provider-switch commands are not instructions to change the current Hermes setup. See [operations](../../../operations/README.md) for current serving boundaries.
8. Qwen is the user's preferred target for new tests; historical Ornith rows remain for record integrity, not as a recommendation.

This wrapper corrects interpretation without editing the byte-preserved original report or inventing missing measurements. Raw server logs not included here remain in the original local benchmark workspace; not every prose claim has a matching structured result in this archive.

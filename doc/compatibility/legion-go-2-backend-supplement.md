# Legion Go 2 — clarification of imported backend notes

> **Applies to: Lenovo Legion Go 2 — Ryzen Z2 Extreme, Radeon 890M, 32 GB shared RAM, Windows 11; recorded ROCm/HIP b12110.**
> Compiled/reviewed on the RTX desktop from the Legion’s documented baseline; not a new Legion test.

The authoritative recorded setup is [AMD 890M Windows](amd-890m-windows.md):
Ryzen Z2 Extreme, 32 GB shared RAM, Windows 11, **portable ROCm/HIP build b12110**
(`cd959bae9`), selected via the machine-local `engine_path`. Its recorded
`dense_ngram: true`, dense context 65536 and MoE cap 131072 must be preserved.

Earlier desktop-session notes incorrectly assumed Vulkan/b12255 was the Legion's
active backend and suggested a gfx target without checking. Those assertions are
withdrawn. Vulkan is an installer fallback, not proof of the actual selected engine.
No new Legion measurements were performed from this desktop.

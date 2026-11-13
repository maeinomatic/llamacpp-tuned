# YYYY-MM-DD — Hardware / workload benchmark

## Measurement identity

- Measurement date/session:
- Report date (if different):
- Hardware: GPU/VRAM or UMA budget, CPU, RAM, OS/driver:
- Backend / exact engine build and revision:
- Plugin revision plus uncommitted changes:
- Exact model repository, GGUF filename and quantization:

## Configuration and workload

- Context, batch/ubatch, cache types and offload:
- Speculation / expert-cache settings:
- Sampling, prompt/input and requested/actual output tokens:
- Warm/cold state, prompt-cache behavior, concurrent load:
- Paired A/B method and repetitions:

## Results

| Condition | Prefill | Decode | Draft acceptance | Errors / caveats |
|---|---|---|---|---|
| Measured condition only | Units | Units | If observed | Preserve failures |

## Evidence and reproduction

Link raw structured results, selected sanitized logs, input and script/command. Explain any machine-specific paths or destructive behavior in archived scripts. Do not bundle model weights, binaries or credentials.

## Conclusions and limits

Separate context-copy/RAG from novel generation. Separate same-session results from historical numbers. Do not generalize AMD results to CUDA or infer long-context quality from a successful load. Label missing cells as untested, never estimate them silently.

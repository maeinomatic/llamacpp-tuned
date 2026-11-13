# llamacpp-tuned compatibility review

## Verdict: do not pull/apply origin/main as-is

Installed: fdfadc0f0325e7b7a2be8c5bf137e1013ceacd04
Reviewed: 7ff358270a4dbf359de4502c46ef20f94976b599
Incoming commits: 14.

No commit, push, merge, installed-file edit, config change, model download, or live model load/unload/restart was performed. `git fetch origin` updated remote-tracking metadata only. Incoming files and test outputs were extracted into this scratch directory. The test script uses explicit HTTP fixtures, not synthetic model-inference results.

## This machine / tune compatibility: PASS

Hardware discovery: AMD Radeon 890M; no nvidia-smi on PATH.
Existing router: PID 68708, C:/Users/jup03/llama-local/llama-rocm10/llama-server.exe, public port 8080.

Both revisions were imported and their real preset generators exercised using this machine's settings, actual staged GGUF headers, Hermes estimator, and the same live planning budget. Generated outputs were redirected to scratch, not the installed preset file.

- All seven staged models were emitted by both revisions.
- Old and incoming generated presets were byte-identical.
- Incoming tune values also matched every corresponding value in the running router's /v1/models status presets. This comparison used the live in-memory presets, not merely the on-disk file, which differs from the running configuration.
- Custom engine_path still resolves to the same existing ROCm binary.
- Six dense presets keep context 65536, q8_0 K/V cache, flash-attn on, ubatch-size 512, ngram-mod max/min/match 16/2/24.
- Huihui-gpt-oss-20b-abliterated-v2-MXFP4_MOE keeps context 131072, q4_0 K/V cache, expert-to-CPU override, load-mode none, ngram-mod max/min 10/2.
- No CUDA moe-cache-mib/moe-cache-cpu-share options were emitted on this AMD host.
- Every generated command-line option was present in the existing engine's --help.
- local_guard_fix remains true in the unchanged machine settings. __init__.py is unchanged by the incoming revision.

This establishes tuning/config compatibility, not a full inference acceptance test of the new proxy.

## Blocking regressions in dashboard/plugin_api.py

### 1. Enabling tuned mode also stops its proxy

Location: set_mode(), lines 852-879; unconditional _proxy_stop at line 873.

The proxy is stopped after either branch, including enabled=True. The router has moved to port 8081, so stopping its public 8080 proxy removes Hermes' normal access path. The state read-back may catch this as a failed enable, or race the asynchronous shutdown and briefly report success.

Reproduction: invoke actual set_mode(ModeRequest(enabled=True)) with subprocess/model/thread side effects isolated by test doubles. _proxy_stop was called.

Required correction: stop the proxy only in the disable path; verify public listener health after enabling and closed listener after disabling.

### 2. Catch-all route shadows both chat handlers

Location: catch-all registration lines 586-589 precedes specific chat registrations lines 592-594.

Starlette's real ordered matcher resolves POST /v1/chat/completions to _proxy_any before _proxy_chat. Consequently the intended serialization/load/keepalive logic is never reached.

Reproduction: ordered full matches were [_proxy_any, _proxy_chat]. Two simultaneous same-model chat requests through the actual proxy app reached the local fixture upstream concurrently (maximum active requests: 2).

Required correction: register specific routes before the catch-all; cover every supported chat path explicitly and add dispatch/concurrency tests.

### 3. Actual chat path buffers SSE instead of streaming

Location: _proxy_any calls _passthrough(..., False), lines 556-589.

The generic handler waits for the full response body before returning it. This breaks interactive token delivery and makes long requests vulnerable to the non-streaming 30-second read timeout during upstream silence. /models/sse is affected by the same catch-all behavior.

Reproduction: a real local HTTP fixture flushed an SSE first event immediately, then a DONE event after a 0.35-second delay. Through the incoming proxy, the first downstream bytes arrived approximately 0.352 seconds after the upstream first event and already contained DONE. The stream had been buffered to completion.

Required correction: forward SSE incrementally, keep the upstream client/response alive until downstream consumption ends, close on disconnect, and separate streaming timeouts from short control requests. Simply selecting the existing stream=True branch is insufficient: its AsyncClient context exits before the returned generator is consumed.

### 4. Intended cold-load keepalives do not cover cold load or prefill

Location: _proxy_chat(), load loop lines 641-651; generator/StreamingResponse lines 655-686.

Even after fixing route precedence, the handler awaits model residency before returning StreamingResponse. It cannot emit its promised pings during cold load. After lock acquisition it also waits on upstream headers/chunks without a concurrent heartbeat, leaving slow prefill uncovered. Pings currently only cover waiting for a busy per-model lock.

Reproduction: register the intended handler directly in a separate test app, bypassing the shadowing route. A fixture model load took 4.5 seconds. Client response headers arrived after 6.194 seconds (status polling included), and the first chunk was not a ping.

Required correction: begin the downstream streaming response before load/queue/prefill waits and emit periodic keepalives throughout those phases; test first-byte latency with delayed load and delayed prefill.

### 5. Intended handler masks upstream HTTP errors

Location: _proxy_chat() returns StreamingResponse without upstream status propagation, line 686.

Reproduction: with the intended handler registered directly and a fixture upstream returning HTTP 500, the client received HTTP 200.

Required correction: preserve error semantics. For a response already committed as HTTP 200 to enable early heartbeats, send an explicit compatible stream error event and terminate cleanly; do not present an upstream failure as successful completion.

## Additional concerns from source review

- Detached /models/load requests occur before the per-model lock and are not deduplicated. Concurrent cold requests can issue duplicate load requests even after the route-order fix.
- Serialization is per model while the router is configured with --models-max 1. Requests for different models still need residency/load coordination.
- The new UNLOAD menu creates a document.body backdrop but registers no unmount/disposal cleanup; disabling or reloading the plugin with the menu open can leave an input-blocking overlay. This is a source-review concern, not an exercised desktop UI test.
- Proxy bind retry catches OSError, but uvicorn can exit with SystemExit on bind failure; port-collision startup/recovery needs its own test before deployment.

## Checks and limits

Executed: real preset generation for both revisions; comparison against running in-memory model presets; engine --help capability check; actual ASGI route matching; localhost HTTP streaming/concurrency/status/latency tests; isolated mode lifecycle test; node --check; git diff --check.

Not executed: incoming plugin installation/hot reload; real GPU model loading or completion through the incoming proxy; desktop UNLOAD interaction; end-to-end Hermes agent/tool-call acceptance. Those would not justify applying a known-broken version during this review.

Final live read-back: original llama-server PID 68708 and original port-8080 command line unchanged; /health returned {"status":"ok"}; installed working tree clean and still at fdfadc0; machine settings hash unchanged.

## Recommended next step

Keep the installed revision. Prepare proxy corrections and regression tests in an isolated copy or branch only after authorization; do not commit or push without explicit user approval. Preserve this machine's settings.json and custom ROCm engine. After fixes pass, schedule a controlled enable/disable/re-enable, cold-load, streaming, and real dense-plus-MoE completion smoke test before calling the update safe.

Raw evidence: review-results.json, old-presets.ini, new-presets.ini, live-models-before.json, engine-help.txt. Reproducer: review_checks.py.

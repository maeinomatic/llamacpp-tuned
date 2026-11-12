"""Tuned llama.cpp router supervisor for Hermes.

Portable across machines and models:
- Engine: downloaded once from llama.cpp releases into
  HERMES_HOME/runtimes/llamacpp-tuned/ (no absolute personal paths), or a
  user-configured path via settings.json.
- Models: a preset INI is generated for EVERY staged GGUF in Hermes' models
  directory, tuned from the GGUF header and the machine's real VRAM budget:
  MoE models get expert-to-RAM offload + q4 KV + ngram lookup drafting at the
  model's full native window; dense models that fit stay fully in VRAM.
- Lifecycle: detached watchdog kills the router tree when the gateway dies;
  models unload after 15 min without token activity.
No arbitrary commands or paths are accepted over HTTP.
"""
import asyncio
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import threading
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, StrictBool

router = APIRouter()

# -- paths ----------------------------------------------------------------
def _hermes_home() -> Path:
    try:
        from hermes_constants import get_hermes_home
        return get_hermes_home().resolve()
    except Exception:
        env = os.environ.get("HERMES_HOME")
        if env:
            return Path(env).resolve()
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "hermes"

HOME_DIR = _hermes_home()
MODELS_DIR = HOME_DIR / "models"
ENGINE_DIR = HOME_DIR / "runtimes" / "llamacpp-tuned"
IS_WIN = platform.system() == "Windows"
ENGINE = ENGINE_DIR / ("llama-server.exe" if IS_WIN else "llama-server")
PRESET = ENGINE_DIR / "presets.ini"
LOG = ENGINE_DIR / "router.log"
SETTINGS_FILE = Path(__file__).parent / "settings.json"

PINNED_RELEASE = "b12255"
ENGINE_ASSETS = {  # (system, nvidia?) -> release asset name
    ("Windows", True): "llama-{tag}-bin-win-cuda-12.4-x64.zip",
    ("Windows", False): "llama-{tag}-bin-win-vulkan-x64.zip",
    ("Linux", True): "llama-{tag}-bin-ubuntu-cuda-12.8-x64.tar.gz",
    ("Linux", False): "llama-{tag}-bin-ubuntu-x64.tar.gz",
}

GUARD_SETTING = "local_guard_fix"
LEGACY_GUARD_SETTING = "local_write_guard_bypass"   # same opt-in under its old name

DEFAULTS = {"port": 8080, "idle_unload_s": 900, "poll_s": 60,
            "moe_ctx_cap": 262144, "dense_ctx": 32768,
            # Opt-in fix (chip toggle), OFF by default. While a write_file/patch call
            # from a session on one of the staged local models is executing, the
            # plugin rebinds the guard's snapshot helper to a version that takes ONE
            # metadata view (os.stat) and leaves byte identity to its sha256 -- this
            # filesystem's os.fstat/os.stat st_ctime_ns mismatch otherwise stops the
            # guard recording a whole-file baseline, so write_file refuses legitimate
            # overwrites. Sessions on other providers keep the shipped helper.
            "local_guard_fix": False,
            # Optional overrides for non-default machines (settings.json):
            # "engine_path": "<path to an existing llama-server binary>" —
            #   wins over everything (use your own CUDA/Vulkan/ROCm build);
            # "backend": "cuda"|"vulkan"|"cpu" — asset picked by /install
            #   instead of nvidia-smi auto-detection.
            "engine_path": "", "backend": ""}

_operation = threading.Lock()
_proc = None
_sweeper = None
_sse = None
_loading = {}   # model_id -> start time (chip state)
_state = {}     # download/install progress for the chip


def _settings() -> dict:
    try:
        return {**DEFAULTS, **json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))}
    except Exception:
        return dict(DEFAULTS)


def _bypass_setting() -> bool:
    """The persisted chip choice (accepting the pre-rename key). The guard itself is
    untouched here: the plugin's pre_tool_call hook applies or removes the corrected
    snapshot helper, scoped to write calls from local-model sessions.
    """
    s = _settings()
    return bool(s.get(GUARD_SETTING, s.get(LEGACY_GUARD_SETTING, False)))


def _write_settings(patch: dict) -> None:
    """Merge *patch* into settings.json, preserving the machine overrides there."""
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    data.update(patch)
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


# -- engine acquisition ---------------------------------------------------
def _nvidia() -> bool:
    return shutil.which("nvidia-smi") is not None


def _engine_asset(tag: str) -> str:
    backend = (_settings().get("backend") or "").lower() or ("cuda" if _nvidia() else "cpu")
    if backend == "rocm":
        backend = "vulkan"  # no official HIP assets; AMD cards ride the Vulkan build
    key = (platform.system(), backend == "cuda")
    name = ENGINE_ASSETS.get(key)
    if name is None:
        if platform.system() == "Darwin":
            name = ("llama-{tag}-bin-macos-arm64-metal.tar.gz" if platform.machine() == "arm64"
                    else "llama-{tag}-bin-macos-x64-metal.tar.gz")
        else:
            raise RuntimeError(f"no engine asset mapping for {platform.system()}/{backend}")
    return name.format(tag=tag)


def _install_engine(tag: str = PINNED_RELEASE) -> None:
    """Download the llama.cpp release for this platform into ENGINE_DIR."""
    global _state
    _state = {"stage": "download", "percent": 0}
    base = f"https://github.com/ggml-org/llama.cpp/releases/download/{tag}"
    url = f"{base}/{_engine_asset(tag)}"
    tmp = ENGINE_DIR / "download.tmp"
    ENGINE_DIR.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=60) as resp, open(tmp, "wb") as out:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
            done += len(chunk)
            if total:
                _state = {"stage": "download", "percent": round(100 * done / total)}
    _state = {"stage": "extract", "percent": 0}
    if url.endswith(".zip"):
        with zipfile.ZipFile(tmp) as z:
            z.extractall(ENGINE_DIR)
    else:
        with tarfile.open(tmp) as t:
            t.extractall(ENGINE_DIR)
    tmp.unlink(missing_ok=True)
    # flat or nested extraction -- find the binary (exact name; llama-server-impl.dll etc.)
    candidates = [p for p in ENGINE_DIR.rglob("llama-server.exe" if IS_WIN else "llama-server")]
    if not candidates:
        candidates = list(ENGINE_DIR.rglob("llama-server*"))
    if not candidates:
        raise RuntimeError("llama-server not found in the downloaded archive")
    exe = candidates[0]
    if exe != ENGINE:
        shutil.copy2(exe, ENGINE)
        os.chmod(ENGINE, 0o755)
    _state = {"stage": "done", "percent": 100}


def _engine_ready() -> bool:
    return ENGINE.is_file()


def _resolve_engine() -> str:
    """Engine resolution order:
    1. settings.json "engine_path" — a user-provided llama-server binary
       (e.g. an existing CUDA/Vulkan/ROCm build on another machine);
    2. Hermes' own PM-installed engine when its build is new enough
       (PM manages it, the Desktop update button upgrades it);
    3. the plugin's own copy in runtimes/llamacpp-tuned/ (outside PM's
       managed dir, so a Desktop update can never clobber it).
    """
    custom = (_settings().get("engine_path") or "").strip()
    if custom and Path(custom).is_file():
        return custom
    try:
        from hermes_cli.local_runtime.binaries import installed_engine
        eng = installed_engine(os.environ.get("LLAMACPP_TUNED_BACKEND", "auto"))
        if eng is not None:
            build = int(str(eng.tag).lstrip("b"))
            if build >= 12255 and Path(eng.binary).is_file():
                return str(eng.binary)
    except Exception:
        pass
    return str(ENGINE)


# engine actually in use right now (resolved at spawn; kept in state)
_engine_in_use: str | None = None


# -- preset generation (model-independent) --------------------------------
def _gguf_tools():
    from hermes_cli.local_runtime.gguf import model_id_from_stem, read_gguf_header
    from hermes_cli.local_runtime.estimator import profile_from_gguf
    return model_id_from_stem, read_gguf_header, profile_from_gguf


def _vram_bytes() -> int:
    """Usable VRAM budget, best effort."""
    try:
        from hermes_cli.local_runtime.hardware import probe_budget
        return int(probe_budget(planning=True).usable_vram_bytes)
    except Exception:
        return 8 << 30  # assume 8 GiB


def _generate_presets() -> int:
    """Write a tuned section for every staged GGUF. Returns the count."""
    model_id_from_stem, read_gguf_header, profile_from_gguf = _gguf_tools()
    vram = _vram_bytes()
    s = _settings()
    reserve = 2 << 30  # compute buffers + headroom
    sections, count = [], 0
    for gguf in sorted(MODELS_DIR.glob("*.gguf")):
        if gguf.is_symlink() and not gguf.exists():
            continue
        try:
            header = read_gguf_header(gguf)
            profile = profile_from_gguf(header)
        except Exception:
            continue
        model_id = model_id_from_stem(gguf.stem)
        native_ctx = profile.n_ctx_train or 32768
        kv_per_tok = max(profile.per_token_kv_f16, 1)
        # Core's layer classifier marks a layer RECURRENT only when the file gives it
        # zero KV heads. qwen3next (Qwen3-Next-80B) instead declares its hybrid split
        # in `recurrent_blocks`, which the classifier ignores, so every layer — including
        # the ~36 Gated-DeltaNet layers whose state is constant, not a growing KV cache —
        # is charged per-token KV. That overcharged the 80B ~4x (98304 B/token instead of
        # 24576) and would have cut its window from 256K to ~87K. Re-derive from the
        # blocks the file actually declares; verified on an 8 GB RTX 3070: the corrected
        # 256K preset loads (q4 KV, 5.6 GiB VRAM).
        n_recurrent = len(header.recurrent_blocks)
        if n_recurrent and not profile.recurrent_layer_count and profile.layers:
            per_layer = kv_per_tok / len(profile.layers)
            kv_per_tok = max(int(round(per_layer * (len(profile.layers) - n_recurrent))), 1)
        keys = {"model": str(gguf).replace("\\", "/"),
                "flash-attn": "on", "ubatch-size": "512"}
        if profile.moe:
            # experts to RAM, attention on GPU, q4 KV, lookup drafting at the
            # model's native window capped so q4 KV + buffers fit VRAM
            keys["override-tensor"] = r"blk\.\d+\.ffn_.*_exps\.weight=CPU"
            keys["cache-type-k"] = keys["cache-type-v"] = "q4_0"
            budget_kv = max(vram - reserve, 512 << 20)
            ctx = min(native_ctx, int(s["moe_ctx_cap"]),
                      int(budget_kv // (kv_per_tok * 0.5)))
            ctx = max(min(ctx, native_ctx), 4096)
            keys["ctx-size"] = str(ctx)
            keys["spec-type"] = "ngram-mod"
            keys["spec-ngram-mod-n-max"] = "10"
            keys["spec-ngram-mod-n-min"] = "2"
            keys["load-mode"] = "none"
        else:
            w = profile.weights_bytes
            if w + reserve <= vram:
                keys["ctx-size"] = str(min(native_ctx, int(s["dense_ctx"])))
                keys["cache-type-k"] = keys["cache-type-v"] = "q8_0"
            else:
                # dense too big: FFN layers to CPU (attention split), q8 KV
                keys["override-tensor"] = r"blk\.\d+\.ffn_.*\.weight=CPU"
                keys["cache-type-k"] = keys["cache-type-v"] = "q8_0"
                keys["load-mode"] = "none"
                budget_kv = max(vram - reserve - w, 256 << 20)
                ctx = min(native_ctx, int(s["dense_ctx"]),
                          int(budget_kv // kv_per_tok))
                keys["ctx-size"] = str(max(ctx, 4096))
        body = "\n".join(f"{k} = {v}" for k, v in keys.items())
        sections.append(f"[{model_id}]\n{body}\n")
        count += 1
    PRESET.parent.mkdir(parents=True, exist_ok=True)
    PRESET.write_text("\n".join(sections), encoding="utf-8")
    return count


# -- router control -------------------------------------------------------
def _base() -> str:
    return f"http://127.0.0.1:{_settings()['port']}"


def _req(path, body=None, timeout=10):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(_base() + path, data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _health() -> bool:
    try:
        _req("/health", timeout=3)
        return True
    except Exception:
        return False


def _models_status():
    try:
        return {m["id"]: (m.get("status") or {}).get("value", "")
                for m in _req("/models").get("data", [])}
    except Exception:
        return {}


def _loaded_models():
    return [m for m, s in _models_status().items() if s == "loaded"]


# -- load progress (the router relays per-tensor progress ONLY over its
#    /models/sse stream; /models carries just the coarse status) -----------
_progress = {}          # model_id -> {"percent","stage","ts"}
_TEXT_STAGE_SHARE = 0.85
_STALE_TTL_S = 120.0


def _pct(x):
    return max(0, min(100, round(x * 100)))


def _composite(stages, current, value):
    if not stages or current not in stages or len(stages) == 1:
        return _pct(value)
    extras = [s for s in stages if s != "text_model"]
    extra_share = (1.0 - _TEXT_STAGE_SHARE) / len(extras) if extras else 0.0
    offset = 0.0
    for stage in stages:
        share = _TEXT_STAGE_SHARE if stage == "text_model" else extra_share
        if stage == current:
            return _pct(offset + share * value)
        offset += share
    return _pct(value)


def _sse_watch():
    while True:
        try:
            req = urllib.request.Request(_base() + "/models/sse",
                                         headers={"Accept": "text/event-stream"})
            with urllib.request.urlopen(req) as resp:
                event, data = None, {}
                for raw in resp:
                    line = raw.decode(errors="replace").rstrip("\r\n")
                    if line.startswith("event:"):
                        event = line[6:].strip()
                    elif line.startswith("data:"):
                        try:
                            payload = json.loads(line[5:].strip() or "{}")
                        except Exception:
                            payload = {}
                        if isinstance(payload, dict):
                            # b12255 shape: {"model","event","data":{"status","progress"}}
                            inner = payload.get("data")
                            data = inner if isinstance(inner, dict) else {}
                            data.setdefault("model", payload.get("model", ""))
                            data.setdefault("event", payload.get("event", ""))
                    elif line == "" and event:
                        model = str(data.get("model", ""))
                        status = str(data.get("status", ""))
                        if data.get("event", event) in ("status_change", "model_status") and model:
                            if status == "loading":
                                prog = data.get("progress") or {}
                                _progress[model] = {
                                    "percent": _composite(
                                        [str(s) for s in (prog.get("stages") or [])],
                                        str(prog.get("current", "")),
                                        prog.get("value") or 0),
                                    "stage": str(prog.get("current", "")),
                                    "ts": time.monotonic(),
                                }
                            else:
                                _progress.pop(model, None)
                        event, data = None, {}
        except Exception:
            pass
        time.sleep(3.0)  # router down -- reconnect with backoff


def _progress_state() -> dict:
    now = time.monotonic()
    for m in [m for m, e in _progress.items() if now - e["ts"] > _STALE_TTL_S]:
        _progress.pop(m, None)
    return {m: {"percent": e["percent"], "stage": e["stage"]}
            for m, e in _progress.items()}


def _idle_sweeper():
    """Unload every loaded model after idle_unload_s without token activity."""
    cfg = _settings()
    last_sig, last_change = None, time.time()
    while True:
        time.sleep(cfg["poll_s"])
        if not _health():
            last_sig, last_change = None, time.time()
            continue
        loaded = _loaded_models()
        if not loaded:
            last_sig, last_change = None, time.time()
            continue
        sig = _token_totals()
        if sig and sig != last_sig:
            last_sig, last_change = sig, time.time()
        elif sig == last_sig and time.time() - last_change >= cfg["idle_unload_s"]:
            for model in loaded:
                try:
                    _req("/models/unload", {"model": model}, timeout=120)
                except Exception:
                    pass
            last_sig, last_change = None, time.time()


def _token_totals() -> dict:
    """Per-loaded-model token activity signature from /metrics?model=..."""
    sig = {}
    for model in _loaded_models():
        try:
            with urllib.request.urlopen(
                    f"{_base()}/metrics?model={urllib.parse.quote(model)}", timeout=5) as r:
                text = r.read().decode(errors="replace")
        except Exception:
            continue
        totals = 0.0
        for line in text.splitlines():
            if line.startswith("#") or " " not in line:
                continue
            name, _, val = line.partition(" ")
            if name in ("llamacpp:tokens_predicted_total", "llamacpp:prompt_tokens_total"):
                try:
                    totals += float(val)
                except ValueError:
                    pass
        sig[model] = totals
    return sig


def _attach_watchdog(proc):
    """Detached watcher: if this gateway process dies, kill the router tree.

    Windows job objects are unreliable here (AssignProcessToJobObject can be
    refused when the gateway already sits inside another job). Never probe
    liveness with os.kill(pid, 0) on Windows -- os.kill TERMINATES the target.
    """
    watchdog_src = (
        "import ctypes,subprocess,sys\n"
        "SYNCHRONIZE=0x00100000; INFINITE=0xFFFFFFFF\n"
        "ppid, rpid = int(sys.argv[1]), sys.argv[2]\n"
        "h = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, ppid)\n"
        "if h:\n"
        "    ctypes.windll.kernel32.WaitForSingleObject(h, INFINITE)\n"
        "subprocess.run(['taskkill','/PID',rpid,'/T','/F'], capture_output=True)\n"
        if IS_WIN else
        "import os,signal,subprocess,sys,time\n"
        "ppid, rpid = int(sys.argv[1]), int(sys.argv[2])\n"
        "while True:\n"
        "    time.sleep(2)\n"
        "    try: os.kill(ppid, 0)\n"
        "    except OSError:\n"
        "        os.kill(rpid, signal.SIGTERM); break\n")
    subprocess.Popen(
        [sys.executable, "-c", watchdog_src, str(os.getpid()), str(proc.pid)],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=(getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
                       | getattr(subprocess, "CREATE_NO_WINDOW", 0)) if IS_WIN else 0)


def _spawn():
    global _engine_in_use
    ENGINE_DIR.mkdir(parents=True, exist_ok=True)
    _generate_presets()
    log = open(LOG, "a")
    engine = _resolve_engine()
    _engine_in_use = engine
    proc = subprocess.Popen(
        [engine, "--models-preset", str(PRESET), "--models-max", "1",
         "--port", str(_settings()["port"]), "--metrics", "--host",
         "127.0.0.1"],
        stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if IS_WIN else 0)
    _attach_watchdog(proc)
    return proc


def _wait_healthy(timeout_s=180):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if _health():
            return True
        if _proc and _proc.poll() is not None:
            return False
        time.sleep(2)
    return False


def _ensure_threads():
    global _sweeper, _sse
    if _sweeper is None or not _sweeper.is_alive():
        _sweeper = threading.Thread(target=_idle_sweeper, daemon=True,
                                    name="llamacpp-tuned-idle")
        _sweeper.start()
    if _sse is None or not _sse.is_alive():
        _sse = threading.Thread(target=_sse_watch, daemon=True,
                                name="llamacpp-tuned-progress")
        _sse.start()


def _read_state():
    global _engine_in_use
    running = _proc is not None and _proc.poll() is None and _health()
    engine = _engine_in_use or _resolve_engine()
    return {"enabled": _proc is not None,
            "running": running,
            "loaded": _loaded_models() if running else [],
            "loading": sorted(_loading) if running else [],
            "progress": _progress_state() if running else {},
            "models": list(_models_status()) if running else [],
            "port": _settings()["port"] if running else None,
            "engine": engine,
            "engine_ready": Path(engine).is_file(),
            "engine_progress": dict(_state),
            "local_guard_fix": _bypass_setting(),
            "busy": _operation.locked()}


# -- HTTP API -------------------------------------------------------------
@router.get("/status")
def get_status():
    return _read_state()


class ModeRequest(BaseModel):
    enabled: StrictBool


class LoadRequest(BaseModel):
    model: str


class InstallRequest(BaseModel):
    tag: str | None = None


@router.post("/install")
async def install_engine(body: InstallRequest | None = None):
    """Download the llama.cpp engine into HERMES_HOME/runtimes/llamacpp-tuned."""
    if not _operation.acquire(blocking=False):
        raise HTTPException(409, "Another operation is already running.")
    try:
        await asyncio.to_thread(_install_engine,
                                (body.tag if body else None) or PINNED_RELEASE)
        return _read_state()
    except Exception as exc:
        raise HTTPException(502, f"Engine install failed: {exc}")
    finally:
        _operation.release()


@router.post("/load")
async def load_model(body: LoadRequest):
    """Start loading a staged model now (pre-load ahead of the chat request)."""
    global _proc
    if not Path(_resolve_engine()).is_file():
        raise HTTPException(503, "llama-server engine is not installed (POST /install first).")
    if not _operation.acquire(blocking=False):
        raise HTTPException(409, "Another operation is already running.")
    try:
        if not (_proc and _proc.poll() is None):
            _proc = await asyncio.to_thread(_spawn)
            if not await asyncio.to_thread(_wait_healthy):
                tail = LOG.read_text(errors="replace")[-600:] if LOG.exists() else ""
                raise HTTPException(502, "Tuned router failed to become healthy. " + tail)
        _ensure_threads()
        if body.model not in _loaded_models():
            _loading[body.model] = time.monotonic()

            def _do_load():
                try:
                    _req("/models/load", {"model": body.model}, timeout=1800)
                finally:
                    _loading.pop(body.model, None)

            threading.Thread(target=_do_load, daemon=True).start()
        return _read_state()
    finally:
        _operation.release()


@router.post("/mode")
async def set_mode(body: ModeRequest):
    global _proc
    if body.enabled and not Path(_resolve_engine()).is_file():
        raise HTTPException(503, "llama-server engine is not installed (POST /install first).")
    if not _operation.acquire(blocking=False):
        raise HTTPException(409, "Another mode change is already running.")
    try:
        if body.enabled:
            if not (_proc and _proc.poll() is None):
                _proc = await asyncio.to_thread(_spawn)
                if not await asyncio.to_thread(_wait_healthy):
                    tail = LOG.read_text(errors="replace")[-600:] if LOG.exists() else ""
                    raise HTTPException(502, "Tuned router failed to become healthy. " + tail)
            _ensure_threads()
        else:
            if _proc and _proc.poll() is None:
                await asyncio.to_thread(_proc.terminate)
                await asyncio.to_thread(_proc.wait, 30)
            _proc = None
        state = _read_state()
        if state["enabled"] != body.enabled:
            raise HTTPException(502, "Read-back did not confirm the requested mode.")
        return state
    finally:
        _operation.release()


class FileGuardRequest(BaseModel):
    enabled: StrictBool


@router.post("/file-guard")
async def set_file_guard(body: FileGuardRequest):
    """Chip toggle for the LOCAL-MODEL guard fix.

    OFF (default) leaves Hermes' read-before-write guard exactly as shipped. ON lets
    the plugin's pre_tool_call hook rebind the guard's snapshot helper -- only while a
    write_file/patch call from a session on one of this router's staged local models is
    executing -- to a version that takes one consistent metadata view and leaves byte
    identity to its sha256. That is the fix for a filesystem where the guard can never
    record a whole-file baseline. Sessions on any other provider (Codex, Copilot,
    OpenRouter, ...) keep the shipped helper.

    The choice persists in settings.json and the hooks pick it up on the next tool
    call, so no gateway restart is involved."""
    _write_settings({GUARD_SETTING: bool(body.enabled)})
    state = _read_state()
    if state["local_guard_fix"] != bool(body.enabled):
        raise HTTPException(502, "Read-back did not confirm the write-guard setting.")
    return state

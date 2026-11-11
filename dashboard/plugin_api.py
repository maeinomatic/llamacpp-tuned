"""Tuned llama.cpp router supervisor. Fixed-purpose: starts/stops the tuned
llama-server (b12255 router mode) for the staged Qwen3.5 GGUFs, unloads models
after 15 min of no token activity, and a detached watchdog kills the router
tree when this gateway process dies. No arbitrary commands or paths are
accepted over HTTP.
"""
import asyncio
import json
import os
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, StrictBool

router = APIRouter()

ENGINE = Path.home() / "AppData/Local/hermes/llamacpp-bench/llama-server.exe"
PRESET = Path(__file__).parent / "tuned-presets.ini"
LOG = Path.home() / "AppData/Local/hermes/llamacpp-bench/router-plugin.log"
PORT = 8080
IDLE_UNLOAD_S = 15 * 60
POLL_S = 60

_operation = threading.Lock()
_proc: subprocess.Popen | None = None
_sweeper: threading.Thread | None = None


def _base() -> str:
    return f"http://127.0.0.1:{PORT}"


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


def _loaded_models() -> list[str]:
    try:
        data = _req("/models").get("data", [])
        return [m["id"] for m in data
                if (m.get("status") or {}).get("value") == "loaded"
                or m.get("status") == "loaded"]
    except Exception:
        return []


def _all_models() -> list[str]:
    try:
        return [m["id"] for m in _req("/models").get("data", [])]
    except Exception:
        return []


# --- load progress (mirrors Hermes' local_runtime.load_progress: the router
# relays per-tensor {stages,current,value} only over its /models/sse stream) ---
_progress = {}          # model_id -> {"percent": int, "stage": str, "ts": float}
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
    """Subscribe to the router's /models/sse and track load progress."""
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
                        payload = json.loads(line[5:].strip() or "{}")
                        if not isinstance(payload, dict):
                            payload = {}
                        # b12255 shape: {"model": ..., "event": ..., "data": {"status","progress"}}
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
        time.sleep(3.0)  # router down / restarted — reconnect with backoff


def _progress_state() -> dict:
    now = time.monotonic()
    for m in [m for m, e in _progress.items() if now - e["ts"] > _STALE_TTL_S]:
        _progress.pop(m, None)
    return {m: {"percent": e["percent"], "stage": e["stage"]}
            for m, e in _progress.items()}


_sse: threading.Thread | None = None


def _ensure_threads():
    """Start the idle sweeper and the SSE progress watcher once."""
    global _sweeper, _sse
    if _sweeper is None or not _sweeper.is_alive():
        _sweeper = threading.Thread(target=_idle_sweeper, daemon=True,
                                    name="llamacpp-tuned-idle")
        _sweeper.start()
    if _sse is None or not _sse.is_alive():
        _sse = threading.Thread(target=_sse_watch, daemon=True,
                                name="llamacpp-tuned-progress")
        _sse.start()


def _idle_sweeper():
    """Unload every loaded model after IDLE_UNLOAD_S without token activity."""
    last_sig, last_change = None, time.time()
    while True:
        time.sleep(POLL_S)
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
        elif sig == last_sig and time.time() - last_change >= IDLE_UNLOAD_S:
            for model in loaded:
                try:
                    _req("/models/unload", {"model": model}, timeout=120)
                except Exception:
                    pass
            last_sig, last_change = None, time.time()


def _attach_watchdog(proc: subprocess.Popen) -> None:
    """Detached watcher: if this gateway process dies, kill the router tree.

    A job object is unreliable here (AssignProcessToJobObject can be refused when
    the gateway already sits inside another job), so use a small detached helper
    that waits on the parent's process handle, then taskkill /T the router.
    NOTE: never use os.kill(pid, 0) on Windows to probe liveness — os.kill on
    Windows terminates the target even with signal 0.
    """
    subprocess.Popen(
        [sys.executable, "-c",
         "import ctypes,subprocess,sys,time\n"
         "SYNCHRONIZE=0x00100000; INFINITE=0xFFFFFFFF\n"
         "ppid, rpid = int(sys.argv[1]), sys.argv[2]\n"
         "h = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, ppid)\n"
         "if h:\n"
         "    ctypes.windll.kernel32.WaitForSingleObject(h, INFINITE)\n"
         "subprocess.run(['taskkill','/PID',rpid,'/T','/F'], capture_output=True)\n",
         str(os.getpid()), str(proc.pid)],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
        | getattr(subprocess, "CREATE_NO_WINDOW", 0))


def _spawn():
    LOG.parent.mkdir(parents=True, exist_ok=True)
    log = open(LOG, "a")
    proc = subprocess.Popen(
        [str(ENGINE), "--models-preset", str(PRESET), "--models-max", "1",
         "--port", str(PORT), "--metrics", "--host", "127.0.0.1", "--no-mmap"],
        stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
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


def _read_state():
    running = _proc is not None and _proc.poll() is None and _health()
    return {"enabled": _proc is not None,
            "running": running,
            "loaded": _loaded_models() if running else [],
            "loading": sorted(_loading) if running else [],
            "progress": _progress_state() if running else {},
            "models": _all_models() if running else [],
            "port": PORT if running else None,
            "engine": str(ENGINE) if ENGINE.is_file() else None,
            "busy": _operation.locked()}


@router.get("/status")
def get_status():
    return _read_state()


class ModeRequest(BaseModel):
    enabled: StrictBool


class LoadRequest(BaseModel):
    model: str


_loading = {}  # model_id -> monotonic start time, for the chip's loading state


@router.post("/load")
async def load_model(body: LoadRequest):
    """Start loading a staged model now (pre-load ahead of the chat request)."""
    global _sweeper, _proc
    if not ENGINE.is_file():
        raise HTTPException(503, f"llama-server engine not found at {ENGINE}")
    if not _operation.acquire(blocking=False):
        raise HTTPException(409, "Another mode change is already running.")
    try:
        if not (_proc and _proc.poll() is None):
            _proc = await asyncio.to_thread(_spawn)
            if not await asyncio.to_thread(_wait_healthy):
                raise HTTPException(502, "Tuned router failed to become healthy.")
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
    global _proc, _sweeper
    if not ENGINE.is_file():
        raise HTTPException(503, f"llama-server engine not found at {ENGINE}")
    if not PRESET.is_file():
        raise HTTPException(503, f"preset not found at {PRESET}")
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

"""Tuned Llama.cpp: API, Desktop UI, and one scoped hook pair.

The chip's WG segment is an opt-in, OFF-by-default workaround for Hermes'
read-before-write guard on this filesystem: os.fstat and os.stat disagree on
st_ctime_ns here, so the guard can never record a whole-file baseline and
write_file refuses legitimate overwrites of files the session just wrote or read.

The guard re-reads HERMES_DISABLE_FILE_STATE_GUARD on every call and that variable
is PROCESS-WIDE, so it is never set globally here. `pre_llm_call` records each
session's model; `pre_tool_call`/`post_tool_call` set the variable only for the
duration of a write_file/patch call whose session runs one of the router's staged
local models. Codex and every other provider keep the guard untouched. While the
switch is on the pre hook rewrites the variable on every call, so a call that
never reaches post_tool_call (approval refusal, crash) cannot leave a stale "1".
"""
import json
import os
import time
from collections import OrderedDict
from pathlib import Path

GUARD_ENV = "HERMES_DISABLE_FILE_STATE_GUARD"
SETTING = "local_write_guard_bypass"
SETTINGS_FILE = Path(__file__).parent / "dashboard" / "settings.json"

# Tool calls that touch the guard's read-before-write baseline.
GUARDED_TOOLS = ("write_file", "patch")
_SESSION_CAP = 512
_MODEL_CACHE_TTL_S = 60.0

_session_models: "OrderedDict[str, str]" = OrderedDict()
_settings_cache = {"mtime_ns": None, "enabled": False}
_models_cache = {"ts": 0.0, "ids": frozenset()}


def _models_dir() -> Path:
    try:
        from hermes_constants import get_hermes_home
        home = get_hermes_home().resolve()
    except Exception:
        env = os.environ.get("HERMES_HOME")
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        home = Path(env).resolve() if env else Path(base) / "hermes"
    return home / "models"


def _staged_model_ids() -> frozenset:
    """Model ids of the staged GGUFs this router serves (cached briefly)."""
    now = time.monotonic()
    if now - _models_cache["ts"] < _MODEL_CACHE_TTL_S:
        return _models_cache["ids"]
    try:
        from hermes_cli.local_runtime.gguf import model_id_from_stem
    except Exception:
        def model_id_from_stem(stem: str) -> str:
            return stem
    ids = set()
    try:
        for gguf in _models_dir().glob("*.gguf"):
            if gguf.is_symlink() and not gguf.exists():
                continue
            ids.add(model_id_from_stem(gguf.stem))
    except Exception:
        pass
    _models_cache.update(ts=now, ids=frozenset(ids))
    return _models_cache["ids"]


def _enabled() -> bool:
    """The chip switch, cached by settings.json mtime (this runs on the tool path)."""
    try:
        mtime = SETTINGS_FILE.stat().st_mtime_ns
    except OSError:
        return False
    if _settings_cache["mtime_ns"] != mtime:
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            enabled = bool(data.get(SETTING, False))
        except Exception:
            enabled = False
        _settings_cache.update(mtime_ns=mtime, enabled=enabled)
    return bool(_settings_cache["enabled"])


def on_pre_llm_call(session_id: str = "", model: str = "", **_kwargs) -> None:
    """Remember which model this session runs — the tool hooks cannot see it."""
    if session_id:
        _session_models[session_id] = model or ""
        _session_models.move_to_end(session_id)
        while len(_session_models) > _SESSION_CAP:
            _session_models.popitem(last=False)
    return None


def on_pre_tool_call(tool_name: str = "", session_id: str = "", **_kwargs) -> None:
    """Scope the bypass to local-model write calls. Bounded hook: never vetoes."""
    if not _enabled():
        return None
    local = (tool_name in GUARDED_TOOLS
             and _session_models.get(session_id, "") in _staged_model_ids())
    os.environ[GUARD_ENV] = "1" if local else "0"
    return None


def on_post_tool_call(**_kwargs) -> None:
    """Drop the bypass again — a leak would outlive this one call."""
    if _enabled():
        os.environ[GUARD_ENV] = "0"
    return None


def register(ctx):
    ctx.register_hook("pre_llm_call", on_pre_llm_call)
    ctx.register_hook("pre_tool_call", on_pre_tool_call)
    ctx.register_hook("post_tool_call", on_post_tool_call)

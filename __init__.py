"""Tuned Llama.cpp: API, Desktop UI, and one scoped hook pair.

Hermes' read-before-write guard can never establish a whole-file baseline on this
filesystem. tools/file_tools_read_tracking._file_version() builds its snapshot with
os.fstat(fd) and requires it to equal os.stat(path) field by field -- including
st_ctime_ns. On Windows those two Win32 calls report DIFFERENT timestamps in that
slot (path lookup -> creation time, open handle -> change time), so the equality can
only hold for a file never modified since creation. Everywhere else the function
returns None, no write baseline is ever recorded, and write_file refuses legitimate
overwrites with "has not seen its full current content".

The chip's WG segment (settings.json: local_guard_fix, OFF by default) makes the
guard WORK again -- for local sessions only -- by rebinding that one helper, for the
duration of a write_file/read_file/patch call from a session on a staged local model, to a
version that takes ONE metadata view (os.stat, the same one _file_metadata uses) and
leaves byte identity to the sha256 it already computes. A genuinely stale overwrite
(digest mismatch) or a file that changed mid-read is still refused. Codex, Copilot,
OpenRouter and every other provider keep the shipped helper untouched.

The rebinding targets a private helper, so it FAILS OPEN: if the module or function is
missing, or the corrected version cannot be confirmed on this filesystem, the plugin
restores what it touched, leaves core alone, and the WG segment reports that it could
not be applied.

The same switch also registers one system-prompt section (llamacpp-tuned-file-editing)
with the three rules the staged GGUFs break: read before you edit, write whole files
with write_file instead of shell heredocs, quote patch old_string exactly. It is doubly
scoped -- the chip switch must be ON and the session's model must be one of the staged
GGUFs -- so a Codex/Copilot/OpenRouter session renders no section at all (the core skips
empty content).
"""
import hashlib
import json
import os
import stat
import tempfile
import time
from collections import OrderedDict
from pathlib import Path

SETTING = "local_guard_fix"
LEGACY_SETTING = "local_write_guard_bypass"   # pre-rename key: same opt-in, kept alive
SETTINGS_FILE = Path(__file__).parent / "dashboard" / "settings.json"
# read_file belongs here: its result decides the snapshot's completeness flag AND drops
# a baseline the session had established (`if not complete: baselines.pop(...)`), so an
# unshimmed read both fails to establish a baseline and destroys the one a shimmed write
# just recorded. Measured in the field: write -> read -> write was refused on the read.
GUARDED_TOOLS = ("write_file", "patch", "read_file")
_SESSION_CAP = 512
_MODEL_CACHE_TTL_S = 60.0
_HELPER = "_file_version"
_OURS = "_consistent_file_version"

_session_models: "OrderedDict[str, str]" = OrderedDict()
_settings_cache = {"mtime_ns": None, "enabled": False}
_models_cache = {"ts": 0.0, "ids": frozenset()}
_installed: tuple = ()          # ((module, name, original), ...) while the fix is live
_last_error = ""
_section_error = ""             # "" once the prompt section registered (reported by shim_state)


# ── settings / staged models ─────────────────────────────────────────────
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
            enabled = bool(data.get(SETTING, data.get(LEGACY_SETTING, False)))
        except Exception:
            enabled = False
        _settings_cache.update(mtime_ns=mtime, enabled=enabled)
    return bool(_settings_cache["enabled"])


# ── local-model prompt section ───────────────────────────────────────────
# The staged GGUFs already receive these rules in the tool descriptions and ignore them
# (write_file: "For an EXISTING file, call read_file first"; patch: old_string is the
# exact current text; both say to prefer the file tools over heredocs), so restating
# them at greater length changes nothing -- a short imperative block in the prompt does.
# Doubly scoped: chip switch ON and the session's model is a staged GGUF, so every other
# provider renders no section (the core drops empty content).
SECTION_ID = "llamacpp-tuned-file-editing"
SECTION_TEXT = (
    "Local-model file-editing rules for this session:\n"
    "- Before editing an existing file with write_file or patch, call read_file on that file in the same turn.\n"
    "- Write whole files with write_file. Never emit file bodies through terminal or execute_code "
    "heredocs (cat > f << 'EOF'), and never paste a file body into a Python string.\n"
    "- patch old_string must be the exact current text of the file, with surrounding context lines."
)


def local_editing_rules(session_info) -> str:
    """Section content: the rules for a staged local model, else '' (core skips empty)."""
    try:
        if not _enabled():
            return ""
        model = str((session_info or {}).get("model") or "")
        return SECTION_TEXT if model in _staged_model_ids() else ""
    except Exception:
        return ""


# ── the corrected helper ─────────────────────────────────────────────────
def _consistent_file_version(resolved):
    """``_file_version`` with ONE metadata view instead of two syscalls.

    Fields 0-4 come from os.stat -- exactly what _file_metadata() returns, so every
    existing equality (version[:-1] == metadata, baseline comparisons, dedup keys)
    keeps its meaning. The open handle is used only to hash the bytes, and "changed
    during the read" is decided on (dev, ino, size, mtime_ns), which Windows reports
    consistently. The sha256 still decides byte identity, so a stale overwrite is
    refused exactly as before.
    """
    key = ("st_dev", "st_ino", "st_size", "st_mtime_ns")
    try:
        before = os.stat(resolved)
        if not stat.S_ISREG(before.st_mode):
            return None
        fd = os.open(resolved, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0)
                     | getattr(os, "O_BINARY", 0))
        with os.fdopen(fd, "rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").digest()
        after = os.stat(resolved)
    except OSError:
        return None
    if tuple(getattr(before, f) for f in key) != tuple(getattr(after, f) for f in key):
        return None                      # changed while we were reading it
    return (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns,
            after.st_ctime_ns, digest)


def _self_check() -> bool:
    """Prove the corrected helper produces a version for a file this box used to fail
    on (created, then modified) before we trust the rebinding."""
    from tools import file_tools_read_tracking as rt
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(prefix="wgfix-", suffix=".txt")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write("first\n")
        time.sleep(0.02)
        with open(tmp, "a", encoding="utf-8") as fh:
            fh.write("second\n")          # birthtime now differs from change time
        return rt._file_version(tmp) is not None
    except Exception:
        return False
    finally:
        if tmp:
            try:
                os.unlink(tmp)
            except OSError:
                pass


# ── install / remove ─────────────────────────────────────────────────────
def install_guard_fix() -> bool:
    """Rebind the guard's snapshot helper in the defining module AND in file_tools
    (which imported it by name). Idempotent; restores everything on any doubt."""
    global _installed, _last_error
    if _installed:
        return True
    try:
        import tools.file_tools as ft
        import tools.file_tools_read_tracking as rt
    except Exception as exc:                      # core not importable (yet)
        _last_error = f"import failed: {exc}"
        return False
    targets = [(rt, _HELPER)]
    if hasattr(ft, _HELPER):
        targets.append((ft, _HELPER))
    saved = []
    try:
        for module, name in targets:
            current = getattr(module, name, None)
            if not callable(current):
                raise LookupError(f"{module.__name__}.{name} missing")
            if getattr(current, "__name__", "") == _OURS:
                continue
            saved.append((module, name, current))
            setattr(module, name, _consistent_file_version)
        if not _self_check():
            raise RuntimeError("self-check failed")
    except Exception as exc:
        for module, name, original in saved:
            try:
                setattr(module, name, original)
            except Exception:
                pass
        _installed = ()
        _last_error = str(exc)
        return False
    _installed = tuple(saved)
    _last_error = ""
    return True


def remove_guard_fix() -> None:
    """Put the shipped helper back (no-op when not installed)."""
    global _installed
    for module, name, original in _installed:
        try:
            setattr(module, name, original)
        except Exception:
            pass
    _installed = ()


def shim_state() -> dict:
    return {"applied": bool(_installed), "error": _last_error,
            "prompt_section": _section_error or "registered"}


# ── hooks ────────────────────────────────────────────────────────────────
def on_pre_llm_call(session_id: str = "", model: str = "", **_kwargs) -> None:
    """Remember which model this session runs -- the tool hooks cannot see it."""
    if session_id:
        _session_models[session_id] = model or ""
        _session_models.move_to_end(session_id)
        while len(_session_models) > _SESSION_CAP:
            _session_models.popitem(last=False)
    return None


def on_pre_tool_call(tool_name: str = "", session_id: str = "", **_kwargs) -> None:
    """Apply the corrected helper for a local session's write call, remove it
    otherwise. Bounded hook: never vetoes, never raises."""
    try:
        if not _enabled():
            remove_guard_fix()          # the chip may have been switched off mid-run
            return None
        local = (tool_name in GUARDED_TOOLS
                 and _session_models.get(session_id, "") in _staged_model_ids())
        if local:
            install_guard_fix()
        else:
            remove_guard_fix()
    except Exception:
        remove_guard_fix()
    return None


def on_post_tool_call(**_kwargs) -> None:
    """Restore the shipped helper after the call -- a leak past this call would
    silently extend the fix to other sessions."""
    try:
        if _enabled():
            remove_guard_fix()
    except Exception:
        pass
    return None


def _register_prompt_section(ctx) -> None:
    """Register the scoped prompt section. A core without the surface (or one that rejects
    the id) must not break the hooks, so this fails open and reports through shim_state()."""
    global _section_error
    register_section = getattr(ctx, "register_system_prompt_section", None)
    if not callable(register_section):
        _section_error = "core has no register_system_prompt_section"
        return
    try:
        register_section(SECTION_ID, local_editing_rules, position="after_memory")
        _section_error = ""
    except Exception as exc:
        _section_error = f"{type(exc).__name__}: {exc}"


def register(ctx):
    try:
        import tools.file_tools_read_tracking as rt
        if not callable(getattr(rt, _HELPER, None)):
            _last_error = f"{_HELPER} not found in tools.file_tools_read_tracking"
    except Exception as exc:
        _last_error = f"import failed: {exc}"
    _register_prompt_section(ctx)
    ctx.register_hook("pre_llm_call", on_pre_llm_call)
    ctx.register_hook("pre_tool_call", on_pre_tool_call)
    ctx.register_hook("post_tool_call", on_post_tool_call)

# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
# Engine design contributed by Ahsan Mehmood (PR #1), hardened here.
"""Runtime plugin discovery — the engine behind the Extensions menu.

A plugin is a Python file (or a package directory) dropped into one of two
places:

- ``<app_root>/plugins/`` — plugins bundled with the application. Read-only
  in a frozen install (AppImage mount, Program Files), listed in
  ``ingetrazo.spec`` so they actually travel with the installers.
- the per-user directory (``%APPDATA%/ingetrazo/plugins`` on Windows,
  ``$XDG_DATA_HOME/ingetrazo/plugins`` — default ``~/.local/share/...`` —
  elsewhere): where third-party plugins are installed without touching the
  app install.

Candidates are imported BY FILE PATH (``importlib.util``), never by package
name: ``import plugins.x`` only resolves while the repo layout happens to be
on ``sys.path``, which is exactly what a PyInstaller bundle does not
guarantee (the ``core/paths.py`` lesson). Loading by path behaves the same
from the repo, the AppImage and the Windows build — and never puts a plugin
directory on ``sys.path``, so a user file named ``json.py`` cannot shadow a
stdlib module for the whole app.

The contract ``views/main_window.py`` relies on:

- A broken plugin NEVER breaks startup. Import errors, constructor errors —
  every failure is logged, returned as a :class:`PluginError` and shown as a
  disabled menu entry; the application opens regardless.
- A module-level ``setup(app)`` is called once with a
  :class:`views.extension_api.ExtensionApp` (document data, a side panel,
  viewport overlays and inferences); if it raises, the plugin shows as a
  load error like an import failure.
- Only ``Tool`` subclasses *defined in the plugin's own module* are
  registered. A plugin that imports ``LineTool`` (to reuse or subclass it)
  must not duplicate the built-in in the menu or clone its shortcut.
- Two plugins with the same stem: the first directory wins (app-bundled
  before user), the loser is logged and skipped.
- Optional TOML manifests are read before import. Malformed manifests and
  plugins requiring a newer IngeTrazo are reported without executing code.
"""
from __future__ import annotations

import importlib.util
import inspect
import logging
import os
import shutil
import sys
import tempfile
import tomllib
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from core.paths import app_root
from core.version import __version__

log = logging.getLogger("ingetrazo.plugins")


@dataclass
class LoadedPlugin:
    """One plugin file that imported cleanly and produced tools."""
    stem: str                       # file / package name, e.g. "model_info"
    path: Path
    tools: list = field(default_factory=list)   # instantiated Tool objects
    #: The module's ``setup(app)`` (views.extension_api), or None — a plugin
    #: may have tools, a setup, or both.
    setup: object = None


@dataclass
class PluginError:
    """One plugin file that failed; surfaces as a disabled menu entry."""
    stem: str
    path: Path
    error: str                      # "ExcType: message", for the tooltip


@dataclass(frozen=True)
class PluginManifest:
    """Display and compatibility metadata read without importing code."""
    name: str
    version: str = ""
    author: str = ""
    description: str = ""
    min_ingetrazo: str = ""
    homepage: str = ""


@dataclass(frozen=True)
class PluginCandidate:
    """A plugin found on disk, before any of its code is imported."""
    stem: str
    path: Path
    manifest: PluginManifest | None = None
    manifest_error: str = ""


def user_plugins_dir() -> Path:
    """The per-user plugin directory. May not exist yet — that is fine."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA")
                    or (Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME")
                    or (Path.home() / ".local" / "share"))
    return base / "ingetrazo" / "plugins"


def plugin_dirs() -> list[Path]:
    """Candidate directories, app-bundled first (first stem wins)."""
    return [app_root() / "plugins", user_plugins_dir()]


def _version_tuple(value: str) -> tuple[int, ...]:
    """Comparable numeric release prefix (``0.5.7-beta`` → ``(0, 5, 7)``)."""
    release = value.split("+", 1)[0].split("-", 1)[0]
    parts = release.split(".")
    if not parts or any(not p.isdigit() for p in parts):
        raise ValueError(f"Invalid version: {value}")
    numeric = tuple(int(p) for p in parts)
    return numeric + (0,) * max(0, 3 - len(numeric))


def _manifest_path(path: Path) -> Path:
    return (path.parent / "plugin.toml" if path.name == "__init__.py"
            else path.with_suffix(".toml"))


def read_plugin_manifest(stem: str, path: Path) -> PluginManifest | None:
    """Read optional ``plugin.toml``/``stem.toml`` metadata safely."""
    manifest_path = _manifest_path(path)
    if not manifest_path.is_file():
        return None
    with manifest_path.open("rb") as handle:
        document = tomllib.load(handle)
    values = document.get("plugin")
    if not isinstance(values, dict):
        raise ValueError("Manifest must contain a [plugin] table.")
    allowed = ("name", "version", "author", "description",
               "min_ingetrazo", "homepage")
    for key in allowed:
        if key in values and not isinstance(values[key], str):
            raise ValueError(f"Manifest field {key!r} must be text.")
    manifest = PluginManifest(
        name=values.get("name", stem).strip() or stem,
        version=values.get("version", "").strip(),
        author=values.get("author", "").strip(),
        description=values.get("description", "").strip(),
        min_ingetrazo=values.get("min_ingetrazo", "").strip(),
        homepage=values.get("homepage", "").strip())
    if manifest.version:
        _version_tuple(manifest.version)
    if manifest.min_ingetrazo:
        _version_tuple(manifest.min_ingetrazo)
    return manifest


def _compatibility_error(manifest: PluginManifest | None) -> str:
    if (manifest is not None and manifest.min_ingetrazo
            and _version_tuple(__version__) < _version_tuple(
                manifest.min_ingetrazo)):
        return (f"Requires IngeTrazo {manifest.min_ingetrazo} or newer "
                f"(installed: {__version__}).")
    return ""


def _plugin_target(path: Path) -> Path:
    """The installed file/package represented by a candidate source path."""
    return path.parent if path.name == "__init__.py" else path


def is_user_plugin(path: Path, user_dir: Path | None = None) -> bool:
    """Whether ``path`` is a direct child plugin of the writable user dir."""
    root = (user_dir or user_plugins_dir()).resolve()
    try:
        target = _plugin_target(Path(path)).resolve()
    except OSError:
        return False
    return target.parent == root


def _zip_plugin_source(archive: Path, stage: Path) -> tuple[Path, str]:
    """Extract a small, traversal-safe plugin archive into ``stage``."""
    with zipfile.ZipFile(archive) as zf:
        infos = [i for i in zf.infolist() if not i.is_dir()]
        if len(infos) > 1000 or sum(i.file_size for i in infos) > 50 * 1024 ** 2:
            raise ValueError("Plugin archive is too large.")
        paths = [PurePosixPath(i.filename) for i in infos]
        if any("\\" in i.filename for i in infos) or any(
                p.is_absolute() or ".." in p.parts for p in paths):
            raise ValueError("Plugin archive contains an unsafe path.")
        # Unix symlinks in ZIPs can escape after extraction just as ``..`` can.
        if any((i.external_attr >> 16) & 0o170000 == 0o120000 for i in infos):
            raise ValueError("Plugin archive may not contain symbolic links.")
        roots = {p.parts[0] for p in paths if p.parts}
        root_init = any(p == PurePosixPath("__init__.py") for p in paths)
        package_roots = {
            p.parts[0] for p in paths
            if len(p.parts) == 2 and p.parts[1] == "__init__.py"}
        top_py = [p for p in paths if len(p.parts) == 1 and p.suffix == ".py"]
        top_toml = [
            p for p in paths if len(p.parts) == 1 and p.suffix == ".toml"]
        if root_init:
            name = archive.stem
            source = stage
        elif len(package_roots) == 1 and roots == package_roots:
            name = next(iter(package_roots))
            source = stage / name
        elif (len(top_py) == 1 and len(paths) in (1, 2)
              and (not top_toml
                   or top_toml == [top_py[0].with_suffix(".toml")])):
            name = top_py[0].name
            source = stage / name
        else:
            raise ValueError(
                "Plugin ZIP must contain one .py file or one package with "
                "an __init__.py file.")
        stage.mkdir(parents=True, exist_ok=True)
        zf.extractall(stage)
    return source, name


def install_plugin(source: Path, *, replace: bool = False,
                   user_dir: Path | None = None) -> Path:
    """Install a local ``.py``, package folder, or ZIP without importing it.

    Files are copied to a staging sibling first, so a failed copy never leaves
    a half-written plugin at the name the startup scanner imports.
    """
    source = Path(source)
    root = user_dir or user_plugins_dir()
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ingetrazo-plugin-") as tmp:
        stage_root = Path(tmp)
        if source.is_file() and source.suffix.lower() == ".zip":
            payload, name = _zip_plugin_source(source, stage_root / "unpacked")
        elif source.is_file() and source.suffix.lower() == ".py":
            payload, name = source, source.name
        elif source.is_dir() and (source / "__init__.py").is_file():
            payload, name = source, source.name
        else:
            raise ValueError(
                "Choose a Python plugin (.py), plugin package, or ZIP package.")

        target = root / name
        source_manifest = (payload.with_suffix(".toml")
                           if payload.is_file() else None)
        if source_manifest is not None and not source_manifest.is_file():
            source_manifest = None
        target_manifest = (target.with_suffix(".toml")
                           if payload.is_file() else None)
        if target.exists() and not replace:
            raise FileExistsError(str(target))
        staged = root / f".{name}.installing"
        staged_manifest = (root / f".{target_manifest.name}.installing"
                           if target_manifest is not None else None)
        if staged.exists():
            shutil.rmtree(staged) if staged.is_dir() else staged.unlink()
        if staged_manifest is not None and staged_manifest.exists():
            staged_manifest.unlink()
        try:
            if payload.is_dir():
                shutil.copytree(
                    payload, staged,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            else:
                shutil.copy2(payload, staged)
                if source_manifest is not None:
                    shutil.copy2(source_manifest, staged_manifest)
        except Exception:
            if staged.exists():
                shutil.rmtree(staged) if staged.is_dir() else staged.unlink()
            if staged_manifest is not None and staged_manifest.exists():
                staged_manifest.unlink()
            raise
        backup = root / f".{name}.previous"
        backup_manifest = (root / f".{target_manifest.name}.previous"
                           if target_manifest is not None else None)
        if backup.exists():
            shutil.rmtree(backup) if backup.is_dir() else backup.unlink()
        if target.exists():
            target.replace(backup)
        if backup_manifest is not None and backup_manifest.exists():
            backup_manifest.unlink()
        if target_manifest is not None and target_manifest.exists():
            target_manifest.replace(backup_manifest)
        try:
            staged.replace(target)
            if staged_manifest is not None and staged_manifest.exists():
                staged_manifest.replace(target_manifest)
        except Exception:
            if target.exists():
                target.unlink()
            if backup.exists() and not target.exists():
                backup.replace(target)
            if (backup_manifest is not None and backup_manifest.exists()
                    and not target_manifest.exists()):
                backup_manifest.replace(target_manifest)
            raise
        if backup.exists():
            shutil.rmtree(backup) if backup.is_dir() else backup.unlink()
        if backup_manifest is not None and backup_manifest.exists():
            backup_manifest.unlink()
        return target


def uninstall_plugin(path: Path, *, user_dir: Path | None = None) -> Path:
    """Remove one user-installed plugin; bundled plugins are read-only."""
    target = _plugin_target(Path(path))
    if not is_user_plugin(target, user_dir):
        raise PermissionError("Bundled extensions cannot be removed.")
    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink(missing_ok=True)
        target.with_suffix(".toml").unlink(missing_ok=True)
    return target


def _candidates(p_dir: Path):
    """Yield ``(stem, file)``: loose ``x.py`` files and ``x/__init__.py``
    packages, skipping dunders, dotfiles and non-Python clutter (README)."""
    for entry in sorted(p_dir.iterdir()):
        if entry.name.startswith(("_", ".")):
            continue
        if entry.is_file() and entry.suffix == ".py":
            yield entry.stem, entry
        elif entry.is_dir() and (entry / "__init__.py").is_file():
            yield entry.name, entry / "__init__.py"


def plugin_candidates(dirs=None) -> list[PluginCandidate]:
    """List the winning plugin files without importing them.

    The manager uses this safe inventory to show disabled and broken plugins.
    Duplicate stems follow discovery's existing first-directory-wins rule.
    """
    out: list[PluginCandidate] = []
    seen: set[str] = set()
    for p_dir in (list(dirs) if dirs is not None else plugin_dirs()):
        if not p_dir.is_dir():
            continue
        for stem, file in _candidates(p_dir):
            if stem in seen:
                log.warning("plugin %r at %s shadowed by an earlier one; "
                            "skipped", stem, file)
                continue
            seen.add(stem)
            try:
                manifest = read_plugin_manifest(stem, file)
                manifest_error = _compatibility_error(manifest)
            except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
                manifest = None
                manifest_error = f"{type(exc).__name__}: {exc}"
            out.append(PluginCandidate(
                stem, file, manifest, manifest_error))
    return out


def _import_by_path(stem: str, file: Path):
    """Import ``file`` under a private module name, off ``sys.path``."""
    mod_name = f"ingetrazo_plugin_{stem}"
    spec = importlib.util.spec_from_file_location(
        mod_name, file,
        submodule_search_locations=(
            [str(file.parent)] if file.name == "__init__.py" else None))
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot build an import spec for {file}")
    mod = importlib.util.module_from_spec(spec)
    # Registered so dataclasses / pickling / introspection inside the
    # plugin resolve their own module; unregistered again on failure.
    sys.modules[mod_name] = mod
    try:
        spec.loader.exec_module(mod)
    except BaseException:
        sys.modules.pop(mod_name, None)
        raise
    return mod


def discover_plugins(dirs=None, disabled=None, candidates=None):
    """Scan ``dirs`` (default :func:`plugin_dirs`) and load every plugin.

    Returns ``(plugins, errors)`` and never raises: each failing candidate
    becomes a :class:`PluginError` instead of an exception, because the one
    thing a plugin system must not do is keep the host from starting.
    """
    from tools.base import Tool     # deferred: core stays Qt-import-light

    plugins: list[LoadedPlugin] = []
    errors: list[PluginError] = []
    disabled = set(disabled or ())

    for candidate in (plugin_candidates(dirs) if candidates is None
                      else candidates):
        stem, file = candidate.stem, candidate.path
        if stem in disabled:
            log.info("plugin %r disabled by the user; skipped", stem)
            continue
        if candidate.manifest_error:
            errors.append(PluginError(
                stem, file, candidate.manifest_error))
            log.warning("plugin %r manifest rejected: %s",
                        stem, candidate.manifest_error)
            continue
        try:
            mod = _import_by_path(stem, file)
            tools = [
                obj() for _n, obj in inspect.getmembers(mod,
                                                        inspect.isclass)
                if (issubclass(obj, Tool) and obj is not Tool
                    and obj.__module__ == mod.__name__     # defined here
                    and not inspect.isabstract(obj))
            ]
        except Exception as exc:                # noqa: BLE001 — contract
            log.exception("failed to load plugin %r from %s", stem, file)
            errors.append(PluginError(
                stem, file, f"{type(exc).__name__}: {exc}"))
            continue
        setup = getattr(mod, "setup", None)
        if not callable(setup):
            setup = None
        if tools or setup is not None:
            plugins.append(LoadedPlugin(stem, file, tools, setup))
            for t in tools:
                log.info("loaded plugin tool %r from %s", t.name, file)
    return plugins, errors

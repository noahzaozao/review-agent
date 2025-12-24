import configparser
import os
from typing import List, Optional

from .types import ScanConfig


DEFAULT_EXCLUDE_DIR_GLOBS = [
    "**/.git/**",
    "**/.hg/**",
    "**/.svn/**",
    "**/node_modules/**",
    "**/bower_components/**",
    "**/venv/**",
    "**/.venv/**",
    "**/__pycache__/**",
    "**/.tox/**",
    "**/dist/**",
    "**/build/**",
    "**/.eggs/**",
    "**/*.egg-info/**",
    # Explicit CMS subprojects to exclude (vendored subrepos inside the platform).
    # These are matched relative to the scan root, so when scanning the Open edX
    # "platform/" root, the correct patterns start with "cms/...".
    "cms/edx_xblock_scorm/**",
    "cms/edx-ora2/**",
    "cms/edx-search/**",
    "cms/xblock-drag-and-drop-v2/**",
    "cms/xblock-ilt/**",
    "cms/xblock-pdf/**",
    "cms/xblock-poll/**",
    "cms/xblock-utils/**",
]

DEFAULT_CRITICAL_DIRS = [
    "lms",
    "cms",
    "openedx/core",
    "openedx/features",
    "common",
    "xmodule",
]

DEFAULT_TOP_N_DIRS = 15
DEFAULT_HOTSPOT_DEPTH = 3


def _dedupe_keep_order(items: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for x in items:
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


def _split_multiline_values(raw: str) -> List[str]:
    items: List[str] = []
    for line in (raw or "").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        items.append(s)
    return items


def _normalize_posix_path(p: str) -> str:
    p = (p or "").strip()
    p = p.replace("\\", "/")
    # Remove leading "./"
    while p.startswith("./"):
        p = p[2:]
    return p.strip("/")


def load_scan_config(root: str, config_path: Optional[str]) -> ScanConfig:
    """
    Load INI config if present; otherwise use built-in defaults.

    Note: rule set is fixed/minimal; config only affects excludes, critical dirs, and report size.
    """
    root = os.path.abspath(root)
    cp = configparser.ConfigParser()

    loaded_path: Optional[str] = None
    if config_path:
        loaded_path = os.path.abspath(config_path)
        cp.read(loaded_path, encoding="utf-8")
    else:
        # Try local ai_review.ini in CWD
        candidate = os.path.abspath(os.path.join(os.getcwd(), "ai_review.ini"))
        if os.path.exists(candidate):
            loaded_path = candidate
            cp.read(candidate, encoding="utf-8")

    # Excludes
    exclude_globs: List[str] = list(DEFAULT_EXCLUDE_DIR_GLOBS)
    if cp.has_option("scan", "exclude_dir_globs"):
        exclude_globs.extend(_split_multiline_values(cp.get("scan", "exclude_dir_globs")))
    exclude_globs = [_normalize_posix_path(g) for g in exclude_globs if _normalize_posix_path(g)]
    # Backward compatibility / operator convenience:
    # If the scan root itself is "platform/", users often (incorrectly) prefix
    # excludes with "platform/..." even though matching is relative to root.
    # When root basename == "platform", transparently accept both forms.
    root_base = os.path.basename(root.rstrip(os.sep))
    if root_base == "platform":
        normalized: List[str] = []
        for g in exclude_globs:
            normalized.append(g)
            if g.startswith("platform/"):
                normalized.append(g[len("platform/") :])
        exclude_globs = normalized
    exclude_globs = _dedupe_keep_order(exclude_globs)

    # Critical dirs
    critical_dirs: List[str] = []
    if cp.has_option("critical_dirs", "paths"):
        critical_dirs = _split_multiline_values(cp.get("critical_dirs", "paths"))
    critical_dirs = [_normalize_posix_path(p) for p in critical_dirs if _normalize_posix_path(p)]
    if not critical_dirs:
        critical_dirs = list(DEFAULT_CRITICAL_DIRS)
    critical_dirs = _dedupe_keep_order(critical_dirs)

    # Report
    top_n_dirs = DEFAULT_TOP_N_DIRS
    if cp.has_option("report", "top_n_dirs"):
        try:
            top_n_dirs = int(cp.get("report", "top_n_dirs").strip())
        except ValueError:
            top_n_dirs = DEFAULT_TOP_N_DIRS
    if top_n_dirs <= 0:
        top_n_dirs = DEFAULT_TOP_N_DIRS

    hotspot_depth = DEFAULT_HOTSPOT_DEPTH
    if cp.has_option("scan", "hotspot_depth"):
        try:
            hotspot_depth = int(cp.get("scan", "hotspot_depth").strip())
        except ValueError:
            hotspot_depth = DEFAULT_HOTSPOT_DEPTH
    if hotspot_depth <= 0:
        hotspot_depth = DEFAULT_HOTSPOT_DEPTH

    return ScanConfig(
        root=root,
        exclude_dir_globs=exclude_globs,
        critical_dirs=critical_dirs,
        top_n_dirs=top_n_dirs,
        hotspot_depth=hotspot_depth,
    )


def resolve_loaded_config_path(explicit_path: Optional[str]) -> Optional[str]:
    if explicit_path:
        return os.path.abspath(explicit_path)
    candidate = os.path.abspath(os.path.join(os.getcwd(), "ai_review.ini"))
    return candidate if os.path.exists(candidate) else None



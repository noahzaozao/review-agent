import fnmatch
import os
from collections import defaultdict
from datetime import datetime, timezone
import platform
from typing import Dict, Iterable, List, Optional, Set, Tuple

from . import __version__
from .rules import minimal_ruleset
from .types import Rule, ScanConfig, ScanSummary


def _to_posix_relpath(path: str, root: str) -> str:
    rel = os.path.relpath(path, root)
    if rel == ".":
        return ""
    return rel.replace(os.sep, "/")


def _matches_any_glob(posix_path: str, globs: List[str]) -> bool:
    # Ensure consistent matching: no leading "./"
    p = posix_path.lstrip("./")
    for g in globs:
        # fnmatch doesn't treat "**/" specially; patterns like "**/.git/**" won't match ".git/...".
        # To be robust, also try matching without a leading "**/".
        candidates = [g]
        if g.startswith("**/"):
            candidates.append(g[len("**/") :])
        for gg in candidates:
            if fnmatch.fnmatch(p, gg):
                return True
        # Convenience: allow matching directories without trailing /**
        if g.endswith("/**"):
            base = g[:-3]
            if p == base.strip("/"):
                return True
    return False


def iter_python_files(
    root: str, exclude_dir_globs: List[str], pruned_dirs_counter: Optional[List[int]] = None
) -> Iterable[str]:
    root = os.path.abspath(root)
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        rel_dir = _to_posix_relpath(dirpath, root)

        # Prune excluded directories in-place
        kept: List[str] = []
        for d in dirnames:
            sub_abs = os.path.join(dirpath, d)
            sub_rel = _to_posix_relpath(sub_abs, root)
            if sub_rel and _matches_any_glob(sub_rel + "/", exclude_dir_globs):
                if pruned_dirs_counter is not None:
                    pruned_dirs_counter[0] += 1
                continue
            kept.append(d)
        dirnames[:] = kept

        # Also skip processing files in excluded dirpath itself
        if rel_dir and _matches_any_glob(rel_dir + "/", exclude_dir_globs):
            continue

        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            yield os.path.join(dirpath, fn)


def detect_critical_dirs(root: str, configured: List[str]) -> List[str]:
    """
    Return configured critical dirs that actually exist under root.
    """
    root = os.path.abspath(root)
    detected: List[str] = []
    for p in configured:
        abs_p = os.path.join(root, p.replace("/", os.sep))
        if os.path.isdir(abs_p):
            detected.append(p.strip("/"))
    return detected


def _bucket_dir_for_topn(relpath: str, depth: int) -> str:
    # relpath is a file path; we want its directory bucket truncated to `depth`.
    d = relpath.rsplit("/", 1)[0] if "/" in relpath else ""
    if not d:
        return "."
    parts = [p for p in d.split("/") if p]
    if not parts:
        return "."
    return "/".join(parts[: min(depth, len(parts))])


def _critical_key(relpath: str, critical_dirs: List[str]) -> str:
    for cd in critical_dirs:
        if relpath == cd or relpath.startswith(cd + "/"):
            return cd
    return "other"


def scan_codebase(config: ScanConfig, config_path: Optional[str]) -> ScanSummary:
    rules: List[Rule] = minimal_ruleset()
    rule_ids = [r.id for r in rules]
    rule_by_id: Dict[str, Rule] = {r.id: r for r in rules}

    started = datetime.now(timezone.utc)

    critical_detected = detect_critical_dirs(config.root, config.critical_dirs)
    critical_keys_all = list(critical_detected) + ["other"]
    categories_all = sorted({r.category for r in rules})
    severities_all = ["high", "medium", "low"]

    # Aggregations
    rule_occ: Dict[str, int] = {rid: 0 for rid in rule_ids}
    rule_files: Dict[str, int] = {rid: 0 for rid in rule_ids}
    dir_occ: Dict[str, Dict[str, int]] = defaultdict(lambda: {rid: 0 for rid in rule_ids})
    dir_files_scanned: Dict[str, int] = defaultdict(int)
    top_dir_hits: Dict[str, int] = defaultdict(int)

    scanned_files = 0
    skipped_files = 0
    read_errors = 0

    category_occ: Dict[str, int] = {c: 0 for c in categories_all}
    severity_occ: Dict[str, int] = {s: 0 for s in severities_all}
    category_files: Dict[str, int] = {c: 0 for c in categories_all}
    severity_files: Dict[str, int] = {s: 0 for s in severities_all}

    dir_category_occ: Dict[str, Dict[str, int]] = {
        k: {c: 0 for c in categories_all} for k in critical_keys_all
    }
    dir_severity_occ: Dict[str, Dict[str, int]] = {
        k: {s: 0 for s in severities_all} for k in critical_keys_all
    }

    pruned_dirs_counter = [0]
    for abspath in iter_python_files(
        config.root, config.exclude_dir_globs, pruned_dirs_counter=pruned_dirs_counter
    ):
        rel = _to_posix_relpath(abspath, config.root)

        # Exclude is already handled at directory-level, but keep a safe check
        if rel and _matches_any_glob(rel, config.exclude_dir_globs):
            skipped_files += 1
            continue

        scanned_files += 1
        crit_key = _critical_key(rel, critical_detected)
        dir_files_scanned[crit_key] += 1

        try:
            with open(abspath, "rb") as f:
                raw = f.read()
        except Exception:
            read_errors += 1
            continue

        # Decode in a tolerant way; regex rules are ASCII-based.
        text = raw.decode("utf-8", errors="replace")
        lines = text.splitlines()

        per_file_counts: Dict[str, int] = {rid: 0 for rid in rule_ids}

        for line in lines:
            stripped = line.lstrip()
            # Minimal noise reduction: ignore pure comment lines
            if stripped.startswith("#"):
                continue
            # v2 rule constraint: only trigger on non-comment, line-start syntax.
            # We match against the line with leading whitespace removed; rules are expected
            # to be anchored (via ^) or used with .match()-like semantics.
            hay = stripped

            for rule in rules:
                for rx in rule.regexes:
                    # Line-start only: count at most once per regex per line.
                    if rx.match(hay) is None:
                        continue
                    per_file_counts[rule.id] += 1

        total_hits_this_file = 0
        file_categories_hit: Set[str] = set()
        file_severities_hit: Set[str] = set()
        for rid in rule_ids:
            c = per_file_counts[rid]
            if c <= 0:
                continue
            rule_occ[rid] += c
            total_hits_this_file += c
            meta = rule_by_id.get(rid)
            if meta is not None:
                category_occ[meta.category] = category_occ.get(meta.category, 0) + c
                severity_occ[meta.severity] = severity_occ.get(meta.severity, 0) + c
                file_categories_hit.add(meta.category)
                file_severities_hit.add(meta.severity)
                dir_category_occ.setdefault(crit_key, {}).setdefault(meta.category, 0)
                dir_category_occ[crit_key][meta.category] += c
                dir_severity_occ.setdefault(crit_key, {}).setdefault(meta.severity, 0)
                dir_severity_occ[crit_key][meta.severity] += c
        for rid in rule_ids:
            if per_file_counts[rid] > 0:
                rule_files[rid] += 1
        for c in file_categories_hit:
            category_files[c] = category_files.get(c, 0) + 1
        for s in file_severities_hit:
            severity_files[s] = severity_files.get(s, 0) + 1

        dir_bucket = _bucket_dir_for_topn(rel, depth=config.hotspot_depth)
        top_dir_hits[dir_bucket] += total_hits_this_file
        for rid in rule_ids:
            if per_file_counts[rid] > 0:
                dir_occ[crit_key][rid] += per_file_counts[rid]

    finished = datetime.now(timezone.utc)

    top_dirs_sorted: List[Tuple[str, int]] = sorted(
        top_dir_hits.items(), key=lambda x: (-x[1], x[0])
    )
    top_dirs_sorted = [t for t in top_dirs_sorted if t[1] > 0][: config.top_n_dirs]

    return ScanSummary(
        tool_version=__version__,
        python_version=platform.python_version(),
        root=config.root,
        config_path=config_path,
        started_at_iso=started.isoformat(),
        finished_at_iso=finished.isoformat(),
        scanned_files=scanned_files,
        skipped_files=skipped_files,
        pruned_dirs=pruned_dirs_counter[0],
        read_errors=read_errors,
        top_n_dirs=config.top_n_dirs,
        hotspot_depth=config.hotspot_depth,
        rule_occurrences=rule_occ,
        rule_files=rule_files,
        dir_occurrences=dict(dir_occ),
        dir_files_scanned=dict(dir_files_scanned),
        top_dirs=top_dirs_sorted,
        critical_dirs_detected=critical_detected,
        excluded_dir_globs=list(config.exclude_dir_globs),
        category_occurrences=dict(category_occ),
        severity_occurrences=dict(severity_occ),
        category_files=dict(category_files),
        severity_files=dict(severity_files),
        dir_category_occurrences=dict(dir_category_occ),
        dir_severity_occurrences=dict(dir_severity_occ),
    )



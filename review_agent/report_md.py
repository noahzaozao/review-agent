from typing import Dict, List, Tuple

from .rules import minimal_ruleset
from .types import ScanSummary


def _md_table(headers: List[str], rows: List[List[str]]) -> str:
    out: List[str] = []
    out.append("| " + " | ".join(headers) + " |")
    out.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for r in rows:
        out.append("| " + " | ".join(r) + " |")
    return "\n".join(out)


def render_markdown(summary: ScanSummary) -> str:
    rules = minimal_ruleset()
    rule_meta: Dict[str, tuple] = {r.id: (r.category, r.severity, r.description) for r in rules}

    lines: List[str] = []
    lines.append("# Hawthorn Offline Code Risk Scan Report (Text Rules Baseline)")
    lines.append("")
    lines.append("## Scan metadata")
    lines.append("")
    lines.append(f"- **root**: `{summary.root}`")
    lines.append(f"- **config**: `{summary.config_path or '(built-in defaults)'}`")
    lines.append(f"- **started**: `{summary.started_at_iso}`")
    lines.append(f"- **finished**: `{summary.finished_at_iso}`")
    lines.append("")

    lines.append("## Scan statistics")
    lines.append("")
    total_hits = sum(summary.rule_occurrences.values())
    lines.append(
        _md_table(
            ["Metric", "Value"],
            [
                ["Python files scanned", str(summary.scanned_files)],
                ["Directories pruned (excluded)", str(getattr(summary, "pruned_dirs", 0))],
                ["Files skipped (file-level exclude)", str(summary.skipped_files)],
                ["Read errors", str(summary.read_errors)],
                ["Total hits (all rules)", str(total_hits)],
            ],
        )
    )
    lines.append("")

    lines.append("## Critical directories (auto-detected)")
    lines.append("")
    if summary.critical_dirs_detected:
        lines.append(
            "- **detected**: "
            + ", ".join(f"`{p}/`" for p in summary.critical_dirs_detected)
            + ", `other`"
        )
    else:
        lines.append(
            "- **detected**: (No default critical directories found under root; all files are categorized as `other`.)"
        )
    lines.append("")

    lines.append("## Rule hit overview (aggregated by rule)")
    lines.append("")
    rows: List[List[str]] = []
    for rid, occ in sorted(summary.rule_occurrences.items(), key=lambda x: (-x[1], x[0])):
        cat, sev, desc = rule_meta.get(rid, ("?", "?", ""))
        rows.append([rid, cat, sev, str(occ), str(summary.rule_files.get(rid, 0)), desc])
    lines.append(_md_table(["rule_id", "category", "severity", "occurrences", "files", "description"], rows))
    lines.append("")

    lines.append("## Rollups (by category / severity)")
    lines.append("")
    cat_rows: List[List[str]] = []
    for cat, occ in sorted(summary.category_occurrences.items(), key=lambda x: (-x[1], x[0])):
        cat_rows.append([cat, str(occ), str(summary.category_files.get(cat, 0))])
    if cat_rows:
        lines.append(_md_table(["category", "occurrences", "files"], cat_rows))
    else:
        lines.append("(No data.)")
    lines.append("")

    sev_rows: List[List[str]] = []
    for sev, occ in sorted(summary.severity_occurrences.items(), key=lambda x: (-x[1], x[0])):
        sev_rows.append([sev, str(occ), str(summary.severity_files.get(sev, 0))])
    if sev_rows:
        lines.append(_md_table(["severity", "occurrences", "files"], sev_rows))
    else:
        lines.append("(No data.)")
    lines.append("")

    lines.append("## Hit distribution (by critical directory)")
    lines.append("")
    # Build a compact table: dir, files_scanned, total_hits
    dist_rows: List[List[str]] = []
    all_dir_keys = sorted(set(summary.dir_files_scanned.keys()) | set(summary.dir_occurrences.keys()) | {"other"})
    for d in all_dir_keys:
        files_scanned = summary.dir_files_scanned.get(d, 0)
        occ_map = summary.dir_occurrences.get(d, {})
        total_hits = sum(occ_map.values()) if occ_map else 0
        dist_rows.append([f"`{d}`", str(files_scanned), str(total_hits)])
    lines.append(_md_table(["dir_key", "py_files_scanned", "total_hits"], dist_rows))
    lines.append("")

    lines.append("### Per-directory category / severity rollups (only partitions with hits)")
    lines.append("")
    dcs_rows: List[List[str]] = []
    for d in sorted(summary.dir_occurrences.keys()):
        occ_map = summary.dir_occurrences.get(d, {})
        if sum(occ_map.values()) <= 0:
            continue
        for cat, occ in sorted(summary.dir_category_occurrences.get(d, {}).items(), key=lambda x: (-x[1], x[0])):
            if occ <= 0:
                continue
            dcs_rows.append([f"`{d}`", "category", cat, str(occ)])
        for sev, occ in sorted(summary.dir_severity_occurrences.get(d, {}).items(), key=lambda x: (-x[1], x[0])):
            if occ <= 0:
                continue
            dcs_rows.append([f"`{d}`", "severity", sev, str(occ)])
    if dcs_rows:
        lines.append(_md_table(["dir_key", "dimension", "key", "occurrences"], dcs_rows))
    else:
        lines.append("(No hits.)")
    lines.append("")

    # Per-dir per-rule table (only for dirs with hits)
    lines.append("### Per-directory rule breakdown (only partitions with hits)")
    lines.append("")
    pr_rows: List[List[str]] = []
    for d in sorted(summary.dir_occurrences.keys()):
        occ_map = summary.dir_occurrences.get(d, {})
        total_hits = sum(occ_map.values()) if occ_map else 0
        if total_hits <= 0:
            continue
        for rid, occ in sorted(occ_map.items(), key=lambda x: (-x[1], x[0])):
            if occ <= 0:
                continue
            pr_rows.append([f"`{d}`", rid, str(occ)])
    if pr_rows:
        lines.append(_md_table(["dir_key", "rule_id", "occurrences"], pr_rows))
    else:
        lines.append("(No hits.)")
    lines.append("")

    # Hotspot depth is a config concern; preserve backward-compatible default (3) while
    # letting the report reflect the actual run behavior.
    depth_note = ""
    if summary.top_dirs:
        # We don't store depth in summary; infer from common prefix segment count is unreliable.
        # Keep wording generic to avoid misreporting.
        depth_note = " (bucketed by directory prefix)"
    lines.append(f"## Top directory hotspots{depth_note} (Top {len(summary.top_dirs)})")
    lines.append("")
    if summary.top_dirs:
        top_rows: List[List[str]] = []
        for p, hits in summary.top_dirs:
            top_rows.append([f"`{p}`", str(hits)])
        lines.append(_md_table(["dir_bucket", "total_hits"], top_rows))
    else:
        lines.append("(No hits.)")
    lines.append("")

    lines.append("## Excluded directory globs (effective list)")
    lines.append("")
    for g in summary.excluded_dir_globs:
        lines.append(f"- `{g}`")
    lines.append("")

    return "\n".join(lines)



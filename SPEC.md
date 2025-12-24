# Local Offline Code Risk Scanner (Hawthorn / Python 2.7) — SDD (Upgraded)

> Goal: perform **text-only scanning** of an **entire codebase** (not a git diff) and produce a structured **risk distribution report** (Markdown) to establish a baseline understanding of stability/risk signals.
>
> Constraints: **no Python upgrades**, **no refactors**, **no external systems/network**, **no per-line commentary**, **no AST parsing**, **no auto-fixes**.

---

## 1) Requirements

### In scope

- **Offline scan of the entire codebase**: recursively scan a user-provided root directory (e.g. `.`).
- **Backend Python only**: scan `*.py` files only.
- **Text-only rule scanning**: match content via file paths and regex; do not import or execute code.
- **Markdown risk report output**: print a short stdout summary and write a `.md` report file.
- **Fixed, low-false-positive ruleset**:
  - **V1 rules (must remain unchanged; rule IDs stable)**:
    - `PY3_FSTRING`: f-string prefix (`f"..."` / `f'...'`, including `rf` / `fr`)
    - `PY3_ASYNC_DEF`: `async def`
    - `PY3_AWAIT`: `await ...` (heuristic; medium confidence)
    - `EXCEPT_AS`: `except ... as e` (informational)
    - `STR_ENCODE`: `.encode(`
    - `STR_DECODE`: `.decode(`
  - **Allowed minor extensions (upgrade objective)**:
    - Only add syntax signals that are essentially invalid in Python 2.7.
    - Use **start-of-line anchoring** and **skip pure comment lines** to keep false positives low.
- **Critical directory partitioning**: auto-detect and aggregate risk distributions under key directories (e.g. `lms/`, `cms/`, `openedx/core/`, etc.); allow override via config.
- **Configurable directory exclusions**: allow excluding specific directories via config (including the listed `platform/cms/*` subprojects).
- **Aggregation enhancements (upgrade objective)**: all hits must be aggregatable by:
  - Rule `category` (e.g. `py3_syntax`, `unicode_str`)
  - Rule `severity` (`high|medium|low`)
  - Critical directory partition key (`critical_dir_key`: detected critical dirs + `other`)

### Out of scope / non-goals

- Not PR/diff based; no per-line reviews; no remediation suggestions.
- No auto-fixes, formatting, or refactoring.
- No modernization guidance (especially no “upgrade Python/Django” recommendations).
- No AST/semantic analysis; no runtime behavior inference.
- No frontend scanning (`.js/.ts/.jsx/.tsx/.css`, etc.).

---

## 2) Specification

### CLI interface

Single command entrypoint:

- `python3 ai_review.py scan PATH`

Optional arguments (do not change the “single command entrypoint”; they only improve usability):

- `--config PATH`: INI config path. Defaults to attempting `ai_review.ini` (prefer current working directory; otherwise use built-in defaults).
- `--out PATH`: Markdown report output path. Default: `ai_review_report.md` (created in the current working directory).
- `--quiet`: reduce stdout output (still writes the Markdown report).

Exit codes:

- `0`: scan completed (hits do not cause a failure).
- `2`: fatal errors (invalid args, missing path, cannot write report, etc.).

### Rule categories

Rules are grouped into categories for distribution statistics:

- `py3_syntax`: Python 3 syntax signals (f-strings / async/await / except-as)
- `unicode_str`: unicode/str signals (encode/decode)

Rule “severity” is used only for report ordering (no per-hit recommendations):

- `high`: strongly indicates Python 3-only or highly suspicious (f-strings, `async def`)
- `medium`: strong signal but may have rare false positives (`await`)
- `low`: informational/style clues (`except-as`, encode/decode)

### Output format (Markdown)

The report is designed for distribution summaries and avoids per-line/per-file details. It includes:

- Scan metadata: time, root path, config source, exclusion summary, version info
- Scan statistics: files scanned, skipped, read errors, pruned directories, total hits
- Hit overview:
  - By **rule**: occurrences / files-with-hits
  - By **category**: occurrences / files-with-hits
  - By **severity**: occurrences / files-with-hits
- Critical directory partitioning:
  - Per-partition scanned file counts and total hits
  - Per-partition aggregation tables by category / severity / rule (only show non-zero entries)
- Top-N hotspots: bucket directory hits (default Top 15); bucket depth defaults to 3 and is configurable

It does not include:

- Per-file/per-line details, code snippets, or line numbers.

### Config file (INI)

Recommended filename: `ai_review.ini`

```ini
[scan]
# Only scans *.py (fixed). Configure directory exclusion rules (glob, '/' separators).
exclude_dir_globs =
    **/.git/**
    **/node_modules/**
    **/venv/**
    **/__pycache__/**
    cms/edx_xblock_scorm/**
    cms/edx-ora2/**
    cms/edx-search/**
    cms/xblock-drag-and-drop-v2/**
    cms/xblock-ilt/**
    cms/xblock-pdf/**
    cms/xblock-poll/**
    cms/xblock-utils/**

# Optional: hotspot bucket depth (default: 3; buckets by the first N path segments).
hotspot_depth = 3

[report]
top_n_dirs = 15

[critical_dirs]
# If empty: auto-detect from the default list; otherwise use the paths you specify (relative to root).
paths =
    lms
    cms
    openedx/core
    openedx/features
    common
    xmodule
```

### Core data structures

- `Rule`:
  - `id: str`
  - `category: str`
  - `severity: str` (`high|medium|low`)
  - `description: str`
  - `regexes: List[Pattern]` (line-based matching)
- `FileFinding`:
  - `path: str` (absolute)
  - `relpath: str` (posix path relative to root)
  - `rule_counts: Dict[rule_id, int]`
- `ScanSummary`:
  - `root: str`
  - `scanned_files: int`
  - `skipped_files: int`
  - `read_errors: int`
  - `rule_occurrences: Dict[rule_id, int]`
  - `rule_files: Dict[rule_id, int]` (number of files with hits)
  - `dir_occurrences: Dict[dir_key, Dict[rule_id, int]]` (partition aggregation)
  - `category_occurrences: Dict[category, int]`
  - `severity_occurrences: Dict[severity, int]`
  - `category_files: Dict[category, int]` (files-with-hits, de-duplicated)
  - `severity_files: Dict[severity, int]` (files-with-hits, de-duplicated)
  - `dir_category_occurrences: Dict[dir_key, Dict[category, int]]`
  - `dir_severity_occurrences: Dict[dir_key, Dict[severity, int]]`

---

## 3) Design

Project structure:

- `ai_review.py`
  - CLI entrypoint; parse args; load config; scan; print stdout summary; write Markdown report
- `review_agent/config.py`
  - Parse INI; merge defaults; normalize glob rules; produce final `ScanConfig`
  - Constraint: keep v1 keys working (`exclude_dir_globs`, `top_n_dirs`, `critical_dirs.paths`)
- `review_agent/rules.py`
  - Define the fixed ruleset (includes v1 rules; allows minor low-false-positive extensions)
- `review_agent/scanner.py`
  - `os.walk` scanning and directory pruning (exclude globs)
  - Line-based regex counting (skip pure comment lines)
  - Aggregation only: rule/category/severity/critical_dir/topN
- `review_agent/report_md.py`
  - Render `ScanSummary` to Markdown (tables + Top-N + metadata/summary)
- `review_agent/types.py`
  - Lightweight data structures (dataclasses/typing); compatible with Python 3 stdlib

Design principles:

- **Robust**: tolerate decoding/permission errors; count and continue.
- **Low noise**: scan `.py` only; default excludes for generated dirs; skip pure comment lines; new rules must stay low-false-positive.
- **Configurable**: exclusions, critical dirs, Top-N, and hotspot bucket depth adjustable via INI.

---

## 4) Implementation constraints

- Runs on Python 3; no third-party dependencies.
- Regex + file path scanning only; no AST parsing.
- No per-line commentary; aggregation only.

---

## 5) Validation

Manual test steps:

1. Use the repo-provided `ai_review.ini` (or create your own) in the `review-agent` directory.
2. Smoke test on a small directory:
   - `python3 ai_review.py scan .`
   - Verify `ai_review_report.md` is generated and stdout prints a summary.
3. Run on the Hawthorn root:
   - `python3 path/to/review-agent/ai_review.py scan /path/to/hawthorn/platform --out hawthorn_review.md`
4. Modify `exclude_dir_globs` (add/remove exclusions), rerun, and confirm file counts/distributions change as expected.
5. (Upgrade) Add `[scan] hotspot_depth = 1` and confirm “Top directory hotspots” buckets become coarser.
6. (Upgrade) Verify the report includes rollups by `category` and `severity` overall and inside critical directory partitions.
7. (Upgrade) Ensure new rules (`PY3_NONLOCAL`, `PY3_RAISE_FROM`) only trigger when the syntax appears at the beginning of a non-comment line (low false positives).

### Execution Environment / Constraints

- All scan commands **must** be executed using the `uv run` wrapper to ensure a consistent Python environment:

```bash
uv run python ai_review.py scan <ROOT_PATH> --out <REPORT_PATH>
```

Success criteria:

- The tool completes scanning offline with stdlib only and outputs Markdown.
- The report includes overall stats, per-rule aggregation, critical directory partitions, and Top-N hotspots.
- Exclusion config takes effect (hits and scanned file counts respond to config changes).
- Additional upgrade success criteria:
  - The report includes overall rollups by category/severity and per-critical-dir rollups.
  - `exclude_dir_globs` handling is robust (e.g., tolerate directory globs without trailing `/**`, tolerate `./` prefixes and backslashes via normalization).
  - New config keys (e.g., `hotspot_depth`) are optional and have safe defaults that preserve v1 behavior.
  - The scan remains offline and text-only, scans `.py` only, and does not emit per-line/per-file findings.
  - Backward compatibility:
    - CLI args `scan PATH --config --out --quiet` behave the same as v1.
    - Existing INI keys keep working; new keys are optional with safe defaults.

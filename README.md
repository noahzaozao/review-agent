# review-agent: Local Offline Risk Scanner for Open edX Hawthorn (Text Rules Baseline)

This is a **local, offline** CLI tool that performs a **full scan** (not a git diff) of an **Open edX Hawthorn (Python 2.7 / Django 1.11)** codebase and produces a **Markdown distribution report**. It helps you establish a baseline view of “stability/risk signals” across the repository.

> Core principles: **low false positives**, **distribution-only statistics**, **no per-line review**, **no code changes**.

---

## What it does / does not do

### In scope
- **Scan an entire codebase directory**: recursively scan a given root (e.g. `platform/`)
- **Backend Python only**: scan `*.py` files only
- **Text-only rules**: file paths + regex matching; no AST; no imports; no code execution
- **Markdown report output**: aggregated distributions (by rule / category / severity / critical directories / Top-N hotspots)
- **Configurable directory exclusions**: via `exclude_dir_globs` in `ai_review.ini`
- **Critical directory partitioning**: auto-detect (only if present), or override in config

### Out of scope / non-goals
- Not a PR tool: **not based on git diff**
- No per-file/per-line comments: **no line numbers, no snippets, no itemized suggestions**
- No auto-fixes: does not modify source code or generate patches
- No external systems/network: no GitHub/Jenkins/LLM APIs
- No modernization guidance (especially no “upgrade Python/Django” advice)

---

## Requirements
- Python **3** (stdlib only, no third-party dependencies)
- Offline execution

---

## Directory structure

This tool expects the following directory structure (sibling directories):

```
./
├── platform/          # Open edX Hawthorn codebase to scan
└── review-agent/       # This repository
```

Place `review-agent` as a sibling directory to the `platform` directory you want to scan.

---

## Using `uv` (recommended)

From the `review-agent/` directory:

```bash
uv venv
uv run python ai_review.py scan ../platform --out hawthorn_review.md
```

Notes:
- This project has **no third-party dependencies**, so you typically do not need `uv pip install ...`.
- `uv run` executes inside `.venv/` to keep the Python version consistent and the environment isolated.

---

## Quick start

From the `review-agent/` directory:

```bash
python3 ai_review.py scan ../platform --out hawthorn_review.md
```

Common arguments:
- `--config PATH`: config INI path (defaults to `./ai_review.ini` if present in the current working directory)
- `--out PATH`: output Markdown report path (default: `ai_review_report.md`)
- `--quiet`: reduce stdout output (still writes the report)

Exit codes:
- `0`: scan completed (rule hits do not make the run “fail”)
- `2`: fatal errors (invalid args, missing path, cannot write report, etc.)

---

## Configuration (`ai_review.ini`)

The config file uses INI format. Recommended: edit the repository’s `ai_review.ini`.

### 1) Directory exclusions (required)

Add glob rules under `[scan] exclude_dir_globs` (matched relative to the scan root, using `/` separators):

- Common defaults: `.git/`, `node_modules/`, `venv/`, `__pycache__/`, `.tox/`, `dist/`, `build/`, etc.
- The following CMS subprojects are excluded by default (to avoid counting vendored subrepos as core platform code):
  - `cms/edx_xblock_scorm/**`
  - `cms/edx-ora2/**`
  - `cms/edx-search/**`
  - `cms/xblock-drag-and-drop-v2/**`
  - `cms/xblock-ilt/**`
  - `cms/xblock-pdf/**`
  - `cms/xblock-poll/**`
  - `cms/xblock-utils/**`

### 2) Critical directories (partitioning)

List paths relative to the scan root under `[critical_dirs] paths` (only existing directories are counted). Default list:
- `lms`
- `cms`
- `openedx/core`
- `openedx/features`
- `common`
- `xmodule`

### 3) Report Top-N

Configure `[report] top_n_dirs` to control how many hotspot directory buckets are shown (default: 15).

### 4) Hotspot bucketing depth (optional)

Configure `[scan] hotspot_depth` to control how many leading path segments are used to bucket hotspots (default: 3).

---

## Current minimal ruleset (fixed; low false positives)

### `py3_syntax`
- `PY3_FSTRING`: f-string prefix (`f''/f""`, including `rf/fr`)
- `PY3_ASYNC_DEF`: `async def`
- `PY3_AWAIT`: `await ...` (heuristic; may have very rare false positives)
- `EXCEPT_AS`: `except ... as e` (informational)
- Minor, low-false-positive extensions (anchored; skipped on pure comment lines):
  - `PY3_NONLOCAL`: `nonlocal ...`
  - `PY3_RAISE_FROM`: `raise ... from ...`

### `unicode_str` (count-only)
- `STR_ENCODE`: `.encode(...)`
- `STR_DECODE`: `.decode(...)`

> Note: these rules are only “risk signal statistics”. A hit does not imply a bug or a required change.

---

## What the report contains (no per-line details)
- Scan metadata (root/config/time)
- Scan statistics (Python files scanned, read errors, etc.)
- Aggregation by rule (occurrences, files-with-hits)
- Rollups by category and severity (occurrences, files-with-hits)
- Hit distribution by critical directory partition
- Per-critical-dir rollups (category/severity) and per-critical-dir rule breakdown (only non-zero entries)
- Top-N hotspots (bucketed by directory prefix; depth controlled by `hotspot_depth`)
- Effective directory exclusion globs

---

## Minimal manual validation
1. Smoke test on a small directory: `python3 ai_review.py scan .`
2. Run on Hawthorn platform root: `python3 ai_review.py scan ../platform --out hawthorn_review.md`
3. Edit `exclude_dir_globs` in `ai_review.ini`, rerun, and confirm the scanned file count/distribution changes as expected.

---

## Project layout
- `ai_review.py`: CLI entrypoint
- `ai_review.ini`: scan config (excludes / critical dirs / Top-N)
- `SPEC.md`: SDD document (Requirements/Specification/Design/Validation)
- `review_agent/`: implementation modules (config/rules/scanner/report)



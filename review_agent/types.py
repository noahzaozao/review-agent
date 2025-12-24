from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Pattern, Tuple


@dataclass(frozen=True)
class Rule:
    id: str
    category: str
    severity: str  # high|medium|low
    description: str
    regexes: List[Pattern[str]]


@dataclass
class FileFinding:
    path: str
    relpath: str  # posix, relative to scan root
    rule_counts: Dict[str, int] = field(default_factory=dict)

    def total_hits(self) -> int:
        return sum(self.rule_counts.values())


@dataclass
class ScanConfig:
    root: str
    exclude_dir_globs: List[str]
    critical_dirs: List[str]
    top_n_dirs: int = 15
    hotspot_depth: int = 3


@dataclass
class ScanSummary:
    tool_version: str
    python_version: str

    root: str
    config_path: Optional[str]
    started_at_iso: str
    finished_at_iso: str

    scanned_files: int
    skipped_files: int
    pruned_dirs: int
    read_errors: int

    # effective config (for report rendering / traceability)
    top_n_dirs: int
    hotspot_depth: int

    # rule_id -> total occurrences across all files
    rule_occurrences: Dict[str, int]
    # rule_id -> number of files with at least 1 occurrence
    rule_files: Dict[str, int]

    # dir_key -> (rule_id -> occurrences)
    dir_occurrences: Dict[str, Dict[str, int]]
    # dir_key -> scanned python files under that dir
    dir_files_scanned: Dict[str, int]

    # directory -> total hits (all rules), for Top N display
    top_dirs: List[Tuple[str, int]]

    # metadata
    critical_dirs_detected: List[str]
    excluded_dir_globs: List[str]

    # rollups (overall)
    category_occurrences: Dict[str, int] = field(default_factory=dict)
    severity_occurrences: Dict[str, int] = field(default_factory=dict)
    category_files: Dict[str, int] = field(default_factory=dict)
    severity_files: Dict[str, int] = field(default_factory=dict)

    # rollups (by critical dir)
    dir_category_occurrences: Dict[str, Dict[str, int]] = field(default_factory=dict)
    dir_severity_occurrences: Dict[str, Dict[str, int]] = field(default_factory=dict)



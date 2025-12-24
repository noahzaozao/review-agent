import re
from typing import List

from .types import Rule


def minimal_ruleset() -> List[Rule]:
    """
    Fixed minimal ruleset (low false-positive) for a Python 2.7 legacy codebase.
    Text-only regex scanning; no AST parsing.
    """
    rules: List[Rule] = []

    # Python 3-only syntax signal: f-strings (including rf/fr combinations).
    #
    # v2 constraint: only trigger on non-comment, line-start syntax (scanner matches on lstrip() lines).
    rules.append(
        Rule(
            id="PY3_FSTRING",
            category="py3_syntax",
            severity="high",
            description="Python 3 f-string prefix (f''/f\"\"\", including rf/fr).",
            regexes=[
                re.compile(r"""(?i)^(?:f|rf|fr)(?:'''|\"\"\"|'|")"""),
            ],
        )
    )

    # Python 3-only syntax signal: async def
    rules.append(
        Rule(
            id="PY3_ASYNC_DEF",
            category="py3_syntax",
            severity="high",
            description="Python 3 async function definition (async def).",
            regexes=[
                re.compile(r"^async\s+def\b"),
            ],
        )
    )

    # Python 3 syntax signal: await (note: in Python 2 it can be an identifier => medium).
    rules.append(
        Rule(
            id="PY3_AWAIT",
            category="py3_syntax",
            severity="medium",
            description="Potential Python 3 await usage (heuristic).",
            regexes=[
                re.compile(r"^await\b\s*[\w(]"),
            ],
        )
    )

    # Python 3-style exception binding: informational (Python 2.7 may accept it in some cases).
    rules.append(
        Rule(
            id="EXCEPT_AS",
            category="py3_syntax",
            severity="low",
            description="except ... as e (informational: Python 3-style exception binding).",
            regexes=[
                re.compile(r"^except\b[^:]*\bas\b\s+[A-Za-z_]\w*\s*:?\s*$"),
            ],
        )
    )

    # unicode/str risk signals
    rules.append(
        Rule(
            id="STR_ENCODE",
            category="unicode_str",
            severity="low",
            description="Potential unicode/str boundary: .encode(...).",
            regexes=[
                # Heuristic to avoid matching inside inline comments:
                # match only before any '#' on the line.
                re.compile(r"^[^#]*\.encode\s*\("),
            ],
        )
    )
    rules.append(
        Rule(
            id="STR_DECODE",
            category="unicode_str",
            severity="low",
            description="Potential unicode/str boundary: .decode(...).",
            regexes=[
                re.compile(r"^[^#]*\.decode\s*\("),
            ],
        )
    )

    # --- Minor, low-false-positive extensions (Python 2.7-incompatible syntax) ---
    # Note: these are anchored to reduce false positives; scanner also skips pure comment lines.

    rules.append(
        Rule(
            id="PY3_NONLOCAL",
            category="py3_syntax",
            severity="high",
            description="Python 3-only keyword: nonlocal (anchored).",
            regexes=[
                re.compile(r"^nonlocal\b"),
            ],
        )
    )
    rules.append(
        Rule(
            id="PY3_RAISE_FROM",
            category="py3_syntax",
            severity="high",
            description="Python 3 exception chaining syntax: raise ... from ... (anchored).",
            regexes=[
                # Avoid matching 'from' inside inline comments by restricting to pre-# text.
                re.compile(r"^raise\b[^#]*\bfrom\b[^#]*$"),
            ],
        )
    )

    return rules



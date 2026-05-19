"""Test that core code contains no domain-specific vocabulary.

This test ensures the domain-agnostic architecture constraint is met:
core code in `antalens/` must not contain ANTARES-specific terms.

Forbidden terms (from refactor.md):
- ANTARES, eco2mix, Adequacy, Reserve, Marginal Price
- bidding zone, CCGT, nuclear, wind load, France, RTE, Enel, production margin

These terms should only appear in:
- `catalogs/` (YAML configuration)
- `examples/` (demonstration code)
- `docs/` (documentation)
"""

import re
from pathlib import Path

import pytest

FORBIDDEN_TERMS = [
    r"\bANTARES\b",
    r"\beco2mix\b",
    r"\bAdequacy\b",
    r"\bReserve\b",
    r"\bMarginal Price\b",
    r"\bbidding zone\b",
    r"\bCCGT\b",
    r"\bnuclear\b",
    r"\bwind load\b",
    r"\bFrance\b",
    r"\bRTE\b",
    r"\bEnel\b",
    r"\bproduction margin\b",
]

CORE_PATH = Path(__file__).parent.parent / "src" / "antalens"
EXCLUDE_DIRS = {"legacy", "examples"}
EXCLUDE_PATTERNS = {r".*test_.*\.py$", r".*_test\.py$"}


def _should_exclude_file(file_path: Path) -> bool:
    """Check if a file should be excluded from the domain leak check."""
    rel_path = file_path.relative_to(CORE_PATH)

    # Exclude certain directories
    if any(part in EXCLUDE_DIRS for part in rel_path.parts):
        return True

    # Exclude test files
    return any(re.match(pattern, file_path.name) for pattern in EXCLUDE_PATTERNS)


@pytest.mark.skip(reason="Not useful for now")
@pytest.mark.parametrize("term", FORBIDDEN_TERMS, ids=lambda t: t.strip())
def test_no_domain_leak_in_core_code(term: str) -> None:
    """Assert no forbidden domain vocabulary appears in core code."""
    pattern = re.compile(term, re.IGNORECASE)
    violations = []

    for file_path in CORE_PATH.rglob("*.py"):
        if _should_exclude_file(file_path):
            continue

        content = file_path.read_text(encoding="utf-8")
        matches = pattern.findall(content)

        if matches:
            violations.append((file_path.name, matches))

    if violations:
        error_msg = "Domain vocabulary leak detected in core code:\n"
        for file_name, matches in violations:
            error_msg += f"\n  {file_name}: {matches!r}"
        pytest.fail(error_msg)

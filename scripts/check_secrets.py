"""Fail if the tree contains secrets, credentials, or machine-local paths.

Publicable-state gate (PLAN Fase 0, puerta de salida): no keys, no private
data, no machine-local paths outside the excluded internal docs.

Usage: ``python scripts/check_secrets.py`` from the repo root.
Exit 0 = clean, 1 = findings (listed, never hidden).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

EXCLUDED_DIRS = {
    ".git", ".venv", "__pycache__", ".pytest_cache", ".tox",
    "node_modules", "dist", "build",
}
# Root-relative paths excluded from scanning. Only the internal PLAN.md at
# the root is excluded (git-ignored, never published); a PLAN.md anywhere
# else would still be scanned.
EXCLUDED_PATHS = {"PLAN.md"}
EXCLUDED_SUFFIXES = (".egg-info",)

# Files that must never be tracked by git (would be published).
NEVER_TRACK = (".env", ".env.local", "credentials.json", ".pem", ".key")

SECRET_PATTERNS = [
    # Known token prefixes are always findings, even in tests.
    (re.compile(r"(AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{8,}|"
                r"xox[bap]-[A-Za-z0-9-]{8,}|sk-(live|test)-[A-Za-z0-9]{8,})"),
     "known credential prefix"),
    (re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
     "private key block"),
    # Assignments naming a credential (e.g. token = "test-fixture"). Only
    # dummy-prefixed values (test fixtures) are skipped, not flagged.
    (re.compile(r"(?i)\b(api[_-]?key|secret|token|passwd|password)\b"
                r"\s*[:=]\s*['\"]([^'\"]+)['\"]"),
     "credential-like assignment"),
]

DUMMY_PREFIX = re.compile(
    r"(?i)^(test|secret|example|fake|dummy|changeme|placeholder|sample|mock|huel|fixture)"
)

# A drive path is a *single* letter (negative lookbehind excludes URI
# schemes like https://); UNC shares and Unix home dirs are also covered.
MACHINE_PATH = re.compile(
    r"(?<![A-Za-z])[A-Za-z]:[/\\]|\\\\[\w.$-]+\\[\w.$-]+|/(?:home|Users)/[\w.~-]+"
)


def _safe_stdout() -> None:
    """Never crash while reporting: Windows consoles are not UTF-8."""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except (AttributeError, OSError, ValueError):
        pass


def iter_files() -> list[Path]:
    files: list[Path] = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if rel.as_posix() in EXCLUDED_PATHS:
            continue
        if any(part in EXCLUDED_DIRS or part.endswith(EXCLUDED_SUFFIXES)
               for part in rel.parts):
            continue
        files.append(path)
    return files


def check_assignment(value: str) -> bool:
    """True if a credential-like value looks real (not a test fixture).

    The dummy exemption is anchored: only values *starting* with a dummy
    marker (``test-key``, ``secret_local``…) are skipped. A marker buried
    mid-value (``a1b2c3secretvalue99``) is still flagged.
    """
    if DUMMY_PREFIX.match(value):
        return False
    return True


def main() -> int:
    _safe_stdout()
    findings: list[str] = []
    for path in iter_files():
        rel = path.relative_to(ROOT).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # binary or unreadable: not a secret carrier here
        for lineno, line in enumerate(text.splitlines(), 1):
            for pattern, label in SECRET_PATTERNS:
                for match in pattern.finditer(line):
                    if label == "credential-like assignment":
                        if not check_assignment(match.group(2)):
                            continue
                    findings.append(f"{rel}:{lineno}: {label}: {line.strip()[:120]}")
            # Exact origin paths required by PLAN §21 are allowed only in
            # "- Origen:" lines of PROVENANCE.md; machine-agnostic
            # (repo-relative) origins are preferred for new entries.
            if MACHINE_PATH.search(line):
                if rel == "PROVENANCE.md" and line.strip().startswith("- Origen:"):
                    continue
                findings.append(f"{rel}:{lineno}: machine-local path: {line.strip()[:120]}")
    # Secret-carrying filenames must never enter git history.
    try:
        tracked = subprocess.run(
            ["git", "ls-files"], cwd=ROOT, capture_output=True,
            text=True, check=False).stdout.splitlines()
    except OSError:
        tracked = []
    for name in tracked:
        base = name.rsplit("/", 1)[-1]
        if base in NEVER_TRACK or base.endswith((".pem", ".key")):
            findings.append(f"{name}: secret-carrying file tracked by git")
    if findings:
        print(f"check_secrets: {len(findings)} finding(s):")
        for finding in findings:
            print(f"  - {finding}")
        return 1
    print(f"check_secrets: clean ({len(iter_files())} files scanned)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

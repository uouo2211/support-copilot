"""Read-only repository hygiene checks, using the Python standard library only."""

import ast
import csv
import io
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIRS = {
    ".git", ".venv", ".local", "__pycache__", ".pytest_cache", ".ruff_cache",
    "node_modules", "artifacts", "test-results", "htmlcov",
}
REQUIRED_FILES = (
    "README.md", "CONTRIBUTING.md", "AGENTS.md", "Dockerfile", "compose.yaml",
    "Makefile", "alembic.ini", "pyproject.toml", "uv.lock", "requirements.txt",
    "requirements-dev.txt", ".env.example", ".gitignore", ".dockerignore",
    "docs/README.md", "docs/development/status.md", "docs/ai-history/README.md",
)
REQUIRED_DIRS = (
    "app/api", "app/services", "app/repositories", "app/models", "app/schemas",
    "app/providers", "app/connectors", "app/jobs", "app/templates", "app/static",
    "migrations", "fixtures", "tests/unit", "tests/integration", "tests/e2e",
    "evals", "scripts", "docs/requirements", "docs/architecture", "docs/deployment",
    "docs/decisions", "docs/development", "docs/ai-history",
)
IMPORT_FIELDS = {
    "platform", "platform_tenant", "application_id", "chat_id", "message_id",
    "sender", "timestamp", "reply_to", "content",
}
PIN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*(?:\[[A-Za-z0-9_,.-]+\])?==[A-Za-z0-9_.+!-]+(?:\s*;.+)?")


def source_files(root):
    for directory, folders, files in os.walk(root, followlinks=False):
        folders[:] = sorted(f for f in folders if f not in EXCLUDED_DIRS and
                            not (Path(directory) / f).is_symlink())
        for name in sorted(files):
            path = Path(directory) / name
            if path.is_symlink() or name.startswith(".env") or name.endswith(".log"):
                continue
            if path.suffix in {".md", ".py", ".json", ".csv"} or name in {
                "requirements.txt", "requirements-dev.txt",
            }:
                yield path


def local_links(markdown):
    # Archived verbatim messages intentionally retain old paths inside fences.
    visible = re.sub(r"```.*?```|~~~.*?~~~", "", markdown, flags=re.DOTALL)
    for match in re.finditer(r"\[[^\]\n]*\]\((<[^>]+>|[^\s)]+)(?:\s+\"[^\"]*\")?\)", visible):
        target = match.group(1).strip("<>")
        parts = urlsplit(target)
        if not parts.scheme and not parts.netloc and parts.path:
            yield unquote(parts.path)


def link_errors(path, text, root):
    errors = []
    for target in local_links(text):
        resolved = (path.parent / target).resolve()
        try:
            resolved.relative_to(root.resolve())
        except ValueError:
            errors.append(f"nonportable or out-of-repository link: {target}")
            continue
        if not resolved.exists():
            errors.append(f"missing local link: {target}")
    return errors


def requirement_errors(text):
    errors = []
    for number, line in enumerate(text.splitlines(), 1):
        value = line.strip()
        if value and not value.startswith("#") and not PIN.fullmatch(value):
            errors.append(f"line {number}: dependency must have an exact == version")
    return errors


def validate_text(path, text, root):
    if path.suffix == ".md":
        return link_errors(path, text, root)
    if path.suffix == ".py":
        try:
            ast.parse(text, filename=str(path))
        except SyntaxError as exc:
            return [f"invalid Python syntax at line {exc.lineno}: {exc.msg}"]
    elif path.suffix == ".json":
        try:
            json.loads(text)
        except ValueError as exc:
            return [f"invalid JSON: {exc}"]
    elif path.suffix == ".csv" and path.parent.name == "fixtures":
        reader = csv.DictReader(io.StringIO(text))
        missing = IMPORT_FIELDS - set(reader.fieldnames or [])
        if missing:
            return ["missing import columns: " + ", ".join(sorted(missing))]
        for number, row in enumerate(reader, 2):
            if None in row or any(value is None for value in row.values()):
                return [f"CSV field count mismatch at line {number}"]
    elif path.name in {"requirements.txt", "requirements-dev.txt"}:
        return requirement_errors(text)
    return []


def check(root=ROOT):
    errors = []
    for name in REQUIRED_FILES:
        if not (root / name).is_file():
            errors.append(f"missing required file: {name}")
    for name in REQUIRED_DIRS:
        if not (root / name).is_dir():
            errors.append(f"missing required directory: {name}")
    files = list(source_files(root))
    for path in files:
        try:
            issues = validate_text(path, path.read_text(encoding="utf-8-sig"), root)
            errors.extend(f"{path.relative_to(root)}: {issue}" for issue in issues)
        except (OSError, UnicodeError, csv.Error, ValueError) as exc:
            errors.append(f"{path.relative_to(root)}: {type(exc).__name__}")
    return files, errors


def main():
    files, errors = check()
    if errors:
        print("Repository checks failed:")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print(f"Repository checks passed: {len(files)} source/document/data files checked.")
    print("No dependency install, application import, database connection or service startup performed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"ctx7sk[A-Za-z0-9_-]{20,}"),
    re.compile(r"PRIVATE KEY"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]{20,}"),
]


def value_contains_placeholder(value: str) -> bool:
    lowered = value.lower()
    return any(word in lowered for word in ("placeholder", "change-me", "change-this", "example", "dev-only", "test-password"))


def is_env_example(path: Path) -> bool:
    return path.name == ".env.example"


def main() -> int:
    failures: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT).as_posix()
        if any(part in {".git", "node_modules", ".opencode", "__pycache__"} for part in path.parts):
            continue
        if path == Path(__file__).resolve():
            continue
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".woff", ".woff2"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for pattern in PATTERNS:
            for match in pattern.finditer(text):
                failures.append(f"{rel}: {match.group(0)[:8]}…")
        if is_env_example(path):
            for line in text.splitlines():
                if "=" not in line or line.lstrip().startswith("#"):
                    continue
                name, value = line.split("=", 1)
                name = name.strip()
                value = value.strip().strip('"').strip("'")
                if name.endswith("_SECRET") and value and not value_contains_placeholder(value):
                    failures.append(f"{rel}: {name} sin marcador de ejemplo/dev-only")
    if failures:
        print("SECRET SCAN FAILED")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("secret scan: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

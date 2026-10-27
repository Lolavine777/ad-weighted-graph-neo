"""Check versioned/unignored paths, UTF-8 text, and inline local Markdown links."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_DIRECTORIES = ("data/raw/", "data/processed/", "reports/generated/")
TEXT_SUFFIXES = {".md", ".py", ".yml", ".yaml", ".json", ".toml", ".txt"}
# Evidence pinned by digest elsewhere, so their bytes cannot change; their links into the
# removed docs/adr and docs/worklog resolve at tag neo-thesis-v2.
FROZEN_DOCUMENTS = {
    "docs/guided-exploration.md",
    "docs/research/seamless-legacy-403-comparison-contract.md",
    "docs/research/week4-extension-scenario-handoff.md",
    "docs/research/week4-scenarios.md",
}


def private_path(name: str) -> bool:
    normalized = name.replace("\\", "/").lower()
    filename = PurePosixPath(normalized).name
    if filename == ".env" or (filename.startswith(".env.") and filename != ".env.example"):
        return True
    return any(
        normalized.startswith(prefix) and normalized != prefix + "readme.md"
        for prefix in PRIVATE_DIRECTORIES
    )


def broken_links(path: Path, root: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    # Only inline links outside fenced code; this is not a complete Markdown parser.
    text = re.sub(r"(?ms)^```[^\n]*\n.*?^```[^\n]*$", "", text)
    text = re.sub(r"(?ms)^~~~[^\n]*\n.*?^~~~[^\n]*$", "", text)
    errors = []
    for match in re.finditer(r"!?\[[^\]\n]*\]\(([^)\n]+)\)", text):
        target = match.group(1).strip()
        if target.startswith("<"):
            target = target[1:].split(">", 1)[0]
        else:
            target = target.split(' "', 1)[0]
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc or not parsed.path:
            continue
        local_path = unquote(parsed.path)
        base = root if local_path.startswith("/") else path.parent
        destination = (base / local_path.lstrip("/")).resolve()
        if not destination.is_relative_to(root.resolve()) or not destination.exists():
            errors.append(f"{path.relative_to(root)}: broken local link {target}")
    return errors


def repository_files(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=root,
        capture_output=True,
        check=True,
    )
    return sorted(set(result.stdout.decode("utf-8").split("\0")) - {""})


def main() -> int:
    errors = []
    files = repository_files(ROOT)
    for name in files:
        if private_path(name):
            errors.append(f"Private data/config must not be committed: {name}")
            continue
        path = ROOT / name
        if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
            continue
        try:
            path.read_text(encoding="utf-8")
            if path.suffix == ".md" and name not in FROZEN_DOCUMENTS:
                errors.extend(broken_links(path, ROOT))
        except (UnicodeError, ValueError) as exc:
            errors.append(f"{name}: invalid text or link: {exc}")
    if errors:
        print("\n".join(errors))
        return 1
    print(f"Repository checks passed for {len(files)} tracked/unignored files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

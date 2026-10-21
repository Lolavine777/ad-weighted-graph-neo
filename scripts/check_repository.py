"""Check versioned/unignored paths, UTF-8 text, and inline local Markdown links."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_DIRECTORIES = ("data/raw/", "data/processed/", "reports/generated/")
TEXT_SUFFIXES = {".md", ".py", ".yml", ".yaml", ".json", ".toml", ".txt"}


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


def extract_section_content(text: str, heading_pattern: str) -> str | None:
    """Extract content of an H2 section by heading pattern up to next H2 or end of string."""
    m = re.search(
        rf"^##[ \t]+{heading_pattern}[ \t]*$\n?(.*?)(?=^##[ \t]|\Z)",
        text,
        re.M | re.S,
    )
    return m.group(1) if m else None


def validate_worklog(path: Path) -> list[str]:
    """Validate structure of docs/worklog/*.md against daily-worklog template."""
    normalized = path.as_posix() if hasattr(path, "as_posix") else str(path).replace("\\", "/")
    filename = Path(normalized).name
    if filename == "README.md" or filename.startswith("week-"):
        return []

    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    # Accepts ASCII hyphen '-', en dash, or em dash for backward compatibility
    # with existing worklog documents (e.g. 2026-09-17-ttsB.md).
    pattern = r"^#\s+Worklog\s+[-\u2014\u2013]\s+\d{4}-\d{2}-\d{2}\s+[-\u2014\u2013]\s+tts[AB]\s*$"
    if not lines or not re.match(pattern, lines[0]):
        errors.append(
            f"{path}: invalid or missing title matching '# Worklog - YYYY-MM-DD - (ttsA|ttsB)'"
        )

    first_h2 = text.find("## ")
    header = text[:first_h2] if first_h2 != -1 else text
    if not re.search(
        r"^-[ \t]*(?:Múi giờ|Mui gio):[ \t]*Asia/Ho_Chi_Minh[ \t]*\(UTC\+07:00\)[ \t]*$",
        header,
        re.M,
    ):
        errors.append(
            f"{path}: missing or invalid timezone metadata "
            "'- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)'"
        )
    if not re.search(
        r"^-[ \t]*Issue[ \t]*/[ \t]*PR[ \t]*/[ \t]*milestone:[ \t]*\S.*$",
        header,
        re.M,
    ):
        errors.append(f"{path}: missing metadata '- Issue / PR / milestone: ...'")
    if not re.search(
        r"^-[ \t]*(?:Thời gian thực tế ước lượng|Thoi gian thuc te uoc luong):[ \t]*\S.*$",
        header,
        re.M,
    ):
        errors.append(f"{path}: missing metadata '- Thời gian thực tế ước lượng: ...'")

    headings = [h.strip() for h in re.findall(r"^##\s+(.+)$", text, re.M)]
    required_headings = [
        "Kết quả và bằng chứng",
        "Điều học được / quyết định",
        "Trở ngại và việc kế tiếp",
    ]
    for req in required_headings:
        if req not in headings:
            errors.append(f"{path}: missing required heading '## {req}'")

    if not errors and all(req in headings for req in required_headings):
        i1 = headings.index(required_headings[0])
        i2 = headings.index(required_headings[1])
        i3 = headings.index(required_headings[2])
        if not (i1 < i2 < i3):
            errors.append(f"{path}: headings must appear in order: {required_headings}")

    results_section = extract_section_content(
        text, r"(?:Kết quả và bằng chứng|Ket qua va bang chung)"
    )
    worklog_table_pattern = (
        r"^[ \t]*\|[ \t]*(?:Công việc|Cong viec)[ \t]*\|"
        r"[ \t]*(?:Đầu ra|Dau ra)[ \t]*/[ \t]*link[ \t]*/"
        r"[ \t]*(?:lệnh kiểm tra|lenh kiem tra)[ \t]*\|"
        r"[ \t]*(?:Kết quả thực tế|Ket qua thuc te)[ \t]*\|"
        r"(?:[^\n]*\|)?[ \t]*\n"
        r"^[ \t]*\|(?:[ \t]*:?-+:?[ \t]*\|){3,}[ \t]*$"
    )
    if results_section is None or not re.search(worklog_table_pattern, results_section, re.M):
        errors.append(
            f"{path}: missing results table with columns "
            "'| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |' "
            "and separator in '## Kết quả và bằng chứng'"
        )

    return errors


def validate_adr(path: Path) -> list[str]:
    """Validate structure of docs/adr/ADR-*.md against adr template."""
    normalized = path.as_posix() if hasattr(path, "as_posix") else str(path).replace("\\", "/")
    filename = Path(normalized).name
    if filename == "README.md":
        return []

    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines or not re.match(r"^#\s+ADR-\d{4}:\s+.+$", lines[0]):
        errors.append(f"{path}: invalid or missing title matching '# ADR-xxxx: <Title>'")

    first_h2 = text.find("## ")
    header = text[:first_h2] if first_h2 != -1 else text
    if not re.search(r"^-[ \t]*(?:Ngày|Ngay):[ \t]*\S.*$", header, re.M):
        errors.append(f"{path}: missing metadata '- Ngày: ...'")
    if not re.search(r"^-[ \t]*(?:Trạng thái|Trang thai):[ \t]*\S.*$", header, re.M):
        errors.append(f"{path}: missing metadata '- Trạng thái: ...'")

    has_combined = bool(
        re.search(
            r"^-[ \t]*(?:Người đề xuất|Nguoi de xuat)[ \t]*/[ \t]*reviewer:[ \t]*\S.*$",
            header,
            re.M,
        )
    )
    if not has_combined:
        if re.search(
            r"^-[ \t]*(?:Người đề xuất|Nguoi de xuat)[ \t]*/[ \t]*reviewer:",
            header,
            re.M,
        ):
            errors.append(f"{path}: missing metadata value for '- Người đề xuất / reviewer: ...'")
        else:
            if not re.search(r"^-[ \t]*(?:Người đề xuất|Nguoi de xuat):[ \t]*\S.*$", header, re.M):
                errors.append(f"{path}: missing metadata '- Người đề xuất: ...'")
            if not re.search(r"^-[ \t]*Reviewer:[ \t]*\S.*$", header, re.M):
                errors.append(f"{path}: missing metadata '- Reviewer: ...'")

    if not re.search(r"^-[ \t]*Issue[ \t]*/[ \t]*PR:[ \t]*\S.*$", header, re.M):
        errors.append(f"{path}: missing metadata '- Issue / PR: ...'")

    headings = [h.strip() for h in re.findall(r"^##\s+(.+)$", text, re.M)]
    expected_patterns = [
        (r"(?:Bối cảnh|Boi canh)", "Bối cảnh"),
        (r"(?:Các phương án|Cac phuong an)", "Các phương án"),
        (r"(?:Quyết định và hệ quả|Quyet dinh va he qua)", "Quyết định và hệ quả"),
        (
            r"(?:Kiểm chứng và điều kiện xem lại|Kiem chung va dieu kien xem lai)",
            "Kiểm chứng và điều kiện xem lại",
        ),
    ]
    matched_indices: list[int] = []
    for pattern, name in expected_patterns:
        idx = next((i for i, h in enumerate(headings) if re.fullmatch(pattern, h)), None)
        if idx is None:
            errors.append(f"{path}: missing required heading '## {name}'")
        else:
            matched_indices.append(idx)

    if len(matched_indices) == 4 and matched_indices != sorted(matched_indices):
        errors.append(f"{path}: ADR headings are not in the required order")

    options_section = extract_section_content(text, r"(?:Các phương án|Cac phuong an)")
    adr_table_pattern = (
        r"^[ \t]*\|[ \t]*(?:Phương án|Phuong an)[ \t]*\|"
        r"[ \t]*(?:Lợi ích|Loi ich)[ \t]*\|"
        r"[ \t]*(?:Chi phí|Chi phi)[ \t]*/[ \t]*(?:hạn chế|han che)[ \t]*\|"
        r"[ \t]*(?:Bằng chứng|Bang chung)[ \t]*\|"
        r"(?:[^\n]*\|)?[ \t]*\n"
        r"^[ \t]*\|(?:[ \t]*:?-+:?[ \t]*\|){4,}[ \t]*$"
    )
    if options_section is None or not re.search(adr_table_pattern, options_section, re.M):
        errors.append(
            f"{path}: missing options comparison table with required columns "
            "and separator in '## Các phương án'"
        )

    return errors


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
            if path.suffix == ".md":
                errors.extend(broken_links(path, ROOT))
                norm_name = name.replace("\\", "/")
                if norm_name.startswith("docs/worklog/"):
                    errors.extend(validate_worklog(path))
                elif norm_name.startswith("docs/adr/"):
                    errors.extend(validate_adr(path))
        except (UnicodeError, ValueError) as exc:
            errors.append(f"{name}: invalid text or link: {exc}")
    if errors:
        print("\n".join(errors))
        return 1
    print(f"Repository checks passed for {len(files)} tracked/unignored files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

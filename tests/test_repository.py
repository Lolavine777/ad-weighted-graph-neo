import hashlib
import re
from pathlib import Path

import pytest

from scripts.check_repository import (
    broken_links,
    private_path,
    validate_adr,
    validate_worklog,
)


@pytest.mark.parametrize(
    "path",
    [
        ".env",
        "nested/.env.local",
        "data/raw/export.json",
        "data/raw/nested/README.md",
        "data/processed/graph.json",
        "reports/generated/metrics.csv",
        "DATA\\RAW\\export.json",
    ],
)
def test_private_files_are_blocked_even_if_force_added(path):
    assert private_path(path)


@pytest.mark.parametrize(
    "path", [".env.example", "data/raw/README.md", "data/samples/toy-graph.json", "README.md"]
)
def test_documentation_and_synthetic_paths_are_allowed(path):
    assert not private_path(path)


def test_local_links_and_missing_targets(tmp_path):
    page = tmp_path / "README.md"
    target = tmp_path / "design notes.md"
    target.write_text("# Design\n", encoding="utf-8")
    page.write_text(
        "[valid](<design notes.md>)\n"
        "[anchor](#heading)\n"
        "[remote](https://example.com/not-fetched)\n"
        "[missing](absent.md)\n"
        "```markdown\n[example](not-a-real-file.md)\n```\n",
        encoding="utf-8",
    )
    errors = broken_links(page, tmp_path)
    assert len(errors) == 1
    assert "absent.md" in errors[0]


def test_link_outside_repository_is_rejected(tmp_path):
    page = tmp_path / "README.md"
    page.write_text("[outside](../outside.md)\n", encoding="utf-8")
    assert len(broken_links(page, tmp_path)) == 1


# --- Document Schema Tests (Worklog & ADR) ---

VALID_WORKLOG = """# Worklog - 2026-09-17 - ttsA

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: Refs #30 / M1
- Thời gian thực tế ước lượng: 2 giờ

## Kết quả và bằng chứng

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Schema validation | scripts/check_repository.py | Passed |

## Điều học được / quyết định

- Kiểm tra định dạng tự động giúp bảo đảm tính đồng nhất.

## Trở ngại và việc kế tiếp

- Tiếp tục các đầu việc trong mốc M1.
"""

VALID_ADR = """# ADR-0099: Chuan hoa quy trinh kiem thu

- Ngày: 2026-09-17
- Trạng thái: Proposed
- Người đề xuất: @Lolavine777 (TTS A)
- Reviewer: @nairyuuu (TTS B)
- Issue / PR: Refs #30

## Bối cảnh

Bối cảnh kỹ thuật mô tả tại đây.

## Các phương án

| Phương án | Lợi ích | Chi phí / hạn chế | Bằng chứng |
| --- | --- | --- | --- |
| 1. Kiểm tra tự động | Phát hiện sớm lỗi định dạng | Cần viết thêm kiểm thử | Thực nghiệm CI |

## Quyết định và hệ quả

Quyết định lựa chọn phương án 1.

## Kiểm chứng và điều kiện xem lại

Lệnh kiểm tra: `python scripts/check_repository.py`.
"""


def test_all_existing_adrs_pass():
    adrs = sorted(Path("docs/adr").glob("ADR-*.md"))
    assert adrs, "No ADR files found in docs/adr/"
    for p in adrs:
        errors = validate_adr(p)
        assert not errors, f"{p.name} failed validation: {errors}"


def test_all_existing_worklogs_pass():
    worklogs = sorted(Path("docs/worklog").glob("*.md"))
    assert worklogs, "No worklog files found in docs/worklog/"
    for p in worklogs:
        errors = validate_worklog(p)
        assert not errors, f"{p.name} failed validation: {errors}"


def test_worklog_valid(tmp_path):
    f = tmp_path / "2026-09-17-ttsA.md"
    f.write_text(VALID_WORKLOG, encoding="utf-8")
    assert validate_worklog(f) == []


def test_worklog_invalid_title(tmp_path):
    f = tmp_path / "2026-09-17-ttsA.md"
    f.write_text(
        VALID_WORKLOG.replace("# Worklog - 2026-09-17 - ttsA", "# Daily Log 2026-09-17"),
        encoding="utf-8",
    )
    errors = validate_worklog(f)
    assert any("title" in e for e in errors)


def test_worklog_missing_metadata(tmp_path):
    f = tmp_path / "2026-09-17-ttsA.md"
    f.write_text(
        VALID_WORKLOG.replace("- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)\n", ""),
        encoding="utf-8",
    )
    errors = validate_worklog(f)
    assert any("timezone" in e for e in errors)


def test_worklog_missing_heading(tmp_path):
    f = tmp_path / "2026-09-17-ttsA.md"
    f.write_text(
        VALID_WORKLOG.replace("## Trở ngại và việc kế tiếp", "## Kế hoạch kế tiếp"),
        encoding="utf-8",
    )
    errors = validate_worklog(f)
    assert any("Trở ngại và việc kế tiếp" in e for e in errors)


def test_worklog_heading_order(tmp_path):
    f = tmp_path / "2026-09-17-ttsA.md"
    content = VALID_WORKLOG.replace("## Kết quả và bằng chứng", "TEMP_HEADING")
    content = content.replace("## Điều học được / quyết định", "## Kết quả và bằng chứng")
    content = content.replace("TEMP_HEADING", "## Điều học được / quyết định")
    f.write_text(content, encoding="utf-8")
    errors = validate_worklog(f)
    assert any("order" in e for e in errors)


def test_worklog_missing_table(tmp_path):
    f = tmp_path / "2026-09-17-ttsA.md"
    content = re.sub(r"\|.*\|", "", VALID_WORKLOG)
    f.write_text(content, encoding="utf-8")
    errors = validate_worklog(f)
    assert any("table" in e for e in errors)


def test_worklog_exemptions(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text("# Readme", encoding="utf-8")
    assert validate_worklog(readme) == []

    week = tmp_path / "week-01-review.md"
    week.write_text("# Weekly Review", encoding="utf-8")
    assert validate_worklog(week) == []


def test_adr_valid(tmp_path):
    f = tmp_path / "ADR-0099-test.md"
    f.write_text(VALID_ADR, encoding="utf-8")
    assert validate_adr(f) == []


def test_adr_invalid_title(tmp_path):
    f = tmp_path / "ADR-0099-test.md"
    f.write_text(
        VALID_ADR.replace("# ADR-0099: Chuan hoa quy trinh kiem thu", "# Quy trinh kiem thu"),
        encoding="utf-8",
    )
    errors = validate_adr(f)
    assert any("title" in e for e in errors)


def test_adr_missing_metadata(tmp_path):
    f = tmp_path / "ADR-0099-test.md"
    f.write_text(VALID_ADR.replace("- Reviewer: @nairyuuu (TTS B)\n", ""), encoding="utf-8")
    errors = validate_adr(f)
    assert any("Reviewer" in e for e in errors)


def test_adr_missing_heading(tmp_path):
    f = tmp_path / "ADR-0099-test.md"
    f.write_text(VALID_ADR.replace("## Bối cảnh", "## Lý do thực hiện"), encoding="utf-8")
    errors = validate_adr(f)
    assert any("Bối cảnh" in e for e in errors)


def test_adr_missing_options_table(tmp_path):
    f = tmp_path / "ADR-0099-test.md"
    content = re.sub(r"\|.*\|", "", VALID_ADR)
    f.write_text(content, encoding="utf-8")
    errors = validate_adr(f)
    assert any("table" in e for e in errors)


def test_adr_combined_proposer_reviewer(tmp_path):
    f = tmp_path / "ADR-0099-combined.md"
    content = VALID_ADR.replace(
        "- Người đề xuất: @Lolavine777 (TTS A)\n- Reviewer: @nairyuuu (TTS B)",
        "- Người đề xuất / reviewer: @Lolavine777 / @nairyuuu",
    )
    f.write_text(content, encoding="utf-8")
    assert validate_adr(f) == []


def test_adr_from_official_template(tmp_path):
    template = Path("docs/templates/adr.md").read_text(encoding="utf-8")
    filled = (
        template.replace("# ADR-<0001>: <quyết định>", "# ADR-0099: Chuan hoa quy trinh")
        .replace("- Ngày: <YYYY-MM-DD>", "- Ngày: 2026-09-17")
        .replace(
            "- Người đề xuất / reviewer: <...>",
            "- Người đề xuất / reviewer: @Lolavine777 / @nairyuuu",
        )
        .replace("- Issue / PR: <...>", "- Issue / PR: Refs #30")
        .replace(
            "| <...> | <...> | <...> | <...> |",
            "| Phương án 1 | Tốt | Chi phí thấp | Bằng chứng đầy đủ |",
        )
    )
    f = tmp_path / "ADR-0099-from-template.md"
    f.write_text(filled, encoding="utf-8")
    assert validate_adr(f) == []


@pytest.mark.parametrize("empty_val", ["", "   "])
def test_worklog_empty_metadata_rejected(tmp_path, empty_val):
    f_issue = tmp_path / "worklog-empty-issue.md"
    f_issue.write_text(
        VALID_WORKLOG.replace(
            "- Issue / PR / milestone: Refs #30 / M1",
            f"- Issue / PR / milestone:{empty_val}",
        ),
        encoding="utf-8",
    )
    errors = validate_worklog(f_issue)
    assert any("Issue / PR / milestone" in e for e in errors)

    f_time = tmp_path / "worklog-empty-time.md"
    f_time.write_text(
        VALID_WORKLOG.replace(
            "- Thời gian thực tế ước lượng: 2 giờ",
            f"- Thời gian thực tế ước lượng:{empty_val}",
        ),
        encoding="utf-8",
    )
    errors = validate_worklog(f_time)
    assert any("Thời gian thực tế ước lượng" in e for e in errors)


@pytest.mark.parametrize("empty_val", ["", "   "])
def test_adr_empty_metadata_rejected(tmp_path, empty_val):
    f_rev = tmp_path / "adr-empty-reviewer.md"
    f_rev.write_text(
        VALID_ADR.replace(
            "- Reviewer: @nairyuuu (TTS B)",
            f"- Reviewer:{empty_val}",
        ),
        encoding="utf-8",
    )
    errors = validate_adr(f_rev)
    assert any("Reviewer" in e for e in errors)

    f_prop = tmp_path / "adr-empty-proposer.md"
    f_prop.write_text(
        VALID_ADR.replace(
            "- Người đề xuất: @Lolavine777 (TTS A)",
            f"- Người đề xuất:{empty_val}",
        ),
        encoding="utf-8",
    )
    errors = validate_adr(f_prop)
    assert any("Người đề xuất" in e for e in errors)

    f_comb = tmp_path / "adr-empty-combined.md"
    content = VALID_ADR.replace(
        "- Người đề xuất: @Lolavine777 (TTS A)\n- Reviewer: @nairyuuu (TTS B)",
        f"- Người đề xuất / reviewer:{empty_val}",
    )
    f_comb.write_text(content, encoding="utf-8")
    errors = validate_adr(f_comb)
    assert any("Người đề xuất / reviewer" in e or "Reviewer" in e for e in errors)


def test_worklog_missing_table_separator(tmp_path):
    f = tmp_path / "worklog-no-sep.md"
    content = VALID_WORKLOG.replace("| --- | --- | --- |\n", "")
    f.write_text(content, encoding="utf-8")
    errors = validate_worklog(f)
    assert any("table" in e for e in errors)


def test_worklog_table_in_wrong_section(tmp_path):
    f = tmp_path / "worklog-wrong-section.md"
    table = (
        "| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |\n"
        "| --- | --- | --- |\n"
        "| Schema validation | scripts/check_repository.py | Passed |\n"
    )
    content = VALID_WORKLOG.replace(table, "\n")
    content = content.replace(
        "## Điều học được / quyết định\n",
        f"## Điều học được / quyết định\n\n{table}",
    )
    f.write_text(content, encoding="utf-8")
    errors = validate_worklog(f)
    assert any("table" in e for e in errors)


def test_adr_missing_options_table_separator(tmp_path):
    f = tmp_path / "adr-no-sep.md"
    content = VALID_ADR.replace("| --- | --- | --- | --- |\n", "")
    f.write_text(content, encoding="utf-8")
    errors = validate_adr(f)
    assert any("table" in e for e in errors)


def test_adr_options_table_in_wrong_section(tmp_path):
    f = tmp_path / "adr-wrong-section.md"
    table = (
        "| Phương án | Lợi ích | Chi phí / hạn chế | Bằng chứng |\n"
        "| --- | --- | --- | --- |\n"
        "| 1. Kiểm tra tự động | Phát hiện sớm lỗi định dạng | "
        "Cần viết thêm kiểm thử | Thực nghiệm CI |\n"
    )
    content = VALID_ADR.replace(table, "\n")
    content = content.replace(
        "## Quyết định và hệ quả\n",
        f"## Quyết định và hệ quả\n\n{table}",
    )
    f.write_text(content, encoding="utf-8")
    errors = validate_adr(f)
    assert any("table" in e for e in errors)


def test_worklog_table_separator_split_across_lines_rejected(tmp_path):
    f = tmp_path / "worklog-split-sep.md"
    split_sep = "| --- |\n  --- |\n  --- |\n"
    content = VALID_WORKLOG.replace("| --- | --- | --- |\n", split_sep)
    f.write_text(content, encoding="utf-8")
    errors = validate_worklog(f)
    assert any("table" in e for e in errors)


def test_adr_table_separator_split_across_lines_rejected(tmp_path):
    f = tmp_path / "adr-split-sep.md"
    split_sep = "| --- |\n  --- |\n  --- |\n  --- |\n"
    content = VALID_ADR.replace("| --- | --- | --- | --- |\n", split_sep)
    f.write_text(content, encoding="utf-8")
    errors = validate_adr(f)
    assert any("table" in e for e in errors)


def test_worklog_extra_columns_allowed(tmp_path):
    f = tmp_path / "worklog-extra-cols.md"
    orig_table = (
        "| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |\n"
        "| --- | --- | --- |\n"
        "| Schema validation | scripts/check_repository.py | Passed |\n"
    )
    extra_table = (
        "| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế | Ghi chú |\n"
        "| --- | --- | --- | --- |\n"
        "| Schema validation | scripts/check_repository.py | Passed | Tự động |\n"
    )
    content = VALID_WORKLOG.replace(orig_table, extra_table)
    f.write_text(content, encoding="utf-8")
    assert validate_worklog(f) == []


def test_adr_extra_columns_allowed(tmp_path):
    f = tmp_path / "adr-extra-cols.md"
    orig_table = (
        "| Phương án | Lợi ích | Chi phí / hạn chế | Bằng chứng |\n"
        "| --- | --- | --- | --- |\n"
        "| 1. Kiểm tra tự động | Phát hiện sớm lỗi định dạng | "
        "Cần viết thêm kiểm thử | Thực nghiệm CI |\n"
    )
    extra_table = (
        "| Phương án | Lợi ích | Chi phí / hạn chế | Bằng chứng | Ghi chú |\n"
        "| --- | --- | --- | --- | --- |\n"
        "| 1. Kiểm tra tự động | Phát hiện sớm lỗi định dạng | "
        "Cần viết thêm kiểm thử | Thực nghiệm CI | Đạt chuẩn |\n"
    )
    content = VALID_ADR.replace(orig_table, extra_table)
    f.write_text(content, encoding="utf-8")
    assert validate_adr(f) == []


def test_dataset_b_hashes_when_present():
    candidate_dirs = [Path("data/raw/dataset_b"), Path("data/raw/ad_sampledata")]
    present_dirs = [d for d in candidate_dirs if d.is_dir()]
    if not present_dirs:
        pytest.skip(
            "Neither data/raw/dataset_b nor data/raw/ad_sampledata is present in local environment"
        )
    inventory = Path("docs/research/data-inventory.md").read_text(encoding="utf-8")
    matches = re.findall(
        r"\|\s*`(20240305\d+_\w+\.json)`\s*\|.*?\|\s*`([0-9a-f]{64})`\s*\|", inventory
    )
    assert len(matches) == 31
    for target_dir in present_dirs:
        for fname, doc_hash in matches:
            fpath = target_dir / fname
            assert fpath.exists(), f"Missing file {fname} in {target_dir}"
            actual = hashlib.sha256(fpath.read_bytes()).hexdigest()
            assert actual == doc_hash, (
                f"Hash mismatch for {fname} in {target_dir}: expected {doc_hash}, got {actual}"
            )

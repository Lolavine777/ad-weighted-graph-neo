"""Review published rubric summaries offline; no search, repricing, or service calls."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = "08755cfdf939dc7f0beae1daa4b2a23e95225a1b"
PLAN_RECORDED_AT = "2026-10-24T08:36:00.326Z"
PINS = {
    "reports/neo/cost-sensitivity-results.json": (
        "5f4cd9c012ad53c6a44b8c752cca017e4d288d63ea06b99603059a3ecb019b87"
    ),
    "reports/neo/minimum-probe.json": (
        "4278d71a1ce1584dfbf74e8d8f3d68df94064fcc95ac337b65a6af1695f0a339"
    ),
    "reports/neo/decision-sample.json": (
        "5ee4634c67ba61ac86f86615d4e581450985cf9470e29f1810930cb8a1d54df4"
    ),
    "src/engine/ranking/effort_profiles.py": (
        "63b8486429c6005691f1dd5d85295179a4103c869a8383eee6de880a14dccb91"
    ),
    "reports/neo/cost-sensitivity.md": (
        "6bc99e0dc4eba6ad9846537cd256e9a61086a1d7ec5a0791ab2b230cf33f66b9"
    ),
}
NIST = "https://nvlpubs.nist.gov/nistpubs/legacy/sp/nistspecialpublication800-30r1.pdf"


def descriptions(program):
    # These are disclosed descriptions, NOT complete work-unit identities.
    return Counter((w["technique"], w["method"], w["target_id"]) for w in program["work_units"])


def families(program):
    return dict(sorted(Counter(w["technique"] for w in program["work_units"]).items()))


def analyze():
    sources = {}
    for name, expected in PINS.items():
        raw = (ROOT / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError(f"Source pin mismatch: {name}")
        sources[name] = raw.decode("utf-8")
    module = ast.parse(sources["src/engine/ranking/effort_profiles.py"])
    operations = next(
        ast.literal_eval(n.value)
        for n in module.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "OPERATIONS" for t in n.targets)
    )
    prices = {name: t1 + t2 - 2 for name, (_, t1, t2, _) in operations.items()}
    decision = json.loads(sources["reports/neo/decision-sample.json"])
    minimum = json.loads(sources["reports/neo/minimum-probe.json"])
    sensitivity = json.loads(sources["reports/neo/cost-sensitivity-results.json"])
    for profile in [minimum["effort_profile"], sensitivity["baseline_profile"]]:
        assert {k: v["cost"] for k, v in profile["classes"].items()} == prices
    checked = 0
    for cell in decision["cells"]:
        for program in cell["programs"]:
            for work in program["work_units"]:
                method, t1, t2, _ = operations[work["technique"]]
                assert (work["method"], work["t1"], work["t2"]) == (method, t1, t2)
                assert work["computed_cost"] == prices[work["technique"]]
            assert sum(w["computed_cost"] for w in program["work_units"]) == program["C"]
            checked += 1

    cards = []

    def add(identifier, label, a, b, category, source, **extra):
        ca = sum(prices[k] * n for k, n in a.items())
        cb = sum(prices[k] * n for k, n in b.items())
        if category == "same_profile_tie":
            assert a == b and ca == cb
        elif category in {"disclosed_extension", "zero_anchor"}:
            assert ca <= cb
        else:
            assert category == "cross_family_unresolved"
        cards.append(
            {
                "id": identifier,
                "label": label,
                "category": category,
                "source": source,
                "A_family_counts": a,
                "B_family_counts": b,
                "A_C": ca,
                "B_C": cb,
                **extra,
            }
        )

    # Feature-based diagnostic selection; published C is not used for pair selection.
    for index, cell in enumerate(decision["cells"]):
        if cell["source_kind"] != "User":
            continue
        programs = sorted(cell["programs"], key=lambda p: p["program_id"])
        inclusion = [
            (a, b)
            for a in programs
            for b in programs
            if a["route_id"] == b["route_id"] and descriptions(a) < descriptions(b)
        ]
        a, b = inclusion[0] if inclusion else programs[:2]
        category = "disclosed_extension" if inclusion else "same_profile_tie"
        add(
            f"S{index + 1:02d}",
            f"SEAMLESS User {cell['source_index'] + 1} / {cell['target']}",
            families(a),
            families(b),
            category,
            f"reports/neo/decision-sample.json#/cells/{index}/programs",
            program_ids=[a["program_id"], b["program_id"]],
            same_route=a["route_id"] == b["route_id"],
            published_C=[a["C"], b["C"]],
        )
        assert [cards[-1]["A_C"], cards[-1]["B_C"]] == [a["C"], b["C"]]

    # Only disclosed aggregate family profiles are available for this tradeoff.
    text = sources["reports/neo/cost-sensitivity.md"]
    rows = [
        line
        for line in text.splitlines()
        if line.startswith(("| Hai work units", "| Một session credential"))
    ]
    assert len(rows) == 2
    published = [int(row.split("|")[2].strip()) for row in rows]
    add(
        "W01",
        "WRAITH / published DA family-profile tradeoff",
        {"use_session_identity": 2},
        {"use_session_identity": 1, "grant_new_object_right": 1, "genericall_add_member": 1},
        "cross_family_unresolved",
        "reports/neo/cost-sensitivity.md#ví-dụ-đảo-thứ-hạng-nhưng-không-thay-minimum",
        evidence_level="Published family profiles, not full programs or empirical effort",
    )
    assert [cards[-1]["A_C"], cards[-1]["B_C"]] == published
    add(
        "T01",
        "Synthetic / two_routes",
        {"grant_new_object_right": 1, "genericall_add_member": 1},
        {"scenario_reset_password": 1, "acquire_reset_identity": 1},
        "cross_family_unresolved",
        "reports/neo/minimum-probe.json#/references/two_routes",
        evidence_level="Existing fixture oracle reuses rubric; not independent cost validation",
    )
    reference = minimum["references"]["two_routes"]["certain"]
    assert cards[-1]["A_C"] == reference["hop_only"]["mapped_C"]
    assert cards[-1]["B_C"] == reference["C"]
    add(
        "T02",
        "Synthetic / existing entitlement",
        {},
        {"grant_new_object_right": 1, "genericall_add_member": 1},
        "zero_anchor",
        "reports/neo/minimum-probe.json#/references/free_membership",
        evidence_level="No additional work in the declared fixture; not zero real-world time",
    )
    reference = minimum["references"]["free_membership"]["certain"]
    assert [cards[-1]["A_C"], cards[-1]["B_C"]] == [
        reference["C"],
        reference["hop_only"]["mapped_C"],
    ]
    counts = dict(sorted(Counter(c["category"] for c in cards).items()))
    assert len(cards) == 9 and checked == 30
    return {
        "version": "neo-rubric-review/1",
        "date": "2026-10-24",
        "source_revision": BASE,
        "review_plan_recorded_at_utc": PLAN_RECORDED_AT,
        "source_sha256": PINS,
        "reviewer": "AI-assisted retrospective review with prior C exposure",
        "selection": (
            "Six existing User cells; same-route "
            "disclosed inclusion preferred, else "
            "first two canonical program IDs; one "
            "published WRAITH tradeoff and two "
            "synthetic controls."
        ),
        "criteria": [
            "Check disclosed arithmetic against unchanged prices.",
            "Check index monotonicity for disclosed extensions and the zero anchor.",
            "Retain ties for identical priced family vectors.",
            "Leave cross-family real-effort preferences unresolved without independent anchors.",
        ],
        "arithmetic_checked_program_summaries": checked,
        "cases": cards,
        "category_counts": counts,
        "reasoning_patterns": 4,
        "decision": "retain_numeric_prices; clarify interpretation and validation scope",
        "limits": [
            (
                "Not blind, independent human review, a "
                "representative sample, or empirical "
                "calibration."
            ),
            (
                "Six SEAMLESS cases repeat two patterns; "
                "do not count them as six independent "
                "validations."
            ),
            (
                "Published work descriptions omit "
                "actor/context/work-unit IDs: no new "
                "identity-dedup, state-equivalence or "
                "replay proof."
            ),
            "Synthetic oracle checks reuse current prices and cannot validate those prices.",
            "WRAITH tradeoff has aggregate profiles only; no new program or feasibility result.",
            "GoodHound full local ledgers were not available in Git and were not reconstructed.",
            (
                "No search, new paths, candidate-set "
                "changes, repricing, production changes "
                "or minimum-C claim."
            ),
        ],
        "method_reference": {
            "url": NIST,
            "section": "2.3.2, printed page 14",
            "use": (
                "General guidance on explicit "
                "semi-quantitative scales; not a source "
                "for AD action prices or an approval of "
                "this additive formula."
            ),
        },
    }


def render(data):
    lines = [
        "# Rà soát rubric C: giữ giá, làm rõ ý nghĩa",
        "",
        "Ngày 24/10/2026. Review tĩnh trên các summary đã công bố, từ main `08755cfd`.",
        "**Chưa có bằng chứng đủ để thay giá production.** Đã đối chiếu 9 cặp và kiểm",
        "phép cộng của 30 program summaries. Đây không phải 9 xác nhận thực nghiệm độc lập.",
        "",
        "## Phương pháp",
        "",
        "Chốt tiêu chí trước khi tính các phân loại mới: cùng profile thì giữ tie; thêm công",
        "việc không âm không được làm giảm C; quyền có sẵn không tạo thêm công việc;",
        "khác họ công việc thì chưa suy ra thứ tự công sức thực tế nếu thiếu mốc độc lập.",
        "Chọn cặp theo đặc trưng ledger/route và program ID, không chọn theo C.",
        (
            "Người phân tích là AI đã thấy các điểm "
            "công bố: **không phải blind rating hoặc "
            "expert panel**."
        ),
        "",
        "## Chín cặp đã kiểm",
        "",
        "| Ca | C A / B | Kết quả |",
        "| --- | --- | --- |",
    ]
    labels = {
        "same_profile_tie": "Cùng vector họ công việc: tie nhất quán; công sức thật chưa xác nhận",
        "disclosed_extension": "C tăng theo phần việc công bố thêm; kiểm tính nhất quán",
        "zero_anchor": "Không thêm công việc theo fixture: C=0 hợp quy ước",
        "cross_family_unresolved": "Khác họ công việc: thiếu mốc để xác nhận thứ tự công sức",
    }
    for case in data["cases"]:
        conclusion = labels[case["category"]]
        lines.append(
            f"| {case['id']} — {case['label']} | {case['A_C']} / {case['B_C']} | {conclusion} |"
        )
    lines += [
        "",
        "Ba cặp SEAMLESS tới EA là biến thể trên cùng route, không phải ba lựa chọn",
        "cấu trúc khác nhau. Ba cặp tới DA có các route khác nhau nhưng cùng profile công việc.",
        "Chín cặp chỉ bao phủ bốn mẫu lập luận. Bốn kiểm tra anchor/extension nhất quán,",
        "ba tie đúng theo profile, hai tradeoff khác họ vẫn chưa có đáp án độc lập.",
        "",
        "## Kết luận về rubric",
        "",
        "- Chưa phát hiện mâu thuẫn số học trong summary hoặc lý do có căn cứ để đổi giá cụ thể.",
        (
            "- Bằng chứng trong panel này chủ yếu là"
            " diễn giải công việc và phân biệt biến "
            "thể thêm việc."
        ),
        "- Chưa kiểm chứng được lợi ích chọn giữa các họ phương án khác nhau. Không dùng",
        "  đáp án synthetic tính từ cùng bảng giá để tự xác nhận giá đó đúng.",
        "- Tie giữa các profile giống nhau là giới hạn thông tin của rubric; không tự thêm",
        "  điểm chỉ để ép thành thứ hạng duy nhất.",
        "",
        "## Đề xuất chỉnh định nghĩa, chưa đổi giá",
        "",
        "Gọi C là **chỉ số công sức quy ước theo scenario**, giữ tổng cộng như một giả định",
        "thiết kế. C=4 không có nghĩa gấp đôi thời gian/công sức thực tế của C=2.",
        "C=0 không có nghĩa không có hành động: có thể là hành động ở mức sàn ordinal.",
        "Khi trình bày nên giữ cả thành phần công việc, số thao tác active và route; không",
        "diễn giải Top-3 program IDs thành ba phương án độc lập nếu chúng cùng route.",
        "Định nghĩa T1 chỉ về mức tùy biến công cụ, T2 về thao tác/xác minh trong scenario;",
        "không ngầm đưa xác suất thành công, tác động nghiệp vụ hoặc thời gian vào cùng C.",
        "Đây là đề xuất diễn giải; lượt này không sửa scorer, UI, bảng giá hoặc semantic gates.",
        "",
        "[NIST SP 800-30r1, mục 2.3.2, trang in 14](" + NIST + ") phân biệt thang định",
        "lượng với thang bán định lượng và yêu cầu giải thích ý nghĩa các mức/giả định.",
        "Áp dụng ở đây là lập luận phương pháp; NIST không cung cấp giá AD, không phê",
        "duyệt công thức cộng này và không xác nhận các thứ hạng của neo.",
        "",
        "## Giới hạn và tái lập",
        "",
        "Các summary thiếu actor/context/work-unit IDs đầy đủ. So phần việc công bố không",
        (
            "chứng minh state tương đương, công việc "
            "thực sự dư thừa, hoặc phép khử trùng "
            "runtime đúng."
        ),
        "Không chạy engine hay replay mới. Kết quả dùng các summary lịch sử, không phải",
        "một lượt discovery mới của main. Không suy ra minimum-C hoặc ưu thế BloodHound.",
        "Các ledger GoodHound còn ở evidence local nên không được suy đoán để đủ mẫu.",
        "",
        "Từ repo root, chỉ cần Python với thư viện chuẩn và output directory mới:",
        "",
        "```sh",
        (
            "python -m "
            "scripts.research.neo_rubric_review "
            "--output-dir "
            "reports/generated/rubric-review-repeat"
        ),
        "```",
        "",
        "Runner kiểm SHA256 năm input, đối chiếu giá hiện hành với hai artifact lịch sử,",
        "kiểm 30 ledger summaries rồi dựng lại JSON và Markdown. File kết quả gốc:",
        (
            "[rubric-review-results.json](rubric-revi"
            "ew-results.json). Giữ nguyên mọi "
            "evidence lịch sử."
        ),
    ]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        parser.error("Use a new output directory to preserve earlier results")
    data = analyze()
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "rubric-review-results.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.output_dir / "rubric-review.md").write_text(render(data), encoding="utf-8")
    print(json.dumps({"cases": len(data["cases"]), "categories": data["category_counts"]}))


if __name__ == "__main__":
    main()

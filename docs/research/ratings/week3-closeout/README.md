# Release tham số Week 3

Bộ tham số đã được lựa chọn và kiểm chứng cho kịch bản SEAMLESS: hai điểm xuất phát, ba ứng viên và 21 bản ghi. [Hồ sơ lựa chọn](parameter-selection.md) giải thích giá trị và lý do; [phạm vi đánh giá](../../week3-rating-requirement-disposition.md) tiếp nhận cơ sở human-reviewed AI-assisted cho kết quả tuần này.

## Kết quả

| Đường | P chính xác | P theo phần trăm | C | I |
| --- | --- | --- | ---: | --- |
| Điểm xuất phát A, qua Lidia | [9/40, 8379/10000] | [22,5%; 83,79%] | 2 | High |
| Điểm xuất phát A, qua Josefa rồi Ollie | [81/800, 7800849/10000000] | [10,125%; 78,00849%] | 3 | High |
| Điểm xuất phát B, qua Ollie | [9/40, 8379/10000] | [22,5%; 83,79%] | 2 | High |

Fraction oracle và canonical engine khớp C/P/I, frontier, quan hệ và Min-Effort. Hai đường A vẫn incomparable theo Pareto bảo thủ; Min-Effort trong supplied set chọn Lidia. Source B là điểm xuất phát riêng, khác người chấm B.

21 probes gồm 11 likelihood (nhân một khoảng từng bước với 9/10), 9 effort (tăng một điểm rubric), 1 impact (High → Medium). Có 24 query outcomes: 0 đổi frontier, 0 đổi quan hệ, 0 đổi danh tính đường Min-Effort; 6 kết quả đổi chi phí nhỏ nhất. Không suy độ ổn định khi nhiều tham số cùng đổi hoặc tối ưu toàn đồ thị.

## Artifacts

- [Đầu vào](source-inputs/README.md): cùng điểm, lý giải và policy nguồn; metadata hành chính chuẩn hóa, có digests.
- [21 quyết định](parameter-decisions-final.json): bindings, giá trị, lý do và dispositions.
- [Actual release](reviewed-release.json): self-contained inputs, replayable decisions và hai query projections.
- [Validation summary](validation-summary.json): expected/actual baseline và mọi probe; digests của full CLI outputs. Đây là bản rút gọn, không phải full report.
- [Báo cáo Week 3](../../../reports/week3-report.md), [việc tiếp theo](../../../reports/week3-remaining-work.md).

Canonical release digest: `sha256:20f67e8604f6399b5b360e412bb30bf898f4d788f13b69c08c78ef2df73d3358`. Metadata nguồn thay đổi làm digest khác bản trước; tất cả baseline/probes đã đối chiếu và giữ nguyên kết quả số. JSON viết gọn có cùng object/canonical digest với CLI output.

Source class và exposure giữ đúng; IoU mô tả hai bộ giá trị, không chứng minh independent reliability. Các cận số là nhận định theo kịch bản, chưa hiệu chuẩn. Marker human_acceptance/publication mặc định của exporter không thay trạng thái nghiệm thu sản phẩm. Phần tích hợp, đối chứng Legacy và tái lập toàn luồng nằm ngoài validation của ba ứng viên này.

## Tái lập

Chạy từ root repo với dependencies hiện hành. Full outputs sinh ở thư mục ignored:

```bash
python scripts/research/reviewed_parameter_release.py export \
  --sheet1 docs/research/ratings/week3-closeout/source-inputs/rater-A.json \
  --sheet2 docs/research/ratings/week3-closeout/source-inputs/rater-B.json \
  --policy docs/research/ratings/week3-closeout/source-inputs/execution-policy.json \
  --confirmation docs/research/ratings/week3-closeout/source-inputs/shared-review-confirmation.json \
  --ai-draft docs/research/ratings/week3-2026-10-02/rater-B-ai-draft.json \
  --template tests/fixtures/ranking/seamless_parameter_bundle.json \
  --decisions docs/research/ratings/week3-closeout/parameter-decisions-final.json \
  --output reports/generated/week3-reviewed-release.json
python scripts/research/reviewed_parameter_release.py validate \
  --release reports/generated/week3-reviewed-release.json \
  --output reports/generated/week3-reviewed-validation.json
```

Có thể validate trực tiếp release đã commit. B consume `query_projections.source_a` / `source_b` sau verify_release; không dùng research verifier hoặc fixture rating defaults. Kiểm chứng local dùng Python 3.12.14 trên text snapshot; full-suite/clean-checkout verification được ghi riêng theo revision chạy.

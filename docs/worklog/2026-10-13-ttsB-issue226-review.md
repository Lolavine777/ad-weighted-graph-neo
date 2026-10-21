# Worklog - 2026-10-13 - ttsB

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: #226 / [PR #273](https://github.com/nairyuuu/ad-weighted-graph/pull/273) / M3 follow-up
- Thời gian thực tế ước lượng: Không đo thao tác liên tục; clean full suite đo 419.08 s.

Review của A trên `fc6221ebeb8c212184c883a257ba6f8abc639be8` yêu cầu sửa P2 và góp ý P3.
Executable source sau sửa: `07a7cc3fee960711d394f0b88ba04f00e96298e6`.

## Kết quả và bằng chứng

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| P2: initial actor/source trong zero-work identity | [Review](https://github.com/nairyuuu/ad-weighted-graph/pull/273#discussion_r4249739356), `tests/test_top_k_search.py::test_zero_work_identity_retains_canonical_source_under_same_state` | Hai User actors cùng target/state/context/scenario có IDs khác; alias cùng actor giữ ID |
| P3: acceptance lineage | [Review](https://github.com/nairyuuu/ad-weighted-graph/pull/273#discussion_r4249739362), CLI explicit/automatic regression và schema 0.4 | Giữ dependency/pending lineage của base mode, thêm #226 |
| Top-K suite | `python -m pytest tests/test_top_k_search.py -q` | 35 PASS, 5.74 s |
| Clean full suite | `python -m pytest -q`, checkout `8034f0b3cd9776f49a8325835fd46bd1e6a01b02` | 2642 PASS / 46 SKIP / 48 subtests PASS, 419.08 s |
| Public CLI reproduction | [Evidence](../../reports/research/issue226-top-k-synthetic-evidence.json) | Bốn ca × ba processes khớp semantics/pins trên clean source |
| Existing acceptance | `python -m scripts.research.week4_acceptance_runner --check-determinism --output reports/research/week4-maintainer-acceptance-manifest-v2.json` | 36 PASS / 1 manual NOT EXECUTED / 1 raw-prerequisite BLOCKED RUN / 0 FAIL |

Reviewed-head key được đối chiếu trên cùng zero-action paths: tái lập actor collision;
key sau sửa phân biệt actors và giữ aliases bằng nhau. `PathResult.initial_actor` giữ
canonical source cho cả zero-action và transition programs; best/all-best path copies
giữ source. Không đổi singleton terminal `nodes` của initial-goal path.

Legacy candidate transport giữ shape; source đã có trong `materialized.initial_actor`
và Top-K canonical key. CLI schema 0.4 chấp nhận lineage explicit/automatic tương ứng.
Ruff check/format, yamllint, repository/contract checks và whitespace PASS.

Independent frozen semantic digest vẫn là
`sha256:3b4eb2e857f1f04700ea3a20df9846d75bb9c32fccd4f83979f212d7fe61a34d`.
Ba historical files freeze bởi #264 giữ byte-for-byte; chỉ current-source successor
pins được refresh. Public Top-K IDs/digests được tái tạo theo corrected identity.
E/K=2, T/ties, K=8, cap=1 giữ C `[2,5]`, `[2,2]`, `[2,5,5]`, `[5]` và guarantees.
CLI median 0.1300 / 0.1163 / 0.1221 / 0.1183 s là synthetic ba-program measurements.

## Điều học được / quyết định

Ordered requests không mang actor khi không có action; query source phải được giữ
riêng ngay tại generation. Initial source scope vẫn cần khi request đầu dùng một
identity khác đã usable. Key sort giữ history trước terminal state/source, nên
existing within-query tie order không đổi. Identity policy đang chờ #226 acceptance;
không dùng old keys để đối chiếu corrected results hoặc gộp snapshots khác nhau.

Giữ base acceptance lineage là audit provenance, không mở lại gates đã đóng hoặc
tuyên bố nghiệm thu private data. Không thêm ranking sources/destinations vào #226.

## Trở ngại và việc kế tiếp

Clean full suite PASS; final handoff chỉ bổ sung worklog, không đổi executable bytes.
46 skips là private/raw prerequisites và Windows-only test, không gọi là PASS.
Không có authorized pinned SEAMLESS raw hoặc Docker cho private probe/local Compose.
Human-independent reproduction và re-review còn pending; #226 giữ OPEN, PR không tự merge.

Vòng full suite đầu có 4 FAIL / 2638 PASS / 46 SKIP / 48 subtests PASS (390.17 s)
do refreshed reports còn là tracked changes: case `W4-CLI-PACKAGE` có
`clean_tracked_source=False`, kéo theo acceptance/mutation/demo checks. Numeric/state
outputs và pins khớp. Commit evidence `8034f0b3cd9776f49a8325835fd46bd1e6a01b02`
trước khi chạy lại clean suite; không sửa independent expectations.

Remote [CI](https://github.com/nairyuuu/ad-weighted-graph/actions/runs/38287646257)
và [Branch policy](https://github.com/nairyuuu/ad-weighted-graph/actions/runs/38287646391)
trên `8034f0b` kết thúc failure trước steps (mọi job `steps=[]`, 2–4 s).
Job logs trả 404 BlobNotFound; connector không đọc được check annotations, nên chưa
xác nhận nguyên nhân runner/workflow prerequisite. Không gọi đây là remote test PASS.

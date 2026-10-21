# Tái lập độc lập SEAMLESS ↔ BloodHound Legacy 4.0.3 Reconciliation (#196)

Ngày thực hiện: 2026-10-06; TTS B: @nairyuuu; reviewer: @Lolavine777 / @nairyuuu.
Base revision: `8535d44771ec9ec1960b4e883103f83654cc1d4f` (kế thừa merged PR #198 từ TTS A).
Refs [#196](https://github.com/nairyuuu/ad-weighted-graph/issues/196), [#195](https://github.com/nairyuuu/ad-weighted-graph/issues/195), [#194](https://github.com/nairyuuu/ad-weighted-graph/pull/194), [#189](https://github.com/nairyuuu/ad-weighted-graph/pull/189), [#184](https://github.com/nairyuuu/ad-weighted-graph/pull/184), [#183](https://github.com/nairyuuu/ad-weighted-graph/pull/183), [#47](https://github.com/nairyuuu/ad-weighted-graph/issues/47), [#48](https://github.com/nairyuuu/ad-weighted-graph/issues/48), [#158](https://github.com/nairyuuu/ad-weighted-graph/issues/158).
Sanitized machine artifact: [`reports/research/issue-196-final-cross-reproduction.json`](../../reports/research/issue-196-final-cross-reproduction.json).

---

## 1. Mục tiêu và phạm vi nghiệm thu

Issue #196 yêu cầu thực hiện final clean-checkout cross-reproduction cho kết quả đối soát giữa SEAMLESS và BloodHound Legacy 4.0.3:
- Không tạo thêm tính năng mới, không sửa production code, không đổi weighting/ranking.
- Không ép comparator trả `MATCH` bằng cách sửa `export_complete` hay tạo machine scope giả.
- Chứng minh toàn bộ kết quả đối soát tái lập được một cách tất định (deterministic) từ checkout sạch tại revision `develop` đã được pin rõ ràng (`8535d44771ec9ec1960b4e883103f83654cc1d4f`), bằng đúng inputs/configs/external prerequisites đã accepted.
- Bắt buộc áp dụng **exact directed-set proof** (chứng minh tập hợp có hướng khớp chính xác) cho từng slice, cấm hoàn toàn việc chỉ dựa vào số lượng (counts).
- Nghiêm cấm mọi hình thức bypass việc parse raw: loại bỏ hoàn toàn cờ `--skip-parser-run`, từ chối tái sử dụng canonical graph có sẵn trong thư mục làm việc.
- Thực hiện cross-check hai lần chạy sạch độc lập (Run 1 và Run 2) để chứng minh tính nhất quán tuyệt đối của pipeline.
- Hai lần chạy địa phương này được gọi chính xác là **independent second clean local reproduction**, không tự claim là human A/B acceptance. Human reviewer xác nhận độc lập sau PR.

---

## 2. Phân định nguồn dữ liệu: external_input, generated_in_this_run, historical_reference_only

| Thành phần | Đường dẫn / Định danh | SHA-256 Digest | Phân loại | Ghi chú |
| --- | --- | --- | --- | --- |
| Raw SEAMLESS Manifest | `data/samples/manifests/seamless-raw-v1.json` | `a18d7a2a8b4cf283069da46d00368ffbe6a1eab6ad92a5c89b5a531809f5da9d` | `external_input` | Pinned snapshot `sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812`; 6 raw files verify không lỗi |
| Time Policy | `time-policy.json` | `3540afa5ff3f4affd9deddd75f3da43409c5885af4ab9b7b2d17a97aac3a2e7b` | `external_input` | Policy thời gian thu thập giả định theo #82/#184 |
| Legacy Nodes Export | `legacy-nodes.json` | `ed4a6aa7775a4bfb5994875243eaf11588cf03cf4301acc1f23ce62fae11839c` | `external_input` | 3.370 nodes đã accepted tại #183/#184 |
| Legacy Relationships Export | `legacy-relationships.json` | `4071dd8747a18aef4f30b074eeac163cbc7454cfe42a234367e81f8c488cdbf6` | `external_input` | 71.596 relationships đã accepted tại #183/#184 |
| Identity Mapping | `identity-mapping.json` | `202a91b951ff9292f57eeb535c65f02bb7063f5c28a6b27589acdc4ae45c570b` | `external_input` | One-to-one mapping 3.370 identities đã accepted tại #183/#184 |
| Legacy Comparison Baseline | `legacy-comparison.json` | `7e170793f88abf39fc927b503aa60a26d6c8480e1a838be76da2840019e4f97d` | `external_input` | Baseline comparator input đã accepted tại #183 |
| Importer Source Reference | `newingestion.js` | `01e969d83e87217318603887c7f5818a82bc044eead26502f0daf78ac55cad3b` | `external_input` | Source code parser BloodHound 4.0.3 dùng để audit ACE decoder |
| Comparison Contract #195 | `docs/research/seamless-legacy-403-comparison-contract.md` | - | `external_input` | Contract scope `seamless-legacy-403-m1-common-v1` |
| Native Legacy Container Run | `issue47-legacy-403-a` (Neo4j 4.1.13) | `1f08dd79d877776e2501ba77d8b4c5354e8953d603fcae31df6b7b2c61685bc0` | `historical_reference_only` | Đo đạc native import ngày 2026-10-04 của TTS A; phiên #196 không rerun native import |
| Canonical Graph Run 1 | `.cache/issue196-rerun1/project.json` | `7d7ebe1f4a9e326f6c71fc0e188fd55188ff415db5486371fbf2e10b30922ec9` | `generated_in_this_run` | Sinh từ raw bằng CLI chính thức tại base commit `8535d44` |
| Comparison Candidate Run 1 | `.cache/issue196-rerun1/project-comparison.json` | `0095c5df4bd18081dfdf1c55ba00ce9cb0d525c43235faea70cdca8f7c1c766e` | `generated_in_this_run` | Chuẩn bị metadata cho comparator gate |
| Canonical Graph Run 2 | `.cache/issue196-rerun2/project.json` | `7d7ebe1f4a9e326f6c71fc0e188fd55188ff415db5486371fbf2e10b30922ec9` | `generated_in_this_run` | Khớp 100% từng byte với Run 1 |
| Comparison Candidate Run 2 | `.cache/issue196-rerun2/project-comparison.json` | `0095c5df4bd18081dfdf1c55ba00ce9cb0d525c43235faea70cdca8f7c1c766e` | `generated_in_this_run` | Khớp 100% từng byte với Run 1 |
| Reproduction Artifact | `reports/research/issue-196-final-cross-reproduction.json` | Xem file | `generated_in_this_run` | Báo cáo máy sanitized, không chứa authentic identities |

---

## 3. Lệnh tái lập chính thức

### 3.1. Chạy toàn diện kiểm tra exact proofs qua script tái lập

```bash
python scripts/research/reproduce_legacy_reconciliation.py \
  --raw-root data/raw/SEAMLESS \
  --manifest data/samples/manifests/seamless-raw-v1.json \
  --prerequisites-dir .cache/issue196-prerequisites \
  --work-dir .cache/issue196-rerun1 \
  --report-output reports/research/issue-196-final-cross-reproduction.json
```

Quy trình tự động thực hiện:
1. Verify digests của snapshot raw và toàn bộ external prerequisites.
2. Kiểm tra workdir sạch: nếu phát hiện `project.json` có sẵn, từ chối thực thi ngay lập tức.
3. Chạy `src.parser.cli` để sinh canonical graph mới từ raw SEAMLESS.
4. Validate đồ thị qua contract validator 1.3.0.
5. Chuẩn bị `project-comparison.json` và chạy comparator gate (xác nhận verdict `NOT_MEASURABLE`, exit code 2).
6. Tính toán và assert nghiêm ngặt **exact directed-set equality** cho từng slice theo Contract #195.

---

## 4. Bảng đối soát chi tiết 8 quan hệ M1 theo Contract #195

Toàn bộ các giá trị dưới đây được tính độc lập trực tiếp từ dữ liệu thô và output đồ thị vừa tái lập, sau đó so sánh với bằng chứng đã accepted:

| Quan hệ | Project | Legacy | Matching | Project-only | Legacy-only | Disposition theo Contract #195 | Exact Directed-Set Proof & Decomposition |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `MemberOf` | 15.917 | 15.917 | 15.917 | 0 | 0 | `equivalent_in_accepted_scope` | $C_{\text{MO}} = B_{\text{MO}} = (\text{raw}_{\text{Members}} \cup \text{raw}_{\text{PrimaryGroupSid}})$. 13.324 `Members[]` + 2.593 `PrimaryGroupSid`, overlap 0. Matching 100%, deltas 0/0. |
| `GenericAll` | 37.044 | 37.034 | 37.034 | 10 | 0 | Non-self: `equivalent_in_accepted_scope`<br>Self-ACE: `accepted_policy_difference` | Exact non-self project = Legacy = raw expected set: 37.034 triples. Exact project-only = raw self-ACEs: 10 triples. Legacy self set rỗng: 0. Raw duplicate occurrences: 164. |
| `WriteDacl` | 3.395 | 3.392 | 3.392 | 3 | 0 | Non-self: `equivalent_in_accepted_scope`<br>Self-ACE: `accepted_policy_difference` | Exact non-self project = Legacy = raw expected set: 3.392 triples. Exact project-only = raw self-ACEs: 3 triples. Legacy self set rỗng: 0. Raw duplicate occurrences: 2. |
| `AdminTo` | 9 | 5 | 5 | 4 | 0 | Direct: `equivalent_in_accepted_scope`<br>Derived: `accepted_policy_difference` | Exact direct project = Legacy = raw LocalAdmins: 5 triples. Legacy-only direct: 0. Exact project-only = reviewed derived-only: 4 triples (100% có derivation, 0% raw LocalAdmins). Coalesced direct & derived: 1 edge. |
| `CanPSRemote` | 2 | 2 | 2 | 0 | 0 | `equivalent_in_accepted_scope` | Exact project = Legacy = raw PSRemoteUsers: 2 direct structural matching edges. |
| `CanRDP` | 0 | 3 | 0 | 0 | 3 | `accepted_policy_difference` | Exact Legacy structural = raw RemoteDesktopUsers = project assessment triples (3 triples). Positive traversal edges = 0. 100% assessments có status `unknown` và reason `required UserRights evidence is incomplete`. |
| `ForceChangePassword` | 0 | 0 | 0 | 0 | 0 | `not_measurable` | Exact project = Legacy = raw = 0 stored observations. |
| `HasSession` | 0 | 0 | 0 | 0 | 0 | `not_measurable` | Exact project = Legacy = raw = 0 stored observations trong snapshot. |
| **Tổng M1** | **56.367** | **56.353** | **56.350** | **17** | **3** | - | Giao tập: 56.350 triples. 17 project-only = 10 self-GA + 3 self-WD + 4 nested-AdminTo. 3 legacy-only = 3 CanRDP. |

### Các quan hệ Legacy ngoài M1 (Outside-M1 Ledger)

Tổng cộng có **15.243** quan hệ Legacy nằm ngoài 8 quan hệ M1. Toàn bộ được phân loại `unsupported` / `out_of_scope` trong phép so M1:
- `AllExtendedRights`: 2.499
- `Contains`: 2.816
- `ExecuteDCOM`: 1
- `GenericWrite`: 3.166
- `GetChanges`: 3
- `GetChangesAll`: 2
- `GpLink`: 2
- `Owns`: 3.362
- `WriteOwner`: 3.392

---

## 5. Kết quả Cross-Reproduction độc lập (Run 1 vs Run 2)

Thực hiện hai lượt chạy tái lập độc lập từ trạng thái sạch:
- **Run 1**: work directory `.cache/issue196-rerun1/`
- **Run 2**: work directory `.cache/issue196-rerun2/`

| Chỉ số / Bằng chứng | Run 1 (First Clean Run) | Run 2 (Independent Second Clean Run) | Trạng thái khớp |
| --- | --- | --- | --- |
| Commit SHA Base | `8535d44771ec9ec1960b4e883103f83654cc1d4f` | `8535d44771ec9ec1960b4e883103f83654cc1d4f` | Trùng khớp |
| Snapshot ID | `sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812` | `sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812` | Trùng khớp |
| Raw Manifest SHA-256 | `a18d7a2a8b4cf283069da46d00368ffbe6a1eab6ad92a5c89b5a531809f5da9d` | `a18d7a2a8b4cf283069da46d00368ffbe6a1eab6ad92a5c89b5a531809f5da9d` | Trùng khớp |
| Canonical Graph SHA-256 | `7d7ebe1f4a9e326f6c71fc0e188fd55188ff415db5486371fbf2e10b30922ec9` | `7d7ebe1f4a9e326f6c71fc0e188fd55188ff415db5486371fbf2e10b30922ec9` | **Trùng khớp từng byte** |
| Candidate Comparison SHA-256 | `0095c5df4bd18081dfdf1c55ba00ce9cb0d525c43235faea70cdca8f7c1c766e` | `0095c5df4bd18081dfdf1c55ba00ce9cb0d525c43235faea70cdca8f7c1c766e` | **Trùng khớp từng byte** |
| Node Counts | 3.370 (Comp: 100, Dom: 1, GPO: 2, Grp: 551, OU: 223, Usr: 2493) | 3.370 (Comp: 100, Dom: 1, GPO: 2, Grp: 551, OU: 223, Usr: 2493) | Trùng khớp |
| Edge Counts | 56.367 (AdminTo: 9, CanPSRemote: 2, GA: 37044, MO: 15917, WD: 3395) | 56.367 (AdminTo: 9, CanPSRemote: 2, GA: 37044, MO: 15917, WD: 3395) | Trùng khớp |
| Unknown Assessments | 3 (CanRDP) | 3 (CanRDP) | Trùng khớp |
| Full Comparator Verdict | `NOT_MEASURABLE` (exit code 2) | `NOT_MEASURABLE` (exit code 2) | Trùng khớp |
| Exact Directed-Set Invariants | 100% PASS | 100% PASS | Trùng khớp |
| Outside-M1 Count | 15.243 | 15.243 | Trùng khớp |

---

## 6. Chính sách bảo mật và ẩn danh (Sanitization Statement)

Báo cáo [`reports/research/issue-196-final-cross-reproduction.json`](../../reports/research/issue-196-final-cross-reproduction.json) hoàn toàn sanitized:
- Không chứa Active Directory identities thật (names, SIDs, GUIDs, UPNs).
- Không chứa credentials, hash mật khẩu hoặc secrets thô.
- Toàn bộ các khác biệt (20 entries M1) được định danh thông qua SHA-256 triple digest cùng raw rule pointers (ví dụ `20210920185958_users.json#/users/290/Aces/5`).

---

## 7. Ranh giới nghiệm thu và việc tiếp theo

- Đã chứng minh pipeline tái lập 100% tất định trên revision `develop@8535d44` với pinned prerequisites.
- Sự bằng nhau của hai lần chạy sạch địa phương được ghi nhận là `independent second clean local reproduction`.
- Human reviewer (@Lolavine777 và @nairyuuu) cần cross-confirm sau khi PR được mở.
- Không tự claim Week 3 complete hay đóng #47/#48/#158 trước khi toàn bộ các gate còn lại được review.

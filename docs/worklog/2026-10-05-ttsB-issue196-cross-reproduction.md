# Worklog - 2026-10-05 - ttsB

- Múi giờ: Asia/Ho_Chi_Minh (UTC+07:00)
- Issue / PR / milestone: #196 / M2 / M3; PR #199; Refs #47 #48 #158 #183 #184 #189 #194 #195 #198
- Thời gian thực tế ước lượng: 5 giờ
- Nguồn: develop@8535d44771ec9ec1960b4e883103f83654cc1d4f (sau khi merge PR #198 từ TTS A).

## Kết quả và bằng chứng

Thực hiện đầy đủ quy trình clean-checkout cross-reproduction cho đối soát SEAMLESS ↔ BloodHound Legacy 4.0.3 theo comparison contract #195 và giải quyết trọn vẹn 3 blockers từ review của @Lolavine777 trên PR #199:
- Rebase branch `chore/196-final-cross-reproduction` lên latest `origin/develop@8535d44771ec9ec1960b4e883103f83654cc1d4f`.
- Toàn bộ external prerequisites (raw SEAMLESS, snapshot digest, manifest, Legacy full exports, identity mapping, time policy, importer source) được verify chính xác từng SHA-256 byte digest trước khi chạy.
- Thực hiện hai lượt chạy sạch độc lập (Run 1 và Run 2) từ raw SEAMLESS; toàn bộ outputs sinh ra trùng khớp nhau 100% từng byte:
  - Canonical graph digest: `7d7ebe1f4a9e326f6c71fc0e188fd55188ff415db5486371fbf2e10b30922ec9`
  - Candidate comparison digest: `0095c5df4bd18081dfdf1c55ba00ce9cb0d525c43235faea70cdca8f7c1c766e`
- Full machine comparator giữ nguyên exit code `2` / `NOT_MEASURABLE` do `export_complete is not verified true`.
- Tái lập độc lập toàn bộ các **exact directed-set proofs** theo Comparison Contract #195 (khớp chính xác tập hợp có hướng, không dùng kiểm tra số lượng count đơn thuần):
  - MemberOf: exact sets equal ($C_{\text{MO}} = B_{\text{MO}} = \text{raw}_{\text{MO}}$).
  - GenericAll / WriteDacl: exact non-self project = Legacy = raw expected set; exact project-only = raw self-ACEs; Legacy self set = 0; Legacy-only = 0.
  - AdminTo: exact direct project = Legacy = raw LocalAdmins (5 triples); legacy-only direct = 0; exact project-only = reviewed derived-only (4 triples).
  - CanPSRemote: exact project = Legacy = raw PSRemoteUsers (2 triples).
  - CanRDP: exact Legacy structural = raw RemoteDesktopUsers = project assessment triples (3 triples); positive edges = 0; status unknown & reason complete.
- Loại bỏ hoàn toàn cờ `--skip-parser-run`, cấm tái sử dụng canonical graph có sẵn trong work_dir.
- Bổ sung 12 unit tests trong `tests/test_reproduce_legacy_reconciliation.py`, bao gồm mutation tests (swapped/wrong triples cùng count bị fail-closed) và clean boundary tests.

| Công việc | Đầu ra / link / lệnh kiểm tra | Kết quả thực tế |
| --- | --- | --- |
| Verify external prerequisites | `scripts/research/reproduce_legacy_reconciliation.py` | 6 raw files verify không lỗi; 6 external prerequisites khớp 100% accepted digests |
| Sinh Canonical Graph Run 1 & 2 | `python -m src.parser.cli` qua venv, fail_fast, time policy #184 | 3.370 nodes, 56.367 edges, 3 unknown CanRDP assessments; SHA-256 `7d7ebe1f4a9e326f6c71fc0e188fd55188ff415db5486371fbf2e10b30922ec9` trùng tuyệt đối giữa hai runs |
| Validate Graph Contract | `validate_graph(graph, CONTRACT)` | Đồ thị tái lập đạt chuẩn Graph Contract 1.3.0 |
| Full Comparator Gate | `python scripts/reconcile_graph_baseline.py` | Exit 2 / `NOT_MEASURABLE` (`legacy-comparison: export_complete is not verified true`); xác nhận không phải lỗi input hay digest mismatch |
| Exact Directed-Set Proofs | Assert các tập hợp triple có hướng | 100% PASS cho MemberOf, GenericAll, WriteDacl, AdminTo, CanPSRemote, CanRDP, FCP, HasSession |
| Multiplicity | Đếm stored vs unique triples | Project: 56.367 stored / 56.367 unique triples (tỉ lệ 1.0), 56.373 provenance occurrences; Legacy: 71.596 stored / 71.596 unique triples (tỉ lệ 1.0) |
| Sanitized Artifact | [`reports/research/issue-196-final-cross-reproduction.json`](../../reports/research/issue-196-final-cross-reproduction.json) | Báo cáo máy đầy đủ các mục, 20 sanitized difference entries, không chứa authentic identities |
| Tài liệu chi tiết | [`docs/research/seamless-legacy-403-final-reproduction.md`](../research/seamless-legacy-403-final-reproduction.md) | Tài liệu tái lập chính thức cho #196 |
| Unit & Mutation Tests | `pytest tests/test_reproduce_legacy_reconciliation.py` | 12 passed trong 0.67s |
| Repository & Contract Checks | `python scripts/check_contract.py`<br>`python scripts/check_repository.py` | Đạt yêu cầu |
| Code Quality | `ruff check .`<br>`ruff format --check .`<br>`yamllint .` | Đạt yêu cầu |

## Điều học được / quyết định

1. **Tính tất định của pipeline**: Pipeline parser chính thức `src.parser.cli` và comparator khi chạy trên dữ liệu thô SEAMLESS với time policy đã pin sinh ra output giống nhau 100% từng byte giữa hai lần chạy độc lập (`7d7ebe1f4a9e326f6c71fc0e188fd55188ff415db5486371fbf2e10b30922ec9`).
2. **Khẳng định tính đúng đắn của Comparison Contract #195**: Các exact directed-set proofs chứng minh:
   - Full direct MemberOf union 15.917 triples đạt set equality hoàn hảo với raw Members và PrimaryGroupSid.
   - Non-self GenericAll (37.034) và WriteDacl (3.392) khớp chính xác từng triple giữa project, legacy và raw non-self ACE.
   - Project-only self-ACEs (10 GA, 3 WD) khớp chính xác với raw self-ACEs.
   - AdminTo direct matching 5 edges khớp chính xác với raw `LocalAdmins` support.
   - CanPSRemote 2 edges khớp chính xác với raw `PSRemoteUsers`.
   - CanRDP giữ 3 unknown assessments khớp chính xác với raw `RemoteDesktopUsers` và Legacy structural triples.
3. **Phân định rõ ranh giới nghiệm thu**: Hai lần chạy địa phương chỉ được gọi là **independent second clean local reproduction**. Human reviewer (@Lolavine777 và @nairyuuu) vẫn cần cross-confirm sau PR.
4. **Không vượt quá bằng chứng**: Không tuyên bố Week 3 complete hoặc full BloodHound feature parity.

## Trở ngại và việc kế tiếp

- Toàn bộ bằng chứng đã được ghi nhận đầy đủ, sanitized và có tests bảo vệ.
- Cập nhật PR #199 trên GitHub sau khi giải quyết trọn vẹn 3 blockers từ review của @Lolavine777.
- Request reviewer @Lolavine777 và @nairyuuu hoàn tất cross-confirm để hoàn tất #196.

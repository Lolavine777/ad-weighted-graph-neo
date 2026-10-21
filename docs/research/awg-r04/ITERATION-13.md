# Một foothold → mục tiêu, đường đi, chi phí và quyền nên kiểm tra

**Đã có đầu ra đọc được cho use case một foothold, và C cho đường từ machine identity tới DA.** [Xem kết quả chạy thật](examples/defender-brief.md), [JSON nhỏ kèm provenance/ledger](examples/defender-brief.json), [execution evidence](evidence/iteration-13-defender.json).

## Kết quả thực tế

Full public SEAMLESS: **3.370 nodes / 56.367 edges**; sáu raw files đã kiểm manifest. Nguồn là machine identity **FINWVIR1000001**, đã khai báo dùng được tại đúng Computer context. Nguồn này có ACL mạnh trong dataset; không đại diện mọi máy hoặc local shell thông thường.

Không nhập target IDs hoặc path: inventory tự chọn cả **12 mục tiêu kỹ thuật quan trọng**. Cùng bảy runtime assumptions, ba techniques reset/activation/membership, caps1path/3steps/6.000exp mỗi query, global72.000exp.

| Đầu ra | Trước, clean6cd7247 | Sau, cleanbc8aa99 |
| --- | --- | --- |
| Mục tiêu được xét | 12 | 12 |
| Có witness | 1: DA | 1: DA |
| Chưa kết luận | 11 | 11 |
| Witness có C | 0 | **1, C tìm thấy = 1** |
| Native attempts, states, witness, expansions | Baseline | Bằng baseline cho cả12queries |
| Đầu ra người dùng | SID và tên kỹ thuật | Labels, actor/context, work ledger, assumptions và quyền nên kiểm tra |

Đường tìm thấy: **FINWVIR → reset DENA_WILLIAM → dùng DENA tại context FINWVIR → entitlement Domain Admins**. Bước authentication không đồng nghĩa quyền admin trên FINWVIR. DENA là danh tính mới được acquire; không coi machine ban đầu trở thành thành viên DA.

**C=1 gồm một reset unit C=1 và activation unit C=0** theo rubric ordinal có sẵn; membership là passive closure. Đây là estimated expert scenario effort, không phải thời gian thực hoặc xác suất. Profile mới `reset-activation-c-v2` nhận explicit machine identity; v1/User giữ nguyên definition. Work IDs, owner/context, boundary và provider vẫn do pipeline native kiểm. Recorded inherited actor ACE thuộc scope v2 vì effective permission đã là prerequisite được conditioning; group/derived rights vẫn chưa được profile này chấm. Không cấp thêm capability hoặc adopt P/I.

Raw oracle độc lập đọc ACE Computer FINWVIR→DENA GenericAll (IsInherited=True) và DENA→DA membership. So sánh nguyên attempts/witness states bằng hash, chỉ bỏ rating metadata và scenario reference đã kiểm khi so hai profiles. Cả12 status/expansions/proof flags giữ nguyên. **Đây là cải thiện scoring/usability, chưa tăng reachability hoặc đổi thuật toán discovery.**

## Chạy bằng CLI hiện có

Sau bước chuẩn bị snapshot từ raw theo [README](../../../README.md), chạy từ repository root; thay đường dẫn snapshot nếu pipeline của bạn dùng thư mục khác:

```sh
AWG_FOOTHOLD=S-1-5-21-1271839998-3495686680-2211690266-4157
python -m scripts.exposure \
  --snapshot data/processed/awg-r04/pilot-v2/snapshot.json \
  --source "$AWG_FOOTHOLD" --authentication-context "$AWG_FOOTHOLD" \
  --computer-profile computer_usable_identity \
  --machine-identity-provenance scenario://awg-r04/machine-identity/FINWVIR-4157 \
  --evaluation-mode scenario \
  --assumptions docs/research/awg-r04/examples/machine-identity-assumptions.json \
  --effort-profile reset-activation-c-v2 \
  --technique scenario_reset_password --technique acquire_reset_identity \
  --technique propagate_group_entitlement \
  --max-sources 0 --max-targets 0 --max-paths 1 --max-steps 3 \
  --max-expansions 6000 --max-cells 12 --global-max-expansions 72000 \
  --output-dir reports/generated/demo-defender
```

Đọc **defender-brief.md** trước: 6.418bytes ở run này. JSON đi kèm39.312bytes giữ từng actor/source/target, effects, raw-edge provenance, điều kiện và work-unit cost. Full result1.267.224.242bytes vẫn được giữ để truy ngược audit; thêm brief không làm mất attempts hoặc giảm dung lượng full audit.

Quyền được gợi ý kiểm tra là **GenericAll của FINWVIR trên DENA**. Cần xét toàn bộ ACE và nguồn kế thừa; đây là candidate từ witness, chưa phải biện pháp đã chứng minh cắt hết đường. `--remediate N` tiếp tục dùng executor/replay/rediscovery cũ; brief khi đó trình bày programs bị cắt, cặp chứng minh ngắt và cặp còn Unknown riêng nhau. Composition này có integration test hữu hạn; run fullraw hiện tại chưa bật remediation.

## Những gì chưa được chứng minh

- Cả positive và11negative cells đều truncated; **minimum proofFalse**, không gọi C=1 là global minimum. P/I vẫn unrated/Unknown.
- Bảy runtime gates và machine identity là khai báo, không phải observations. Đây là một scenario minh họa cụ thể; chưa kiểm việc thay toàn bộ assumptions này bằng global profile cho cùng source/budget.
- Ba techniques của run chỉ đi tới identity entitlement; các mục tiêu host-admin cần technique tương ứng. Không dùng bảng này để kết luận DC hoặc toàn domain an toàn. Ngoài cohort còn31.068 cặp inventory.
- Pipeline vẫn tìm riêng từng goal. Timing một lần: batch/audit48,95s trước và67,79s sau khi thêm công việc C; serialize12,20/12,95s. Brief thêm0,21s. **Không có speedup claim**, không so hai feature scopes như một benchmark tối ưu.
- Không tạo extraction recipe, xác suất mới, business impact hay production AND–OR engine.

97selected checks pass, gồm v1/v2, identity/owner/context/False/Unknown, union-work oracle, worker/resume, byte preservation và brief/remediation composition. Week4 chạy hai lần36PASS/2NOT_EXECUTED/0FAIL, frozen semantic unchanged; appendv14, giữ history. Các authority pins v13 vẫn khớp vì những source authority đó không đổi; không tạo source successor dư thừa. **Final clean `ffcad383`: 527/527 selected checks PASS trong 144,73s, zero skip**; gồm native CLI/worker/resume, Computer boundary, v1/v2, independent shared-work oracle, identity goals, AS-REP/RBCD, R1/R2/R3 và Week4/source-history. Counts có overlap, không cộng. [Closeout/JUnit](evidence/iteration-13-closeout.json). Cả70 fullraw source pins và127 native/v14 file pins vẫn bằng current bytes. Mọi jobs đã complete.

**Việc tiếp theo có giá trị:** kiểm global scenario profile trên cohort này, profile phần C/preparation mới thêm và thử giảm repeated traversal/preparation theo kết quả đo. Tạm dừng đào HasSession/FCP khi chưa chặn use case có data thực.

# AWG-R04 — khôi phục và tiếp tục implementation

User đã ủy quyền coding, tải raw public, local tests/benchmarks và push branch/PR. Không chờ B hoặc GitHub CI billing. Không force-push, không ghi trực tiếp main/develop. Lệnh bắt đầu cho coding agent: **đọc file này, CONTINUE.md, RESULTS.md, issue #297 và PR #298 ở head mới nhất; tiếp tục thực hiện, không chỉ viết kế hoạch.**

## Điểm đã bảo toàn

Production code đã push: `4f009856f9071f02083f42e62de0f0608802abdd`, parent `025489a8a4486ff87c3e3142ffbfaa47675f961b`, branch `feat/awg-r04-product-readiness`. PR draft #298, base `perf/295-immutable-graph-contract@996ee35d154051abee4eb3c940c91264b68cb5fb`. Các commit docs sau 4f không phải source benchmark mới.

[iteration-2.json](evidence/iteration-2.json) có hashes/commands/results đã publish. Không phải chạy lại research từ đầu. Raw installer đã download thành công đúng public archive; full snapshot/pilot/remediation đã thực thi.

## Trạng thái môi trường lúc checkpoint

Exec-server báo transport disconnected/recovery timed out; không đọc được filesystem/process tiếp. Chưa có bằng chứng để kết luận OOM, test failure hoặc process còn chạy. Không gọi đây là chờ automation. GitHub connector vẫn hoạt động.

- Main checkout: `/workspace/scratch/b1f06964c680/awg-r04/repo`, HEAD 4f, clean trước khi chạy whole suite.
- Detached worktree prototype: `/workspace/scratch/b1f06964c680/awg-r04/iteration3`, cùng HEAD 4f, **có edits chưa commit**. Không reset/xóa.
- Python: `/workspace/scratch/b1f06964c680/awg-r02/.venv/bin/python`, 3.14.8. Bootstrap system Python thiếu networkx; dùng đúng venv.
- Raw: main checkout `data/raw/SEAMLESS`. Snapshot/query JSON: `data/processed/awg-r04/`, gitignored.
- Helper `sync_published_git.py` ở scratch chỉ dùng khi mọi source file khớp remote tree; **không chạy vào worktree có edits**.

Nếu filesystem còn: đầu tiên `git status` ở cả hai worktrees, đọc logs/JUnit, bảo toàn diff. Nếu mất: clone/materialize current branch mới và dùng đặc tả bên dưới, không tự nhận prototype đã có trong repo.

## Prototype goal: đã thực thi phần nào?

Năm probe trước prototype ở `awg-r04/goal_scope_probe.py` và `goal-scope-results.json` đã tái hiện:
U GenericAll V; V MemberOf DA. Goal membership(U,DA) không đạt; membership(V,DA) AND usable(V,CTX) đạt. Python existential predicate đạt cùng trace; thiếu activation hoặc auth False không đạt. Planner đúng với goal hẹp, default DA/EA không biểu diễn đầy đủ attacker exposure sau identity switching.

Native trace đúng theo recipe hiện tại:
1. scenario_reset_password: actor U, source U, target V;
2. acquire_reset_identity: actor V, source V, target Computer CTX;
3. propagate_group_entitlement: actor V, source V, target DA.

Prototype trong worktree iteration3 đã có:
- `UsableIdentityEntitlementGoal(SemanticGoalDescriptor)`, frozen custom-init subclass để không thay fields/serialization của legacy base. Required-state cũ vẫn version 1.0.0.
- Predicate: `exists (identity,ctx) in state.usable_identity: ctx == declared_context AND (identity,target_group) in state.effective_member`. Không cấp state effect mới.
- Descriptor mới đúng bốn keys: `version=semantic-goal/1.1.0`, `kind=usable_identity_entitlement`, `target_asset_id`, `authentication_context`.
- Strict shared decoder `semantic_goal_from_dict(value, IdentityResolver)` dùng materializer/adapter/replay/I guard; known nodes buộc target Group, context Computer.
- Query goal wire: `{"target":"DA","kind":"usable_identity_entitlement"}`. Context mặc định từ query; explicit goal context khác query bị từ chối. Cùng lúc đặt required_state và new kind bị từ chối.
- Callable bổ sung vẫn AND với typed goal, không được làm yếu goal.
- Checkpoint goals hỗ trợ cùng typed semantics.
- Adapter và semantic replay reconstruct descriptor; verify final capability/digests và first-hit prefixes.
- I guard vẫn đòi exact reviewed descriptor + review/snapshot/goal binding; không tự adopt impact mapping của goal cũ.
- Batch TargetGoal có optional `goal_kind`; legacy `to_dict` không xuất key khi None. Manifest dùng version `target-manifest/1.1.0` khi có field mới; 1.0.0 không được mang new field.
- New kind trong manifest có required_state={} (schema envelope compatibility), Group target, admin_entitlement. Batch compile thành query typed goal, lấy context từ source profile. Missing/non-Computer context trả unsupported_source/UNSUPPORTED_AUTHENTICATION_CONTEXT.
- `configs/targets/seamless-v2.json` là successor mới; DA/EA dùng existential goal, goal IDs có -v2; DC admin giữ semantics và dùng new typed DA checkpoint. Không sửa frozen v1 fixture.
- Pilot thêm `--target-manifest PATH`; bỏ option vẫn giữ historical scope.

Files đã sửa trong worktree: query.py, batch.py, ranking/adapter_145.py, ranking/verification.py, ranking/resolution_service.py, scripts/research/source_goal_batch.py, scripts/research/run_source_goal_batch_pilot.py, target-manifest.schema.json; thêm successor config và tests/test_identity_entitlement_goal.py.

Kết quả cuối đã đọc trước mất transport:
- `goal-regression-first.xml/log`: 139 pass, 20,88s; suites source_goal_batch_contract, source_goal_batch_runner, public_rating_integration.
- `goal-new.xml/log`: 17 pass, 0,30s. Same identity/context, acquired identity chain, old goal parity, no activation, auth False/Unknown, callable False, malformed/context/kind controls, wire roundtrip, replay binding forgery, first-hit prefixes, batch unsupported context, successor manifest roundtrip.
- Chưa có SHA-256 của final prototype sources trong durable evidence; đây là observed execution record, không phải reproducible attestation.
- Lệnh cuối định sửa public-rating-coverage.schema.json để chấp nhận descriptor 1.1 và export class qua engine/__init__.py đã **thất bại do transport**. Kiểm actual diff; không giả định patch đó đã apply.
- **Chưa** chạy full public coverage schema / numeric I binding / CLI worker / full-SEAMLESS successor-goal tests. Không gọi prototype production-ready.

## P0 tiếp tục ngay

1. Khôi phục execution; kiểm actual worktree, whole-suite PID/log/JUnit. Main 4f chạy `pytest -q --junitxml=.../full-4f.xml`; session cũ 2154, PID đã quan sát 8623. Lần đọc cuối chỉ hơn 30% với dots, **không có final result**. Khi đã mất process thì ghi interrupted, chạy lại có log/JUnit/appropriate resource bounds. Đừng chỉnh historical reports để test pass.
2. Hoàn tất goal prototype. Thêm oneOf descriptor v1.0 required_state / v1.1 usable_identity_entitlement trong public-rating-coverage schema; giữ old branch. Export class nếu API cần. Kiểm versioning/unknown fields/refusal thay vì silent downgrade.
3. Bổ sung independent tests: public JSON CLI và worker replay; reviewed I mapping đúng new goal được xét, old descriptor không được reuse, malformed descriptor refused; same identity join âm. Không invent ratings để có số.
4. Chạy broader query/materialization/boundary/ranking/RBCD/F1 regressions. Original F1 frozen expectations giữ nguyên. Chạy full-SEAMLESS same source/request/budgets, old vs successor goals, báo cáo goal semantics khác và unknown/truncated scope.
5. Publish code + new immutable evidence + checkpoint lên cùng PR, leased ref update từ remote head đã đọc. Không copy đè main checkout khi baseline test vẫn đọc nó.

## P1 performance đã có profile, chưa tối ưu

Scratch `profile_remediation.py`, `remediation-profile/profile.pstats`, profile.txt, summary.json: một fixed-snapshot AS-REP query + runtime admin-channel=False intervention. 145,607s instrumented ngoài graph load, 353 triệu calls; bảy searches chỉ khoảng 2,982s. to_canonical 24 calls/32,85s, Prepared init 12/20,13s, _digest 254/54,09s, deepcopy 57,73s. Times inclusive lồng nhau.

Ứng viên thay đổi tối thiểu:
- remediation.extract_witness(): dùng graph.to_prepared() đã bound, không dựng Prepared từ canonical copy mỗi witness.
- _effective(): runtime-only edits không đổi structural graph/static facts; chỉ RuntimeContext mới có explicit intervention provenance. Không fabricate observed evidence.
- effective_scenario(): khi structural/static view thực sự không đổi, reuse same EngineGraph, không dict(prepared) → rebuild.
- _check_edits(): exact source/target/kind lookup qua edges_between thay vì copy toàn bộ edges.
- Structural/snapshot edits vẫn phải giữ validation/binding; không biến _validated=True thành bỏ evidence binding. Independent verify_package phải tiếp tục chạy.

Trước code: đo unprofiled baseline 4f từ clean isolated copy, cùng snapshot/query/request/run IDs, không chạy cùng heavy pytest; lưu full package và source pins. Sau code: same-input before/after; compare deterministic packages ngoài execution metadata + independent negative controls. Không báo speedup remediation cho tới khi có phép đo này.

Một nghi ngờ shallow public nodes view chưa có repro với canonical nodes hợp lệ: current contract chỉ cho scalar fields; fixture probes không có nested list/dict. Không gọi là bug đã xác nhận hoặc làm recursive-freeze overhaul chỉ vì giả thuyết.

## Numeric/comparator/closeout

- Current approved scoped numeric v5 cần fresh execution và successor attestation nếu source drift. Pilot không nạp registries nên không dùng C/P null để kết luận missing numeric product coverage.
- FCP và HasSession composition vẫn unsupported. Không sửa bằng typed-secret grant ngầm; đó là coverage change cần independent oracle mới.
- BloodHound fresh comparator chưa chạy; không biết approach mentor. Không claim outperform BH hoặc full đề bài acceptance.
- Báo cáo RESULTS.md có requirements matrix và alternatives. Hoàn tất các gaps được nêu, không viết thêm architecture framework.

Automation continuation đã tạo một lần, 05:04:47 ngày 18/10/2026 giờ Việt Nam. Không tạo thêm lịch trùng; nếu phiên khác đang chạy trên checkout thì tránh concurrent edits. Không cần user cung cấp thêm dữ liệu hoặc xác nhận để làm các việc đã được ủy quyền.

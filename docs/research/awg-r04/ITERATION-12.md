# Iteration 12 — không biến khoảng trống HasSession thành bằng chứng an toàn

**Giữ planner, sửa coverage/proof reporting; chưa tự chuyển session material thành password.** Baseline sạch `e0345e2ae38af994cecab9ae154f38d32c8c9f65`. Đây là kiểm chứng hữu hạn trên fixture tổng hợp, không phải chạy kỹ thuật AD hay đo accuracy của sản phẩm.

## Kết quả và thay đổi

Oracle độc lập gồm hai action AND: password đúng owner/context + enabled/valid/network/accepted → usable identity; identity đó + membership gates → entitlement. Closure definite/possible tách Unknown. Không dùng AWG candidate generator, evaluator, state hoặc cost helper trong oracle. Material không rõ loại không có activation rule; oracle phân loại coverage thiếu là unsupported, không khẳng định khai thác được.

Clean baseline khớp23/26 ca. Ba ca opaque initial material, material tạo bởi HasSession, và lời khai password qua runtime metadata đều trả completed scoped `no_path`/negative proofTrue. Đây là **Verified reporting/coverage defect ở workflow defender**, không chứng minh nguyên thủy HasSession sai: primitive cố ý chỉ tạo `credential_material`, chưa có consumer tạo password. Password artifact được khai báo riêng thì activation→membership đã chạy đúng và switch actor sang owner; các ca sai owner/context, False, Unknown và observed-False veto không tìm thấy defect mới.

Bản sửa thêm diagnostic `UNTYPED_CREDENTIAL_ACTIVATION_UNSUPPORTED` trên các declared identity goals khi initial/reached branch có untyped material nhưng thiếu password/usable identity đúng owner/context. Nó không union capabilities giữa branches, không cấp capability và không suy chủ material có đường tới goal. Completed negative result chuyển `unsupported`; Unknown/truncated giữ ưu tiên, kèm diagnostic nếu có gap. Witness vẫn success, material-only goal vẫn supported. Negative/minimum proof flags bị giữ lại khi gặp gap; `complete` chỉ nói enumeration đã hết trong implemented model.

Batch có `unsupported_semantics`, result1.1; không có witness thì priority Unknown. Với một đích đã có witness và đích khác unsupported, giữ impact/priority từ witness nhưng row disposition vẫn unsupported_semantics; hai controls mới kiểm cả worker/direct. Result1.0 từ chối status mới; các output cũ vẫn1.0. Worker/resume giữ diagnostic và proof. Remediation giữ reachability unsupported, không biến nó thành proven_unreachable/disconnected. Ca kết thúc session với initial material vẫn unsupported cả trước/sau, zero proven disconnect và không có phần trăm giảm exposure hợp lệ.

Không đổi candidate enumeration, semantic catalog, credential forms, work units, C/P/I hoặc replay. Material không mặc định password; free-form metadata không có authority tạo typed artifact. Đây là một coverage detector hẹp, có thể bảo thủ với material không liên quan target; nó không phát hiện mọi thiếu sót semantics.

## Chạy lại hai input khác nhau

```sh
python -m src.engine.query_cli \
  --graph docs/research/awg-r04/examples/session-boundary-graph.json \
  --query docs/research/awg-r04/examples/session-opaque-query.json \
  --label synthetic --output /tmp/session-opaque.json

python -m src.engine.query_cli \
  --graph docs/research/awg-r04/examples/session-boundary-graph.json \
  --query docs/research/awg-r04/examples/session-declared-password-query.json \
  --label synthetic --output /tmp/session-password.json
```

Input đầu chỉ có host-admin/session assumptions, chưa có password: unsupported. Input thứ hai **khai báo sẵn** password artifact có provenance, không chứa giá trị secret thực: activation→membership có witness. Đây không phải before/after reachability gain của cùng initial state, cũng không phải tự thu password từ snapshot.

## Evidence và giới hạn

**Native capture sạch `74b4cd044d4296b67458a8ceb516ce2f1aa7ee9f`:26/26 khớp oracle, trước23/26.** [Machine evidence](evidence/iteration-12-session.json), [full before](evidence/iteration-12-before.json), [full after](evidence/iteration-12-after.json). Cả26inputs/attempts/paths/expansions bằng nhau; chỉ ba completed-negative status/proof đổi. **40new controls PASS/2,47s**, API/CLI/batch/worker/resume/schema/owner/context/Unknown/False/remediation; **216selected PASS/21,38s** ở run trước, có overlap. Giữ first attempts.

Week4 hai lần **36PASS/2NOT_EXECUTED/0FAIL**, same semantic digeste4f9a3f; appendv13 SHA`b29df225b9089400114fe51121e222d52a3c390dcd2054ba418e6a1e87b51774`, giữv12/frozenv3. Fullnative capture giữ ở ignored `reports/generated/awg-r04-acceptance-v13/native.json`; projection theo chính sách cũ giữ K-overlap, thay evidence khác bằng exactdigest và kiểm whole semantic equality. Append likelihood/scenario source successors13, không thay numeric/catalog/history. **Broad clean `d4b8e57`:647PASS/2opt-in skips/156.38s; final clean `78ce4ec`: 216/216 PASS/181.50s, zero skip**, gồm cả hai raw opt-in đã bật, mixed-success/unsupported row, native CLI/worker/resume/source-history. Suites overlap; không cộng counts. Native src/case module và v13bytepins bằng current. [Closeout/JUnit/full CLI](evidence/iteration-12-closeout.json). Mọi jobs complete, không pending. [Exact harness](evidence/session-boundary-harness.txt), [oracle/tests](../../../tests/test_session_material_boundary.py) có đầy đủ inputs và negative controls.

Raw SEAMLESS đã tải/verify ở iteration11 có0Sessions. Không rerun fullraw chỉ để tạo count, không claim session coverage, speedup, minimum C hoặc P. Hai-action oracle không kiểm toàn catalog, shared-work arithmetic hoặc real-world extraction. Fresh BloodHound CE comparison vẫn chưa thực thi. Tests pass không đồng nghĩa đề bài đã nghiệm thu.

## Vì sao chưa thêm typed extraction hoặc AND–OR

Microsoft phân biệt reusable credentials theo logon type: Network thường không để lại reusable credentials tại destination; material có thể là hash, ticket hoặc password. Credential Guard có protection limits; cached logon verifier không dùng để authenticate máy khác. Các tài liệu này không cho phép suy một session edge hoặc `credential_accessible=True` thành một password cụ thể:

- [Administrative tools and logon types](https://learn.microsoft.com/en-us/windows-server/identity/securing-privileged-access/reference-tools-logon-types), checked2026-10-19.
- [Credential Guard: how it works and protection limits](https://learn.microsoft.com/en-us/windows/security/identity-protection/credential-guard/how-it-works), checked2026-10-19.

**Strong inference:** đổi thuật toán discovery không tự bổ sung loại artifact/evidence bị thiếu. Trên fragment này, AND-fact closure là oracle nhỏ hữu ích; chưa có evidence cần một production AND–OR engine. Giữ planner và source/provenance guards. Bước tiếp theo là quyết định contract cho typed session extraction bằng fixture có owner, acquisition host, authentication context, loại material, extraction evidence và False/Unknown controls, rồi mới thêm recipe có cost coverage riêng. ForceChangePassword composition tiếp theo; preparation reuseP1. Không transfer numeric basis của reset sang session.

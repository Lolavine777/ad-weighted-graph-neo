# Bằng chứng chạy #216

Source pin: `afd0f680fa9a327f4c1236c93fa9876accb1031e`, base develop
`adee0896009d6180e68fc3d911a4d21aa22c9713`. Commit bàn giao sau pin chỉ thêm
docs/aggregate evidence, newline policy và sửa regression SHA manifest theo committed
LF bytes; không đổi engine/query/snapshot inputs.
Hai run JSON được đánh dấu `-text` để giữ exact bytes từ Windows; metadata/docs dùng LF.

[Run 1](run-1.json), [run 2](run-2.json) và [manifest](reproduction.json) ghi cùng
revision/input/config, exit 0, byte-identical. SHA-256 cả hai:
`21ee92d7970f840b9174c12ea2f52622857803d53e4beb8851ee04dd4c372a88`.
Semantic digest: `sha256:fd6d8bdf1b66c09347b1122a9b2ddbb0823e6c84103b7b505672de7db1c59980`.
Đây là actual outputs; oracle là rationale/PROGRAM đã chốt trong docs/tests,
không lấy output này để regenerate expected.

## Tái lập cho A / integration #213

Tại source pin, Python 3.14 và requirements-dev đã cài:

```bash
python scripts/research/kerberoasting_probe.py --code-version afd0f680fa9a327f4c1236c93fa9876accb1031e --raw-dir <private-SEAMLESS-root> --output run1.json
python scripts/research/kerberoasting_probe.py --code-version afd0f680fa9a327f4c1236c93fa9876accb1031e --raw-dir <private-SEAMLESS-root> --output run2.json
python -c "from pathlib import Path; import hashlib; a=Path('run1.json').read_bytes(); b=Path('run2.json').read_bytes(); assert a==b; print(hashlib.sha256(a).hexdigest())"
```

Private prerequisite: sáu raw files khớp
`data/samples/manifests/seamless-raw-v1.json` (snapshot `e0601d76…`). Thiếu raw root
trả SKIP/exit 2; synthetic run không thay actual SEAMLESS PASS.
Không commit raw identities, SPN values hoặc private mappings. Chỉ synthetic input
và alias/locator/count/digest/owner aggregates được lưu. Để chạy chỉ synthetic,
bỏ `--raw-dir`; để consume declarative input của #213, dùng `--snapshot/--query`
theo [docs API](../../kerberoasting-216.md).

## Kết quả và giới hạn

| Ca | Kết quả thực chạy | Disposition |
| --- | --- | --- |
| Synthetic positive | 5 transitions request → recovery → activation → membership → WinRM admin | Asset success conditional; material/secret/identity riêng |
| K-FACT-F / K-KDC-F / K-NO-AUTH | blocked, không asset | Known-false/absence giữ nguyên |
| K-FACT-U / K-KDC-U | indeterminate, không asset | Missing evidence không giả định true |
| K-MATERIAL | material có; recovery indeterminate | Không secret/usable identity |
| K-AUTH-F | secret có; activation blocked | Không usable identity |
| Canonical ranking | 1 candidate adapted, feasible, 4 active units | Effort/likelihood/impact null; unrated; không proof minimum |
| Synthetic K-OVERLAP | Baseline 1 route / 5 expansions; extension 26 routes / 182 expansions, step cap | Cả hai đạt cùng asset; không new asset coverage |
| SEAMLESS raw | Manifest PASS; 3.370 nodes / 56.367 edges; User11 SPN observed | Request indeterminate: Kerberos qualification/KDC/request acceptance missing |
| SEAMLESS comparison | Baseline 5.586 vs extension 62.383 expansions; mỗi scope 2 paths, path cap | Cùng shared-input digest; cùng C0 reachable; chỉ generated scope |
| SEAMLESS witness riêng | 5.351 expansions, 9 transitions, C0 reached, path cap | Đủ roast → activation → reset → asset dưới scenario assumptions; khác scope comparison |
| Immutability | Full graph/provenance/raw/normalized equal | Không thêm structural edge |

SEAMLESS PASS chứng minh trace/invariants trên observed snapshot. Runtime/recovery
outcomes chưa có observed basis; scenario assumptions có scope/rationale/method/
budget/horizon được liệt kê riêng. Không chứng minh exploit/cracking success,
password strength, số P/C/I hoặc optimum/complete coverage. Witness withheld U
membership gates để cô lập route; không dùng witness để tính baseline delta.

Full clean source suite: **1977 passed, 11 skipped, 268.42s**. Skips: 5 private
telemetry, 3 SEAMLESS tests dùng đường dẫn local mặc định, 1 dataset B, 2 Windows
filesystem cases. Actual SEAMLESS harness ở trên dùng private root tường minh và
đã PASS cả hai lượt. 132 focused boundary/ranking tests PASS. Ruff, format, YAML,
repository, contract, Compose config và diff checks PASS. CI trên PR head được
ghi bằng run links trong PR; cross-review của A vẫn pending. CI đầu phát hiện Week 4
manifest đang pin CRLF worktree thay cho committed LF; bốn hash được rebind theo
Git blob. Expected programs/states/ratings không đổi; đây là fixture transport fix.

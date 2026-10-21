# Week 4 raw-prerequisite acceptance repair

Goal: retain immutable semantic expectations while asserting the real checkout prerequisite independently.
The full end-user pytest invocation with verified raw reproduces two incorrect no-raw assertions and their nested demo-smoke failure.
No engine, registry, historical manifest or oracle changes are permitted.

- [x] Reproduce exact develop with authorized raw: 3 failed, 2593 passed, 9 skipped, 48 subtests passed.
- [x] Compare every normative case byte-for-byte with the existing fixture and validate the live filesystem prerequisite separately.
- [x] Generate a new versioned manifest with the existing runner; preserve the historical version.
- [x] Run affected tests and both raw-present and raw-absent prerequisite variants.
- [x] Run the full suite and required quality checks; obtain advisory code review.
- [ ] Publish the repair and the exact maintainer acceptance state without closing unresolved rating gates.

Advisory review verified all normative fields and historical bytes remain checked.
The repaired full suite passes 2596 tests, with nine skips and 48 subtests.
Frozen C/I scopes remain pending and prevent release closure.

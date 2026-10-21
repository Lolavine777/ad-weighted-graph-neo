# Issue #269 implementation plan

Goal: hand B an implementation-ready semantic contract and independent acceptance package.
Architecture: declarative catalog and JSON schemas, immutable overlay specification, literal independent oracles checked through existing public queries.
No production runner, search, Top-K, graph mutation, UI, or numeric adoption is added.

- [x] Freeze finite expected programs, including bypass, common gate, ineffective fix, multiple sources, missing/false and truncation.
- [x] Write acceptance tests before the checker; run them to confirm the absent checker fails.
- [x] Add strict catalog/request/result schemas and a small checker that validates artifacts and refuses contradictory claims.
- [x] Replay finite cases through `run_attack_query`; preserve input graph/query and source isolation.
- [x] Verify the SEAMLESS manifest and locator evidence, replay the narrow existing scenario and runtime negative control, and publish only aliases/aggregate results.
- [x] Document definitions, denominators, fact-view boundaries, numeric comparability, viewer fields and B implementation dependencies.
- [x] Run relevant tests, lint, formatting and repository/contract checks.
- [x] Run frozen acceptance checks on a clean commit (13 passed at `9966681`).
- [x] Complete independent advisory review.
Publication instructions: push this branch, open a focused PR to develop linked with Refs #269, and request @nairyuuu review.
The PR records publication and B review status.

User mission supplies scope and acceptance authorization; no intermediate approval checkpoint is needed.

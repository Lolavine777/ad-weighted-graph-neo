# B handoff for #269

A package: [comparison contract 1.1.0](contract-v1.1.md), [11-entry catalog](catalog-v1.json), catalog 1.0.0 and strict request/result 1.1.0 schemas, [finite oracle](../../../tests/fixtures/remediation/finite-v1.json), and [SEAMLESS binding](seamless-v1.json).
Source/goal integration is pinned to pending PR #270 head `690fbd678db4e6cf194e43c4a455bfbc046fff43`; adopt only after B approval.
No source/goal helper, search or executor from that PR is copied here.

1. Verify catalog/config/graph/fact/query/cohort pins and exact before evidence for each edit.
2. Build read-only effective authorization, static-fact and runtime views, with explicit intervention origin.
   Current runtime overrides cannot change preauth/SPN gates; `withheld_relationships` is not a general right-denial mechanism.
3. Rebuild each source from its declared initial state and isolate every source-goal cell.
4. Replay every baseline program to identify cuts, with failed-decision and intervention trace references.
5. Rerun existing semantic discovery for bypasses under identical goal/profile/catalog/budgets.
6. Bind ordered actions, participants, every prerequisite, relevant context and evidence/producer lineage; compare `semantic-program/1` identities, keeping native IDs as observation-local trace references.
   Populate bypass references for every normalized after witness, including retained and new programs; a generated ID change is not a new program.
   Supply explicit rediscovery run/proof references before any negative exposure claim.
7. Produce metrics and viewer panels from actual results, preserving null unrated C/P and capped/unknown results.

Acceptance anchors: Alice 3 -> 1 with membership denial retains direct admin; shared channel denial gives Alice 3 -> 0 and Bob 1 -> 0; shared membership denial leaves Alice reachable but disconnects Bob.
SEAMLESS uses six verified raw files, one source, one host goal and four techniques; membership-only remains ineffective, a declared channel denial blocks, missing recovery remains unknown and a cap remains truncated.
AS-REP request/secret/activation steps have no canonical edge IDs; structural-only pruning is unsound.
Secret hardening requires new recovery basis and is advisory, not a false gate or P=0.

Run `.venv/bin/python -m scripts.research.remediation_acceptance` and `.venv/bin/python -m pytest tests/test_remediation_contract.py -q -p no:cacheprovider` from a clean checkout.
Set `REMEDIATION_SEAMLESS_RAW_DIR` to verified private inputs for the raw-backed acceptance test; absence is an explicit skip.
Inspect [alias-only actual SEAMLESS results](seamless-actual-v1.json).

Pending B work: review #269 and #270, scoped overlay adapters, replay/rerun integration, cohort metrics/proofs and #224 viewer.
#226/#227 guarantee work and #267 numeric adoption remain separate; reachability does not wait for ratings.
No production top-fix optimizer, remote CI PASS, human cross-reproduction, or implemented remediation system is claimed.

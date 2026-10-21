# Week 4 maintainer acceptance - 11/10/2026

Verification role: **A maintainer self-verification**.
No independent B reproduction or new B numeric sign-off is claimed.
Release acceptance remains blocked by the frozen scenario's unadopted C/I scope dispositions.

## Product demonstration

The public flow is `query -> generated attack programs -> automatic C/P/I -> Min-Effort/Pareto`.
The caller supplies semantic context and reusable registries, without an ordered program, candidate list, action bindings or per-path ranking packet.

The frozen SEAMLESS case generates `asrep_request -> recover_asrep_secret -> activate_recovered_identity -> obtain_admin_execution_on_host` from manifest-verified raw inputs.
Its four actions and five projected states reach the declared asset goal under eight explicit assumptions; the DA checkpoint remains false.
All seven frozen controls reproduce: assumed, evidence-only/raw, missing recovery, known-false asset veto, extension off, removed request capability and step cap.
Its automatic coverage is C=0/4, P=0/4 and I=0/1.
Four effort classes remain pending review, all four exact P events lack applicable evidence, and the directional impact mapping remains unreviewed.
Missing P is an allowed localized limitation; the unresolved C/I dispositions prevent closing the rating scopes.

The bounded Source A projection is rebuilt exactly from verified raw: seven original nodes and all 16 internal edges.
The complete declared search produces 24 programs with a four-technique catalog, 10 semantic steps, 1,000 paths and 60,000 expansions.
A separate copy changes only native review/disposition gates to exercise the historical scoped numerical transfer; published proposals remain unchanged.
This is explicit conditional conformance evidence, not numeric activation or empirical calibration.

| Generated program | Actual work | C | Exact P | I |
| --- | --- | --- | --- | --- |
| `generated_0001` | One reset, activation, passive membership, WinRM administration | 2 | [9/40, 8379/10000] | High |
| `generated_0006` | Two distinct resets, two activations, passive memberships, WinRM administration | 3 | [81/800, 7800849/10000000] | High |

Reset contributes C=1, activation contributes C=0 and WinRM administration contributes C=1 under the frozen rubric.
The extra reset explains the C difference; passive membership contributes no C or likelihood event.
The exact conditional intervals are reset [3/5,19/20], activation [3/4,49/50] and WinRM administration [1/2,9/10].
Their separate records bind the complete ordered successful history, actor/target context, 24h horizon and the preserved per-mechanism retry/deadline policy.
Min-Effort selects `generated_0001` at C=2.
Both fully rated programs remain on the risk frontier because their P intervals overlap and their impact is equal.
All 24 programs have C/I coverage in the copy, but only 2/24 have complete P: eight of 46 unique required P requests are rated, leaving 38 distinct missing histories across 22 programs.
Those programs are excluded from risk comparison, not declared impossible or dominated.
The canonical pending query rates C=0/8, P=0/46 and I=0/1 unique requests.

The basis is historical AI-assisted, human-adopted scenario judgment with recorded provenance limitations.
It is not an observed exploit, measured success frequency, confidence interval, universal production baseline or whole-snapshot optimum.
The Source A disposition does not expand the frozen AS-REP recovery or impact-horizon scope.

## Acceptance-to-evidence matrix

All runs start from `develop@a79debb35d40431dd4395b9c6806928792e1835c` in a new managed checkout.
The test-only repair source is `3df54fcde4f4c7f3bd92b88d4d5addc84e0672fc`; engine, semantic inputs, registries and historical oracles are unchanged.
The [machine-readable evidence](../../reports/research/week4-maintainer-verification-2026-10-11.json) pins revisions, inputs, registry digests, outputs, commands and limitations.
The [new manifest](../../reports/research/week4-maintainer-acceptance-manifest-v1.json) preserves every existing normative scenario expectation.
Full raw identities, mappings and process outputs remain in ignored local storage.

| Gate | Evidence | Disposition |
| --- | --- | --- |
| Automatic public resolver | Public CLI/API/orchestration equality, Source A and frozen raw probes | Software conformance PASS |
| Deterministic rating keys | 417 focused rating/scoring tests and two equal Source A CLI packages with verified semantic digests | PASS |
| C resolution | Source A C=8/8, all 24 programs rated in review-gate copy; shared preparation/dedup and passive controls | Scoped conformance PASS; frozen four classes BLOCKED |
| P provider/full history | Eight exact historical-prefix transfers; wrong scenario/history/method/horizon/source controls; prototype quarantine | Scoped conformance PASS; 38 missing histories remain unrated |
| Typed I mapping | Exact Source A goal; weaker/wrong goal and authority/context refusal controls | Scoped conformance PASS; frozen equivalence BLOCKED |
| Frozen semantic coverage | Seven raw-backed public CLI cases, each twice; immutable expected states and cutoffs | PASS; numerical C/I acceptance pending |
| Generated Min-Effort | C=2 versus C=3 from genuinely different work; complete bounded projection | PASS under explicit transferred-basis copy |
| Generated P/I Pareto | Exact Fraction products, two nondominated programs with overlapping intervals | PASS under explicit transferred-basis copy |
| Fail-closed gaps | Eight public-query negative controls plus focused provider regressions | PASS |
| Week 3 and scoring regressions | Raw-backed reviewed Week 3 Source A harness PASS; scoring/proof/zero-action tests | PASS |
| Manual report/API audit | Current fields, scope, provenance and schema 0.3 output checked against public API/CLI | Recorded here; old manual row remains historical NOT EXECUTED |
| Full pytest and required checks | Original raw-present suite exposes baseline-test bug; repaired suite and quality outputs are pinned in the evidence record | Repair verification recorded separately from accepted develop |

## Reproduction and preservation

Python is the existing virtual environment's 3.14.7 interpreter.
Run these commands from the pinned checkout with authorized raw files present as a real directory.

```sh
.venv/bin/python scripts/snapshot_manifest.py verify data/raw/SEAMLESS data/samples/manifests/seamless-raw-v1.json
.venv/bin/python -m scripts.research.issue250_public_probe --seamless-raw data/raw/SEAMLESS --output reports/generated/week4-closure/public-probe.json
.venv/bin/python -m scripts.research.scenario_rating_pack --case source-a
.venv/bin/python -m scripts.research.scenario_rating_pack --verify-source-raw data/raw/SEAMLESS
.venv/bin/python -m scripts.research.scenario_rating_pack --case source-a --simulate-review --export-query reports/generated/source-a-review-copy.json
.venv/bin/python -m src.engine.query_cli --query reports/generated/source-a-review-copy.json --graph docs/research/ratings/scenario-basis-v1/source-a-graph.json --label seamless --prerequisite data/samples/manifests/seamless-raw-v1.json --output reports/generated/source-a-run.json
.venv/bin/python -m scripts.research.week4_acceptance_runner --check-determinism
.venv/bin/python -m scripts.research.week3_engine_acceptance --raw-dir data/raw/SEAMLESS --time-policy tests/fixtures/ranking/seamless_time_policy.json --created-at 2026-10-06T00:00:00Z --require-complete --output reports/generated/week3-acceptance.json
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m yamllint .
.venv/bin/python scripts/check_contract.py
.venv/bin/python scripts/check_repository.py
NEO4J_PASSWORD=ci-validation-placeholder docker compose --env-file .env.example --profile graph config --quiet
```

For automatic transport 0.3, compare complete packages after removing only `runtime` and verify each canonical semantic digest.
The existing comparison command accepts only legacy transport 0.2 and explicitly rejects 0.3; its rejection is not a determinism failure.
The public integration tests independently compare the automatic API, two CLI processes and orchestration results.

The frozen scenario hash remains `66c5ffef9a10d30d685f437b10d2998b0d57b96c2151c7eb9d00a0feeb0df752`.
Frozen actual-output bytes remain identical to the accepted scenario merge.
Reviewed Week 3 release and bridge-plan bytes remain identical to main.
The Source A frozen basis canonical digest remains `sha256:fd709b190fc3d388f61a38cab93100f9786332e667d9b8178914dd4aeefb5ac1`.
The Source A semantic digest is `sha256:9b6dfad90479f0615dce867fb64664d26d12bff03a36c1cfb8c9c0df2e8b483d`; its ranking and coverage digests are recorded in the machine-readable evidence.

## Release decision and remaining work

The original full suite reports 2593 passed, three failed, nine skipped and 48 subtests passed.
The three failures share a test assumption that local raw files are absent, including the nested demo command.
The repair checks the real filesystem observation independently while preserving every normative field and historical oracle byte.
A new versioned manifest is generated with the existing runner; historical manifests are not rewritten.
The repaired full suite passes 2596 tests with nine skips and 48 subtests in 270.01 seconds.
The affected repair tests pass 14/14, and all seven required quality/configuration checks return zero.
The raw-absent prerequisite branch is also checked without removing the authorized dataset.

Remote CI run 38125190114 has four failed jobs with zero executed steps and a billing/spending-limit annotation.
The branch-policy job also executes zero steps.
This is runner/infrastructure unavailable, not code failure and not CI PASS.

Do not close the rating parent or promote develop to main while the frozen C classes and I mapping have no adopted scoped numeric disposition.
The weekend exception supplies honest A reproduction and acceptance audit; it does not turn unadopted scope expansions into historical accepted ratings.
The draft release diff is mergeable and has no new sharding or Week 5 branch merged in this closure attempt.
Previously accepted research/prototype history remains quarantined by production refusal rules.

The next concrete requirement is an explicit disposition for the four frozen effort classes and the exact typed/horizon impact mapping, followed by reproduction using those accepted inputs.
Broad scenario profiles, 19 other active technique classes, new interleaving histories, batch source-risk ranking, chokepoints and empirical calibration remain Week 5/research work.
These broad gaps are not the release blocker identified here.

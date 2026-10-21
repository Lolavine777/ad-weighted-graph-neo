# Week 5 Technical Contract: Initial Footholds, Target Manifests, and Multi-Source Batch Semantics

## 1. Executive Summary and Ownership Boundaries

This specification defines the formal contracts, input/output schemas, capability profiles, and acceptance oracles for issue #268.
It provides an implementation-ready contract for TTS B (@nairyuuu) to build the batch query runner, source prioritization engine, and CLI/viewer extensions.
It deliberately unblocks batch execution without waiting for the final numeric likelihood rating catalog (#267).
Where likelihood ratings are unavailable, the contracts establish unambiguous unrated handling rather than halting or hallucinating probabilities.

### 1.1 Division of Ownership

The boundary between TTS A and TTS B is defined as follows:

- **TTS A Ownership**:
  - Foothold capability profile semantics and prerequisite models.
  - Snapshot-pinned target manifests and goal predicates.
  - Multi-source batch execution semantics and isolation invariants.
  - Explainable source-prioritization policies and mathematical counterexamples.
  - JSON schemas (Draft 2020-12), fixtures, acceptance test suite, and independent oracle definitions (Cases A-I).
  - Reference contract module (`scripts/research/source_goal_batch.py`).
- **TTS B Ownership**:
  - Batch runner execution engine (`src/engine/batch.py` or `src/engine/batch_runner.py`).
  - Search algorithm extensions, graph frontier expansion, and Top-K path pruning.
  - CLI integration for batch queries (`--batch-sources`, `--target-manifest`, `--discovery`).
  - Web viewer/UI integration for the source-goal matrix and ranked summary.
  - Promotion of `scripts/research/source_goal_batch.py` to `src/engine/semantics/foothold.py` when landing engine code.

### 1.2 Downstream Dependencies

This contract forms the normative foundation for downstream issues:
- **Issue #267 (Numeric Likelihood Rating Catalog)**: Provides calibrated numerical probabilities for applicable techniques.
  This contract handles unrated intervals cleanly without blocking on #267.
- **Issue #269 (Chokepoint Identification and Remediation Analysis)**: Relies on the source-goal matrix and immutable snapshot evaluation established here to evaluate cut sets and remediation impact across multiple attack origins.

---

## 2. Initial Foothold and Capability Profile Semantics

An initial foothold defines the adversary starting position within the identity graph.
Prior versions assumed an attacker immediately possessed usable credentials or administrative control.
This contract establishes four valid foothold capability profiles and strictly rejects invalid node types.

### 2.1 Profile Catalog

1. **`user_leaked_password` (User Principal)**:
   - Represents an unverified credential artifact obtained out-of-band (e.g., credential dump, phishing capture).
   - *Initial Attack State*: `control` is empty; `usable_identity` is empty; `recovered_secret` contains 1 `CredentialArtifact` with form `"password"`.
   - *Authentication Context Requirement*: In Active Directory semantics, credential activation (`activate_recovered_identity`) targets `RecoveredSecret` requiring `target_kinds == {"Computer"}`.
     A leaked password cannot authenticate in a vacuum or against a User principal SID.
     It requires an explicit, compatible Computer endpoint context (`authentication_context`).
   - *Input Boundary Validation and Error Codes*:
     - If `authentication_context` is omitted (`null`, empty, or unresolved), the batch contract rejects or marks the foothold at the input boundary with `is_supported = false`, `error_code = "MISSING_AUTHENTICATION_CONTEXT"`, and `authentication_context = null`.
       The contract never silently defaults `authentication_context` to the User's SID.
     - If `authentication_context` is set to the user SID or any non-Computer entity, the foothold is rejected at the input boundary with `is_supported = false` and `error_code = "INVALID_AUTHENTICATION_CONTEXT"`.
   - *Activation Gate*: An attacker cannot execute graph actions (such as group entitlement propagation or ACL abuse) until performing the `activate_recovered_identity` technique on the compatible host.
   - *Preconditions*: Requires network reachability to the KDC (`network_kdc_reachable`), active account status (`actor_enabled`), and Kerberos authentication acceptance (`authentication_accepted`).
   - *Status Semantics*: Without declared assumptions or live telemetry, queries evaluating this foothold yield `INDETERMINATE` (`is_no_path_proven_over_scope = false`).
     If the target account is disabled (`enabled=False`), the transition is `BLOCKED`.
     Unresolved or missing context must never return a false negative `proven_no_path` conclusion.

2. **`user_usable_identity` (User Principal)**:
   - Represents an established interactive logon session, cached token, or verified Kerberos TGT.
   - *Initial Attack State*: `control` contains the user SID; `usable_identity` contains `(user_sid, auth_context)`.
   - *Activation Gate*: None.
     The attacker can immediately execute applicable techniques (e.g., `propagate_group_entitlement`) in step 1.

3. **`computer_control_admin` (Computer Node)**:
   - Represents full SYSTEM or local Administrator compromise on a workstation or server.
   - *Initial Attack State*: `control` contains the computer node ID; `admin_control` contains the computer node ID; `remote_command_execution` contains the computer node ID.
   - *Capabilities*: Can immediately harvest cached credentials, extract active sessions (`HasSession`), or leverage machine account privileges.

4. **`computer_control_user` (Computer Node)**:
   - Represents unprivileged interactive code execution on a domain-joined computer.
   - *Initial Attack State*: `control` contains the computer node ID; `remote_command_execution` contains the computer node ID; `admin_control` is empty.
   - *Capabilities*: Can perform network Kerberos requests (e.g., Kerberoasting or AS-REP requests) originating from the host, but cannot inspect local LSASS memory.

### 2.2 Unsupported Foothold Types

Attack footholds represent entities capable of executing processes or presenting credentials.
Structural organizational nodes cannot initiate actions:
- **`Group`**: Groups are collections of principals, not operational actors.
  Compromising all members requires modeling each member as a foothold.
- **`Domain`**: The domain root is a governance boundary, not an actionable execution endpoint.
- **`OrganizationalUnit` (OU)**: Organizational units are directory containers for policy inheritance.
- **`GroupPolicyObject` (GPO)**: GPOs are policy storage objects, not principals.

When an unsupported node type is submitted as a foothold source, the batch runner must reject it immediately with:
- `is_supported = false`
- `status = "unsupported_source"`
- `error_code = "UNSUPPORTED_FOOTHOLD_KIND"`
- A clear human-readable explanation indicating why the entity cannot serve as an execution origin.

---

## 3. Snapshot-Pinned Target Manifests and Goal Semantics

Target selection must be deterministic, reproducible, and verifiable across environments.
This contract introduces snapshot-pinned `TargetManifest` structures.

### 3.1 Target Manifest Schema and Snapshot Binding

Every target manifest is immutably pinned to a specific graph snapshot via cryptographic digest:
- `manifest_id`: Unique identifier for the manifest.
- `version`: Semantic version string.
- `snapshot_id`: SHA-256 digest of the canonical or raw graph dataset.
- `domain_sid`: Security identifier of the Active Directory domain.
- `default_discovery_goals`: List of default goal IDs evaluated when no specific target is requested.
- `targets`: List of typed `TargetGoal` objects.

### 3.2 Target Goal Typing and Success Predicates

Each `TargetGoal` defines explicit success conditions:
- `goal_id`: Machine-readable target identifier.
- `category`: Classification (`tier_0_identity`, `tier_0_host`, `data_repository`, `infrastructure_service`).
- `target_node_id`: Canonical node ID in the graph.
- `target_node_kind`: Expected entity type (`Group`, `Computer`, `User`).
- `display_name`: Human-readable label.
- `technical_consequence`: Exact security consequence (e.g., `domain_admin_entitlement`, `host_administrative_takeover`).
- `impact_rating`: Business/technical severity (`Catastrophic`, `High`, `Moderate`, `Low`).
- `required_control_level`: Required privilege tier (`admin_entitlement`, `host_admin_execution`, `object_takeover`).
- `required_state`: Typed state predicates that must be satisfied in `AttackState` (e.g., `{"effective_member": [["__RESOLVED_ACTOR__", "S-1-5-21-...-512"]]}`).
- `checkpoint_goal`: Optional intermediate checkpoint (e.g., requiring Domain Admin membership before asserting host compromise).

### 3.3 Default Destination Discovery vs Single-Target Drilldown

The batch runner must support two complementary operational modes:
1. **Destination Discovery Mode (`target_goal_ids = null` or empty `[]`)**:
   - The engine resolves `default_discovery_goals` from the pinned manifest.
   - For every source, the engine evaluates reachability against all default targets in parallel or sequence.
   - Enables attack surface mapping and holistic vulnerability posture assessment.
2. **Single-Target Drilldown Mode (`target_goal_ids = ["goal-id-1"]`)**:
   - The engine restricts path finding strictly to the specified goal.
   - Enables deep forensic path exploration, budget concentration, and remediation planning.

The `TargetManifest.resolve_goals(target_goal_ids)` method and `BatchQueryRequest.resolve_target_goals()` implement deterministic destination resolution.
Omitting `target_goal_ids`, passing `None`, or passing an empty list/tuple `[]` resolves the manifest's configured `default_discovery_goals`.
Specifying explicit goal IDs validates that all requested targets exist in the manifest, raising a typed `KeyError` if any target ID is unknown.

### 3.4 Domain Admin Checkpoint vs Host Administrative Compromise

A critical architectural distinction is enforced between identity entitlement and host control:
- Achieving Domain Admin group membership (`effective_member` predicate) satisfies an identity privilege checkpoint.
- Controlling a Domain Controller or member server (`admin_control` predicate) requires either an active administrative protocol channel (e.g., WinRM, RDP, SMB) or explicit host takeover.
- If network filtering or firewall policy blocks management traffic to a DC (`admin_channel = false`), the path reaches the Domain Admin checkpoint but fails the final host compromise goal.
- The result must record `checkpoint_reached = true` and `final_goal_reached = false` with cell status `checkpoint_reached_final_goal_blocked`.
- High or Catastrophic impact associated with host takeover must not be asserted when only the intermediate identity checkpoint was attained.

---

## 4. Multi-Source Batch Input/Output Contracts

### 4.1 Batch Request Schema (`batch-query-request.schema.json`)

A batch request encapsulates:
- `batch_id`: Unique identifier for the batch execution run.
- `snapshot_id`: Pinned graph snapshot digest.
- `sources`: Array of `BatchSourceItem` objects, each specifying a `source_id`, `foothold_profile`, and optional source-specific budget overrides.
- `target_manifest`: Pinned `TargetManifest` definition.
- `target_goal_ids`: Optional list of goal IDs to evaluate (null indicates discovery mode).
- `evaluation_mode`: Mode of evaluation (`scenario`, `conservative`, `exploratory`).
- `prioritization_policy`: Strategy identifier (`impact_min_effort_pareto`).
- `common_budget`: Global limits on `max_paths`, `max_steps`, and `max_expansions`.
- `rating_resolution`: Optional automatic rating resolution packet containing envelope registries (`work`, `effort`, `likelihood`, `impact`) and policy configuration.

### 4.2 Rating Resolution Transport and Dynamic Scope Binding

To enable authoritative effort and likelihood scoring during batch execution, `BatchQueryRequest` transports an optional `rating_resolution` configuration.
This structure conforms to the `public-rating-resolution/1.1.0` envelope specification and contains domain registries for `work`, `effort`, `likelihood`, and `impact`, alongside execution policies (such as `production` or `synthetic_test_only`).

When serialized via `BatchQueryRequest.to_dict()`, the `rating_resolution` packet is preserved and validated against `batch-query-request.schema.json` via Draft 2020-12 validation.
Crucially, because a batch evaluates multiple source footholds across multiple target goals, the rating resolution scope cannot remain static across the entire run.
For each individual `(source, goal)` cell evaluation, the execution runtime dynamically binds the rating scope:
- `foothold_node_id`: Bound to the canonical node ID of the specific source entity being evaluated (`source.foothold_profile.node_id`).
- `target_goal`: Bound to the target asset ID and goal descriptor of the evaluated target (`target_asset_id` matching `target_goal.target_node_id`).
- `snapshot_id`: Bound to the pinned graph snapshot digest of the batch execution run.
- `evaluation_mode`: Bound to the request's evaluation mode (e.g., `scenario`).
- `query_id` and `scenario_id`: Bound deterministically to cell-specific execution identifiers.

Dynamic scope binding ensures that the underlying rating resolution service validates applicability, governance rules, and scoring baselines strictly against the precise context of each path.
When `rating_resolution` is omitted from the batch request, the engine executes in unrated search mode without evaluating registries or inferring artificial scores.

### 4.3 Batch Result Schema (`batch-query-result.schema.json`)

The batch result produces:
- `batch_id`: Matching request ID.
- `snapshot_id`: Pinned snapshot ID.
- `executed_at`: ISO-8601 execution timestamp.
- `reproducibility`: Pinned commit hash, dirty worktree flags, and engine versions.
- `source_goal_matrix`: A two-dimensional grid of `SourceGoalCell` entries keyed by `(source_id, goal_id)`.
- `source_prioritization`: Ranked list of sources ordered by the prioritization policy with typed `disposition` and `diagnostics`.
- `summary`: Aggregate metrics (total sources, supported sources, successful sources, status counts).

### 4.4 Matrix Cell Status Semantics

Each `(source, goal)` cell in the result matrix is assigned exactly one status:
- `complete_success`: Valid path satisfies the target goal within search bounds.
- `truncated_success`: Target goal was reached, but search bounds capped exhaustive exploration.
- `checkpoint_reached_final_goal_blocked`: Intermediate identity checkpoint reached, but final goal blocked by negative evidence.
- `checkpoint_reached_final_goal_indeterminate`: Intermediate checkpoint reached, but final goal is indeterminate due to unverified facts.
- `checkpoint_reached_final_goal_no_path`: Intermediate checkpoint reached, but no viable continuation path exists to the final goal.
- `checkpoint_reached_final_goal_truncated`: Intermediate checkpoint reached, but continuation search was truncated by budget limits.
- `checkpoint_only`: Intermediate identity checkpoint achieved without final goal attainment.
- `blocked`: Candidate paths exist but are halted by authoritative negative evidence or failed gates.
- `indeterminate`: Feasibility depends on unverified assumptions or missing runtime evidence.
- `truncated_incomplete`: Search budget was exhausted without reaching the target goal.
- `no_path`: Graph search exhaustively determined no topological or semantic route exists within scope.
- `unsupported_source`: The source entity is not an eligible foothold kind.
- `error`: Unexpected execution error during graph traversal.

### 4.5 Multi-Source Isolation and Graph Immutability

Batch execution must enforce strict mathematical isolation between sources:
- Graph topology is strictly immutable.
  No mutation of nodes, edges, or properties is permitted during search.
- Attack state (`AttackState`) accumulated while evaluating Source 1 (such as recovered credentials or acquired host tokens) must never carry over to Source 2.
- Parallel worker threads must operate on independent state clones or read-only graph views.
- Re-running the identical batch request against the same snapshot must yield bit-for-bit identical results regardless of worker scheduling or core count.

### 4.6 Search Bounds and Partial/Truncated Results

When a search budget (`max_steps` or `max_expansions`) is exhausted before finding a path or proving optimality:
- The cell status is marked `truncated_incomplete` (or `truncated_success` if a path was found).
- `truncated = true` and `truncation_reason` (`step_limit_reached` or `expansion_limit_reached`) are recorded.
- `is_minimum_proven_over_scope` must be set to `false`.
- A truncated result cannot be cited as proof that no shorter or lower-effort path exists.

---

## 5. Explainable Source-Prioritization Policies

Security operators need to know which initial footholds present the greatest danger to high-value assets.
This contract establishes a strict lexicographical prioritization policy.

### 5.1 The Multi-Stage Lexicographical Priority Rule

Sources are ranked using the following sequential criteria:
1. **Tier 1: Maximum Reachable Impact**
   - Higher business/technical impact takes precedence.
   - Ordering: `Catastrophic` (4) > `High` (3) > `Medium` (2) > `Low` (1) > `Unknown` (0.5) > `None` (0).
   - Incomplete evaluations (`error`, `indeterminate`, `truncated_incomplete`) are assigned `Unknown` impact and `Unknown` priority class; they are never collapsed into `None` or mischaracterized as proven no-path.
2. **Tier 2: Minimum Required Effort (Cheapest Viable Path)**
   - Among sources capable of achieving the same maximum impact tier, the source requiring the lowest total effort is prioritized.
   - Total effort is computed as the sum of friction costs along the optimal path.
   - Adversaries naturally follow paths of least resistance.
3. **Tier 3: Blast Radius**
   - Among sources tied across impact and effort, the source reaching more Tier-0 goals takes precedence.
   - If Tier-0 counts are equal, the source reaching a greater total number of distinct target goals is prioritized.
   - Evaluating blast radius before likelihood ensures that sources with multiple reachable targets are never demoted below single-target sources due to low rated intervals.
4. **Tier 4: Conditional Likelihood Ordering (Non-Numeric Tiering)**
   - Missing likelihood basis remains explicitly unrated (non-numeric tier 0) rather than inventing a synthetic numeric 0.50 scalar.
   - Mutually rated representatives are ordered in tier 1 by their calibrated lower bound probability ($p_{lower}$).
   - Unrated paths do not jump over genuine rated paths with fabricated probabilities, and low-rated paths do not demote multi-target sources below unrated sources.
5. **Tier 5: Fewest Path Steps**
   - Among sources tied across blast radius and likelihood, paths requiring fewer transition steps are prioritized.
6. **Deterministic Tie-Breaking**:
   - If two sources are identical across all tiers, ties are broken deterministically by alphabetical comparison of `source_id`.
   - Every tie and the specific tie-breaker applied are explicitly logged in `tie_breaking_applied`.

### 5.2 Deterministic Candidate Goal Selection for Multi-Target Sources

When an individual foothold reaches multiple targets in a batch, the engine must select a single representative goal to determine the source's primary impact, effort, and conditional likelihood metrics.
To guarantee deterministic execution that is completely independent of dictionary iteration order or goal evaluation order, candidate goals are sorted using the same criteria as source prioritization:
1. Maximum target impact rating (`Catastrophic` > `High` > `Medium` > `Low`).
2. Minimum effort required to reach the target ($C_{min}$).
3. Rated likelihood tier before unrated likelihood tier (tier 1 for rated intervals, tier 0 for unrated).
4. Calibrated likelihood lower bound ($p_{lower}$) among rated targets.
5. Fewest path transition steps.
6. Deterministic alphabetical `goal_id` tie-breaker.

This deterministic choice ensures that a source's representative metrics remain invariant regardless of how candidate cells are gathered.
It prevents inconsistent priority flips where an unrated goal and a rated goal with equal impact and effort compete within the same source.
Furthermore, explainability text formats reachable Tier-0 goals in sorted alphabetical order to guarantee deterministic output serialization.

### 5.3 Source-Level Disposition and Diagnostics Semantics

Each ranked source entry in `source_prioritization` carries an explicit `disposition` indicating its holistic evaluation outcome across all evaluated goals, alongside structured `diagnostics` objects detailing warning and error codes.
The engine distinguishes eight normative source dispositions:

| Disposition | Description | Highest Reachable Impact | Priority Class | Precedence Condition |
| :--- | :--- | :--- | :--- | :--- |
| `complete` | The source attained at least one configured target goal within search bounds. | Max impact among reached goals (`Catastrophic`, `High`, `Medium`, `Low`) | Computed via multi-stage Pareto rules | Reached $\ge 1$ target goal |
| `unsupported` | The source entity kind is ineligible as an attack foothold under identity semantics (e.g. Group, Domain, OU). | `None` | `None` | All evaluations report `UNSUPPORTED_FOOTHOLD_KIND` |
| `error` | Graph search encountered an unhandled engine traversal error or exception without reaching any target. | `Unknown` | `Unknown` | At least one cell status is `error` without reaching any target |
| `indeterminate` | Graph search completed with inconclusive feasibility due to unverified runtime assertions without reaching any target. | `Unknown` | `Unknown` | At least one cell status is `indeterminate` without reaching any target |
| `truncated_incomplete` | Search budget caps (`max_steps` or `max_expansions`) were exhausted before reaching any target goal. | `Unknown` | `Unknown` | At least one cell status is `truncated_incomplete` without reaching any target |
| `checkpoint_only` | The source attained an intermediate identity checkpoint (e.g. Domain Admin membership) without any final target goal being reached or proven unreachable. | `Unknown` | `Unknown` | At least one cell status is `checkpoint_only` without reaching any target or encountering errors/truncation |
| `proven_no_path` | All configured target goals were fully evaluated with verified negative conclusions. | `None` | `None` | Every evaluated cell status is verified negative (`no_path`, `blocked`, `checkpoint_reached_final_goal_no_path`, `checkpoint_reached_final_goal_blocked`) |
| `not_evaluated` | The source was not evaluated against any target goals (e.g. empty target list), or evaluation was inconclusive without explicit negative proof. | `Unknown` | `Unknown` | Empty matrix row or unclassified inconclusive result |

#### Normative Boundary Between `proven_no_path`, `checkpoint_only`, and `not_evaluated`

A fundamental principle of the batch contract is that negative security conclusions must be rigorously proven.
The disposition `proven_no_path` is assigned strictly and only when the matrix contains non-empty evaluations and every evaluated cell concludes with verified absence of a path (`no_path`, `blocked`, `checkpoint_reached_final_goal_no_path`, or `checkpoint_reached_final_goal_blocked`).
In contrast, `checkpoint_only` indicates that an adversary can achieve an intermediate privileged milestone (such as Domain Admin group entitlement), but the continuation search to the final asset (such as host administrative takeover) was either not evaluated or restricted to intermediate milestones.
Because an intermediate privilege escalation proves substantial identity compromise, a `checkpoint_only` source cannot be declared safe.
It is assigned `highest_impact = "Unknown"` and `priority_class = "Unknown"` rather than collapsing into `proven_no_path` or `None`.
The disposition `not_evaluated` is assigned when a source has zero evaluated cells (for instance, when a batch request specifies an empty target goal list that fails to resolve discovery targets) or when cell outcomes are inconclusive.
Incomplete, error, and checkpoint-only outcomes must never fall through to `proven_no_path`.
Their structured diagnostics retain underlying reason codes so security analysts can distinguish operational budget limits from true defensive barriers.

#### Deterministic Diagnostics Canonicalization and Deduplication

Source prioritization aggregates cell diagnostics across all evaluated goals into `SourcePrioritizationEntry.diagnostics`.
To prevent non-deterministic serialization depending on dictionary iteration order, goal evaluation order, or multi-threaded worker completion order, diagnostics are strictly canonicalized.
Goal keys in each source matrix row are sorted lexicographically before evaluation.
Each diagnostic mapping is normalized using a stable, key-sorted JSON representation (`_canonical_diagnostic_key`).
Duplicate diagnostics are eliminated, and unique diagnostics are ordered lexicographically before serialization.
Furthermore, when a source is classified under the `unsupported` disposition (`all_unsupported = True`), its `explainability` message dynamically extracts the specific diagnostic error code (such as `MISSING_AUTHENTICATION_CONTEXT`, `INVALID_AUTHENTICATION_CONTEXT`, or `UNSUPPORTED_FOOTHOLD_KIND`) rather than emitting a hardcoded constant.

---

## 6. Mathematical Counterexamples to Policy Flaws

Naïve prioritization policies frequently violate probability axioms and graph theory.
This contract explicitly forbids four widespread anti-patterns, backed by mathematical proofs.

### 6.1 Flaw 1: Probability Summation Across Alternative Paths (Kolmogorov Axiom Violation)

- **The Anti-Pattern**: Summing the success probabilities of alternative independent paths from a source to a goal:
  $$P_{total} = \sum_{k} P(Path_k)$$
- **Mathematical Refutation**:
  - By Kolmogorov's third axiom of probability, $P(A \cup B) = P(A) + P(B)$ holds if and only if events $A$ and $B$ are mutually exclusive ($A \cap B = \emptyset$).
  - Alternative attack paths in an Active Directory network are not mutually exclusive; an attacker can attempt Path 1, and if detected or blocked, attempt Path 2.
  - Furthermore, alternative paths routinely share common intermediate edges (e.g., crossing the same network perimeter or authenticating to the same DC).
  - Summing non-disjoint probabilities quickly results in invalid probabilities exceeding 1.0.
  - *Concrete Counterexample*: Consider two independent paths with conditional probabilities $P_1 = 0.60$ and $P_2 = 0.55$.
    Summing them yields $0.60 + 0.55 = 1.15 > 1.0$, which is mathematically absurd.
- **Contract Mandate**: The engine must never sum path probabilities.
  Independent paths may be combined only via union bounds:
  $$P(A \cup B) = 1 - (1 - P(A))(1 - P(B))$$
  provided the paths are genuinely statistically independent, or by reporting the maximum single-path likelihood $P_{max} = \max_k P(Path_k)$.

### 6.2 Flaw 2: Multiplying Probabilities Across Graph Fan-Out (Branching Explosion)

- **The Anti-Pattern**: Multiplying branch probabilities at decision forks during search:
  $$P_{fork} = \prod_{b \in Branches} P(b)$$
- **Mathematical Refutation**:
  - Multiplying probabilities represents the probability of the conjunction of all branches ($A \land B$), meaning the adversary must simultaneously traverse every branch.
  - An attack graph represents an OR-tree of opportunities where the attacker selects a single path, not an AND-tree where all branches must succeed.
  - Multiplying probabilities artificially penalizes sources that possess multiple distinct lateral movement options, making highly connected footholds appear deceptively safe.
- **Contract Mandate**: Evaluated paths are single trajectories.
  Path likelihood is the conditional joint probability along the sequence of steps, never multiplied across disjoint alternatives.

### 6.3 Flaw 3: Equating Unrated Likelihood with Zero / Safe

- **The Anti-Pattern**: Treating techniques or edges with missing numeric ratings as $P = 0$ or dropping them from search.
- **Mathematical Refutation**:
  - Missing empirical telemetry means the true probability is unknown ($P \in [0, 1]$), not zero.
  - Treating unrated paths as zero causes severe false-negative vulnerability assessments.
    An adversary utilizing a novel or unrated technique (such as RBCD abuse or relaying) with low friction will be completely ignored in favor of a noisy, heavily rated, high-effort path.
  - *Concrete Counterexample*: Path A uses RBCD (Effort = 2.0, Likelihood = Unrated).
    Path B uses password spraying (Effort = 12.0, Likelihood = 0.15).
    A naïve policy treating unrated as zero ignores Path A and prioritizes Path B, despite Path A being trivial to execute.
- **Contract Mandate**: Unrated techniques must be preserved with `likelihood_status = "unrated"` and `likelihood_interval = null`.
  Prioritization evaluates Min-Effort and Impact first, ensuring low-effort unrated avenues remain prominent.

### 6.4 Flaw 4: Averaging Non-Commensurate Friction and Effort Across Disjoint Protocols

- **The Anti-Pattern**: Computing an arithmetic mean of disparate cost factors (e.g., combining network round-trip time, detection risk, and manual operator time into an unweighted single scalar).
- **Mathematical Refutation**:
  - Costs measured along different dimensions (time vs stealth vs technical complexity) lack a common unit basis without an explicit utility function.
- **Contract Mandate**: Total effort is computed strictly as the cumulative sum of calibrated step friction units defined in the effort registry, preserving auditability.

---

## 7. Concrete Acceptance Scenarios and Test Oracles

To guarantee implementation readiness before TTS B begins coding, nine independently derived test oracles (Cases A through I) are formally specified and verified.

| Case ID | Name | Core Acceptance Invariant | Expected Outcome |
| :--- | :--- | :--- | :--- |
| **Case A** | Leaked Password vs Usable Identity | Unverified password requires `activate_recovered_identity` before acting. Usable identity acts immediately. | Leaked: 2 steps to DA (`activate` + `propagate`). Usable: 1 step (`propagate`). Missing auth: `INDETERMINATE`. Disabled: `BLOCKED`. |
| **Case B** | Destination Discovery Mode | Unspecified targets trigger automatic resolution of all manifest default goals. | Both DA identity and Host admin targets discovered without manual target specification. |
| **Case C** | DA Checkpoint vs Host Admin | Distinguish achieving group membership from administrative host takeover. | When `admin_channel=False`: `checkpoint_reached=True`, `final_goal_reached=False`, status `checkpoint_reached_final_goal_blocked`. |
| **Case D** | Source Node Eligibility | User and Computer nodes are eligible footholds; Group, Domain, OU, GPO are rejected. | Group/OU submission yields `is_supported=False`, status `unsupported_source`, error `UNSUPPORTED_FOOTHOLD_KIND`. |
| **Case E** | Multi-Source Isolation | Sources executed within the same batch do not leak state, credentials, or sessions. | Source 2 starts with clean state; zero cross-contamination of recovered credentials or host control. |
| **Case F** | Missing Likelihood Handling | Unrated techniques do not halt search and are not treated as safe or zero probability. | Path completes; `likelihood_status="unrated"`, `likelihood_interval=null`; Min-Effort and Impact evaluate cleanly. |
| **Case G** | Known-False Veto Over Assumptions | Authoritative negative evidence vetoes declared assumptions. | Declared assumption of access is rejected when snapshot evidence proves `enabled=False` or relationship missing; status `BLOCKED`. |
| **Case H** | Truncated Search Bounds | Searches capped by step/expansion limits cannot claim global path minimality. | With `max_steps=1` on a 2-step path: `truncated=True`, `truncation_reason="step_limit_reached"`, `is_minimum_proven_over_scope=False`. |
| **Case I** | Multi-Criteria Prioritization & Ties | Sources ranked by Impact -> Min-Effort -> Pareto Likelihood -> Reachability with deterministic ties. | Source with Catastrophic impact ranked #1; ties broken alphabetically by `source_id`; tie log recorded. |

---

## 8. Real-Data SEAMLESS Target Manifest

To guarantee grounding in real Active Directory environments, a complete snapshot-pinned target manifest is established for the SEAMLESS dataset:

- **Snapshot Digest**: `sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812`
- **Domain SID**: `S-1-5-21-1271839998-3495686680-2211690266`
- **Pinned Targets**:
  1. *Domain Admins Entitlement* (`goal-seamless-da-entitlement`):
     - Target Node: `S-1-5-21-1271839998-3495686680-2211690266-512` (RID 512).
     - Target Kind: `Group`.
     - Category: `tier_0_identity`.
     - Impact: `Catastrophic`.
     - Required State: `{"effective_member": [["__RESOLVED_ACTOR__", "S-1-5-21-1271839998-3495686680-2211690266-512"]]}`.
     - Provenance: `20210920185958_groups.json#/groups/40`.
  2. *Enterprise Admins Entitlement* (`goal-seamless-ea-entitlement`):
     - Target Node: `S-1-5-21-1271839998-3495686680-2211690266-519` (RID 519).
     - Target Kind: `Group`.
     - Category: `tier_0_identity`.
     - Impact: `Catastrophic`.
     - Provenance: `20210920185958_groups.json#/groups/18`.
  3. *Primary Domain Controller Compromise* (`goal-seamless-dc-admin`):
     - Target Node: `S-1-5-21-1271839998-3495686680-2211690266-1000` (RID 1000).
     - Target Kind: `Computer`.
     - Category: `tier_0_host`.
     - Impact: `Catastrophic`.
     - Required State: `{"admin_control": ["S-1-5-21-1271839998-3495686680-2211690266-1000"]}`.
     - Checkpoint Goal: Domain Admins membership (`S-1-5-21-1271839998-3495686680-2211690266-512`).
     - Provenance: `20210920185958_computers.json#/computers/0`.

### 8.1 EA Provenance Correction and Historical Evidence

Issue #268's raw binding correction supersedes the EA locator published in merged #270 (`3a34dfd62df568ee29b13fe46c4a92944d5d0dd9`).
The previous `20210920185958_groups.json#/groups/41` resolves to Enterprise Key Admins (SID ending `-527`); Enterprise Admins (SID ending `-519`) resolves to `20210920185958_groups.json#/groups/18`.
The target IDs, kinds, predicates, manifest version and exact snapshot digest remain unchanged.
Historical commits and frozen evidence retain their original bytes and must cite this correction when used as provenance evidence for the current contract.
The raw regression in `tests/test_source_goal_batch_raw_binding.py` resolves every manifest target from verified raw JSON, compares `ObjectIdentifier` and the raw collection kind with the target, and rejects the previous EA locator.
Run it with `SEAMLESS_RAW_ROOT=<private-six-file-root>` and the project virtual environment; absent private raw data is explicitly skipped, and an explicitly supplied root must pass all six file hashes before and after the regression.

B's #276 must merge the accepted correction from `develop` into its shared branch, align the consumed manifest/documentation/pin assertion, and include the raw regression.
No change to `src/engine/batch.py` or runner semantics is needed.
Requests embedding the manifest must use the corrected locator; their request and scope digests change, so checkpoints from the previous request must be replaced rather than resumed (`CHECKPOINT_SCOPE_MISMATCH`).
The frozen `reports/research/issue275-seamless-pilot.json` at #276 head `a564a6540940088502b82b98457b72458c0bb964` records a historical run from `2e4790bb9ad1a62f244275c24862712ef7e9a3b1` and must not be rewritten.
Any claim of current raw batch acceptance needs a new run and separately named evidence with refreshed embedded request, request/scope digests and exact revision, plus a supersession link to this correction.
The existing finite synthetic oracles do not embed the EA locator and need no change.

---

## 9. TTS B Implementation Delta and Integration Guide

This section outlines the concrete implementation work required by TTS B (@nairyuuu) to operationalize this specification.

### 9.1 Required Engine Components

1. **Batch Runner Module (`src/engine/batch.py`)**:
   - Accepts a `BatchQueryRequest` and an `EngineGraph`.
   - Validates the request against `batch-query-request.schema.json`.
   - Iterates through `request.sources`, instantiating isolated query contexts for each source.
   - For each source, resolves target goals (using `target_goal_ids` or manifest `default_discovery_goals`).
   - Executes search runs with isolated state clones.
   - Populates the `matrix` grid with typed `SourceGoalCell` records.
   - Invokes `prioritize_sources` to generate the ranked source summary.
   - Returns a validated `BatchQueryResult`.

2. **CLI Flags Extension (`src/engine/query_cli.py`)**:
   - Add `--batch-request <path>`: Path to a JSON batch request payload.
   - Add `--target-manifest <path>`: Optional override for target manifest.
   - Add `--discovery`: Flag to enforce destination discovery mode.
   - Add `--batch-output <path>`: Destination path for the batch result JSON.

3. **Viewer and UI Rendering (`src/ui/` or web viewer)**:
   - Render the source-goal matrix as a heat map (Reachable = Red/Orange, Checkpoint = Yellow, Blocked = Gray, Indeterminate = Purple).
   - Display the ranked source leaderboard with Impact, Min-Effort, and Likelihood columns.
   - Allow drilldown from any matrix cell directly into the detailed path visualization.

4. **Engine Promotion of Reference Models**:
   - When landing the batch engine, migrate the models from `scripts/research/source_goal_batch.py` to `src/engine/semantics/foothold.py`.
   - Re-export the public types in `src/engine/semantics/__init__.py`.
   - Update the maintainer file pins manifest for Week 5 technical closure.

### 9.2 Verification Commands for TTS B

To verify compliance with this specification, TTS B must execute:
```bash
# 1. Run the comprehensive contract test suite
pytest tests/test_source_goal_batch_contract.py -v

# 2. Validate all JSON schemas against fixtures
python -c "
import json
from pathlib import Path
from jsonschema import Draft202012Validator

schemas = ['target-manifest', 'foothold-profiles', 'batch-query-request', 'batch-query-result']
for name in schemas:
    schema = json.loads(Path(f'docs/research/{name}.schema.json').read_text())
    Draft202012Validator.check_schema(schema)
print('All schemas valid Draft 2020-12')
"

# 3. Verify zero regressions across full test suite
pytest -q
```

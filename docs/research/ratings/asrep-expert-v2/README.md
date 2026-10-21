# AS-REP basis v2 audit and current proposal

Refs #264, #266, #267.
A owns this proposed basis; B reviews numeric applicability and adopts each accepted record.
No independent dual-rater workflow applies.

The current CLI defaults to v2.
The v1 proposal and oracle remain unchanged as archived counterfactual regressions; use `--basis-version v1` only to reproduce that fixture.
V2 removes numerical recovery: the natural-password rank and completed compatible compute coverage are unknown.
An optimistic `recovery_success` scenario declaration permits semantic prediction but supplies no numerical probability.

The v1 assumed floor/cap over 20h is exactly 8192/1125 to 16384/1125 checks/s (about 7.28 to 14.56).
These were unmeasured resource commitments, not benchmark-derived limits.
The author-reported [hashcat v6.2.6 RTX 4090 benchmark](https://gist.github.com/Chick3nman/32e662a5bb63bc4f51b847bb422222fd) reports mode 18200 at 3564.1 MH/s.
That is a scale sanity check only; kernel benchmarking does not measure our achieved distinct candidate coverage, and does not predict password rank.
[Hashcat formats](https://hashcat.net/wiki/doku.php?id=example_hashes) distinguish AS-REP/TGS and encryption types; etype23 throughput cannot be silently applied to AES material.
No cracking job or hardware measurement was performed.

For a known finite rank distribution, q requires the joint event that the rank is covered and the verifier completes/validates before deadline, conditional on acquisition and the exact preceding history.
Under uniform24 with completed secret-independent coverage N, the arithmetic is min(N,2^24)/2^24.
N=2^19, 2^20 and 2^24 give 1/32, 1/16 and 1 respectively.
Without a completed-compute floor, the old positive lower bound disappears.
For natural passwords, uniform rank is not justified and no numerical recovery record is emitted.
The current one-worker 20h/2^36 cap is a scenario stop policy, not a hardware capability claim.
The four deadlines total 1250 minutes inside the 1440-minute campaign; retries are bounded whole events, never independent trials.

Request acquisition now has its own explicit residual-workflow proposal [9/10,99/100], with a 1%-10% failure allowance requiring B judgment.
This is an AI-assisted expert scenario proposal, not a rate derived from protocol documents or a completed human elicitation.
[Microsoft Kerberos documentation](https://learn.microsoft.com/en-us/windows-server/security/kerberos/kerberos-authentication-overview) supports the distinction between exchange/material and usable credentials only.
Activation [3/4,49/50] and terminal WinRM [1/2,9/10] retain historical values solely as pending equivalence questions for the exact recovered-secret lineage, unchanged account policy, offline delay and full successful history.
Generic AdminTo evidence alone does not identify the transport.
No historical acceptance automatically adopts these new contexts.

All three proposed operational records and C/I remain pending.
Even the synthetic wiring copy has only 3/4 P events, no path product and no Pareto candidate.
The current raw production flow has 0/4 P events.
B must review the request judgment, each historical equivalence, C=3/typed High applicability and any future recovery evidence separately.
Natural-password recovery and actual adoption remain concrete product gaps, not grounds to close #264.

Reproduce using `.venv/bin/python -m scripts.research.asrep_expert_basis --raw-dir data/raw/SEAMLESS --output reports/generated/issue264/v2.json` and `.venv/bin/python -m pytest -q tests/test_asrep_basis_audit.py tests/test_asrep_expert_basis.py`.

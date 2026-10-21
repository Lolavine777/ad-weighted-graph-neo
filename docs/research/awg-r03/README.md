# AWG-R03 — Start here

This is the repository-native coding-agent handoff following the executed
AWG-R02 audit. No external attachment or ChatGPT session is needed.

**Task:** implement actor scheduling/composition, CLI null-field compatibility,
and validated-catalog reuse through search/replay. Keep the incumbent planner;
AND-OR production discovery and credential bridges are outside this slice.

## Start

1. Read [HANDOFF.md](HANDOFF.md), `docs/00_todo.md` and applicable repository
   instructions.
2. Read [the full Vietnamese R02 report](AWG-R02_Bao_cao_thuc_nghiem.md).
3. Extract the retained data/scripts to a new scratch directory:

   ```bash
   python docs/research/awg-r03/prepare_evidence.py --output /tmp/awg-r03-evidence
   ```

   On Windows, use a new local scratch path instead of `/tmp/...`.
4. Follow the extracted `AWG-R02/README.md` to set up baseline and implementation
   comparisons. Use Python 3.14 and the repository's pinned test dependencies.
   Keep historical evidence immutable; write post-fix results separately.
5. Implement, test and profile the three changes. Submit the verified changes
   on a feature branch as a draft PR against `develop`; do not merge.

The handoff branch is `docs/awg-r03-planner-handoff`, based on exact audited
`develop@340e8e526e1e693d4c4b55635c459985eb08fa49`. If your checkout cannot
see these files, fetch that branch first. Preserve unrelated local changes.

## Data and integrity

- [Original evidence archive](AWG-R02_Experimental_Evidence.zip): 148 files;
  experiments, 78 finite inputs, independent oracle, results, JUnit/logs,
  phase timings/profiles, dependency pins and source-provenance records.
- SHA-256: `9f0180fce0db17902e361857262a89ac6e89391df6460bf8b41812f082b1d64a`.
- The extraction script checks the archive hash and refuses a non-empty output
  directory. `AWG-R02/MANIFEST-SHA256.txt` verifies individual retained files.
- The original archive is unchanged. Source checkout, venv and private raw
  SEAMLESS data are not embedded. Missing raw data does not block this slice.

310 selected tests passed at R02; 77/78 finite native reachability cases matched
the oracle. The actor-composition mismatch is a task to fix, not an expected
failure to preserve. Native shared-work minimum C=5 must remain correct.

R02's old repro/QA scripts intentionally assert baseline defects and old source
hashes. Read the handoff's **Frozen harness traps** section before adapting
validation; do not restore bugs or overwrite historical evidence to make those
assertions pass.

Related work: #227 (search research), #292 (independently documented exported
query CLI rejection), #293 (retained benchmark/report context). This follow-up
does not close their broader acceptance scopes.

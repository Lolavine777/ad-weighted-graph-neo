# AWG-R04 — checkpoint mới nhất

## Iteration 18 - fresh CE đã chạy, demo local và giới hạn nghiệm thu

Đọc [ITERATION-18.md](ITERATION-18.md), [DEMO.md](DEMO.md) và [closeout](evidence/iteration-18-closeout.json) trước khi tiếp tục.
Code commit `2e4b05dd6b72a657aecda46be1f91968b14b9291` trên feature branch; follow-up84dd61e giữ --all tương thích DatasetA/B, publication tiếp theo chỉ docs/evidence.
Đã fetch trước khi làm; PR298 vẫn ở checkpoint89620794 lúc bắt đầu.

Fresh Docker CE9.8.0/Neo4j4.4.42/Postgres16 có pinned digests, project final `awg-r04-ce-final-v1`, ports18080/17474/17687 và volumes riêng.
Nguyên raw v3 upload6/6 HTTP500/no-data-tag; envelope-only6/6 accepted nhưng553 ACE errors, không dùng làm baseline.
Converter riêng giữ raw/originals/hash pairs, kiểm ngược3369records/53040ACEs/13324memberships/2816containment/11localrefs, chặn unsupported data và tampering/duplicate roles.
Final import từ exact code commit:6/6complete,0serverERROR,3374nodes/78363relationships.
Independent stdlib audit giữ đủ3368unique rawIDs,50358nonself GenericAll/MemberOf triples;10selfACEs bị CE bỏ đúng official source, first failed audit giữ riêng.
Không upload graph AWG vào Neo4j, không gọi historical Legacy là fresh CE.

FINWVIR và OLA→DA cùng raw/scenario/C scope: CE/Cypher direct projection4→3routes mỗi nguồn khi filter đúng OLLIE→DA; cảhai reachable,2hops/foldedC1.
Local native1×12auto goals có4C1witness/8truncated;2×3 có2DAwitness/4truncated.
Native inventory4candidates chọn OLLIE→DA; replay cắt2/2old programs, rediscovery2bypasses quaDENA/C1,reachable2→2/disconnect0/unresolved-after0.
Cả4witnesses kiểmraw riêng; native3actions và Cbestfound1/minimumFalse giữ nguyên.
Brief/examples và full captures có SHA; không gọi projection minimum là full-native minimum hoặc so thời gian import/audit với search.

47import/converterchecks và86workflowchecks PASS; Ruff toànrepo/format/YAML/contractPASS.
75native sourcepins bằng actual89620794Gitobjects/current,127v16pins exact; engine/catalog/numeric/history giữbytes nên không lặp suite nặng/benchmark hoặc append successor dư thừa.
Các captures native bắt đầu tại89620794 với importer working changes được ghi, không nhận clean-tree capture; final CE import có clean committed source2e4b05d.
Giữ nguyên uv.lock/PDF/docs-final-report local, raw và all first attempts/full captures; hai exploratory Docker projects đã stop, giữ volumes.
Final CE project được giữ để demo/query; không thay stack khác hoặc AD thật.

**Kết luận:** MVP hai use cases + fresh CE cohort đã giao; yêu cầu minimum từ node bất kỳ trên full graph dưới truncation **chưa hoàn thành trọn vẹn**.
Simple weighted graph đủ cho direct/additive cohort này; không evidence buộc rewrite AND-OR/ba engines hoặc thêm catalog thiếu data.
P/I vẫn optional khi thiếu basis; chưa có tối ưu defender cost/full-domain exposure claim.
CE có0derivedCanRDP dù giữ3rawlocalRDPrefs, nên chưa claim full-taxonomy semantic equivalence hoặc invent user-right facts.
Nếu mở rộng tiếp, chọn một cohort/semantics có dữ liệu và oracle cùng input trước khi sửa engine; không quét thêm Unknown chỉ để tăng count.
Không force push/main/develop/merge; local validation vì CI billing, không chờ B.
Các mục iteration17 trở xuống là lịch sử đã được supersede ở phần fresh CE/demo.

---

## Iteration 17 — đối chứng công bằng cho bảo vệ, không sửa engine

Native source183ca901,3v3 executableCLIcases (docsworkingchanges giữtrongrecorder/sourcebytesGit+currentverified)/existingtwo-routes+syntheticA2Eledger: completeAWG C2/minimumTrue = independent weightedDijkstraC2, BFS1hopC5; cap1AWGC5/truncated/minimumFalse (Dijkstrafullprojectionkhôngcùngbudget); authenticationFalse nativeblocked/scopednegativeTrue = conditionedBFS/Dijkstra no_route. Independentstdlibunion-workoracle kiểm3completeprograms, bestedgeIDs bằngDijkstra. Không newC/P/I/speed/CEclaims. [Report](ITERATION-17.md), [evidence/exactharness](evidence/iteration-17-comparison.json).

FreshBHCE NOT_EXECUTED: noDocker/Podman/Neo4j,7474/8080refused,<100MiBfree. ExistingCErunner chỉA/B, khôngSEAMLESS. Không dùnghistoricalLegacy4.0.3reconciliation làmfreshCE. OfficialSpecterOps cócustomCypher/complexqueries: khôngnóichỉBFS hoặc khôngthểmodelprereqs. RawdirectC1case ởiteration16 simpleweightedgraph cũngđủ.

**Next:** chốtMVP/demo/bảo vệ với advantage/workflowvàlimitrõ; chỉfreshCEcùngsnapshot/querysemantics khi córuntime/đĩa, không mởframework/AND–ORrewrite. Fullgraphminimumdướitruncation vàCEcomparison cònopen. Lượt nàydocs/evidenceonly,127v16pins giữexact; all3CLIjobs complete; production/Python/testbytes giữ183ca901. Iteration16 dưới đây là lịch sử.

---

## Iteration 16 — một can thiệp đã verify, thấy rõ bypass và exposure còn lại

Ưu tiên user: chỉ làm việc quan trọng. Clean native09686f1, hai exact prior guided DA queries (ComputerFINWVIR/UserOLA độc lập, standardprofile/Cv2/3techniques/1path3steps6000exp). Inventory4candidates tự chọn supported relationship theo bindingcoverage/stableID: OLLIE_LONG→DA MemberOf. Native replay+rediscovery+independent package verifier đã complete2after cells: cut2/2old programs (100%observedcorpus), new2bypasses quaDENA, cả2/2pairs vẫnreachable/Cbestfound1,0disconnect/0unknownafter; truncated/minimumFalse giữ nguyên. Native214.97s/setup62.97s đơnlượt, khôngspeedclaim. Fullgzip375800973uncompressed bytes/CRC/SHA verified,75sourcepinscurrent.

Independentstdlibraworacle6manifestfiles/4witnesses/rawlocators: directconditioned subset4→3routes mỗi nguồn; BFS/Dijkstra cùng tìm đượcC1 trênprojection này, khôngnative globalminimum hoặc freshBHclaim. Small UI: exposure summary cóoutcomes từverifiedpackage; brief ghieditlabels/reachablebeforeafter/newpaths, oldsummaryfallback. Khôngengine/numeric/sourceauthoritychange;75native+127v16pinsgiữexact nênkhôngnewacceptancesuccessor. [Report](ITERATION-16.md), [demo](examples/remediation-defender-brief.md), [evidence](evidence/iteration-16-remediation.json). Initial86selectedPASS/24.59s, **Final clean `986c278f89699bf9336a8e2029af6dee1206e932`:86/86selectedPASS/25,21s/zeroskip**; [closeout/JUnit](evidence/iteration-16-closeout.json). Hai lượt86overlap, không cộng hoặc gọi whole-suite.75native sourcepins đối chiếu actualGitobjects/currentsource,127v16pins exact; strictauthority14/Ruff3files/contract2fixturesPASS, chỉ historicalR03ZIPlinkgap. Mọi native/verifier/oracle/test jobs complete. Không thay engine/numeric/history; finaldescendant chỉdocs/evidence.

**Next quan trọng:** chốt chuỗi demo/bảo vệ và fairBHcomparison nếumôitrườngcho phép; không lặp lại queue/remediation này, không mởdata-poorcatalog/AND–ORrewrite. Bỏ riêngmembershipOLLIE khôngđủ: xemGenericAllcủahai nguồn lênDAusers vàinheritanceprovenance. Giữraw/fullcaptures;4newlargeoutputs đãlosslessgzip+byteverified/storageindex đểgiữđĩa. No force/main/develop/parentwrite/merge. Iteration15 dưới đây là lịch sử.

---

## Iteration 15 — opt-in goal-guided đã vào sản phẩm, chốt MVP

User steering2026-10-19: ưu tiên giá trị tối thiểu cho đề bài khi quota ít, không đào thiếu-data/Unknown. Clean implementation29e52c4; reporter compatibility829965b. Query/exposureCLI `--search-order goal_guided`, defaultFIFO; native queue giữ mọi candidate/state, chỉ catalog reset/activation/membership với usableidentityGroupgoals; explicitFIFO fallback ngoài scope. Order bind query/cell/checkpoint/replay; per-cell deepcopy progress journal và stderr trước fullaudit, refusedresume giữ priorjournal. Không sharedtraversal/costlowerbound/globalminimum.

Fullraw3370/56367/globalstandardprofile/Cv2/no7handwrittenfacts: matched2sources×3auto goals cùngrequest/70pins/query-state-assumption scopes/caps1path3steps6000: FIFO0/6 vs guided2/6DAtargetwitness C1,2native replayPASS;36000→33990exp,63.96→72.58s đơnlượt **không speedup claim**. Computer×all12auto goals:4witness C1/8truncated,4replayPASS,67989exp/132.66s, firstwitness30.35s trướcfullserialize. GroupDC/RODC entitlement không hostcontrol.15distinctpairs vìComputer3overlap. Fullgzip CRC/size/SHA/sourcepins independentlyPASS. [Report/demo](ITERATION-15.md), [evidence](evidence/iteration-15-guided.json).

23newselectedPASS/exhaustedprogramsetFIFOparity/actor-switch/alternative/sharedC/FalseUnknown/context/workerresume/replayscope/executableCLI. Week4 initialcapturereporterdefaultfield drift, giữ log; sửa serializer không oracle/outcomes, clean829965b twice36PASS/2NOT_EXECUTED/0FAIL/frozensemantic unchanged. Appendv16 SHA3951d543abaa704cab2c50f84363a1eba47ce29a259539e1ab9ab038cc1e97de; strictauthority14/sourcepinsupdate/numeric+historyunchanged. **Final clean `a846394dea000d54b66a1a9616373eef00a7cb99`: 593/593 selected checks PASS trong164,74s, zero skip**, gồm23checks mới; không cộng với81/23lượt trước hoặc gọi whole-suite. [Closeout/JUnit](evidence/iteration-15-closeout.json) ghi các module và dependencies. Cả70native sourcepins và127v16pins bằng current bytes; strictauthority14PASS, v15/historical numeric+catalog giữbytes. Ruffcheck/format, contract2fixturesPASS; repository-links chỉ thiếu historical R03ZIP đã biết. Mọi jobs/captures/replays complete; finaldescendant chỉdocs/evidence, khôngsourcechange.

**NextP0:** chốt demo/bảo vệ, một can thiệp thực qua replay+rediscovery/bảngreachability riêngprogramcut; fair topology/weighted/BloodHound comparison nếu còn quota. Đừng lặp queue prototype đã giao; chưa productionAND–OR/sharedtraversal hoặc mở lạiHasSessionFCP. No main/develop/parentwrite, giữraw/captures. Iteration14 dưới đây lịch sử.

---

## Iteration 14 — tôn trọng scenario assumptions; sửa Unknown do technique alias

User steering2026-10-19: giả định là hợp lệ; không để thiếu observation làm demo/ranking tê liệt. C-first là khuyến nghị chính, strict Pareto bổ sung; không chờ P loại hết candidate.

Parent133517f74459ba6b0f0d505f2ed416f41e40ecf4, native clean e5b63817a6dceacb1d8b803cbcf3dfc66c277849. Confirmed bug: >200edges policy candidate filter thiếu canonical scenario_reset_password và4mutation/remote IDs. Finite2edges positive→padding201indeterminate trước; sau cảhaiC1/witness, controlsFalse/no-rightpass. CLI selectedscenario profile tự chọnmode; explicit evidence-only conflict vẫnrefused.

Full3370/56367, samebytesrequest/standardprofile,1Computer×12autoimportantgoals/3techniques/6000exp each/global72000/nohandwrittenfacts: indeterminate71916/72000→48/72000 (99,883%→0,067%), applicable36→71904, blocked48same. **IncumbentFIFO0/12witnessboth/truncated**: branch explosion sau khi conditioning, không no_path. One DA-only external priorityqueue prototype dùng nativegenerator/evaluator/no pruning tìmC1 ở4995exp/native replay1pass; không production/globaloptimum/all12speedup. No owner/path hardcode, heuristic từreverseMemberOf. [Report](ITERATION-14.md), [evidence/harness](evidence/iteration-14-global-policy.json).

NativeWeek4twice36PASS/2NOT_EXECUTED/0FAIL/frozensemantic unchanged; appendv15 SHA8967b072a5590775902cb9bfbc54f7200439ed15aee1b8c9ffea7ae1c1f0a4a2, v14/numeric/catalog/history giữbytes; authorityv13strictPASS. 35initialselectedPASS; broad-P testfirstrepresentationfloat→stringcorrected. **Finalclean48c3dee6:570/570selectedPASS/156,60s/zero skip**, [closeout/JUnit](evidence/iteration-14-closeout.json). Same70native-sourcepins/127v15pins/currentbytes. Entire FIFO/pilot query equals, hash513b881939d642805ec654b433a096b8044bacd8f6e89f47d8972324294c1eec. Alljobs complete; finaldescendant docs/evidenceonly, leasedfeaturepushPR298/issue297. Preserveallraw/fullgzipcaptures/nativeprojections/firstattempts; no mutateHEAD/source while jobsrun.

**NextP0:** production opt-in goal-guided witness queue with full-enumeration parity/alternative-route/actor-switch controls, then multi-goal benchmark; do not duplicate semantics or claim cost-optimality. Optimize measured preparation/C/serialization later. PauseHasSession/FCP; no fabricatedP/no AND–OR overhaul yet. Iteration13below historical.

---

## Iteration 13 — ưu tiên sản phẩm: một foothold → đích, đường, C và quyền nên kiểm tra

**User steering2026-10-19:** dừng đào HasSession/thiếu-data; ưu tiên demo hữu ích và hiệu năng thực tế. Các NextP0 về typed-session/FCP bên dưới là lịch sử, không tiếp tục mặc định.

Parent `6cd7247cf17a83e25e12ed906f68221ce9277e24`, branchfeat/awg-r04-product-readiness. Baseline actualCLI full3370nodes/56367edges, ComputerFINWVIR...4157 usableidentity,7assumptions/3techniques, cả12autoimportantgoals (không targetIDs),1path3steps6000exp/query/global72000:1witnessDA/11truncated-incomplete,0C-rated. Fullartifact namespace reports/generated/awg-r04-defender-v1/before; exactbefore-sourcepins verifiedagainstGitobjects.

Implementation: opt-in reset-activation-c-v2 dùng rubric reset1/activation0 cũ cho direct effective User/explicitComputer principal rights; existing v1 definition giữ nguyên. Machine cần usable_identity đúngcontext; không host/control ngầm, không newP/I. Inherited recorded actorACE có thể là effective right đã conditioning; group/derived rights ngoài costscope. New defender-brief.json/md trình bày labels,actor/source/target/effects/provenance,actualunitledger,assumptions,12goalstatuses và quyền nên kiểmtra; nếu bật existing remediation thì giữ programcut/disconnect riêng. Không đổi planner/semantics hoặc nạp xác suất mới.

Clean native/fullrawcapture `bc8aa99c19eff85df316c11046ae390e33cc2a1c`: full1Computer×12autoimportantgoals,1DAtarget C1/11truncatedincomplete; samecomplete attempts/witnessstates/expansions/status/proofs before6cd7→afterbc8, request/inventorysame. Brief6.418bytes/JSON39.312bytes; fullaudit1.267GBgiữlocal. [Demo/report](ITERATION-13.md), [exact output](examples/defender-brief.md), [evidence](evidence/iteration-13-defender.json). 97selectedPASS/9,71s; Week4twice36PASS/2NOT_EXECUTED/0FAIL, appendv14 SHA2d28d61e23cc601249606f34411376aa1a01bfcfee12882871dc0292677c17cc/frozensemantic unchanged. **Final clean `ffcad383`:527/527 selectedPASS/144,73s/zero skip**; [closeout/JUnit](evidence/iteration-13-closeout.json). Same70fullrawsourcepins/127native-v14pins/currentbytes; V1definition giữnguyên. Alljobs complete, khôngpending; finalpublicationdescendant chỉdocs/evidence, leasedfeaturepushPR298/issue297. Native costcompiler đổi nên appendacceptance14; authoritysource13pins không có reset_effort/exposure/brief và vẫn khớp, không tạo numeric/source successors dư thừa. Giữ mọi raw/fullcaptures/firstattempts, không mutateHEAD/source khi jobscapture/tests đang chạy.

**Next:** demo/brief đã hoàn thiện; thử global scenario profile và giảm repeated traversal/preparation theo measured bottleneck. Không ưu tiên kỹ thuật không có data. Main/develop/parent refs không đổi, không productionAND–OR khi chưa có evidence.

---

## Iteration 12 — HasSession coverage/proof hoàn tất implementation và validation

Parent `e0345e2ae38af994cecab9ae154f38d32c8c9f65`. Finite26-case independent two-action oracle, clean baselinee034 khớp23/26: ba completed untyped-material cases trả scopedno_path/proofTrue dù không có material→password consumer. Đây là coverage/reporting gap, chưa chứng minh đường AD thực. Typedpassword→activation→membership/actor switching, owner/context/False/Unknown/veto giữ đúng.

Small change: known coverage diagnostic trên declared usable-identity goals; complete negative→unsupported, negative/minimum proof withheld; Unknown/truncated ưu tiên trước, witness/material-only goal giữsupported. Batchstatusunsupported_semantics/result1.1, legacy1.0 từ chối statusmới; ưu tiênUnknown. Remediationunsupported không phảiproven_unreachable; sessionend không xóa initialmaterial. Không thêm extraction rule, numeric, credential form, catalog owner hay AND–OR engine. 40new checks pass; integration216pass trước hai controls cuối, suitesoverlap. Native/src đổi nên append strictsource successors13 và Week4v13; historical/numeric/catalog giữbytes.

Clean native/captures `74b4cd044d4296b67458a8ceb516ce2f1aa7ee9f`:26/26, sameinputs/attempts/paths/expansions. [Report](ITERATION-12.md), [machine evidence](evidence/iteration-12-session.json), full finitebefore/after publish kèm. Week4twice36PASS/2NOT_EXECUTED/0FAIL, frozensemantic unchanged; appendv13 SHA`b29df225b9089400114fe51121e222d52a3c390dcd2054ba418e6a1e87b51774`, strictsource successors13, oldnumeric/catalog/history giữbytes. **Broad clean `d4b8e57`:647PASS/2opt-in skips/156.38s; final clean `78ce4ec`: 216/216 PASS/181.50s, zero skip**, gồm cả hai raw opt-in đã bật, mixed-success/unsupported row, native CLI/worker/resume/source-history. Suites overlap; không cộng counts. Native src/case module và v13bytepins bằng current. [Closeout/JUnit/full CLI](evidence/iteration-12-closeout.json). Mọi jobs complete, không pending. Closeout descendant chỉ docs/evidence; fresh leased featurepushPR298/issue297, main/develop/parent refs giữ nguyên. Giữ raw/full captures và allfirstattempts. Không mutate HEAD/source khi captures/tests đang chạy. Raw0Sessions nên không giả fullraw sessioncoverage/performance hoặc accuracygain. NextP0 typed-session contract mới (chỉ nếu explicit type/extraction evidence), FCP composition; preparationreuseP1, chưa productionAND–OR.

---

## Iteration 11 — machine profile hoàn tất implementation và validation

Native implementation/captures sạch **`4c920a1f0f2997dd4b6f26320fc2819d3ac3a07d`**, parentdafde9b. [Report](ITERATION-11.md), [evidence](evidence/iteration-11-machine-profile.json). `computer_usable_identity` chỉ khai báo network identity, không host/admin/credential hoặc User identity. Explicit Computer context, cùng domain/non-boundary và provenance reference bắt buộc; disabled-source veto/Unknown giữ nguyên. Request/profile documents1.1 nhận capability mới;1.0 serialization giữ nguyên và từ chối capability mới. Thay reference làm đổi scope/cell và từ chối resume.

**227 selected PASS/13,85s**,35checks mới + old boundary/schema/worker/resume/CLI/source isolation/C-only/R1/R2/R3/source-history. Full raw6file manifest verified, snapshot3370nodes/56367edges. Actual exposure CLI1Computer FINWVIR...4157×3auto goals, seven assumptions/3techniques/1path3steps10kexp, global30k: local3blocked (2494exp mỗi goal); machine DA1truncated-success/4996exp, DC+EA2truncated-incomplete/7490exp mỗi goal. Native API/batch positive paths equal, replay1PASS. C/P/Iunrated/minimumFalse. Ba distinct pairs/hai declarations, không performance hoặc remediation claim. Full captures/local checkpoints/first attempts giữ nguyên.

V12 acceptance byte pins vẫn exact, native src/catalog/numeric/source-authority không đổi nên không tạo successor. Ruff581files/contractpass. **Final clean `7119371`: 504/504 PASS/123.56s, zero skip**, gồm các Week4 assertions/source-history/CLI/worker/binding/C-only/AS-REP/RBCD và old/new source contracts. [Closeout/JUnit](evidence/iteration-11-closeout.json). Captured code/schema và v12 pins bằng current bytes; mọi jobs complete, không pending. Closeout descendant chỉ docs/evidence; fresh leased feature push PR298/issue297. Không mutate HEAD/source/tracked set khi tests chạy; main/develop/parent refs không đổi. Machine checkpoint fullraw chỉ156bytes vì cả3cells truncated, không quảng cáo fullraw cache hits; finite completed fixture đã kiểm resume.

**Next P0:** finite oracle cho typed HasSession composition, phân biệt opaque material/password và owner/context/host-admin/Unknown/False. Raw0Sessions nên chỉ synthetic trước, không giả fullraw coverage. FCP composition tiếp theo; preparation reuseP1, chưa production AND–OR. Current branch `feat/awg-r04-product-readiness`; đọc latest GitHub/issue297 trước push, giữ mọi local work.

---

## Iteration 10 — Computer boundary hoàn tất implementation và validation

Native implementation và captures sạch tại **`3480f745fb664415f1c414586696e841be415026`**, parent `055f2d6` (iteration9 đã push). [Report](ITERATION-10.md), [evidence](evidence/iteration-10-computer.json). Oracle hữu hạn gồm 12 ca Computer mới: baseline668 có evaluator bytes bằng055f2d6, khớp5/12 → after khớp12/12. **217 selected PASS/8,60s**; có overlap với248 checks trước.

Fullraw: Computer FINWVIR (`...4157`) → DENA (`...2799`) → DA (`...512`), bảy assumptions, ba techniques, caps1path/3steps/10.000exp. Trước: local-only tạo witness/4.996exp. Sau: local-only blocked/2.494exp; explicit machine identity giữ witness/4.996exp, API/CLI parity và native replay pass. Positive vẫn path-limit truncated, minimumFalse, C/P/I unrated. Đây là một pair với ba declarations, không phải benchmark performance hoặc remediation gain.

Computer actor dùng techniques có `source_authorized` nay cần `usable_identity` đúng context. Host control không đủ; authUnknown/missing-context giữ indeterminate. HasSession local-admin gates không đổi; untyped material → identity còn unsupported. SYSTEM có thể dùng machine account trong Windows; profile local-admin/SYSTEM hiện gộp nên explicit declaration là contract bảo thủ. Exposure overview, README và exact query examples đã cập nhật.

Clean Week4 hai lần: **36PASS/2NOT_EXECUTED/0FAIL**, frozen semantic unchanged; appendv12 SHA `d7e0705fe2f67ea81ec846f1676ea52243eba132dc306cc37abaca9e2754aaf4`, giữv11. Append likelihood sourcev12 only; scenario sourcev12, numeric/history giữ bytes. Ruff579files/contractpass; historical R03ZIP là link gap duy nhất. Finite/raw/replay/native jobs đều complete. **Final clean `69f2093`: 425/425 PASS/121.81s**, zero skip; native/v12 pins khớp actual files. [Closeout/JUnit](evidence/iteration-10-closeout.json). Fresh executable fullraw CLI giữ entire underlying adapter package; bốn envelope fields về label/snapshot được xác minh riêng, gồm toàn7.479facts/provenance/giá trị. Mọi jobs complete, không pending. Closeout descendant chỉ docs/evidence; fresh leased feature push/PR298/issue297. Không mutate HEAD/source/tracked set khi tests chạy; main/develop không đổi.

**Next P0:** profile Computer network identity tường minh cho exposure/batch, có context/provenance validation và current oracle; không auto-grant User identity. Kiểm tra `scripts/research/source_goal_batch.py`, batch request schema, `scripts/exposure.py`, `tests/test_computer_foothold_boundary.py`. Typed HasSession activation chỉ thử synthetic trước vì raw có0Sessions. Preparation reuse làP1; chưa production AND–OR. Giữ mọi raw/captures/first attempts. Iteration9 trở xuống là lịch sử.

---

## Iteration 9 — batch/writer hoàn tất implementation và validation

Parent `668bf5f6cb70c5c14397b11967adb920d0e15278`. Exact raw/full snapshot và OLA1×3auto goals (DC/DA/EA), seven assumptions/three techniques/caps10paths4steps10.000exp mỗiquery, global30.000. **6sequential ABBAAB trials** old2708100 vs668bf5f complete; whole result/checkpoint/summary plus exact inventory/request/selection/overview parity, scope/fingerprint/hash independently checked trước normalization. Median35,442→33,183s, RSS khoảng2.786.472KiB (~2,66GiB) unchanged. 1C1success/2truncated, no minimum/no_path proof. `reports/generated/awg-r04-batch-audit-v1`, exact external harness `../benchmark_batch_audit.py`; không relabel source pins.

Profile trên clean668:62,038s instrumented; wire21,227s/copy14,222s/atomicwriter6,794s cumulative (overlap), generator3,149s. Fullresult476.356.988bytes/checkpoint126.209.561bytes. Existing atomicwriter nay ghi JSON/newline riêng; same JSON/atomic replace, no search/scoring/binding change. **4ABBA trials/2mỗi mode**, baseline668 vs clean **acf4a0fea8c9bee0477110f1f505f33242149f3d**: RSS2.787.308→2.321.284KiB (-16,72%), wall29,612→29,557s (không meaningful speedup). Whole result/checkpoint/summary + exact triage parity sau independent scope/checksum validation. `reports/generated/awg-r04-batch-writer-v1`; không gộp phase timing baselines. [Report](ITERATION-9.md), [evidence](evidence/iteration-9-batch.json).

**109selectedPASS/10,89s**: batch/resume/worker, exposure/policy, R1/R2/R3, source-history và rollback-after-serialization-error. Các captures/bench/profile đã complete; giữ toàn artifacts. Giữ mọi full captures/raw/checkpoints; không duplicate thêm full audits khi không cần.

Clean native twice **36PASS/2NOT_EXECUTED/0FAIL**, frozen semantic unchanged; append **v11** SHA-256 `5d273d2f7a95d265d6f6912a283422f689b4774735128da7adfb559f565ff513`, giữv10. **Final clean `47d039e7bf86ed05c0a8006ab6d27b219324aecd`:248/248PASS/115,34s/zero skip**, native writer/v11 bytepins bằng actual files. [Closeout/JUnit](evidence/iteration-9-closeout.json). Mọi jobs đã complete, không pending. Closeout descendant chỉ docs/evidence; fresh leased feature push/PR298/issue297. Không mutate HEAD/source/trackedset khi tests chạy; main/develop không đổi. NextP0: Computer foothold capability/oracle theo đề bài gốc; no implicit identity/Sessions. P1 safe source/preparation reuse, chưa production AND–OR. Iteration8 trở xuống là lịch sử.

---

## Iteration 8 — audit optimization đã hoàn tất implementation/validation

Native code bắt đầu `745bbd2a206312756de024af020bb8d419b8ef98`; corrected benchmark/profile/native capture sạch **`b605f5db596511aad40204cc62af58cb625073b5`**, baseline **`2708100b83549dc606d610de2c0b20e19130209d`** trong detached `../baseline-270`. [Report](ITERATION-8.md), [machine evidence](evidence/iteration-8-audit.json). Giữ mọi local work/raw/captures, không sửa main/develop/parent branches.

- Shared `wire` exact-scalar fast path; opt-in native query CLI `--compact-output` chỉ bỏ whitespace. Không sample/truncate attempts, không đổi search/cost/replay/schema/binding. **152selectedPASS/29,846s**: compact stdout/file whole-package parity, independent synthetic ledger, native batch/worker/resume, C-only và binding/reuse. First100checks overlap.
- Corrected `reports/generated/awg-r04-audit-benchmark-v2`: **9sequential trials/3permode**, whole semantic/normalized-package equality. Median oldpretty10,036s/newpretty9,563s/newcompact9,078s; compact output90,49→59,80MB/RSS720.272→627.856KiB. Một workload, không statistical/global/batch speedup claim. Giữ đủ7.490attempts/7.494diagnostics, C1/P/Iunrated/native minimumFalse.
- Separate profiles `../audit-profile-before/after`: wire cumulative14,160→9,316s, total24,776→19,198s instrumented; native generator1,393→1,308s. Cumulative overlap/profiler overhead, không dùng ratio đó thay unprofiled benchmark.

- Clean native Week4twice **36PASS/2NOT_EXECUTED/0FAIL**, frozen semantic unchanged. Append **v10**, SHA-256 `bb0905bd9d5141fa9d1eb86d31e51511fb356920aa67fe347836c4d103def353`, giữv9. Ruff577files/contractpass, repository links chỉ historical R03ZIP gap.
- **Final clean `2eef19515a8d464860a444b67ef151ab70705fdb`: 247/247 PASS, 113,42s, zero skip**; native src bytes bằng benchmarkb605 và v10bytepins khớp current. Fresh executable CLI sau source-compat correction có whole semantic/package parity, chỉ khác đúng3researchscript hashes/revision/runtime. [Closeout/JUnit](evidence/iteration-8-closeout.json). Mọi benchmark/profile/native/history/CLI/final-test jobs đã complete, không có worker cần đợi. Publication descendant chỉ docs/evidence, fresh leased feature push/PR298/issue297; không sửa main/develop hoặc parent branches.

First clean `0ca40af`247checks:246PASS/1source-authority fail bắt đúngquery_cli drift. Append strict likelihood manifestv11/scenario manifestv12, update3reader/generator scripts và testpointers; không thay numeric/old manifests hoặc bỏ guard. **76 history/catalog/scenario PASS/164,53s**, including raw/API/CLI/oracle. [Compatibility evidence](evidence/iteration-8-compatibility.json). Correction đã được clean247rerun và fresh native CLI xác nhận ở2eef195; giữ failing attempt, không rerun heavyweight76 chỉ để tăng count.

V1 full parity nhưng RSS/parent fork overhead nhiễu: giữ toàn `awg-r04-audit-benchmark-v1`, không dùng làm primary claim. Probe160MiB xác nhận, corrected measurement qua fresh supervisor đã independently checked và chạy v2. Không phải production regression; native wire/compact code không đổi sau745bbd2.

**Next:** đo bounded multi-goal batch cùng scope để xác nhận shared-wire gain chuyển được sang use case2; chỉ tối ưu một preparation/serialization hotspot theo profile, giữ whole decision-package parity/R1/R2/R3. Computer capability oracle, FCP/HasSession composition và fresh BH comparator còn open. Không mở P/I/production AND–OR khi chưa có evidence. Iteration7 trở xuống là lịch sử.

---

## Iteration 7 — C-only đã hoàn tất code và validation

Native code đã capture sạch tại **`143dc5d833e20270a1b343124df11b95fab3f506`**, parent `6c582c581cc922d2cefd4f013da51ec3687bd968`. Opt-in `--effort-profile reset-activation-c-v1` biên dịch hai C classes cũ vào exact source/owner/context/work-unit scope cho acquired-identity Group goal. Không có evaluator/giá/P/I mới; đây là applicability extension được solo fork chủ động áp dụng, không phải historical reviewer đã review scope mới. Existing membership/seeded second identity, Computer/host/cross-domain scopes không được profile này chấm; search vẫn chạy và metadata ghi not_applicable. [Report](ITERATION-7.md), [evidence](evidence/iteration-7-effort.json).

- 166 selected checks PASS; sau đó strengthened per-unit oracle/CLI/policy-composition controls **21/21 PASS**. Suites overlap. Union-work oracle không dùng native unit-ID/cost compiler; kiểm nhiều owner/orderings, False/Unknown, foreign contexts và incomplete optimum.
- **Final full-snapshot v4:** OLA (không có DA membership ban đầu, nhưng ACL mạnh) → reset DENA → activation → DA entitlement, 1 witness/7.490 expansions/C=1/P/I unrated, native `minimum_proven=False`. Full paths trước/sau và API/CLI/batch semantics bằng nhau. Captures `awg-r04-effort-pilot-v4` giữ full artifacts; first/v2/v3 là development, hai lỗi runner đã sửa, không nới CLI/semantics.
- `awg-r04-effort-legacy-v1`: old actor goal 0 paths/10.000 expansions/truncated, không no_path proof. `awg-r04-effort-exposure-v1`: 1 source ×2 auto goals, 1 C-rated complete success/1 truncated incomplete, 31.078 inventory pairs ngoài cohort. Không cộng với historical 1.600 cells khác scope.
- Clean native Week4 twice **36 PASS/2 NOT EXECUTED/0 FAIL**, semantic unchanged; append **v9**, SHA-256 `90be6f244fc3c7fb87659c91149752033ee1ef835ce2476b8996f9a2bc2f623e`, giữ v8/frozen v3. Raw/pilot/legacy/exposure/acceptance jobs đều complete, không pending.
- **Final clean `7fae1ba1355f4f627e4a8cd4f5a50d4296bd2070`: 182/182 PASS, 86,669s, zero skip**, gồm C-only oracle/CLI/batch/resume, binding/reuse/source-history và ba Week4 modules; native/acceptance pins bằng actual files. Ruff575 files/contract pass; đúng historical R03 ZIP link gap còn thiếu. [Closeout/JUnit](evidence/iteration-7-closeout.json). Jobs đều complete, không pending. Publication descendant chỉ docs/evidence; kiểm fresh remote lease trước push feature branch/PR #298, checkpoint issue #297. Không sửa main/develop hoặc parent branches.

### Sau publication

P0 paired profile audit/serialization của exact rated query: API ~0,925s, CLI ~10,521s/full output 90.488.145 bytes. Scope khác nhau, chưa claim speedup/function bottleneck. Thử bounded/spooled attempt audit với full semantic/provenance parity và R1/R2/R3. Sau đó Computer capability profile có oracle, FCP/HasSession composition, fresh BH comparator. Không mở P/I hoặc production AND–OR chưa có evidence; không quét lại hàng loạt Unknown chỉ tăng counts.

Các phần iteration6 trở xuống là checkpoint lịch sử, chưa bao gồm completion iteration7.

---

## Iteration 6 — profile integration và mixed-context remediation

Native code đã chốt/thực thi sạch tại **`9ce0703388fde6332816708289a5db0d6c47fdc8`** (parent `4dabde62223d9aeedb67fc9e4ba1ba3380058284`); report/attestation là descendant trên feature branch/PR #298. Kiểm remote lease trước push tiếp; không sửa main/develop. [Report mới](ITERATION-6.md), [machine evidence](evidence/iteration-6-policy.json).

**Final clean validation:** `bc2c0f3a6abdb25e6db1de4c4e036b196b660870`, **55/55 PASS trong 58,66s**. Bao gồm ba Week4 modules, policy/CLI/worker/checkpoint, R1/R2/R3 binding/reuse và source history. Native pins bằng captured run; v8 byte pins bằng actual files. [Closeout/JUnit](evidence/iteration-6-closeout.json). Ruff check/format 571 files và contract pass; repository links còn đúng historical ZIP gap. Các jobs đã hoàn tất, không pending. Final publication chỉ append closeout/docs, không đổi native code.

- `scripts.exposure --evaluation-mode scenario --scenario-policy seamless-standard-v1` nay gọi compiler cũ; không cần assumptions JSON cho standard profile. Evidence-only vẫn default. Native batch pin resolved profile contents/digest vào scope/cell identity; mismatch mode/snapshot bị từ chối. Compiled query/audit giữ qua worker/replay/remediation; profile khác không reuse cache.
- Confirmed inventory composition defect: runtime proposal theo một witness không áp dụng cho cả baseline nhiều auth contexts. Candidate generation nay reuse `_check_edits`, giữ refusal thành unsupported. Verifier/overlay guard không đổi; cố ép proposal vẫn bị từ chối.
- **261 selected PASS/1 opt-in skip**, sau đó **1 raw opt-in PASS**; **43 discovery/remediation PASS**, scopes overlap. Clean native Week4 twice **36 PASS/2 NOT EXECUTED/0 FAIL**, semantic unchanged. Append **v8**, SHA-256 `989cac2c3a84077a3fe363c1ebe0fed1b8d253c67abd2dd5d3126cc962cf2b9e`; giữ v7/v6/v5. Final clean-source test completion được append ở publication descendant.
- Captures `reports/generated/awg-r04-policy-v1/`: evidence-only 12 indeterminate; standard 3 truncated-success/9 truncated-incomplete; explicit-four 2 complete-success/10 truncated-incomplete; injected False 2 truncated-success/10 truncated-incomplete. User DENA vốn có DA membership, không ordinary-user escalation. Standard 85 unique assumption keys; C/P unrated. Exact harness/full example query/source hashes đã publish.
- `reports/generated/awg-r04-policy-system-v1/`: DENA+GINO+non-DC Computer, 36 selected cells, 12 auto goals. 3 truncated-success/21 truncated-incomplete/12 indeterminate; 31.044 inventory pairs ngoài cohort. Khác profile với historical 1.600 cells, không cộng domain coverage. Remediation3sources×1goal,7candidates/1mixed-context unsupported,1tested: **4/5 programs cut,0proven disconnect; DENA vẫn reachable bằng bypass**, hai nguồn khác Unknown. Full native captures/packages giữ local, pin trong machine evidence.
- Separate profile `reports/generated/awg-r04-policy-profile-v1/`, `/workspace/scratch/b1f06964c680/awg-r04/policy-full-snapshot.pstats`: instrumented total120,718s; remediation101,524s; native generator12calls4,557s; policy3calls3,855s (extraction3,609s); canonicalization/deepcopy lớn. Cumulative times overlap; không claim speedup. Numeric basis chưa applicable nên chưa đo heavy rated cost.

### Nối tiếp

1. Capture/profile/raw jobs iteration6 đã complete; không có worker cần đợi. Giữ mọi `reports/generated/awg-r04-policy-*`, raw/snapshot và historical iteration5 artifacts. Code/profile đổi phải fresh namespace; không rebind cache bằng source pins giả.
2. **P0:** C-only new-goal applicability trên một verified witness, existing resolver + independent union-work oracle. Không transfer P/I, không nới context/owner/work-unit/source pins. Chưa bind basis thì chưa claim minimum cost.
3. **P1:** paired experiment giảm repeated immutable graph/facts fingerprint hoặc policy extraction copies theo profiler mới; full normalized decisions parity và R1/R2/R3 negatives bắt buộc. Không bỏ verifier/guard để tăng speed. Iteration6 chưa có optimized after-run.
4. **P1:** Computer/catalog coverage theo explicit facts, FCP/HasSession typed composition còn unsupported; fresh BloodHound comparator chưa có. Không giả biết approach riêng của mentor. Chưa production AND–OR khi bottleneck đang thiên về evidence preparation.
5. Historical R03 ZIP vẫn chưa materialize, link check có đúng gap đó. Dataset0Sessions/1host nonempty LocalAdmins; không giả enterprise/full-domain/all-catalog coverage.

Iteration5 và checkpoint dưới đây là lịch sử; gap scenario-policy CLI được supersede bởi iteration6.

---

## Iteration 5 — discovery tự động và resume đã thực thi

Native implementation/clean acceptance đã publish và test tại **`74166e7c7438153f2d882901426272ebb78e8a7b`**, preparation `bc7da0d86ddf6a88a594d1f38d5ccad7eeb6c78e`. CLI resume extension/source hashes và final captures ở [iteration-5-exposure.json](evidence/iteration-5-exposure.json); final publication là descendant trên `feat/awg-r04-product-readiness`, PR #298. Kiểm lại branch head/issue #297 trước khi push. Không sửa main/develop hoặc parent branches, không chờ B/CI.

- New `python -m scripts.exposure`: snapshot inventory, generated manifest/request, bounded batch, readable overview và optional native remediation. Important = observed DA/EA role SIDs, DC/RODC membership, Group admincount marker; all = non-boundary Group/Computer. Không đoán business criticality; không structural-reachability prune. User credential goals/business assets/cross-domain còn ngoài inventory.
- Target manifest 1.2 cho impact `Unknown`; 1.0/1.1 không được nhận giá trị mới, legacy serialization giữ nguyên. Unknown impact có witness không được ưu tiên thành `None`/an toàn. C/P vẫn cần native applicable basis; không invent.
- Full raw inventory: **2.590 eligible User/Computer sources, 649 all targets, 12 important targets**. Important product 31.080 pairs. User scenario 12 goals có 2 complete-success/10 truncated; evidence-only 12 indeterminate, bốn scenario gates là assumptions. Native code giữ source/context và Unknown/False/caps.
- **171 selected tests PASS** trên clean 74166e7, **16 binding/reuse PASS**; CLI resume extension **69 tests PASS**, gồm current exposure suite, native runner và executable CLI. Counts overlap, không whole-suite claim. V7 capture: 36 PASS/2 NOT EXECUTED/0 FAIL, deterministic, semantic bằng frozen v3 sau đúng normalization cũ; giữ V5/V6. JUnits và manifest đã lưu.
- Lượt system-evidence checkpoint-per-cell chủ động ngắt exit130 sau 675 cacheable cells, checkpoint 14.895.683 bytes, SHA-256 `63526018e4c718a09fc8d95317ac2597abc0fb5d48a2cd09d69359c826cbdddd`; không có final result và không claim toàn cohort pass. Giữ `reports/generated/awg-r04-exposure/system-evidence/`. Lỗi quy mô quan sát được: serialize lại nguyên cache sau mỗi cell.
- Native batch thêm `checkpoint_interval=1` mặc định giữ behavior cũ; exposure chọn 25. Chỉ đổi persistence, không đổi search/query/cost/proof. Có final flush; abrupt exit có thể chạy lại tới N cacheable cells (kể cả flush bị ngắt), incomplete cells vốn luôn cần chạy lại. Scope/binding validation vẫn giữ.
- Paired ABBA benchmark đã complete: cùng 20 sources × 12 goals/240 cells, median interval1 **48,321s** → interval25 **43,127s** (~10,75% reduction); 241→10 writes, logical 949,77→44,07MB/trial. Cả bốn full normalized dictionaries bằng nhau, chỉ loại elapsed và interval runtime fields. [Exact harness](evidence/checkpoint-benchmark.txt), [machine measurement](evidence/iteration-5-checkpoint-benchmark.json). Không chạy AWG tests/bench khác đồng thời; 2 trials/setting, không generalize.
- `system-grouped-v2` đã complete lượt 1.500 cells; **resume thật reuse 1.500 + chạy thêm 100 = 1.600 evaluated / 134 sources (100 Computers + 34 Users)**. **29.480 unrun**. Một success là declared initial DC-admin, zero actions/C=0, không lateral finding; 1.599 executed indeterminate. Prefix deterministic, không đại diện domain. Old reports/checkpoint được archive/hash trong `history/`; source/request binding guard giữ nguyên. CLI adapter code đã đổi để thêm resume, native bytes/pins không đổi và actual request equality được kiểm trước resume.
- Fresh mined intervention: inventory 5 candidates, thử 1 trên **1 User × 1 DC-admin goal**. Loại 3/3 observed programs nhưng **0 proven disconnected pairs, after Unknown**; 11 discovery goals khác ngoài remediation cohort. [Full public native package](evidence/iteration-5-intervention.json). Không gọi domain-wide reduction hoặc can thiệp tối ưu.

### Nối tiếp đúng trạng thái

1. Đọc [ITERATION-5.md](ITERATION-5.md), dùng current feature head và giữ mọi artifacts. Các jobs của iteration này đã complete/stopped, không có job cần đợi. Raw/snapshot không đổi; `reports/generated/awg-r04-exposure/` có all inventory, old interrupted run, ABBA, user-scenario-v2/user-evidence-v2, system-grouped-v2 + history. Không cộng 675 interrupted cells vào 1.600 cells.
2. **P0:** nối optional existing scenario-policy compiler vào workflow để giảm việc viết JSON assumptions, giữ evidence-only default, observed-False veto và forbidden predicates. Hiện mới hỗ trợ explicit assumptions JSON; không pretend profile compiler đã tự chạy trong CLI. Xem `src/engine/semantics/scenario_policy.py`, `scripts/exposure.py`, `src/engine/batch.py`. Không dùng blanket True/P midpoint.
3. **P1:** profile repeated static preparation/indexing ở batch trước khi pilot shared grounding/AND–OR. Hiện vẫn full search mỗi goal; checkpoint optimization không giải quyết hết. Bổ sung supported initial-capability profiles/catalog coverage và C-only new-goal applicability bằng independent oracles, không widen frozen authority.
4. Muốn chạy thêm đúng cohort hiện tại: dùng lại lệnh system ở ITERATION-5, output `reports/generated/awg-r04-exposure/system-grouped-v2`, thêm `--resume`, runtime max-cells tùy budget. Input snapshot dùng actual `data/processed/awg-r04/pilot-v2/snapshot.json`; source profiles/techniques/logical budgets phải giữ. Native code/config/source pins đổi sẽ từ chối cache; không rebind/fake pins. Tạo fresh namespace khi đổi semantics. Không quét tiếp hàng loạt Unknown chỉ để tăng count; đánh giá value của scenario-policy integration trước.
5. Fresh BH/CE comparator, FCP/HasSession typed composition, full numeric validation và historical R03 zip access còn open. Dataset có 0 Sessions, chỉ 1 host với nonempty LocalAdmins; không giả định full enterprise coverage hoặc biết approach riêng của mentor.

Các checkpoint phía dưới là lịch sử, được phần iteration 5 này supersede khi trạng thái khác nhau.

---

## Closeout đã thực thi — không còn failure đã quan sát chưa xử lý

Published/tested feature head: **`633bfaf6d5cc8d3dc1c610e4d39abfff3e92b353`**, PR #298. Chỉ push descendants trên `feat/awg-r04-product-readiness`; kiểm lại remote lease trước lần push tiếp theo. Không sửa main/develop hoặc parent branches.

- **15/15 Week 4 tests PASS**, 52,24s trên checkout sạch 633bfaf6, không sửa source/HEAD/tracked-file set trong khi chạy. Gồm checkout CRLF, exact source pins, hai lần semantic reproduction, independent verdicts, mutation negatives và demo smoke. [JUnit](evidence/iteration-4-week4.xml).
- Đối chiếu JUnit bằng exact node IDs: cả **14 failures của core-before-compat** có passing rerun trong 113 compatibility checks hoặc 15 Week 4 checks. Không cộng các suites có overlap và **không gọi whole suite pass**. [Machine closeout](evidence/iteration-4-closeout.json). 193 final-CPI tests chưa chạy đủ; numeric chỉ có một completed case như scope bên dưới.
- Independent raw audit không import AWG parser/evaluator/cost: **46.109 unique direct edges / 46.254 raw references**, đúng directed endpoints + raw/time provenance; 0 failures. Census của plain-SID endpoints (builtin được scope bằng observed raw Domain SID), 10.275 references ngoài phạm vi được đếm riêng. Ba mutation controls đều phát hiện lỗi. [Report](evidence/iteration-4-direct-raw.json), [executable exact harness](evidence/direct-raw-audit.txt). Không kiểm hết derived edges hoặc false-positive extras; không thay BloodHound comparator.
- Lượt oracle đầu có 19 “missing” do chính oracle chưa scope S-1-5-32-581/582. Đã xác minh canonical scoped nodes/edges; sửa oracle theo contract 1.3, không sửa graph. First failed report giữ local + SHA trong closeout. Không gọi đây là parser bug.
- Raw coverage limit: 100 Computers nhưng chỉ 1 có LocalAdmins không rỗng (5 direct references), 1 có PSRemoteUsers (2), không có Sessions. Ba RDU references có CanRDP Unknown vì thiếu UserRights; không có CanRDP positive edge. Dataset này không đủ kiểm chứng session-heavy hoặc multi-host lateral movement coverage.
- Full captured reports/first attempts vẫn giữ trong gitignored namespaces; public projections khai báo omissions/hashes. Không có test process đang chạy cần nối tại closeout. Historical R03 zip vẫn không tải được qua connector, repository link check còn đúng gap này.

### Tiếp tục từ đây

1. **P0 sản phẩm:** thử C-only portability cho `usable_identity_entitlement`, giữ exact work-unit/context/snapshot/source applicability; tuyệt đối không transfer impact hoặc probability basis. Dùng existing resolver, native replay, independent union-work oracle và một acquired-identity full-snapshot witness. Candidate min C phải khác `minimum_proven`; dừng nếu bất kỳ owner/context/provenance guard nào bị nới. Files khảo sát: `src/engine/ranking/{effort_registry,resolution_service,orchestration,verification}.py`, `scripts/research/final_cpi_effort_release.py`, `tests/test_identity_entitlement_goal.py`. Chưa thay các files này trong closeout.
2. **P1 hiệu năng:** profile controlled transport/canonicalization trên cùng completed numeric projection (native CLI ~311MB). Thử compact opt-in projection với exact witness/provenance references; giữ default full audit và normalized decision equality. Chưa có production transport optimization hoặc speed claim. Batch vẫn chạy từng goal; chỉ pilot shared grounding/AND–OR nếu repeated search thật sự chi phối sau preparation.
3. **P1 nghiệm thu đề bài:** fresh BloodHound/CE comparator cùng manifest; Docker/Neo4j chưa có tại đây. Raw forward audit không chứng minh comparator này. Full numeric successor acceptance/sensitivity và FCP/HasSession typed composition vẫn open. Không invent P hoặc tự nhận approach của mentor.

Tái lập audit (output mới; snapshot đã có hoặc dùng full build được hướng dẫn ở README):

```bash
python docs/research/awg-r04/evidence/direct-raw-audit.txt --repo . \
  --snapshot data/processed/awg-r04/pilot-v2/snapshot.json \
  --output reports/generated/new-direct-raw-audit.json
```

Các phần dưới là checkpoint lịch sử, đã được phần closeout này supersede khi có trạng thái khác nhau.

---

## Clean Week 4 successor — capture đã hoàn tất

Source preparation được thực thi sạch tại **`b2db836bdc784473556678dfe99e5f30805130dd`**, descendant của `d3b99be` và `ca3eceef`. Đây là recapture sau khi sửa POSIX path portability của test; không sửa file pins bằng tay. `week4_acceptance_runner --check-determinism` chạy hai lần: **36 PASS / 2 NOT EXECUTED / 0 FAIL**, semantic determinism verified. Hai NOT EXECUTED vẫn là legacy scope; không đổi thành raw acceptance dù R04 đã có raw evidence riêng.

- New `reports/research/week4-guided-exploration-acceptance-manifest-v6.json`: SHA-256 `eb919132cabcaf9c974bd6bfcb6dcb1938bb5ec74f992cced2984ce540d84548`, 330.431 bytes. Compact public source successor, full K-overlap evidence giữ nguyên, các evidence khác thay bằng exact digest; full 3,5MB capture local được giữ trong `reports/generated/awg-r04-acceptance-v6-posix/` và pin trong `execution.evidence_projection`. **Nguyên semantic payload của compact = full capture**; sau đúng existing prerequisite normalization, bằng nguyên frozen cases-v3. Không sửa oracle/outcomes/numeric basis. Generator tái lập: `evidence/acceptance-v6-generator.txt`. Capture đầu ở d3b vẫn giữ riêng, không ghi đè.
- V5 cũ SHA `08738fce5a0212c243235dacb1c3f6e1eb963d27b45568718f31546b73c074b0` được giữ, link trong execution metadata và test assertion. Source byte pins khớp actual current files, không normalize source để ép khớp.
- Đã có 113 compatibility checks pass trước clean capture. **Tiếp theo chạy lại cả ba `tests/test_week4_acceptance_{checkout_bytes,manifest,review_regressions}.py` trên published clean successor**, không sửa HEAD/source trong khi chạy. Chưa gọi whole suite pass. Lưu final JUnit và update issue sau completion.
- Không có core/numeric process cũ cần nối: core đã completed 14 failure trước compatibility; all-case numeric đã chủ động dừng sau một completed checkpoint. Các ghi chú “đang chạy” bên dưới là lịch sử. Raw/script/test artifacts giữ tại `/workspace/scratch/b1f06964c680/awg-r04` và các gitignored namespaces, không ghi đè.

---

## Iteration 4 follow-up — compatibility và stable acceptance

Published implementation hiện tại: `ca3eceef5c8db8ffc8efda38f122afbdb048f582` (code optimization `2006fa1`). Parent remote phải kiểm lại trước update-ref. Không sửa main/develop/parent branches.

- Full raw standalone remediation CLI đã exit 0; lặp lại toàn bộ raw CLI assertions + strict 4 report schemas đều pass. Bốn controls giữ bypass/Unknown/truncation đúng nghĩa. First pytest raw attempt 1 pass/1 fail vẫn giữ log, không có captured stderr đủ để chốt nguyên nhân.
- Fresh numeric v5 hoàn tất một projected case: 330 fully rated programs, 2.190 C units checked, CLI×2/API/orchestration equality. Cả 330 trên frontier; min C=2 trong candidate set, `minimum_proven=False`. Không phải full 16-case hoặc new v2 goal adoption. Đã dừng lượt all-case sau checkpoint đầu để ưu tiên failures; namespace hiện có không được ghi đè.
- After cProfile hoàn tất: 7 native searches cumulative 9,68s; canonicalization/hash/copies vẫn lớn. Instrumented elapsed không so với 6 unprofiled timing trials. [Machine profile](evidence/iteration-4-after-profile.json).
- Core rerun **đã kết thúc**: `pytest --ignore-glob='tests/test_final_cpi*'`: **14 fail, 3.145 pass, 11 skip, 88 subtests pass**, 1.450,49s. Không gọi whole suite pass. 8 failures do source packets stale; 6 Week 4 acceptance failures gồm source-byte pins cũ và checkout-dirty guard. Fresh isolated AS-REP/native acceptance đều pass. Đã xác minh original two-CLI mismatch khác DUY NHẤT `.reproducibility.tracked_changes`, semantic hash giống nhau; lỗi do sửa artifact khi test đang chạy, không nới guard.
- Đã append likelihood source v10 / scenario source v11 bằng generator hiện có, giữ SHA của cả 35 files cũ và numeric packets. Thêm `graph.py` vào authoritative coverage; giữ tampering/previous-history guards và refuse overwrite. **113 selected tests pass, 4 transport cases deselected** vì đã chạy trong core. Không thêm P/I adoption, không sửa expected oracle.
- Hai Week 4 tests đã chuyển sang successor manifest v6; source-preparation commit tiếp theo phải clean để capture fresh current observations. **v6 chưa được tạo/chốt tại checkpoint này**. Giữ nguyên v5 + cases-v3. Chỉ tạo v6 nếu normalized semantic payload đúng frozen v3, actual clean-source PASS; link previous v5 hash trong execution metadata. Public compact evidence được phép thay full traces bằng exact `evidence_digest` trừ K-overlap evidence mà test cần; full local capture phải giữ hash và đường dẫn.

### Nối tiếp ngay

1. Commit source preparation trên feature history; chạy clean `week4_acceptance_runner` twice, không sửa source/HEAD hoặc tracked-file set giữa các lượt. Chưa publish claim sạch/36 PASS cho tới khi quan sát được. Append v6 rồi chạy lại 3 Week 4 acceptance modules và source-successor negatives; không sửa historical expectations để lấy PASS.
2. Lưu completed JUnit/compact test record và update report/issue #297. Core-before-compat logs tại `/workspace/scratch/b1f06964c680/awg-r04/core-after-reuse.{log,xml}`; compatibility delta tại `compat-after.{log,xml}`. Không có full/core process còn chạy sau các completion trên.
3. P1: C-only portability cho acquired-identity goals (không tự transfer I/P), controlled canonicalization/transport optimization giữ exact digest/witness; batch vẫn **rerun từng goal** (`batch.py` loop), chưa shared traversal. Không gọi per-goal prep gain là shared multi-goal search. FCP/HasSession composition và fresh CE/BloodHound comparator còn open.

Historical zip R03 4,6MB vẫn thiếu trong môi trường; repository link check chưa xanh. Không fake archive. Không chạy `restore_checkout.py --git` khi còn unpublished edits. Full raw/static model không phải full-source/full-catalog acceptance.

---

## Iteration 4 — counterfactual reuse và public-index binding guard

Phần này supersede các ghi chú “chưa có optimization gain”/“sparse text materialization” bên dưới. Parent đã publish: `6e68621a83749b24170b9ab44b8e1368909123e6`; tiếp tục trên `feat/awg-r04-product-readiness`, PR #298, không sửa main/develop.

- Đã đo đủ 3 before + 3 after trên cùng immutable full-SEAMLESS snapshot/query/UUID/run/request IDs. Median pipeline **155,897 → 62,093s**, observed ratio 2,51×, normalized full packages bằng nhau cả 6. Chỉ loại ba metadata fields khai báo; giữ exact source pins trước/sau. Không generalize một cặp AS-REP thành mọi discovery/counterfactual.
- `remediation.py` reuse owned prepared cho witnesses/runtime-only edits, endpoint lookup cho structural check; structural/static edits vẫn isolated và validate. Independent verifier giữ nguyên.
- Confirmed thêm R3 public-index replacement có thể mint replay binding trên disabled canonical graph ở 6e; getter-only indices chặn replacement. Đây là API correctness, không remote exploit/arbitrary-Python sandbox claim.
- Fresh selected tests **101 passed / 2 raw-opt-in skipped**, F1 **78/78** không mismatch; source/tests Ruff và contract checks pass. [Iteration 4 report](ITERATION-4.md), [machine measurement](evidence/iteration-4-counterfactual.json), exact harness + input request + JUnit đã lưu trong repo.
- Whole pytest và hai raw opt-ins đã khởi chạy, **chưa có final completion tại checkpoint này**. Không suy pass từ progress dots. Logs/JUnits tại `/workspace/scratch/b1f06964c680/awg-r04/{full,raw}-after-reuse.*`; không khởi chạy cạnh tranh nếu process còn sống. Current executable production hashes bằng candidate `after.source_pins` trong machine measurement.
- Đã phục hồi đủ text/source/tests/historical JSON và 6 PNG + R02 zip theo Git blobs. Chỉ thiếu historical `docs/research/awg-r03-implementation/AWG-R03_Verification.zip` (4.624.303 bytes); `check_repository.py` báo đúng broken link này. Không sửa/fake archive hoặc historical attestation để làm xanh.

### Hành động nối tiếp theo thứ tự

1. Thu final whole/raw JUnit, phân loại lỗi thực và environmental/historical failures, sửa regressions nếu có. Các counts ở iteration 3/4 là selected và có overlap, không cộng thành suite total.
2. Sau khi publication tạo clean executable, chạy fresh numeric v5 delivery replay trong namespace mới (module default ghi historical `reports/research/issue267-wave2-delivery-v11.json`, **không ghi đè**). Giữ source/context/history pin checks; nếu drift cần successor evidence chứ không bỏ attestation.
3. Tăng coverage một foothold → v2 high-value goals, đo lại profile sau reuse; ưu tiên product gaps, không xây production AND–OR khi chưa có bottleneck evidence. FCP/HasSession composition và fresh BloodHound comparator vẫn open.

---

## Iteration 3 — goal implementation đã hoàn tất kiểm chứng chọn lọc

Phần này supersede trạng thái prototype chưa commit và execution disconnected phía dưới. Môi trường đã phục hồi; không có process cũ đang giữ checkout khi nối tiếp. Source base là `7cb7e7245318ee82ac6d0f9a64d6949608f6e93c`; kiểm current remote head trước khi sửa/push.

- Đã triển khai `UsableIdentityEntitlementGoal`, descriptor `semantic-goal/1.1.0`, strict decoder chung, query/checkpoint, batch `goal_kind`, schema/manifest 1.1 và successor `configs/targets/seamless-v2.json`. Legacy required-state/manifest 1.0 giữ serialization/scope cũ.
- Native adapter/replay xác minh cùng identity + context; replay còn từ chối goal ở Computer context khác dù final state có identity đó. I mapping cũ không tự transfer; exact review binding được giữ.
- Fresh completed suites: 25 new/public checks; 177 integration/binding; 434 broader semantics/query/search checks, không fail/error/skip. Counts có thể overlap; không cộng thành whole-suite claim. F1 frozen oracle 78/78, mismatch rỗng.
- Raw installer chạy lại, đủ 6 checksums. Full-snapshot v2 pilot: 3.370 nodes / 56.367 edges; 5 independent profiles × 3 goals × scenario/evidence-only. Scenario 5 successful cells/3 sources; evidence-only 1 initial DC-admin success. Không nạp numeric registry; không có production C/P/I adoption claim.
- `scripts/research/compare_identity_goals.py` tìm 5 enabled User GenericAll User MemberOf DA pairs mà source không sẵn reach DA qua membership. Chọn một pair trên full snapshot: new goal có witness reset → activation → membership, 7.490 expansions, complete; old actor goal dừng 10.000 expansions, truncated, không negative proof. Bảy runtime gates là declared assumptions. Không gọi old run là unreachable hoặc so hai goals khác nhau để claim speedup.
- Machine evidence: `evidence/iteration-3-goals.json`; README đã dùng explicit v2 manifest. R1/R2 fixes vẫn qua regressions.

### Việc đang làm tiếp

1. Giữ planner; đo before/after counterfactual preparation trên cùng snapshot/query/run/request IDs. Baseline isolated worktree `../baseline-7cb` còn nguyên, không sửa. Reuse owned prepared cho witness/runtime-only views; giữ independent verifier và binding checks. Chưa công bố remediation optimization gain.
2. Whole suite chưa có fresh completion. Checkout phục hồi hiện là sparse materialization (source/tests/scripts cần cho các suite trên đã kiểm Git blobs); nhiều historical docs/reports còn chưa materialize. Không sửa frozen files để qua attestation. Clone đầy đủ hoặc bổ sung exact missing blobs trước broad repository checks.
3. Chạy current numeric v5 examples và fresh comparator nếu environment đủ; không giả P, không inherit impact từ actor-specific goal. FCP/HasSession composition và BloodHound head-to-head còn open.

Python hiện tại: `/workspace/scratch/b1f06964c680/awg-r04/.venv/bin/python` (3.14.8). Nếu symlink interpreter mất sau environment recovery, `uv python install 3.14` đã phục hồi được; không cần clear venv. Không chạy `restore_checkout.py --git` vào worktree có edits chưa publish.

---

**Đọc [RESULTS.md](RESULTS.md) và [RECOVERY.md](RECOVERY.md) trước khi tiếp tục.** Production source đã publish tại 4f009856f9071f02083f42e62de0f0608802abdd; các kết quả sau đó ở worktree prototype chưa thành code trên PR.

- Giữ native planner, chưa xây production AND–OR. Measured gain discovery và full raw evidence đã publish.
- Goal-scope concern bên dưới đã **confirmed bằng finite counterexample**: original-actor membership có thể bỏ sót acquired usable DA/EA identity. Prototype riêng có 139 existing regression + 17 new checks pass; còn schema/I/CLI/full-raw validation.
- Remediation profile đã **hoàn tất**: copy/hash/preparation chi phối ca đã đo; bảy native searches khoảng 2,982s trong 145,607s instrumented. Chưa có optimization/before-after remediation.
- Whole suite 4f đã khởi chạy nhưng chưa có final JUnit khi exec-server mất transport. **Không claim pass/fail hoặc còn chạy.** P0 là khôi phục execution, giữ local edits, hoàn tất goal và verification.
- Không biết nguyên nhân transport loss; không gán OOM/product failure khi chưa có evidence. GitHub code/evidence ở PR đã an toàn; continuation schedule là backup, không phải lý do chờ.
- Materialization đã có đủ text/source/tests/docs/historical JSON; chỉ historical binary zip R03 còn không truy xuất được. Các todo “fetch text”, “chưa có profile” và “goal còn hypothesis” trong phần iteration-2 dưới đây là lịch sử, đã được supersede.

---

# Checkpoint iteration 2 (lịch sử)

Theo [issue #297](https://github.com/nairyuuu/ad-weighted-graph/issues/297), user đã ủy quyền implementation tự chủ, tải raw public, local validation và push code/PR. Không chờ TTS B hoặc CI GitHub billing. Không force-push hoặc ghi trực tiếp main/develop.

## Nhánh và baseline

- Nhánh công việc: `feat/awg-r04-product-readiness`.
- Parent implementation: #296 tại `996ee35d154051abee4eb3c940c91264b68cb5fb`, trên #295 tại `dc39c13ca5fc8a35dd640fbd9d28377b2832edf4`.
- Đề bài gốc đã đọc: `docs/00_todo.md`. Chưa biết approach cụ thể của mentor; không tự gán một phương pháp cho mentor.

## Đã thực hiện

### Iteration 2 — chạy thật trên full input và cải tiến workflow

- Native query materialization chỉ copy nodes; search reuse owned prepared graph và chỉ copy edge khi xuất witness. Callback/witness mutations không sửa graph cache.
- Đo tuần tự cùng Python/snapshot/request, một User × ba goals: bốn calls/revision (first use + ba warm). Median warm 5,7962 → 0,5124 giây; cả 12 cell traces khớp từng byte. Không suy rộng tỷ số 11,31× thành speedup toàn sản phẩm.
- F1 sau optimization: 78/78, không mismatch. Preparation/binding regression: 80 pass. Remediation regression: 47 pass, 1 raw opt-in skip; fresh batch/single-source CLI: 51 pass với JUnit hoàn chỉnh; đã chạy raw command tương đương riêng.
- CLI batch có `--source SOURCE_ID`, dùng `discover_source()` hiện có, không tái tạo query bằng defaults khác.
- Downloader `python -m scripts.download_seamless` đã tải thành công pinned public URL và kiểm toàn bộ archive/file hashes. Có offline `--archive` và refuse overwrite.
- Full snapshot đã dựng: 3.370 nodes, 56.367 edges, build đầu 13,216 giây. Full-input pilot chạy 5 independent profiles × 3 goals × scenario/evidence-only; không nạp numeric registries nên không dùng số cell unrated để suy ra numeric coverage của toàn dự án.
- `--discover-interventions N` đánh giá thêm mined candidates bằng executor/replay/rediscovery hiện có. Finite: 8 supported candidates, thử 6; counterexample cut 50% programs nhưng 0% pairs được giữ đúng. Full SEAMLESS: 4 inventory candidates, 3 supported được thử, 1 advisory unsupported giữ rõ; raw checks trước/sau pass. Runtime toàn vòng 327,44 giây, không phải tốc độ native query 0,51 giây.
- Full raw controls: shared-channel ngắt 1/1 pair trong declared AS-REP cohort; ineffective-membership giữ bypass; missing recovery là unknown; step cap là truncated. Ba mined candidates là admin-revoke, admin-channel, asrep-preauth; mỗi candidate ngắt 1/1 pair trong đúng cohort này, không claim domain-wide reduction.
- README đã thay trạng thái tuần cũ bằng lệnh synthetic/full-SEAMLESS/single-source/remediation thật và giới hạn hiện tại. Chi tiết máy đọc: [iteration-2.json](evidence/iteration-2.json).

Source của iteration 2 được pin bằng SHA-256 trong evidence; kiểm branch head/PR trước khi chạy tiếp. Baseline đo trước optimization là commit `025489a8a4486ff87c3e3142ffbfaa47675f961b`, đã chứa hai binding fixes bên dưới.

- Sửa R1: `_validated=True` không còn bỏ qua kiểm tra snapshot-facts binding.
- Sửa R2: replay chỉ dùng prepared view thuộc graph; supplied view phải khớp exact graph content và facts. Các view có thứ tự node/edge khác nhưng cùng canonical digest vẫn được chấp nhận.
- Guard bổ sung cho cặp supplied engine/canonical graph/facts không khớp.
- Thêm 11 regression cases tại `tests/test_prepared_graph_binding.py`; positive matched reuse không validate/copy lại graph trong từng replay.
- Đã chạy 428 selected core tests: tất cả pass (0 fail/error/skip); F1 78/78, 99 witnesses hợp lệ, minimum shared-work C=5. Đây không phải fresh whole-suite claim. Raw public đã khớp manifest; full-SEAMLESS product benchmark còn tiếp tục.
- Đã tải đủ SEAMLESS public từ `mike-nolan-councilman/Bloodhound_Data`, source commit `3febc4089421725f9527c187f78d064ad09d5158`.
- Archive `20210920185958_BloodHound.zip`: SHA-256 `b8e9f003dd51a98838be86d8f98b0844a19a7876aad0a81b525f19e110105813`.
- Sáu raw files, tổng 11.371.828 bytes, khớp toàn bộ manifest `data/samples/manifests/seamless-raw-v1.json`; snapshot `sha256:e0601d763eeea285d268ec9e468d321c50c9d7faba53c8e7442a2fcc4159c812`. Không sửa raw.

## Môi trường phiên đang chạy

- Checkout: `/workspace/scratch/b1f06964c680/awg-r04/repo` (đang bổ sung file của private repo qua GitHub API; Git blob/commit/tree được kiểm SHA).
- Raw: `data/raw/SEAMLESS` trong checkout, được gitignore.
- Python: `/workspace/scratch/b1f06964c680/awg-r02/.venv/bin/python`, CPython 3.14.8; dependencies pinned theo `requirements-tests.txt`.
- Evidence ngoài checkout: `/workspace/scratch/b1f06964c680/awg-r04/`; frozen R02 evidence ở `/workspace/scratch/b1f06964c680/awg-r02`.
- Trigger tiếp tục đã đặt 05:04 ngày 18/10/2026, giờ Việt Nam. Nếu phiên hiện tại còn chạy, không ghi cạnh tranh trên cùng checkout.

## Việc tiếp theo, theo thứ tự

1. Hoàn tất fetch những historical reports còn thiếu để chạy whole suite/source attestation. Lượt whole suite đầu có nhiều missing-file setup errors, không được gọi là production regressions hoặc pass. Không overwrite historical manifests/reports để che drift.
2. Kết thúc fresh batch/source CLI regressions và broader local checks. Một log batch cũ bị thiếu summary dù tool báo exit 0; chỉ dùng fresh JUnit hoàn chỉnh làm bằng chứng.
3. Profile riêng remediation 327 giây; process `profile_remediation.py` ở scratch đã khởi chạy, chưa kết luận bottleneck khi chưa có pstats. Không so runtime này trực tiếp với historical 704 giây vì có thêm mined interventions và khác code/environment.
4. Chạy current scoped numeric release/query examples với basis thật; phân biệt intentionally unrated pilot với missing numeric coverage. Preserve P assumptions, no midpoint/calibration claims. Kiểm tra cách làm successor attestation nếu source drift.
5. Kiểm định một product-goal concern mới: DA/EA manifest hiện yêu cầu membership của `__RESOLVED_ACTOR__` (foothold ban đầu). Cần finite counterexample U reset/activate V rồi V có DA để biết default discovery có bỏ sót acquired-identity entitlement không. Đây còn là hypothesis, không tự sửa existential goal/ranking proof khi chưa có repro/test.
6. Hoàn thiện báo cáo VN đối chiếu đề bài và alternatives, evidence-backed backlog. Giữ native planner; chưa có bằng chứng cần AND–OR production. Broad shared traversal chỉ pilot nếu profile sau reuse chứng minh enumeration/goal reruns chi phối.
7. Push checkpoints tiếp. Không dừng do CI billing/B; không tự merge main/develop. Full BloodHound fresh comparator chưa chạy, Docker không có trong môi trường; ghi đúng giới hạn.

Không dừng chỉ vì CI billing hoặc thiếu teammate. Không tự nhận global optimum khi search truncated; không invent P, không coi expert assumptions là observed probabilities. Trước khi tiếp tục, đọc current PR/branch state và file này ở revision mới nhất để tránh làm lại việc đã xong.

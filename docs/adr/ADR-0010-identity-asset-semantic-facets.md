# ADR-0010: Identity-Asset semantic facets va structural node kinds

- Ngay: 2026-09-21
- Trang thai: Accepted
- Nguoi de xuat: @Lolavine777 (TTS A)
- Reviewer: @nairyuuu (TTS B)
- Issue / PR: Refs #62, #41, #72, PR #65, PR #67

## Boi canh

De tai la Identity-Asset Graph, trong khi structural contract M2 da freeze sau kinds `User`, `Computer`, `Group`, `Domain`, `OU` va `GPO`.
Research #62/PR #65 dinh nghia `Identity`, `Asset`, `PrivilegeContainer` va `ControlPlane` la semantic facets, dong thoi tach `security_labels` khoi role.
Can co decision authoritative de tranh doi node kind thanh role hoac tao contract change ngam.

## Cac phuong an

| Phuong an | Loi ich | Chi phi / han che | Bang chung |
| --- | --- | --- | --- |
| Thay node kinds bang Identity/Asset | Ten graph phan anh ngay business semantics | Mat AD object structure, khong bieu dien duoc multi-role va pha contract | #62, #41 |
| Materialize roles/security_labels vao contract M2 ngay | Serialized graph mang du semantic metadata | Can versioned contract, migration, validator, fixture va parser change chua duoc phe duyet | #41, PR #67 |
| Giu structural kinds, dung semantic facets ngoai contract | Bao toan canonical schema va mo hinh hoa multi-role ro rang | Consumers can tu ap dung classification cho den khi co contract change rieng | #62, PR #65 |

## Quyet dinh va he qua

Chon phuong an 3.

1. Canonical structural node kinds van la `User`, `Computer`, `Group`, `Domain`, `OU`, `GPO`.
   `Identity`, `Asset`, `PrivilegeContainer` va `ControlPlane` la semantic facets, khong phai replacement node kinds.
2. Semantic role la flat multi-label model.
   Mot node co the mang nhieu role va khong ep primary/secondary hierarchy.
   Vi du, `Computer` co the dong thoi la `Asset` va `Identity` vi machine account la security principal.
3. `security_labels` la chieu truc giao voi semantic role.
   `Tier0`, `Privileged`, `HighValue`, `CrownJewel`, `PartialSecrets` khong duoc tron voi `roles` va khong la node kinds.
4. Domain Controller la structural `Computer` co `ControlPlane` semantics.
   Phan loai Writable DC/RODC phai dua tren predicates co evidence nhu SID/RID, UAC va PRP context khi co, khong dua mu vao collector flag.
5. M2 khong materialize `roles` hoac `security_labels` vao `configs/contract.yml`, serialized graph, parser hay engine.
   Ontology hien tai la research/interpretation layer cho EDA, target selection va reporting, khong phai schema contract ngam.
6. Bat ky materialization nao trong tuong lai phai la contract decision rieng co version, migration/backward compatibility, validator, fixture, parser/engine impact va acceptance tests.

He qua:

- Ten Identity-Asset Graph duoc giai thich bang semantic classification ma van bao toan AD object topology.
- Consumers khong duoc gia dinh `node.kind == role` hoac suy dien security label tu role.
- ADR nay khong thay doi contract, parser, engine, node/edge taxonomy hay weighting.

## Kiem chung va dieu kien xem lai

- Kiem chung bang `uv run pytest`, Ruff, yamllint, `uv run python scripts/check_contract.py`, `uv run python scripts/check_repository.py` va `git diff --check`.
- Tieu chi thanh cong: documentation phan dinh ro structural schema, semantic facet va security value ma khong doi serialized contract.
- Dieu kien xem lai: M3/M4 can materialized role/label de target selection hoac choke-point reporting va co de xuat contract versioned duoc chap thuan.

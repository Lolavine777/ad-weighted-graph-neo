# ADR-0009: Direct MemberOf storage va transitive resolution

- Ngay: 2026-09-21
- Trang thai: Accepted
- Nguoi de xuat: @Lolavine777 (TTS A)
- Reviewer: @nairyuuu (TTS B)
- Issue / PR: Refs #53, #44, #45, #47, #71, PR #54, PR #69

## Boi canh

Nested group membership la authorization relationship co tinh bac cau.
Raw snapshot va BloodHound A/B baseline ghi nhan direct `MemberOf` evidence, trong khi SEAMLESS cho thay nesting depth toi 5 va 119 chain dai hon mot cap.
Canonical graph can giu raw provenance ma van ho tro effective membership cho query, traversal va host-access inference.

## Cac phuong an

| Phuong an | Loi ich | Chi phi / han che | Bang chung |
| --- | --- | --- | --- |
| Chi materialize direct MemberOf | Bao toan raw evidence, provenance va topology | Query/inference can resolve closure khi can | #53, PR #54 |
| Materialize direct va transitive MemberOf | Don gian hoa mot so query | Tao shortcut khong co raw evidence, duplicate path va provenance tong hop phuc tap | #53 |
| Bo MemberOf khoi graph, chi cache effective membership | Co the toi uu mot use case | Mat topology, audit trail va kha nang truy van chain | Contract M1 va #53 |

## Quyet dinh va he qua

Chon phuong an 1.

1. Canonical structural graph chi materialize direct `MemberOf` relationship co raw evidence va direct provenance.
   Khong tao shortcut/transitive `MemberOf` edge trong graph canonical.
2. Effective/transitive membership la ket qua cua traversal, query hoac inference layer theo use case.
   Host-access inference co the dung effective membership de suy ra `AdminTo`, `CanRDP` hoac `CanPSRemote` khi co host-bound evidence theo ADR-0003.
   Ket qua nay phai giu membership chain/provenance va khong thay the direct evidence trong snapshot.
3. Cycle guard la bat buoc cho traversal va inference.
   Multiple inheritance paths duoc giu nhu cac direct chain rieng; output suy luan cung logical privilege co the deduplicate, nhung provenance phai giu tat ca chain lien quan.
4. Unresolved SID, missing group record hoac collection failure la `unknown`/incomplete evidence, khong phai false membership va khong tao traversable edge gia tao.
5. Cross-domain/FSP traversal phai giu canonical identity va domain scope.
   Khong strip prefix hay lam phang namespace khi resolve membership.
6. Direct-only la structural/provenance decision.
   No khong gan fixed unit weight, khong quyet dinh production weighting va khong thay doi `maut_v1`.
7. BloodHound A/B baseline la evidence ingestion lich su cho direct storage.
   SEAMLESS EDA la evidence ve do sau can ho tro, nhung BloodHound parity/reconciliation cho SEAMLESS chua duoc chung minh.

He qua:

- Graph size va audit trail phan anh raw relationship thay vi closure suy dien.
- Traversal/inference phai co ownership ro rang cho closure, cycle termination, domain boundary va provenance chain.
- ADR nay khong implement GraphBuilder, host-access inference hay weighting.

## Kiem chung va dieu kien xem lai

- Kiem chung bang `tests/test_group_nesting.py`, `uv run pytest`, Ruff, yamllint, `uv run python scripts/check_contract.py`, `uv run python scripts/check_repository.py` va `git diff --check`.
- Tieu chi thanh cong: direct edge giu provenance 1:1 voi raw evidence; cycle/diamond/cross-domain/incomplete-evidence cases ket thuc an toan va khong sinh shortcut structural edge.
- Dieu kien xem lai: contract versioned thay doi de bieu dien derived relationship, hoac co use case performance duoc do luong can cache closure ma van bao toan chain/provenance.

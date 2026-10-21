# ADR-0007: Enterprise topology va chien luoc danh gia telemetry doc lap

- Ngay: 2026-09-21
- Trang thai: Accepted
- Nguoi de xuat: @Lolavine777 (TTS A)
- Reviewer: @nairyuuu (TTS B)
- Issue / PR: #55, #58, #63, PR #59
- Thay the: [ADR-0006](ADR-0006-two-dataset-evaluation-framework.md)

## Boi canh

Mentor review Week 1 ket luan Dataset A/GOAD NORTH va Dataset B/`ad_sampledata` khong dat yeu cau ve quy mo va tinh dai dien de lam tap danh gia chinh.
PR #59 da dua vao snapshot SEAMLESS va corpus security logs, trong khi #58 va #63 da xac lap ranh gioi Attack Semantics.

## Cac phuong an

| Phuong an | Loi ich | Chi phi / han che | Bang chung |
| --- | --- | --- | --- |
| Giu A/B lam primary evaluation | Co baseline collector va da mien da co | Khong dat quy mo va tinh dai dien sau mentor review | #55 |
| Dung SEAMLESS va join telemetry theo entity | Co the tao cau chuyen end-to-end | Khong co chung environment, identity va time context de join hop le | #58, #63 |
| SEAMLESS topology chinh va telemetry doc lap | Tach bang chung structural khoi activity/observability, giu A/B cho baseline | Can danh gia semantic rieng va chua co SEAMLESS BloodHound parity | #55, #58, #63, PR #59 |

## Quyet dinh va he qua

1. **SEAMLESS la tap du lieu structural/topology chinh tu M2 tro di.**
   Day la nguon de tao va danh gia do phu topology cua structural graph tinh, group nesting, privilege concentration va kha nang mo rong cua pipeline.
2. **A/NORTH va B/`ad_sampledata` la baseline lich su, khong phai primary evaluation datasets.**
   A duoc giu cho regression, so sanh collector va BloodHound reference baseline.
   B duoc giu cho regression, multi-domain/parser robustness va BloodHound reference baseline.
3. **Security logs la nguon nghien cuu telemetry doc lap.**
   Chung phuc vu Attack Semantics, expected telemetry va observability/detection-coverage o cap technique/relation class.
   Khong duoc entity-level join telemetry voi SEAMLESS khi hai nguon khac environment hoac khong co cung identity/time context.
4. **Structural graph van la static.**
   Telemetry nam o semantic/evaluation layer, khong tao, xoa hay xac nhan structural edge trong topology SEAMLESS.
5. Ba khai niem phai luon tach bach:

   ```text
   Structural Relationship != Attack Technique != Observed Activity
   ```

   Tu do, `ExpectedTelemetry != ObservedActivity != StructuralRelationship != ConfirmedAttack`.
6. **BloodHound parity/reconciliation cho SEAMLESS chua duoc chung minh.**
   Baseline BloodHound hien co chi ap dung cho A/B.
   Bat ky so sanh SEAMLESS voi BloodHound trong tuong lai phai dung cung snapshot, scope va ghi ro cac chenh lech.

### He qua

- M2+ uu tien reproducible SEAMLESS structural evaluation va manifest/EDA cua no.
- Ket qua A/B van co gia tri regression, collector comparison va robustness, nhung khong duoc suy rong thanh dai dien enterprise.
- Telemetry doc lap chi ho tro ket luan ve expected evidence va observability o cap lop.
  No khong chung minh mot path SEAMLESS da duoc khai thac, khong xac nhan attack, va khong tu dong hieu chinh weighting.
- ADR nay khong thay doi `configs/contract.yml`, parser/engine behavior hay weighting implementation.

## Kiem chung va dieu kien xem lai

- Kiem chung tai lieu bang `uv run python scripts/check_repository.py`, `uv run python scripts/check_contract.py`, `uv run pytest`, Ruff, yamllint va `git diff --check`.
- Dieu kien xem lai: co cung environment va identity/time context cho telemetry-structure correlation, hoac co SEAMLESS BloodHound import/reconciliation tren cung snapshot va scope.

- Chua co BloodHound import parity/reconciliation cho SEAMLESS.
- Telemetry va SEAMLESS khong co chung environment de danh gia quan he nhan qua o cap thuc the.
- Weighting production van can quy trinh danh gia rieng, co version va evidence phu hop.

## Lich su

ADR-0006 duoc giu nguyen nhu evidence cua khung danh gia A/B truoc mentor review Week 1.

# ADR-0004: Xu ly Synthetic Goal Edge va Dieu kien kep DCSync

- Ngay: 2026-09-14 (Cap nhat trang thai: 2026-09-22)
- Trang thai: Rejected / Superseded by ADR-0008 and Graph Contract 1.0.0
- Nguoi de xuat: @Lolavine777 (TTS A)
- Reviewer: @nairyuuu (TTS B)
- Issue / PR: Refs #3, Refs #4, Refs #5, Refs #83
- Thay the boi: [ADR-0008](ADR-0008-structural-graph-attack-semantics-layering.md), Graph Contract 1.0.0 (`configs/contract.yml`)

> [!WARNING]
> **Supersession & Deprecation Notice (Reconciled under Issue #83):**
> Quyết định sơ bộ này bị bác bỏ và thay thế (Rejected / Superseded), không phải là kiến trúc hay kế hoạch triển khai hiện hành:
> 1. **Không có cạnh cấu trúc `ControlsDomain`, `DumpNTDS` hoặc `DCSync`:** Graph Contract 1.0.0 đóng băng danh mục cạnh cấu trúc ở đúng 8 quan hệ (`MemberOf`, `AdminTo`, `HasSession`, `GenericAll`, `WriteDacl`, `ForceChangePassword`, `CanRDP`, `CanPSRemote`).
>    DCSync hoặc trích xuất NTDS, nếu được mô hình hóa trong tương lai, thuộc tầng semantic/runtime theo ADR-0008, không phải cạnh trên đồ thị cấu trúc.
>    Catalog hiện hành chưa có DCSync transition; đây là architectural boundary, không phải bằng chứng implementation.
> 2. **Nghiêm cấm trọng số bằng không ($W = 0.0$):** Graph Contract 1.0.0 quy định toàn bộ cạnh có thể duyệt (traversable edge) bắt buộc phải có trọng số hữu hạn $W \ge 1.0$.
>    Công cụ kiểm tra hợp đồng (`scripts/check_contract.py`) từ chối tuyệt đối trọng số bằng không.
> 3. **Mục tiêu chiến dịch (Goal State):** Trạng thái chiếm quyền Crown Jewels được mô hình hóa ở tầng truy vấn thuật toán tìm đường hoặc vị từ ngữ nghĩa (query predicates), không tạo cạnh nhân tạo $W = 0$ trên đồ thị cấu trúc.
> ADR này được lưu giữ như một ghi chép lịch sử về thảo luận giai đoạn đầu và không được sử dụng làm đặc tả kỹ thuật cho bất kỳ mô-đun nào.

## Boi canh

Trong quá trình phân tích đường tấn công thử nghiệm từ máy trạm tới Crown Jewels, chúng tôi nhận thấy hai vấn đề mang tính ngữ nghĩa bảo mật cần được minh định rõ:
1. **Quan hệ Domain Controller tới Domain Admins:**
   Một số đồ thị thử nghiệm gán cạnh `WINTERFELL --AdminTo--> DOMAIN ADMINS`.
   Tuy nhiên, trong mô hình bảo mật Windows, một `Computer` không thể có quyền `AdminTo` lên một `Group`.
   Đây thực chất là một giả định logic: chiếm được máy chủ Domain Controller (quyền SYSTEM trên DC) đồng nghĩa với việc chiếm được toàn bộ cơ sở dữ liệu xác thực `NTDS.dit`, từ đó kiểm soát hoàn toàn nhóm Domain Admins.
2. **Quyền hạn của kỹ thuật DCSync:**
   Kỹ thuật DCSync đòi hỏi chủ thể phải có đồng thời hai quyền mở rộng trên đối tượng Domain: `DS-Replication-Get-Changes` và `DS-Replication-Get-Changes-All`.
   Nếu chỉ đưa một trong hai quyền vào contract, hệ thống sẽ tạo ra một giả định ẩn (implicit assumption) thiếu chặt chẽ.

## Cac phuong an

| Phuong an | Loi ich | Chi phi / han che | Bang chung |
| --- | --- | --- | --- |
| 1. Giu nguyen AdminTo cho DC -> DA va tach le GetChanges | Don gian, khong can sua schema | Sai lech ban chat an ninh AD, gay hieu nham trong luan van | Prototype ban dau |
| 2. Minh dinh Synthetic Goal Edge va gop quy tac kep DCSync | Chuan xac tuyet doi ve mat nghiep vu va hoc thuat | Can giai thich ro trong bao cao va luan van | Microsoft MS-DRSR spec, SpecterOps research |

## Quyet dinh va he qua

Chúng ta chọn phương án 2:

1. **Chuẩn hóa Synthetic Goal Edge:**
   - Cạnh nối từ Domain Controller tới nhóm mục tiêu `Domain Admins` được định nghĩa chính thức là **Synthetic Goal Edge** (với định danh logic `ControlsDomain` hoặc `DumpNTDS`).
   - Cạnh này được ấn định chi phí cố định là $W = 0.0$ (chi phí bằng không biểu diễn bước chuyển logic tức thời sau khi đã kiểm soát Domain Controller) để thuật toán Dijkstra kết thúc chuỗi tấn công tại Crown Jewels mà không làm sai lệch tổng chi phí nỗ lực và rủi ro tích lũy của chuỗi tấn công thực tế.
   - Luận văn và tài liệu kiến trúc phải ghi chú rõ: Đây là cạnh nhân tạo biểu diễn mục tiêu hoàn thành chiến dịch, không phải là thuộc tính DACL tự nhiên của AD.
2. **Chuẩn hóa Điều kiện kép DCSync:**
   - Trong giai đoạn mở rộng M2/M3, kỹ thuật DCSync được biểu diễn bằng một cạnh duy nhất mang tên `DCSync` (thay vì hai cạnh rời rạc).
   - Điều kiện bắt buộc để parser sinh cạnh `DCSync`:
     $$\text{DCSync} \iff \text{GetChanges} \land \text{GetChangesAll}$$
   - Trong tập dữ liệu pilot NORTH, hai quyền này đồng xuất hiện (co-occur) trên nhóm Administrators, do đó logic này hoàn toàn bảo toàn tính tương thích.

Hệ quả:
- Tài liệu hóa minh bạch trong thesis và `docs/research/taxonomy.md`.
- Tránh việc reviewer phản biện về tính bất hợp lý của quan hệ `Computer --AdminTo--> Group`.

## Kiem chung va dieu kien xem lai

- Lệnh kiểm tra: `python scripts/check_contract.py`.
- Tiêu chí thành công: Tài liệu taxonomy và báo cáo nghiên cứu phản ánh chính xác phân định Synthetic Edge.
- Điều kiện xem lại: Khi bài toán mở rộng sang mô hình nhiều miền (Multi-domain Forest) có Read-Only Domain Controller (RODC).

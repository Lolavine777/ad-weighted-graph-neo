# Quy trình đóng góp

## Nhánh và tích hợp

| Nhánh | Mục đích | Đích PR |
| --- | --- | --- |
| `main` | Bản sạch, kiểm tra đạt, chạy được theo README | Nhận từ `develop` |
| `develop` | Tích hợp công việc chung, CI phải đạt | `main` khi nghiệm thu mốc |
| `feature/ttsA-taxonomy` | Ví dụ nghiên cứu taxonomy của A | `develop` |
| `feature/ttsB-parser` | Ví dụ parser của B | `develop` |
| `feature/dijkstra-engine` | Ví dụ thuật toán | `develop` |
| `fix/<issue>-<slug>`, `docs/<issue>-<slug>` | Sửa lỗi, tài liệu | `develop` |

Không push trực tiếp lên `main`/`develop` sau lần khởi tạo. Mỗi nhánh xử lý một issue hoặc nhóm thay đổi nhỏ liên quan. Dùng merge commit cho `develop → main` để giữ lịch sử đồng bộ; có thể squash PR tính năng. Sau nghiệm thu, xóa nhánh tính năng đã merge.

```powershell
git switch develop
git pull --ff-only origin develop
git switch -c feature/ttsA-taxonomy
# Sửa file, chạy kiểm tra trong README; chọn rõ file cần stage.
git add docs/templates/taxonomy.md
git commit -m "docs(taxonomy): clarify edge prerequisites"
git push -u origin feature/ttsA-taxonomy
```

Mở PR với base `develop`, điền [PR template](.github/pull_request_template.md). Commit dùng `feat`, `fix`, `docs`, `test`, `chore` hoặc `refactor`, scope tùy chọn. Khi cần cập nhật nhánh tính năng đã chia sẻ, merge `origin/develop`; tránh rewrite lịch sử chung.

## Issue, review và hoàn thành

1. Chọn việc trong [backlog](docs/05_backlog.md) hoặc [Project Board (Kanban)](https://github.com/users/nairyuuu/projects/3/views/1?system_template=kanban), tạo issue bằng form Task/Research/Bug/Experiment.
2. Gán assignee A hoặc B, milestone, labels và tiêu chí nghiệm thu có thể kiểm tra. Điền người review bằng tài khoản GitHub thực tế.
3. Tạo nhánh; mở draft PR sớm nếu cần thống nhất contract. Thay đổi `configs/contract.yml` phải cập nhật tài liệu và tests liên quan trong cùng PR.
4. Người còn lại review tính đúng, dữ liệu, lập luận và bằng chứng chạy. CI đạt và ít nhất một approval trước khi merge.
5. Cập nhật worklog bằng kết quả thực tế, link issue/PR và hạn chế. Khi PR vào `develop` đã merge và nghiệm thu đạt, đóng issue thủ công nếu GitHub chưa tự đóng.

`Closes #...` tự đóng issue khi PR vào **default branch**. Nếu default branch là `main`, PR vào `develop` nên dùng `Refs #...` và đóng issue sau nghiệm thu; tránh hiểu nhầm cơ chế tự đóng.

Definition of Done cho một công việc:

- Đạt acceptance criteria, có lệnh tái lập hoặc tài liệu/bằng chứng phù hợp.
- Tests kiểm tra hành vi được thêm khi thay đổi logic; trường hợp biên được cân nhắc.
- CI đạt, review chéo xong, thảo luận đã xử lý.
- Contract/tài liệu/worklog cập nhật nếu bị ảnh hưởng.
- File đưa lên GitHub không chứa dữ liệu AD thực, thông tin định danh hay bí mật truy cập.

### AI Code Review với GitHub Copilot

GitHub Copilot được cấu hình để hỗ trợ review tự động dựa trên repository instructions ([.github/copilot-instructions.md](.github/copilot-instructions.md)) và các checklist theo từng khu vực ([.github/instructions/](.github/instructions)).

- **Cách yêu cầu review**: Trên PR, thêm `@copilot` vào danh sách reviewers hoặc chạy `gh pr edit <PR> --add-reviewer @copilot` (yêu cầu tài khoản/tổ chức có gói Copilot Pro/Business/Enterprise). Với gói Copilot Free, thành viên có thể dùng Copilot Chat trong IDE (`/review`) để tự đối chiếu instructions trước khi push.
- **Vai trò khuyến nghị**: Nhận xét từ Copilot có tính chất hỗ trợ cảnh báo sớm (advisory) về contract drift, directionality, provenance và edge cases.
- **Quy tắc phê duyệt**: Copilot tuyệt đối không thay thế human review. Merge vào `develop` bắt buộc phải có approval từ maintainer phụ trách (@Lolavine777 hoặc @nairyuuu).
- **Phản hồi và tinh chỉnh**: Nếu Copilot đưa ra feedback chưa phù hợp hoặc bỏ sót rủi ro, ghi nhận để tinh chỉnh instruction tương ứng trong `.github/instructions/`.



## Phối hợp hai người

A (@Lolavine777) chủ trì taxonomy, trọng số, giải thích đường đi và khuyến nghị. B (@nairyuuu) chủ trì môi trường, parser, engine và đo hiệu năng. Cả hai cùng duyệt schema, trọng số và kết quả đối chứng. Người chủ trì không phải người duy nhất được sửa thư mục; báo trên issue trước khi cùng sửa `contract.yml` hoặc tài liệu chung.

Notebook chỉ dùng khám phá. Xóa output có dữ liệu trước khi commit; chuyển logic ổn định sang `src/`. CI hiện chưa thực thi notebook. Dữ liệu thật và kết quả suy ra giữ tại các thư mục local được mô tả trong [data/README.md](data/README.md).

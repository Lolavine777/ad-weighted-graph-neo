# Thiết lập GitHub và CI

Các file workflow/template đã nằm trong repo. Chúng hoạt động trên GitHub sau khi được commit và push. Tạo labels, milestones, branch rules và đổi default branch là thiết lập trên GitHub, không tự phát sinh từ các file này.

## Khởi tạo lần đầu

Tại thời điểm dựng khung, checkout local chưa có commit và đang mang tên `master`. Với repo mới, sau khi xem lại các file và chọn những file cần đưa lên Git:

```powershell
git branch -m main
git add .github configs src tests scripts docs data notebooks reports README.md CONTRIBUTING.md .gitignore .gitattributes .editorconfig .python-version .env.example .yamllint.yml pyproject.toml requirements.txt requirements-dev.txt compose.yml
git diff --cached --stat
git commit -m "chore: bootstrap project documentation and CI"
git push -u origin main
git switch -c develop
git push -u origin develop
```

Chỉ dùng chuỗi lệnh này khi remote chưa có lịch sử cần hợp nhất. Nếu remote đã có commit, fetch và đối chiếu trước; không force push. Đặt `main` làm default branch trong Settings. Kể từ đây, làm việc qua nhánh riêng và PR theo [CONTRIBUTING](../CONTRIBUTING.md).

## CI đã chuẩn bị

| Workflow/job | Trigger | Kiểm tra |
| --- | --- | --- |
| `CI / quality` | PR vào main/develop; push main/develop; chạy tay | Python 3.14, Ruff lint/format, YAML, liên kết Markdown local, đường dẫn dữ liệu riêng |
| `CI / tests (ubuntu-latest)` | Như trên | Contract/profile và fixture tổng hợp, tests của validator |
| `CI / tests (windows-latest)` | Như trên | Cùng bộ tests trên Windows của nhóm |
| `CI / compose` | Như trên | Compose hợp lệ, không khởi động DB |
| `Branch policy / main-source` | PR vào main hoặc develop | PR vào main phải từ develop cùng repo |
| Dependabot | Hàng tuần sau khi cấu hình vào default branch | PR nâng dependency Python và GitHub Actions |

Không lọc bỏ thay đổi docs, để required checks luôn trả kết quả. CI chỉ có quyền đọc nội dung, không cần secrets, không thực thi dữ liệu AD thật. Workflow branch policy dùng `pull_request`, không chạy mã PR với token có quyền ghi. Dependabot tạo PR; không tự merge.

Kiểm tra đường dẫn riêng chỉ chặn file nằm tại vị trí quy định, không phải công cụ dò mọi bí mật hay nhận diện nội dung nhạy cảm. Kiểm tra Markdown chỉ xác nhận đích file của inline link local; không kiểm tra URL Internet, heading anchors hoặc toàn bộ cú pháp Markdown. YAML lint không thay thế bộ kiểm tra ngữ nghĩa GitHub Actions. Tests hiện xác minh nền tảng contract; CI xanh chưa có nghĩa thuật toán AD đã hoàn thành.

## GitHub Copilot Code Review

Bên cạnh các kiểm tra tự động của CI, repo tích hợp GitHub Copilot Code Review làm lớp rà soát sơ bộ:
- **Hướng dẫn toàn repo**: [copilot-instructions.md](../.github/copilot-instructions.md) định hình bối cảnh kiến trúc và các nguyên tắc thẩm định bảo mật AD.
- **Checklist theo khu vực**: Thư mục [.github/instructions/](../.github/instructions) chứa các hướng dẫn chuyên sâu theo từng đường dẫn (`configs/contract.yml`, `src/parser/`, `src/engine/`, `docs/`, `tests/`).
- **Phân tầng kiểm soát PR**:
  1. *CI Automation*: Lint cú pháp, format, contract validator, unit tests.
  2. *Copilot AI Review*: Advisory review, đối chiếu acceptance criteria, phát hiện nguy cơ false-positive/false-negative attack path và contract drift (yêu cầu gói Copilot Pro/Business/Enterprise trên GitHub.com; với gói Free, thực hiện review qua Copilot Chat trong IDE).
  3. *Human Review*: Quyết định cuối cùng, xác nhận ngữ nghĩa bảo mật AD và cấp approval trước khi merge.


## Cấu hình một lần trên GitHub


1. Bật Actions và cho phép các action chính thức được dùng trong workflow.
2. Push khung và để CI chạy lần đầu để tên checks xuất hiện.
3. Bảo vệ cả `main` và `develop`: yêu cầu PR, ít nhất 1 approval, giải quyết mọi conversation, bỏ approval cũ khi có commit mới; không cho force push hoặc xóa nhánh.
4. Chọn required checks đúng tên hiển thị: `quality`, `tests (ubuntu-latest)`, `tests (windows-latest)`, `compose`, `main-source`. Workflow branch policy trả đạt cho PR vào develop. Trên main, yêu cầu thêm nhánh cập nhật theo chính sách nhóm.
5. Bật merge commit để merge `develop → main`; cho phép squash cho feature PR. Không bật yêu cầu lịch sử tuyến tính nếu dùng merge commit.
6. Tạo milestones `M0`–`M5` và hạn theo ngày bắt đầu; tạo labels trong bảng dưới. Gán tài khoản thật cho A/B. Chỉ thêm CODEOWNERS khi đã có tên tài khoản chính xác và quyền truy cập phù hợp.

Khả năng bảo vệ nhánh phụ thuộc loại repo/gói GitHub. Nếu tài khoản không hỗ trợ, giữ quy tắc review thủ công và ghi giới hạn trong worklog.

| Nhóm label | Tên đề xuất |
| --- | --- |
| Loại việc | `task`, `research`, `bug`, `experiment`, `documentation` |
| Khu vực | `area:data`, `area:parser`, `area:engine`, `area:weights`, `area:infra`, `area:report` |
| Ưu tiên | `priority:P0`, `priority:P1`, `priority:P2` |
| Trở ngại | `blocked` |

Các form không gán label/tài khoản giả. Sau khi tạo labels, gán trên issue hoặc bổ sung defaults vào form. Quản lý trạng thái trên [Project Board (Kanban)](https://github.com/users/nairyuuu/projects/3/views/1?system_template=kanban): Backlog → Ready → In progress → In review → Done; trạng thái blocked dùng label và giải thích trong issue. Mỗi người chỉ giữ 1–2 việc In progress.

## Nâng dependency và mở rộng CI

Review PR Dependabot, chạy bộ kiểm tra rồi merge vào develop. Vì config nằm trên main, các cập nhật cấu hình Dependabot có hiệu lực sau lần đưa lên main. Nâng image Neo4j bằng PR riêng, kiểm tra tương thích và ghi phiên bản đã thử. Khi có parser/engine, thêm tests hành vi và integration raw giả lập → đường đi. Chỉ thêm integration Neo4j khi có phần mềm thực sự phụ thuộc DB.

Nguồn: [workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax), [issue forms](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms), [protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches), [Dependabot options](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference).

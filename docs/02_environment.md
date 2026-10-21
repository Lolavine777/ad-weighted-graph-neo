# Môi trường thống nhất

Python 3.14.x là phiên bản bắt buộc. Cài dependencies từ `requirements-dev.txt` cho phát triển/CI; `requirements.txt` chứa thư viện runtime dự kiến. Chưa có CLI nghiệp vụ. Dùng các lệnh kiểm tra trong [README](../README.md).

Nếu đã có `uv`, có thể dùng `uv python install 3.14` rồi `uv venv --python 3.14 .venv` và `uv pip install --python .venv -r requirements-dev.txt`. Không cần activate môi trường khi gọi trực tiếp Python trong `.venv`.

Các dependency runtime/development và phụ thuộc gián tiếp hiện tại đều được khóa để hai người dùng cùng bộ công cụ; `colorama` chỉ cài trên Windows. Khi thay đổi, cập nhật file requirements trong một PR và chạy CI, bao gồm dependency gián tiếp mới phát sinh. Ghi `python --version` và `python -m pip freeze` trong manifest thực nghiệm để lưu môi trường thực tế và bản vá Python.

## Neo4j tùy chọn

Compose cung cấp Neo4j Community riêng cho đồ thị của đề tài. Đây không phải bộ cài BloodHound. Không giả định bản BloodHound đang dùng tương thích với database này; chốt phiên bản và cách cài BloodHound theo hướng dẫn chính thức của phiên bản đã chọn.

1. Cài Docker Desktop với Linux containers (Windows) hoặc Docker Engine và Compose plugin.
2. Nếu chưa có `.env`, sao chép `.env.example`. Nếu đã có, thêm khóa thiếu bằng tay, giữ các giá trị cũ.
3. Đặt `NEO4J_PASSWORD` riêng, tối thiểu 12 ký tự; không dùng mật khẩu thật của AD. Giữ `.env` local.

```powershell
docker compose --profile graph config --quiet
docker compose --profile graph up -d --wait
docker compose --profile graph ps
```

Truy cập `http://localhost:7474`, tài khoản `neo4j`, mật khẩu trong `.env`; Bolt tại `bolt://localhost:7687`. Cổng chỉ bind loopback. Dữ liệu DB nằm trong named volume `neo4j_data` do Compose quản lý. Dừng bằng `docker compose --profile graph down`; volume được giữ. Không dùng `down -v` khi còn dữ liệu cần giữ.

Image được cố định trong `compose.yml`; ghi image digest thực tế trong manifest. Thay đổi mật khẩu khởi tạo trong `.env` không đổi mật khẩu database đã tồn tại; dùng chức năng đổi mật khẩu của Neo4j. Nếu cổng đang bận, thống nhất port mới trong Compose và URI của nhóm.

Canonical Graph JSON có thể chiếu phần cấu trúc node/edge vào Neo4j bằng `python scripts/import_canonical_graph.py <validated-graph.json> --structural-projection` trên database rỗng, với `NEO4J_PASSWORD` trong môi trường cục bộ. Importer xác thực toàn bộ JSON trước khi ghi, giữ edge provenance/derivation dưới dạng JSON properties, và báo cáo rõ số lượng/trạng thái/digest của `assessments` không import. Các assessment không traversable vẫn ở file canonical JSON; cần đọc file đó để xem uncertainty evidence. Đây là projection của graph dự án, không phải BloodHound CE import.

## Tiếp nhận dữ liệu

Đặt JSON gốc tại `data/raw/<dataset-id>/`. Ghi checksum, snapshot, nguồn, quyền sử dụng và phiên bản export trong data inventory nội bộ; chỉ đưa bản mô tả đã kiểm tra lên repo. Không sửa raw tại chỗ. `data/processed/` là đầu ra có thể dựng lại. CI dùng `data/samples/` hoàn toàn tổng hợp và không cần Neo4j hoặc dữ liệu riêng.

Trong tuần 1 cần ghi: Python/OS, BloodHound edition/version, collector/export version, Neo4j image nếu dùng, cách import, số lượng node/cạnh và lỗi import. Không suy đoán GOADv2 export và dữ liệu ẩn danh có cùng schema.

## BloodHound CE baseline độc lập

Để phục vụ đối chứng baseline ở M1 theo [Issue #32](https://github.com/nairyuuu/ad-weighted-graph/issues/32) và báo cáo [bloodhound-import-baseline.md](research/bloodhound-import-baseline.md), môi trường BloodHound CE tách biệt được cung cấp tại `deploy/bloodhound/compose.yml`.

1. Khởi chạy stack BloodHound CE (bao gồm `bloodhound` v9.7.0, `neo4j:4.4.42` và `postgres:18`):
```powershell
docker compose -f deploy/bloodhound/compose.yml config --quiet
docker compose -f deploy/bloodhound/compose.yml up -d
```
2. Đăng nhập tại `http://localhost:8080`, mật khẩu khởi tạo được in trong log:
```powershell
docker logs bloodhound-baseline-bloodhound-1
```
3. Sau khi hoàn thành đo đạc baseline, dọn sạch stack và volume:
```powershell
docker compose -f deploy/bloodhound/compose.yml down -v
```
4. Để chạy kiểm định baseline nhanh và đối soát số liệu tự động:
```powershell
.venv\Scripts\python scripts/bloodhound_baseline_audit.py
```

Tham khảo: [Neo4j Docker chính thức](https://neo4j.com/docs/operations-manual/current/docker/introduction/), [BloodHound CE deployment](https://bloodhound.specterops.io/get-started/quickstart/community-edition-quickstart).

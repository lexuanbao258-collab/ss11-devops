# 4 bài tập Nginx — DevOps SS11

Bộ bài độc lập: reverse proxy, định tuyến theo đường dẫn, HTTPS Let's Encrypt và tối ưu Nginx. Cấu hình dành cho Nginx trên Linux; có thể kiểm thử bằng Docker Desktop từ Windows PowerShell mà không sửa Nginx hoặc service cũ.

## Cấu trúc repository

```text
ss11/
├── .gitignore
├── README.md
├── bai-01-reverse-proxy/
│   ├── default.conf
│   └── README.md
├── bai-02-api-gateway/
│   ├── default.conf
│   └── README.md
├── bai-03-https/
│   ├── install-certbot.sh
│   ├── https.conf
│   └── README.md
├── bai-04-nginx-optimization/
│   ├── nginx.conf
│   └── README.md
└── tests/
    ├── test_nginx.py
    └── results.json
```

| Bài | Nội dung | Tài liệu |
| --- | --- | --- |
| 1 | Một địa chỉ công khai chuyển request đến frontend cổng 3000 | [Reverse proxy](bai-01-reverse-proxy/README.md) |
| 2 | `/api/` đến backend 8080, các đường dẫn còn lại đến frontend 3000 | [API gateway](bai-02-api-gateway/README.md) |
| 3 | Redirect HTTP sang HTTPS, Certbot và gia hạn | [HTTPS](bai-03-https/README.md) |
| 4 | Giới hạn body 10m, gzip và reload | [Optimization](bai-04-nginx-optimization/README.md) |

## Cách kiểm thử trên Windows PowerShell

Điều kiện: Docker Desktop đang chạy Linux containers, lệnh `docker` và Python 3 có trong PATH. Lần đầu cần Internet để tải image chính thức `nginx:stable` và `python:3.13-slim`. Không cần cài thư viện Python.

```powershell
Set-Location D:\rikkei\Devops\ss11
docker info
python tests/test_nginx.py
```

Script tự kiểm tra syntax, tạo backend giả lập ở 3000/8080 và lần lượt chạy từng bài. Các container có tên `ss11-<mã ngẫu nhiên>-...`; cổng Windows được Docker chọn ngẫu nhiên, chỉ bind `127.0.0.1`. Script dọn các container của chính nó trong `finally`, ghi bằng chứng vào [tests/results.json](tests/results.json); không xóa image. Nếu cưỡng bức tắt Python, có thể cần dọn đúng các container `ss11-...` của lần chạy đó.

Nginx dùng `--network container:<backend>`: hai container dùng chung network namespace, nên upstream `127.0.0.1`/`localhost` truy cập được backend giả lập. Đây là bố trí kiểm thử, không phải yêu cầu triển khai production. Container Docker bình thường có localhost riêng; muốn gọi ứng dụng trên Windows cần `host.docker.internal` và bản cấu hình dành riêng cho Docker. Không sửa cấu hình gốc chỉ để đánh đồng hai môi trường.

### Chỉ kiểm tra syntax

Chạy tại thư mục gốc:

```powershell
$root = (Get-Location).Path
docker run --rm -v "${root}/bai-01-reverse-proxy/default.conf:/etc/nginx/conf.d/default.conf:ro" nginx:stable nginx -t
docker run --rm -v "${root}/bai-02-api-gateway/default.conf:/etc/nginx/conf.d/default.conf:ro" nginx:stable nginx -t
docker run --rm -v "${root}/bai-04-nginx-optimization/nginx.conf:/etc/nginx/nginx.conf:ro" nginx:stable nginx -t
```

Bài 1/2/3 chứa `server`, phải được include bên trong `http`; image Nginx chính thức đã include `/etc/nginx/conf.d/*.conf`. Bài 4 là cấu hình toàn bộ, mount vào `/etc/nginx/nginx.conf`. Không dùng `nginx -c default.conf` cho một file chỉ chứa `server`.

`nginx -t` kiểm tra cấu hình và các file tham chiếu, không chứng minh upstream hoạt động. Bài 3 gốc cần file chứng chỉ thật; xem giới hạn kiểm thử bên dưới. Không khởi động cả bốn cấu hình trên cùng cổng 80.

### Kiểm thử request thực tế

Script xác minh:

- Bài 1: frontend, URI/query, header; upstream dừng trả 502.
- Bài 2: `/api/` đến 8080, `/cart` đến 3000, giữ URI/query và header; `/api` redirect đến `/api/`.
- Bài 3: file gốc báo thiếu chứng chỉ; bản tạm bỏ TLS qua syntax, redirect 301 và proxy backend bằng HTTP. Không kiểm tra HTTPS thật.
- Bài 4: gzip 5 MIME yêu cầu và HTML (XML dùng MIME mapping tạm `application/xml`); không nén file nhỏ hoặc client không yêu cầu; body 10 MiB không bị 413, vượt 1 byte bị 413; syntax trước reload và request sau reload.
- Script cài Certbot: `bash -n`; không chạy apt hoặc xin chứng chỉ.

## Kết quả kiểm tra thực tế

Đã chạy Docker thực tế lúc 2026-10-12 11:55:43 (UTC+7), dùng **Nginx 1.30.5**, **26/26 bước kiểm tra đạt**, tiến trình Python exit code 0. Một bước là xác nhận lỗi thiếu chứng chỉ dự kiến, không phải HTTPS đầy đủ thành công.

- Syntax: bài 1, 2, 4 qua `nginx -t`; script Certbot qua `bash -n`.
- Request: frontend/API đúng upstream, giữ URI/query và header; dừng frontend trả 502; `/api` redirect 301 `/api/`.
- HTTPS: file gốc không qua `nginx -t` vì chưa có `fullchain.pem`. Bản tạm bỏ TLS qua syntax, HTTP redirect 301 và proxy backend; chưa có phiên TLS thật.
- Optimization: gzip sáu loại nội dung, kiểm tra không nén response nhỏ/client không yêu cầu; body 10.485.760 byte trả 405 từ static handler (không bị 413), 10.485.761 byte trả 413; test trước reload và GET sau reload thành công.
- Đã dọn sạch các container kiểm thử `ss11-...`; không chạy service cũ hoặc workflow GitHub Actions.

Bằng chứng chi tiết: [tests/results.json](tests/results.json). Chạy lại sẽ cập nhật file này; image tag có thể thay đổi, nên kết quả ghi cả phiên bản và image ID.

## Giới hạn triển khai

Chưa có domain/VPS được xác nhận, nên chưa kiểm chứng DNS, firewall Internet, chứng chỉ được trình duyệt tin cậy, cấp/gia hạn Let's Encrypt hoặc systemd trên Ubuntu. Không có private key hay chứng chỉ giả trong repository. `.gitignore` chặn các tên private key thông dụng; luôn kiểm tra `git diff --cached` trước commit.

Các backend trong bài 1/2/3 là dịch vụ do người triển khai chuẩn bị. Backend nên chỉ mở loopback hoặc mạng nội bộ; không cần công khai 3000/8080. Bộ bài không thêm workflow GitHub Actions.

## Lệnh Git

Thư mục này ban đầu chưa có Git repository. Chạy `git init` nếu vẫn chưa có repository; nếu đã có thì bỏ lệnh đó.

```powershell
git init
git add README.md .gitignore bai-01-reverse-proxy bai-02-api-gateway bai-03-https bai-04-nginx-optimization tests
git diff --cached --stat
git diff --cached
git commit -m "Complete four Nginx exercises with isolated Docker tests"
git branch -M main
# Chỉ thêm remote nếu chưa có; thay URL bằng repository của bạn.
git remote add origin https://github.com/YOUR_USER/YOUR_REPOSITORY.git
git push -u origin main
```

Không chạy push tự động. Nếu remote đã có lịch sử, đồng bộ lịch sử trước khi push; không dùng force push để ghi đè.

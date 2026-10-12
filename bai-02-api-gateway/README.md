# Bài 2 — Path-based Routing / API Gateway

## 1. Mục tiêu

Một server cổng 80 định tuyến `/api/` đến backend `localhost:8080`, các đường dẫn còn lại đến frontend `localhost:3000`, giữ nguyên URI API và chuyển bốn header.

## 2. Bối cảnh nghiệp vụ

Trang thương mại điện tử dùng `/cart` để hiển thị giao diện và `/api/orders` để lấy dữ liệu đơn hàng. Frontend và backend cùng máy Linux; người dùng chỉ cần một hostname công khai.

## 3. Giải thích giải pháp

Path-based routing chọn upstream theo đường dẫn request. Trong hai prefix location này, Nginx chọn tiền tố khớp dài hơn: `/api/` cụ thể hơn `/`. Request `/api/orders?limit=2` tới backend 8080; `/cart` tới frontend 3000.

Đây là chức năng định tuyến cơ bản của API gateway. Cấu hình này chưa có xác thực, rate limit hoặc quản lý API; các chức năng đó ngoài yêu cầu bài.

## 4. Nội dung cấu hình

File: [default.conf](default.conf), được include trong `http`.

```nginx
server {
    listen 80;
    server_name _;

    location /api/ {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## 5. Giải thích directive quan trọng

| Directive / header | Ý nghĩa |
| --- | --- |
| `listen 80` | Nhận HTTP cổng 80. |
| `server_name _` | Tên quy ước lab; server duy nhất nhận request. |
| `location /api/` | Chọn backend cho đường dẫn có tiền tố `/api/`. |
| `location /` | Chọn frontend cho các đường dẫn còn lại. |
| `Host $host` | Cho upstream biết hostname người dùng truy cập, phục vụ virtual host và URL. |
| `X-Real-IP $remote_addr` | IP peer trực tiếp của Nginx. |
| `X-Forwarded-For $proxy_add_x_forwarded_for` | Chuỗi IP qua các proxy, nối thêm peer hiện tại. |
| `X-Forwarded-Proto $scheme` | Giao thức Nginx nhận từ client, trong bài này là `http`. |

Backend thường thấy IP của Nginx ở kết nối TCP. `X-Forwarded-For` giúp truy vết khách, thống kê, log hoặc rate limit khi backend đã cấu hình proxy tin cậy. Không lấy IP đầu chuỗi một cách mù quáng vì client có thể tự gửi header này.

Nếu Nginx đứng sau một bộ kết thúc TLS khác, `$scheme` thể hiện kết nối đến Nginx; cần thiết kế trust boundary riêng để biết giao thức ban đầu. Bài này giả định Nginx là điểm vào trực tiếp.

### Dấu `/` cuối proxy_pass

Với `location /api/`, không có rewrite hoặc biến trong `proxy_pass`:

| Cấu hình | Request từ client | URI đến backend |
| --- | --- | --- |
| `proxy_pass http://localhost:8080;` | `/api/orders?limit=2` | `/api/orders?limit=2` |
| `proxy_pass http://localhost:8080/;` | `/api/orders?limit=2` | `/orders?limit=2` |

Có `/` cuối nghĩa là URL upstream có phần URI `/`; Nginx thay prefix location đã khớp bằng URI đó. Không có `/` cuối giữ prefix `/api/` như yêu cầu. Quy tắc này không nên suy rộng cho mọi cấu hình có regex location, rewrite hoặc biến.

## 6. Hướng dẫn kiểm thử

Từ thư mục gốc:

```powershell
$root = (Get-Location).Path
docker run --rm -v "${root}/bai-02-api-gateway/default.conf:/etc/nginx/conf.d/default.conf:ro" nginx:stable nginx -t
python tests/test_nginx.py
```

Script kiểm tra upstream cổng 8080 cho `/api/orders?limit=2`, cổng 3000 cho `/cart`; kiểm tra URI, query, cả bốn header và nối chuỗi X-Forwarded-For. Backend giả lập hỗ trợ loopback IPv4/IPv6 để tên `localhost` hoạt động với cả hai.

Trên Linux lab đã có ứng dụng thật:

```bash
curl -i http://127.0.0.1/api/orders?limit=2
curl -i http://127.0.0.1/cart
curl -i http://127.0.0.1/api
```

Muốn kiểm tra header upstream, xem log hoặc endpoint echo của ứng dụng trong lab; `curl` tới Nginx chỉ thấy response, không tự chứng minh mọi header upstream.

## 7. Đáp án câu hỏi bẫy

- **`/api` không có slash vào frontend?** Với prefix location kết thúc `/` có `proxy_pass`, Nginx tự redirect 301 `/api` đến `/api/`. Test kiểm tra hành vi này.
- **`/api-v2/orders` vào backend?** Không khớp `/api/`, nên vào frontend.
- **Đổi thứ tự hai location làm đổi kết quả?** Không đối với hai prefix location đơn giản này; tiền tố dài hơn được ưu tiên.
- **Backend vốn chỉ có `/orders` thì sao?** Cấu hình yêu cầu giữ `/api/`, nên backend phải phục vụ `/api/orders`. Xóa prefix sẽ khác đề.
- **Có thể tin X-Forwarded-For do khách gửi?** Không. Chỉ tin chuỗi proxy theo chính sách backend, không dùng header tùy ý để quyết định quyền truy cập.

## 8. Kết quả kiểm tra thực tế

Đã chạy thực tế lúc 2026-10-12 11:55:43 (UTC+7), Nginx 1.30.5 trong Docker:

- `nginx -t`: thành công.
- `/api/orders?limit=2`: HTTP 200 từ backend 8080, giữ nguyên URI/query.
- `/cart`: HTTP 200 từ frontend 3000.
- Cả hai route có Host, X-Real-IP, X-Forwarded-For nối thêm peer và X-Forwarded-Proto bằng `http`.
- `/api` không có slash: HTTP 301 tới `/api/`.

Xem các mục `bai-02-api-gateway` và `Bai 2` trong [results.json](../tests/results.json). Không kiểm chứng backend production hoặc chính sách trusted proxy của ứng dụng thật.

## 9. Kết luận

Hai prefix location chia một địa chỉ công khai thành frontend và API. Điểm cần nhớ là bỏ dấu `/` cuối `proxy_pass` của API để không mất tiền tố `/api/`.

Nguồn: [Nginx proxy_pass](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_pass), [Nginx location](https://nginx.org/en/docs/http/ngx_http_core_module.html#location).

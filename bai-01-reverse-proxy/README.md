# Bài 1 — Nginx Reverse Proxy

## 1. Mục tiêu

Nginx nhận HTTP ở cổng 80, chuyển mọi đường dẫn đến frontend `127.0.0.1:3000` và chuyển tiếp các header cần thiết.

## 2. Bối cảnh nghiệp vụ

Một cửa hàng có frontend chạy cổng 3000 trên cùng máy Linux với Nginx. Khách truy cập `http://shop.example/` qua Nginx; cổng ứng dụng không cần công khai ra Internet.

## 3. Giải thích giải pháp

Reverse proxy là máy chủ đứng trước ứng dụng, nhận request từ client rồi gửi tiếp đến ứng dụng phía sau, cuối cùng trả response cho client. Trình duyệt dùng cổng 80 mặc định cho URL `http://`, nên khách không phải gõ `:3000`. Ứng dụng vẫn chạy ở 3000; Nginx kết nối đến cổng đó thay khách.

## 4. Nội dung cấu hình

File: [default.conf](default.conf), là một `server` được include trong khối `http`.

```nginx
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

## 5. Giải thích directive quan trọng

| Directive | Ý nghĩa |
| --- | --- |
| `listen 80` | Nhận kết nối HTTP tại cổng 80 của máy chạy Nginx. |
| `server_name _` | Tên quy ước cho server lab; không phải wildcard đặc biệt. Trong bài chỉ có một server nên request vào server này. |
| `location /` | Khớp tiền tố `/`, xử lý mọi đường dẫn trong cấu hình này. |
| `proxy_pass http://127.0.0.1:3000` | Gửi request đến frontend trong cùng network namespace; không có phần URI nên giữ đường dẫn và query trong trường hợp này. |
| `proxy_set_header Host $host` | Chuyển hostname gốc đã được Nginx xác định cho frontend; `$host` thường không gồm port. |
| `X-Real-IP $remote_addr` | Địa chỉ peer trực tiếp kết nối đến Nginx. |
| `X-Forwarded-For $proxy_add_x_forwarded_for` | Giữ chuỗi header hiện có rồi nối thêm địa chỉ peer. |

`Host` hữu ích cho virtual host và tạo URL; các header IP giúp log địa chỉ khách qua proxy. Nếu có proxy khác phía trước, `$remote_addr` có thể là IP proxy đó.

## 6. Hướng dẫn kiểm thử

Tại thư mục gốc trên Windows:

```powershell
$root = (Get-Location).Path
docker run --rm -v "${root}/bai-01-reverse-proxy/default.conf:/etc/nginx/conf.d/default.conf:ro" nginx:stable nginx -t
python tests/test_nginx.py
```

Lệnh đầu chỉ kiểm tra syntax. Script thứ hai chạy Nginx và backend giả lập chung network namespace, gửi GET `/products?q=1`, kiểm tra response đến cổng 3000 và ba header, rồi tắt backend để kiểm tra 502. Nó chạy tuần tự cả bộ bài; xem [hướng dẫn tổng](../README.md).

Trên Linux lab đã có frontend và Nginx dùng cấu hình này:

```bash
curl -i http://127.0.0.1/products?q=1
sudo nginx -t
sudo systemctl reload nginx
```

Dừng frontend bằng công cụ quản lý ứng dụng đang sử dụng, gửi lại request rồi khởi động frontend lại. Không dừng service cũ trên máy học chỉ để thử bài; dùng backend Docker giả lập.

## 7. Đáp án câu hỏi bẫy

- **Frontend ngừng hoạt động thì sao?** Nếu cổng 3000 từ chối kết nối, Nginx thường trả `502 Bad Gateway`; error log thường có `connect() failed ... while connecting to upstream`. Timeout có thể dẫn đến `504 Gateway Timeout`, không phải mọi sự cố upstream đều 502.
- **Cổng 80 có thay thế cổng 3000 của ứng dụng?** Không. Nginx mở 80, frontend vẫn mở 3000.
- **Localhost trong Docker là Windows?** Không. Chỉ dùng được cấu hình nguyên bản khi upstream cùng network namespace; bộ test bố trí đúng điều kiện này.
- **Syntax thành công có nghĩa frontend chạy?** Không. `nginx -t` không kiểm tra HTTP đến ứng dụng.
- **Có thể tin mọi IP trong X-Forwarded-For?** Không. Client có thể gửi header giả; backend chỉ tin proxy đã cấu hình và xử lý chuỗi IP theo ranh giới proxy tin cậy.

## 8. Kết quả kiểm tra thực tế

Đã chạy thực tế lúc 2026-10-12 11:55:43 (UTC+7), Nginx 1.30.5 trong Docker:

- `nginx -t`: thành công.
- GET `/products?q=1`: HTTP 200, backend giả lập xác nhận cổng 3000, URI/query và ba header đúng.
- Chỉ dừng tiến trình frontend giả lập, giữ Nginx hoạt động: request tiếp theo trả HTTP 502.

Đối chiếu các mục `bai-01-reverse-proxy` và `Bai 1` trong [results.json](../tests/results.json). Đây là request đến backend giả lập, chưa phải frontend production.

## 9. Kết luận

Một điểm vào HTTP tại cổng 80 giúp truy cập frontend cổng 3000 bằng URL thông thường. Vận hành cần theo dõi cả Nginx và upstream vì frontend dừng có thể tạo lỗi 502.

Nguồn: [Nginx proxy module](https://nginx.org/en/docs/http/ngx_http_proxy_module.html).

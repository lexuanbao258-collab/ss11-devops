# Bài 4 — Nginx Optimization

## 1. Mục tiêu

Giới hạn request body 10m, bật gzip cho nội dung văn bản và thực hiện quy trình kiểm tra cấu hình trước reload.

## 2. Bối cảnh nghiệp vụ

Cửa hàng cần giới hạn dung lượng upload và giảm dữ liệu truyền khi tải HTML, CSS, JavaScript hoặc JSON. Khi đổi cấu hình production, cần duy trì phục vụ các kết nối đang xử lý.

## 3. Giải thích giải pháp

Cấu hình toàn bộ Nginx đặt giới hạn body và gzip ở mức `http`, áp dụng cho server bên trong. Server static tối thiểu giúp kiểm thử độc lập, không cần thêm backend hay sửa bài cũ. Đây là cấu hình lab, không phải file để ghi đè Nginx production đang có nhiều site.

Gzip nén response trước khi gửi nếu client hỗ trợ, qua `Accept-Encoding: gzip`. Nginx trả `Content-Encoding: gzip`; client giải nén để nhận nội dung gốc. Kích thước truyền giảm nhưng tiêu tốn CPU; mức 5 là giá trị yêu cầu bài, không phải kết luận tối ưu cho mọi workload.

## 4. Nội dung cấu hình

File: [nginx.conf](nginx.conf), gồm `events` và `http`, mount vào `/etc/nginx/nginx.conf` khi dùng Docker.

```nginx
worker_processes auto;

error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    access_log /var/log/nginx/access.log;
    sendfile on;

    client_max_body_size 10m;

    gzip on;
    gzip_comp_level 5;
    gzip_min_length 1024;
    gzip_vary on;
    gzip_types text/css text/plain application/javascript application/json application/xml;

    server {
        listen 80;
        server_name _;
        root /usr/share/nginx/html;

        location / {
            try_files $uri $uri/ =404;
        }
    }
}
```

## 5. Giải thích directive quan trọng

| Directive | Ý nghĩa |
| --- | --- |
| `worker_processes auto` | Chọn số worker theo CPU nhận biết được. |
| `worker_connections 1024` | Giới hạn kết nối mỗi worker; không phải cam kết số người dùng thực tế. |
| `error_log`, `access_log`, `pid` | Đường dẫn log và PID dùng cho vận hành. |
| `include /etc/nginx/mime.types` | Gán Content-Type theo phần mở rộng file; gzip xét MIME của response. |
| `default_type application/octet-stream` | Kiểu mặc định nếu không có MIME phù hợp. |
| `sendfile on` | Cho phép cơ chế sendfile khi phục vụ file. |
| `client_max_body_size 10m` | Giới hạn toàn bộ body request ở 10 MiB = 10.485.760 byte. Vượt giới hạn thường trả HTTP 413. |
| `gzip on` | Bật nén gzip theo điều kiện client/response. |
| `gzip_comp_level 5` | Mức nén 5; mức cao hơn thường tốn CPU hơn. |
| `gzip_min_length 1024` | Ngưỡng kích thước response, được xét từ Content-Length. Response chunked không có độ dài cần đánh giá riêng. |
| `gzip_vary on` | Thêm `Vary: Accept-Encoding` để cache phân biệt representation theo khả năng nén của client. |
| `gzip_types ...` | Cho phép nén năm MIME được yêu cầu. `text/html` đã được Nginx hỗ trợ mặc định khi bật gzip, không cần lặp lại. |
| `root`, `try_files` | Đọc static file trong thư mục gốc, trả 404 nếu không tìm thấy. |
| `listen 80`, `server_name _` | Một server HTTP độc lập cho lab. |

Lưu ý MIME: image Nginx được kiểm thử gán file `.xml` thành `text/xml`, khác `application/xml` trong danh sách yêu cầu. Gzip xét Content-Type thực tế, không chỉ phần mở rộng; file `.xml` với `text/xml` không được nén bởi danh sách này. Bộ test mount bản `mime.types` tạm chỉ đổi XML thành `application/xml` để kiểm tra đúng MIME của đề, giữ nguyên `nginx.conf` gốc. Production cần đối chiếu MIME thực tế nếu muốn nén XML static.

Giới hạn 10m áp dụng cho body, không chỉ riêng nội dung file upload. Multipart có metadata/boundary, nên file đúng 10 MiB có thể làm body vượt mức. Backend có giới hạn riêng vẫn có thể từ chối upload nhỏ hơn mức Nginx.

### Restart và reload

- `restart`: dừng rồi khởi động dịch vụ; có thể gián đoạn và ảnh hưởng kết nối đang xử lý.
- `reload`: master đọc cấu hình, khởi tạo worker mới; worker cũ kết thúc công việc đang phục vụ rồi thoát. Production thường ưu tiên cách này để hạn chế gián đoạn.

Reload không đảm bảo tuyệt đối không gián đoạn với mọi giao thức hoặc mọi tình huống. Nếu cấu hình mới không áp dụng được, Nginx có thể tiếp tục dùng cấu hình cũ; vẫn cần xem log và gửi request kiểm chứng.

Quy trình trên Ubuntu có systemd:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

Chỉ chạy dòng reload nếu dòng test thành công. Có thể gộp để buộc điều kiện:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

Trong container chính thức không có systemd: dùng `nginx -t` rồi `nginx -s reload` với master đang chạy. Không dùng `systemctl` bên trong container này.

## 6. Hướng dẫn kiểm thử

Tại thư mục gốc trên Windows:

```powershell
$root = (Get-Location).Path
docker run --rm -v "${root}/bai-04-nginx-optimization/nginx.conf:/etc/nginx/nginx.conf:ro" nginx:stable nginx -t
python tests/test_nginx.py
```

Script tạo các static file > 1024 byte ở thư mục tạm, mount vào container; xác minh gzip và giải nén khớp nội dung cho CSS, TXT, JS, JSON, XML và HTML. Nó cũng kiểm tra response nhỏ, request không yêu cầu gzip, body ngay mức 10 MiB và lớn hơn một byte, rồi test/reload/request lại. Thư mục tạm được dọn sau chạy.

Trên một Linux lab đã phục vụ file lớn `sample.json`:

```bash
curl -sS -D - -o /dev/null -H 'Accept-Encoding: gzip' http://127.0.0.1/sample.json
curl --compressed http://127.0.0.1/sample.json
```

Lệnh đầu phải có `Content-Encoding: gzip` và `Vary: Accept-Encoding` nếu response đáp ứng điều kiện; lệnh sau cho curl giải nén. Không chỉ dùng `curl -I` để kết luận body đã được nén.

Ví dụ kiểm tra body vượt giới hạn trên Linux lab:

```bash
head -c 10485761 /dev/zero > /tmp/ss11-body.bin
curl -i --data-binary @/tmp/ss11-body.bin http://127.0.0.1/sample.json
rm /tmp/ss11-body.bin
```

Mong đợi 413. Server static này không có handler upload; body không vượt mức sẽ nhận 405 khi POST vào file static. 405 trong test biên 10 MiB chỉ chứng minh không bị giới hạn 413, không chứng minh upload thành công.

## 7. Đáp án câu hỏi bẫy

- **HTTP 413 là backend sập?** Không; có thể Nginx từ chối body quá lớn trước khi gửi đến backend.
- **Bật gzip là mọi response đều nén?** Không; cần client chấp nhận, MIME phù hợp và các điều kiện khác. Response nhỏ hoặc đã nén sẵn có thể không được nén.
- **Gzip giúp upload vượt 10m?** Không; cấu hình này nén response, không nới giới hạn body request.
- **Cần khai báo text/html trong gzip_types?** Không; HTML đã mặc định được hỗ trợ.
- **Reload lỗi syntax thì nên restart?** Không. Sửa cấu hình và chạy `nginx -t` thành công trước; restart có thể biến lỗi cấu hình thành downtime.
- **nginx -t qua là mọi request đúng?** Không; phải kiểm tra request, header và log thực tế.

## 8. Kết quả kiểm tra thực tế

Đã chạy thực tế lúc 2026-10-12 11:55:43 (UTC+7), Nginx 1.30.5 trong Docker:

- File gốc qua `nginx -t`.
- CSS, TXT, JavaScript, JSON, XML có MIME `application/xml` và HTML đều trả gzip, có Vary, giải nén đúng nội dung. XML dùng MIME mapping tạm được ghi rõ bên dưới.
- File 5 byte và client không gửi yêu cầu gzip không bị nén.
- Body 10.485.760 byte: HTTP 405 từ static handler, không bị 413. Body 10.485.761 byte: HTTP 413.
- `nginx -t` trước reload, `nginx -s reload` và GET sau reload đều thành công.

Xem các mục `bai-04-nginx-optimization` và `Bai 4` trong [results.json](../tests/results.json). Reload được chạy bằng `nginx -s reload` trong container; chưa kiểm chứng `systemctl reload nginx` trên Ubuntu hoặc hiệu năng dưới tải production.

## 9. Kết luận

Giới hạn body bảo vệ tài nguyên, gzip giảm lượng dữ liệu response; khi đổi cấu hình nên test trước và reload có kiểm chứng. Chọn mức tối ưu thực tế cần đo tải và độ trễ, ngoài phạm vi bài này.

Nguồn: [Nginx client_max_body_size](https://nginx.org/en/docs/http/ngx_http_core_module.html#client_max_body_size), [Nginx gzip](https://nginx.org/en/docs/http/ngx_http_gzip_module.html), [Nginx reload](https://nginx.org/en/docs/control.html).

# Bài 3 — HTTPS với Let's Encrypt

## 1. Mục tiêu

Minh họa chuyển HTTP cổng 80 sang HTTPS, kết thúc TLS ở Nginx cổng 443 rồi proxy backend `localhost:8080`. Cài Certbot trên Ubuntu và hướng dẫn kiểm tra gia hạn.

**`api.my-ecommerce.com` là domain minh họa của đề, không phải domain được xác nhận thuộc người học. Chưa có domain/VPS được cung cấp thì không thực hiện cấp chứng chỉ.**

## 2. Bối cảnh nghiệp vụ

API cửa hàng cần bảo vệ thông tin đăng nhập và dữ liệu đơn hàng trên đường truyền. Nginx nhận HTTPS từ khách; backend nội bộ cùng máy vẫn nhận HTTP. Chứng chỉ công khai phải khớp domain và được CA cấp hợp lệ.

## 3. Giải thích giải pháp và thứ tự triển khai

Các lệnh dưới đây dành cho **Ubuntu lab/VPS riêng đã có Nginx**, không chạy trực tiếp trong Windows PowerShell. Không thay cấu hình service cũ trên máy khác.

### Điều kiện trước khi xin chứng chỉ

- Sở hữu hoặc kiểm soát domain thật, thay domain minh họa ở mọi lệnh/cấu hình bằng domain đó.
- DNS A trỏ đúng IP public của VPS. Nếu có AAAA, IPv6 cũng phải tới đúng server và phục vụ được HTTP; không để AAAA sai.
- HTTP-01 của cách dùng này cần Internet truy cập **TCP 80**. HTTPS phục vụ khách cần **TCP 443**. Mở đúng firewall hệ điều hành, security group và NAT/router nếu có.
- Server cần kết nối ra ngoài qua HTTPS đến dịch vụ ACME; có quyền sudo để Certbot sửa Nginx và lưu key.
- `fullchain.pem` và `privkey.pem` chỉ tồn tại sau khi cấp thành công. Không bật file HTTPS gốc trước khi có chúng.

### Bước 1 — Cài Certbot

```bash
sudo apt update
sudo apt install certbot python3-certbot-nginx
```

Hoặc từ thư mục bài tập trên Ubuntu:

```bash
sudo bash bai-03-https/install-certbot.sh
```

[install-certbot.sh](install-certbot.sh) kiểm tra quyền root, dừng khi lệnh lỗi và chỉ cài package. Script in lệnh cấp chứng chỉ để người học chạy khi đủ điều kiện; không tự xin chứng chỉ. File dùng LF; `bash script` không cần executable bit.

### Bước 2 — Bootstrap bằng HTTP, chưa tham chiếu chứng chỉ

Trên máy lab riêng, tạo một site cho đúng domain. Ví dụ dưới đây chỉ được chạy sau khi thay domain bằng domain bạn kiểm soát:

```bash
sudo tee /etc/nginx/sites-available/ss11-api > /dev/null <<'NGINX'
server {
    listen 80;
    server_name api.my-ecommerce.com;

    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
NGINX
sudo ln -s /etc/nginx/sites-available/ss11-api /etc/nginx/sites-enabled/ss11-api
sudo nginx -t
sudo systemctl reload nginx
```

Nếu site/link đã tồn tại, kiểm tra và chỉnh đúng site hiện hữu thay vì tạo bản trùng. Chỉ reload nếu `nginx -t` thành công. Kiểm tra từ một máy ngoài VPS để xác nhận DNS và cổng 80, không chỉ curl loopback.

### Bước 3 — Cấp chứng chỉ thật

Lệnh theo đề, **chỉ chạy với domain bạn kiểm soát**:

```bash
sudo certbot --nginx -d api.my-ecommerce.com
```

Plugin nginx thực hiện xác minh và có thể sửa site để cài HTTPS; làm theo bước nhập email/đồng ý điều khoản, chọn redirect khi được hỏi. Sau khi thành công:

```bash
sudo certbot certificates
sudo ls -l /etc/letsencrypt/live/api.my-ecommerce.com/
```

Thông thường lineage nằm ở `/etc/letsencrypt/live/<domain>/`; nếu Certbot báo tên khác như `<domain>-0001`, dùng chính đường dẫn thực tế trong cấu hình. Không `cat` private key để đưa vào báo cáo.

### Bước 4 — Áp dụng cấu hình minh họa sau khi có chứng chỉ

Có thể giữ cấu hình Certbot sinh ra. Nếu cần dùng đúng [https.conf](https.conf) của bài, thay domain/đường dẫn trước rồi thay **cùng site `ss11-api`** đã bootstrap:

```bash
sudo cp bai-03-https/https.conf /etc/nginx/sites-available/ss11-api
sudo nginx -t
sudo systemctl reload nginx
```

Không bật thêm một site trùng server_name/listen bên cạnh site Certbot vừa sửa. Chỉ reload sau khi syntax thành công. Backend phải chạy cổng 8080; backend dừng có thể gây 502 dù chứng chỉ vẫn hợp lệ.

## 4. Nội dung cấu hình

File này là hai khối `server` để include bên trong `http`:

```nginx
server {
    listen 80;
    server_name api.my-ecommerce.com;

    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name api.my-ecommerce.com;

    ssl_certificate /etc/letsencrypt/live/api.my-ecommerce.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.my-ecommerce.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;

    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## 5. Giải thích directive quan trọng

| Directive | Ý nghĩa |
| --- | --- |
| `listen 80` | Nhận HTTP, cũng là cổng cần cho HTTP-01 khi Certbot dùng nginx plugin. |
| `server_name api.my-ecommerce.com` | Chọn site theo domain; không tự tạo DNS. |
| `return 301 https://$host$request_uri` | Redirect cố định HTTP sang HTTPS, giữ đường dẫn và query. |
| `listen 443 ssl` | Nhận HTTPS và thực hiện TLS tại Nginx. |
| `ssl_certificate .../fullchain.pem` | Chứng chỉ server kèm chuỗi chứng chỉ trung gian. |
| `ssl_certificate_key .../privkey.pem` | Private key tương ứng; giữ bí mật, không commit. |
| `ssl_protocols TLSv1.2 TLSv1.3` | Cho phép các phiên bản TLS này. |
| `proxy_pass http://localhost:8080` | Nginx gửi HTTP đến backend nội bộ, giữ URI trong cấu hình này. |
| Bốn `proxy_set_header` | Giữ hostname, thông tin peer/chuỗi proxy và giao thức đầu vào; qua HTTPS, `$scheme` là `https`. |

Không cần mở 8080 cho Internet khi backend cùng máy. Nginx đọc key với quyền phù hợp; không sửa key thành world-readable chỉ để xử lý lỗi quyền.

## 6. Hướng dẫn kiểm thử và gia hạn

### Kiểm thử local không có chứng chỉ

Từ thư mục gốc trên Windows:

```powershell
python tests/test_nginx.py
```

Script thực sự chạy `nginx -t` với file gốc, mong đợi lỗi không mở được `fullchain.pem`. Sau đó tạo **bản tạm** bỏ các directive `ssl_*` và đổi `listen 443 ssl` thành `listen 443`, kiểm tra syntax phần còn lại, HTTP 301 và proxy backend. Bản tạm không sửa file gốc, không tạo cert/key và được xóa sau kiểm thử.

Cổng 443 của bản tạm dùng HTTP, không phải HTTPS. Kết quả này không chứng minh TLS, chứng chỉ hay Let's Encrypt hoạt động. Syntax đầy đủ file gốc chỉ có thể xác nhận khi file chứng chỉ/key hợp lệ có sẵn.

### Kiểm thử trên VPS sau khi đã cấp thành công

```bash
sudo nginx -t
curl -I 'http://api.my-ecommerce.com/api/orders?q=1'
curl -v 'https://api.my-ecommerce.com/api/orders?q=1'
sudo certbot certificates
```

HTTP mong đợi 301 với `Location` tương ứng. HTTPS phải xác minh được chuỗi CA/hostname mà không dùng `curl -k`; mã response API tùy backend. Kiểm tra thêm hostname, hạn dùng và chuỗi chứng chỉ trong trình duyệt.

### Kiểm tra systemd timer

```bash
systemctl list-timers --all | grep -Ei 'certbot|snap.certbot'
systemctl status certbot.timer
systemctl cat certbot.timer
sudo certbot renew --dry-run
sudo journalctl -u certbot.service --since '7 days ago'
```

Với cài apt, kiểm tra timer `certbot.timer`. Nếu unit tồn tại nhưng chưa chạy:

```bash
sudo systemctl enable --now certbot.timer
```

`renew --dry-run` thử quy trình gia hạn với môi trường staging; cần đã có lineage/renewal config và điều kiện xác minh còn hoạt động. Thành công dry-run không có nghĩa chứng chỉ production vừa được gia hạn. Tiếp tục theo dõi timer/log và hạn dùng thực tế.

### Cron chỉ khi không có cơ chế gia hạn tự động

Không tạo thêm cron nếu timer hoặc cơ chế khác đã hoạt động. Kiểm tra đường dẫn bằng `command -v certbot`, `command -v nginx`, `command -v systemctl`. Ví dụ file `/etc/cron.d/ss11-certbot` trên Ubuntu cài apt:

```cron
0 3,15 * * * root /usr/bin/certbot renew --quiet --deploy-hook "/usr/sbin/nginx -t && /usr/bin/systemctl reload nginx"
```

Đây là định dạng `/etc/cron.d` có trường user `root`; với `sudo crontab -e` phải bỏ trường `root`. Hook chỉ chạy sau gia hạn thành công, kiểm tra cấu hình rồi reload để Nginx dùng chứng chỉ mới. Timer trên máy không có systemd sẽ không dùng được; lựa chọn lịch chạy theo môi trường thực tế.

## 7. Đáp án câu hỏi bẫy

- **Không có domain vẫn cấp Let's Encrypt cho tên ví dụ được không?** Không được dùng tên bạn không kiểm soát; Docker local không chứng minh quyền với domain public.
- **Mở 443 là đủ?** Không cho HTTP-01 theo cách này: cần 80 để CA xác minh. Cách DNS-01 có điều kiện khác, ngoài phạm vi bài.
- **Tạo sẵn fullchain.pem/privkey.pem trống để nginx -t qua?** Không. Nginx cần nội dung hợp lệ; file giả không phải chứng chỉ đã cấp.
- **Có HTTPS thì backend hết 502?** Không. TLS bảo vệ kết nối client–Nginx; upstream vẫn có thể hỏng.
- **301 có giữ nguyên method POST trong mọi client?** Không bảo đảm; một số client đổi sang GET. API nên gọi HTTPS trực tiếp. Bài yêu cầu 301, nên giữ 301; production có thể cân nhắc 308 theo nhu cầu.
- **Private key được đưa vào Git private không?** Không. Nếu lộ key cần thay/revoke theo quy trình; xóa file ở commit mới không xóa lịch sử cũ.

## 8. Kết quả kiểm tra thực tế

Đã chạy thực tế lúc 2026-10-12 11:55:43 (UTC+7), Nginx 1.30.5 trong Docker:

- Script cài Certbot: `bash -n` thành công; chỉ kiểm tra syntax Bash.
- `nginx -t` file HTTPS gốc: **không thành công**, lỗi `cannot load certificate` do thiếu `/etc/letsencrypt/live/api.my-ecommerce.com/fullchain.pem`, đúng điều kiện môi trường hiện tại.
- Bản tạm bỏ TLS: `nginx -t` thành công; GET HTTP trả 301 giữ domain/URI/query; HTTP ở port 443 tạm được proxy tới 8080 và giữ URI/query.
- Chưa xác minh TLS handshake, header X-Forwarded-Proto=`https` trên kết nối TLS thật, chứng chỉ được CA tin cậy, cấp chứng chỉ, DNS public, timer hoặc gia hạn.

Xem các mục `HTTPS goc`, `Bai 3` và `Certbot script` trong [results.json](../tests/results.json). Không chạy apt, không xin chứng chỉ, không chạy timer/renew trên Ubuntu trong phiên này.

## 9. Kết luận

Thứ tự đúng là chuẩn bị domain/DNS/HTTP, cấp chứng chỉ thành công rồi bật cấu hình TLS và kiểm tra gia hạn. Bộ bài cung cấp cấu hình và quy trình; phần triển khai public còn cần VPS/domain thật.

Nguồn: [Certbot — nginx và renewal](https://eff-certbot.readthedocs.io/en/stable/using.html), [Let's Encrypt — HTTP-01](https://letsencrypt.org/docs/challenge-types/), [Nginx HTTPS](https://nginx.org/en/docs/http/configuring_https_servers.html).

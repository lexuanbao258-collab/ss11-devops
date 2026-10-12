#!/usr/bin/env bash
set -euo pipefail

if [ "$EUID" -ne 0 ]; then
    echo "Chay tren Ubuntu bang: sudo bash install-certbot.sh" >&2
    exit 1
fi

apt update
apt install -y certbot python3-certbot-nginx

printf '%s\n' \
    'Da cai Certbot. Chua cap chung chi.' \
    'Chi chay sau khi kiem soat domain, DNS va cong 80/443 da san sang:' \
    'sudo certbot --nginx -d api.my-ecommerce.com'

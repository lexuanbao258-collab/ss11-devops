"""Kiem thu Nginx trong Docker; --serve chi dung cho backend gia lap."""
import gzip
import http.server
import json
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NGINX_IMAGE = "nginx:stable"
PYTHON_IMAGE = "python:3.13-slim"


def serve():
    class Server(http.server.ThreadingHTTPServer):
        address_family = socket.AF_INET6

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps({"port": self.server.server_port, "uri": self.path,
                               "headers": dict(self.headers)}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            if self.server.server_port == 3000 and self.path == "/__stop3000":
                threading.Thread(target=lambda: (self.server.shutdown(), self.server.server_close()),
                                 daemon=True).start()

        def log_message(self, *_):
            pass

    servers = [Server(("::", port), Handler) for port in (3000, 8080)]
    for server in servers:
        threading.Thread(target=server.serve_forever, daemon=True).start()
    threading.Event().wait()


def run(*args, required=True):
    result = subprocess.run(["docker", *args], capture_output=True, text=True)
    if required and result.returncode:
        raise RuntimeError(f"docker {' '.join(args)}\n{result.stdout}{result.stderr}")
    return result


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


CLIENT = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())


def request(base, path="/", headers=None, data=None):
    req = urllib.request.Request(base + path, headers=headers or {}, data=data)
    try:
        response = CLIENT.open(req, timeout=10)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        return response.status, response.headers, response.read()


def main():
    report = {"checks": [], "https_limit": "Khong co chung chi: chua xac minh TLS/Let's Encrypt/gia han."}
    tag = "ss11-" + uuid.uuid4().hex[:10]
    backend, proxy = tag + "-backend", tag + "-nginx"

    def check(name, condition, detail=""):
        report["checks"].append({"name": name, "status": "PASS" if condition else "FAIL", "detail": detail})
        print(f"{'PASS' if condition else 'FAIL'} {name}", flush=True)
        if not condition:
            raise AssertionError(f"{name}: {detail}")

    def syntax(config, full=False, required=True):
        destination = "/etc/nginx/nginx.conf" if full else "/etc/nginx/conf.d/default.conf"
        return run("run", "--rm", "-v", f"{config}:{destination}:ro", NGINX_IMAGE,
                   "nginx", "-t", required=required)

    def start(config, full=False, html=None):
        destination = "/etc/nginx/nginx.conf" if full else "/etc/nginx/conf.d/default.conf"
        args = ["run", "-d", "--name", proxy, "--network", "container:" + backend,
                "-v", f"{config}:{destination}:ro"]
        if html:
            args += ["-v", f"{html}:/usr/share/nginx/html:ro",
                     "-v", f"{html.parent / 'mime.types'}:/etc/nginx/mime.types:ro"]
        run(*args, NGINX_IMAGE)
        for _ in range(50):
            try:
                if request(base)[0] < 500:
                    return
            except (OSError, urllib.error.URLError):
                pass
            time.sleep(0.2)
        raise RuntimeError("Nginx khong san sang; " + run("logs", proxy, required=False).stderr)

    def stop_proxy():
        run("rm", "-f", proxy, required=False)

    try:
        run("info")
        for image in (NGINX_IMAGE, PYTHON_IMAGE):
            if run("image", "inspect", image, required=False).returncode:
                print("Pull " + image, flush=True)
                run("pull", image)
        report["nginx_version"] = run("run", "--rm", NGINX_IMAGE, "nginx", "-v").stderr.strip()
        report["nginx_image_id"] = run("image", "inspect", "--format", "{{.Id}}", NGINX_IMAGE).stdout.strip()
        result = run("run", "--rm", "-v", f"{ROOT}:/work:ro", PYTHON_IMAGE,
                     "bash", "-n", "/work/bai-03-https/install-certbot.sh")
        check("Certbot script: bash -n", result.returncode == 0)
        for lesson, filename in (("bai-01-reverse-proxy", "default.conf"),
                                 ("bai-02-api-gateway", "default.conf"),
                                 ("bai-04-nginx-optimization", "nginx.conf")):
            result = syntax(ROOT / lesson / filename, full=filename == "nginx.conf")
            check(lesson + ": nginx -t", result.returncode == 0, result.stderr.strip())

        original = ROOT / "bai-03-https/https.conf"
        result = syntax(original, required=False)
        check("HTTPS goc: loi thieu chung chi du kien",
              result.returncode != 0 and "cannot load certificate" in result.stderr
              and "fullchain.pem" in result.stderr, result.stderr.strip())

        run("run", "-d", "--name", backend, "-p", "127.0.0.1::80", "-p", "127.0.0.1::443",
            "-v", f"{ROOT}:/work:ro", PYTHON_IMAGE, "python", "/work/tests/test_nginx.py", "--serve")
        port = run("port", backend, "80/tcp").stdout.strip().rsplit(":", 1)[1]
        base = "http://127.0.0.1:" + port
        tls_port = run("port", backend, "443/tcp").stdout.strip().rsplit(":", 1)[1]

        start(ROOT / "bai-01-reverse-proxy/default.conf")
        status, _, body = request(base, "/products?q=1", {"Host": "shop.test"})
        echo = json.loads(body)
        check("Bai 1: frontend, URI va header",
              status == 200 and echo["port"] == 3000 and echo["uri"] == "/products?q=1"
              and echo["headers"]["Host"] == "shop.test"
              and bool(echo["headers"].get("X-Real-IP"))
              and bool(echo["headers"].get("X-Forwarded-For")), json.dumps(echo))
        request(base, "/__stop3000")
        time.sleep(1)
        check("Bai 1: upstream dung -> 502", request(base)[0] == 502)
        stop_proxy()
        run("restart", backend)
        port = run("port", backend, "80/tcp").stdout.strip().rsplit(":", 1)[1]
        base = "http://127.0.0.1:" + port
        tls_port = run("port", backend, "443/tcp").stdout.strip().rsplit(":", 1)[1]

        start(ROOT / "bai-02-api-gateway/default.conf")
        for path, expected in (("/api/orders?limit=2", 8080), ("/cart", 3000), ("/api", 8080)):
            status, headers, body = request(base, path, {"Host": "shop.test", "X-Forwarded-For": "198.51.100.10"})
            if path == "/api":
                check("Bai 2: /api -> 301 /api/", status == 301 and headers["Location"].endswith("/api/"))
                continue
            echo = json.loads(body)
            check("Bai 2: " + path,
                  status == 200 and echo["port"] == expected and echo["uri"] == path
                  and echo["headers"]["Host"] == "shop.test"
                  and echo["headers"]["X-Forwarded-Proto"] == "http"
                  and bool(echo["headers"].get("X-Real-IP"))
                  and echo["headers"]["X-Forwarded-For"].startswith("198.51.100.10, "), json.dumps(echo))
        stop_proxy()

        with tempfile.TemporaryDirectory(prefix="ss11-nginx-") as folder:
            temp = Path(folder)
            # shortcut: bo TLS chi trong ban tam, kiem tra TLS day du khi co domain/chung chi that.
            text = original.read_text(encoding="utf-8").replace("listen 443 ssl;", "listen 443;")
            text = "\n".join(line for line in text.splitlines() if not line.strip().startswith("ssl_")) + "\n"
            http_only = temp / "https-without-tls.conf"
            http_only.write_text(text, encoding="utf-8")
            result = syntax(http_only)
            check("Bai 3: nginx -t ban tam bo TLS (kiem tra mot phan)", result.returncode == 0)
            start(http_only)
            status, headers, _ = request(base, "/api/orders?q=1", {"Host": "api.my-ecommerce.com"})
            check("Bai 3: redirect 301 giu URI",
                  status == 301 and headers["Location"] == "https://api.my-ecommerce.com/api/orders?q=1")
            status, _, body = request("http://127.0.0.1:" + tls_port, "/api/orders?q=1",
                                      {"Host": "api.my-ecommerce.com"})
            echo = json.loads(body)
            check("Bai 3: proxy backend tren ban tam HTTP port 443",
                  status == 200 and echo["port"] == 8080 and echo["uri"] == "/api/orders?q=1"
                  and echo["headers"]["X-Forwarded-Proto"] == "http", json.dumps(echo))
            stop_proxy()

            html = temp / "html"
            html.mkdir()
            payload = "x" * 2048
            samples = {"css": "/*" + payload + "*/", "txt": payload, "js": "/*" + payload + "*/",
                       "json": json.dumps({"sample": payload}), "xml": "<sample>" + payload + "</sample>",
                       "html": "<!doctype html><p>" + payload + "</p>"}
            for suffix, content in samples.items():
                (html / ("sample." + suffix)).write_text(content, encoding="utf-8")
            (html / "small.txt").write_text("small", encoding="utf-8")
            # Fixture XML phai tra application/xml de kiem tra dung MIME theo de.
            mime_types = run("run", "--rm", NGINX_IMAGE, "cat", "/etc/nginx/mime.types").stdout
            (temp / "mime.types").write_text(mime_types.replace("text/xml", "application/xml"), encoding="utf-8")
            report["xml_fixture"] = "Mime mapping tam: xml -> application/xml; image mac dinh dung text/xml."
            config = ROOT / "bai-04-nginx-optimization/nginx.conf"
            start(config, full=True, html=html)
            for suffix, content in samples.items():
                status, headers, body = request(base, "/sample." + suffix, {"Accept-Encoding": "gzip"})
                check("Bai 4: gzip " + suffix,
                      status == 200 and headers.get("Content-Encoding") == "gzip"
                      and "Accept-Encoding" in headers.get("Vary", "")
                      and gzip.decompress(body) == content.encode(), str(dict(headers)))
            check("Bai 4: khong nen khi client khong yeu cau",
                  request(base, "/sample.txt")[1].get("Content-Encoding") is None)
            check("Bai 4: khong nen response nho hon 1024",
                  request(base, "/small.txt", {"Accept-Encoding": "gzip"})[1].get("Content-Encoding") is None)
            for size in (10 * 1024 * 1024, 10 * 1024 * 1024 + 1):
                status, _, _ = request(base, "/sample.txt", data=b"x" * size)
                check("Bai 4: body " + str(size) + " bytes",
                      status == (405 if size == 10 * 1024 * 1024 else 413), "HTTP " + str(status))
            check("Bai 4: nginx -t truoc reload", run("exec", proxy, "nginx", "-t").returncode == 0)
            check("Bai 4: reload trong container", run("exec", proxy, "nginx", "-s", "reload").returncode == 0)
            check("Bai 4: request sau reload", request(base, "/sample.txt")[0] == 200)
            stop_proxy()
    except Exception as error:
        report["error"] = str(error)
        print("ERROR " + str(error), file=sys.stderr)
        raise
    finally:
        stop_proxy()
        run("rm", "-f", backend, required=False)
        report["checked_at_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        (ROOT / "tests/results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                                               encoding="utf-8")


if __name__ == "__main__":
    if sys.argv[1:] == ["--serve"]:
        serve()
    else:
        main()

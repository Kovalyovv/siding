#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Локальный сервер сайта подбора сайдинга.
- отдаёт статику (index.html, data.json, фото из папки сайта)
- /api/specs?url=<URL источника> — серверный прокси: тянет страницу товара
  с grandline/mirkrovli и возвращает {description, specs:[{name,value}]}.
  Нужен, потому что браузеру кросс-доменный fetch запрещён (CORS).

Запуск:  python3 server.py   →  http://localhost:8000
"""
import gzip
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# порт: аргумент командной строки, либо переменная PORT, либо 8000
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("PORT", 8000))
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
           "Accept-Encoding": "gzip, deflate"}
ALLOWED = ("belgorod.grandline.ru", "grandline.ru", "mirkrovli31.ru")
_cache = {}


def clean(t):
    t = re.sub(r"<br\s*/?>", "\n", t, flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    t = (t.replace("&nbsp;", " ").replace("&amp;", "&")
          .replace("&quot;", '"').replace("&#8381;", "₽")
          .replace("&laquo;", "«").replace("&raquo;", "»")
          .replace("&mdash;", "—").replace("&deg;", "°"))
    return re.sub(r"[ \t]+", " ", t).strip()


def http_get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=40) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
        return raw.decode("utf-8", "replace")


def extract_grandline(s):
    specs, seen = [], set()
    for m in re.finditer(
            r'specification-item__title[^>]*>(.*?)</[^>]+>\s*'
            r'<[^>]*specification-item__value[^>]*>(.*?)</', s, re.S):
        name, val = clean(m.group(1)).rstrip(":"), clean(m.group(2))
        if name and val and name not in seen:
            seen.add(name)
            specs.append({"name": name, "value": val})
    desc = ""
    m = re.search(r'product-description-tab__content[^>]*>(.*?)</div>\s*</div>', s, re.S) \
        or re.search(r'product-description-tab__content[^>]*>(.*?)</div>', s, re.S)
    if m:
        desc = clean(m.group(1))
        # внутри блока описания идёт встроенный превью характеристик — отрезаем
        desc = re.split(r"\bХарактеристики\b|Показать все характеристики", desc)[0].strip()
    if not desc:
        m = re.search(r'itemprop="description"[^>]*content="([^"]+)"', s)
        if m:
            desc = clean(m.group(1))
    return desc, specs


def extract_mirkrovli(s):
    specs = []
    for m in re.finditer(
            r'<tr>\s*<td[^>]*data-id="\d+"[^>]*>(.*?)</td>\s*'
            r'<td[^>]*>(.*?)</td>\s*</tr>', s, re.S):
        name, val = clean(m.group(1)), clean(m.group(2))
        if name and val:
            specs.append({"name": name, "value": val})
    desc = ""
    m = re.search(r'class="[^"]*\bdescription\b[^"]*"[^>]*>(.*?)</div>', s, re.S)
    if m:
        desc = clean(m.group(1)).replace("Подробности", "").strip()
    return desc, specs


def get_specs(url):
    if url in _cache:
        return _cache[url]
    host = urllib.parse.urlparse(url).netloc
    if not any(host.endswith(a) for a in ALLOWED):
        return {"error": "домен не разрешён"}
    s = http_get(url)
    if "grandline" in host:
        desc, specs = extract_grandline(s)
    else:
        desc, specs = extract_mirkrovli(s)
    res = {"description": desc, "specs": specs, "url": url}
    _cache[url] = res
    return res


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/specs":
            qs = urllib.parse.parse_qs(parsed.query)
            url = (qs.get("url") or [""])[0]
            try:
                self._send(200, get_specs(url))
            except Exception as e:
                self._send(200, {"error": str(e)})
            return
        # статика
        path = parsed.path
        if path == "/" or path == "":
            path = "/index.html"
        path = urllib.parse.unquote(path).lstrip("/")
        try:
            with open(path, "rb") as f:
                data = f.read()
            ct = "text/html; charset=utf-8" if path.endswith(".html") else \
                 "application/json; charset=utf-8" if path.endswith(".json") else \
                 "text/javascript; charset=utf-8" if path.endswith(".js") else \
                 "text/css; charset=utf-8" if path.endswith(".css") else \
                 "image/svg+xml" if path.endswith(".svg") else \
                 "image/webp" if path.endswith(".webp") else \
                 "image/jpeg" if path.endswith((".jpg", ".jpeg")) else \
                 "image/png" if path.endswith(".png") else \
                 "application/octet-stream"
            self._send(200, data, ct)
        except FileNotFoundError:
            self._send(404, {"error": "not found"})


class Server(ThreadingHTTPServer):
    allow_reuse_address = True   # не залипать в TIME_WAIT после перезапуска


def serve():
    last = None
    for port in range(PORT, PORT + 10):     # 8000..8009 — берём первый свободный
        try:
            srv = Server(("127.0.0.1", port), Handler)
        except OSError as e:
            last = e
            continue
        print(f"Сайт подбора сайдинга:  http://localhost:{port}")
        print("Кнопка «Характеристики» тянет данные с источника через этот сервер.")
        print("Остановить: Ctrl+C")
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print("\nОстановлено.")
        return
    print(f"Не удалось занять порт {PORT}..{PORT+9}: {last}", file=sys.stderr)
    print("Похоже, сервер уже запущен — просто открой http://localhost:8000",
          file=sys.stderr)


if __name__ == "__main__":
    serve()

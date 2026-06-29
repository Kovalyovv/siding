#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Догрузка ВСЕХ изображений по каждому товару Grand Line.
Листинг даёт только превью; полная галерея — на странице товара.
Берём оригиналы /image/data/.../<слаг>-<id>[-N].jpg, отфильтрованные по id товара
(чтобы отсечь сопутствующие товары: планки, дюбели, другие цвета).

Кэш результата — galleries.json (id -> [url,...]); запуск можно прерывать и
докачивать. По завершении дописываем поле images в grandline.json/csv.
"""
import csv
import json
import os
import re
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
           "Accept-Encoding": "gzip, deflate"}
CACHE = "galleries.json"
WORKERS = 8

_lock = threading.Lock()


def http_get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    last = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                raw = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    import gzip
                    raw = gzip.decompress(raw)
                return raw.decode("utf-8", "replace")
        except Exception as e:
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise last


def extract_gallery(html, pid):
    """Все изображения галереи товара pid: главное + доп. кадры, по порядку."""
    urls = set(re.findall(
        r'(?:src|data-src|data-lazy|href|data-image|data-zoom-image)="'
        r'(https?://[^"]*pg_files[^"]+\.(?:jpg|jpeg|png|webp))"', html))
    # принадлежность товару: id идёт сразу за слагом -> -<id> или -<id>-<N>
    pat = re.compile(r"-" + re.escape(pid) + r"(?:-(\d+))?(?:-\d+x\d+)?\.(?:jpg|jpeg|png|webp)$")
    found = {}  # index -> url (предпочитаем оригинал /image/data/)
    for u in urls:
        m = pat.search(u)
        if not m:
            continue
        idx = int(m.group(1)) if m.group(1) else 0
        is_orig = "/image/data/" in u
        cur = found.get(idx)
        # приоритет: оригинал без размера > крупный кэш 1304x890 > прочее
        score = (2 if is_orig else 0) + (1 if "1304x890" in u else 0)
        if cur is None or score > cur[0]:
            found[idx] = (score, u)
    return [found[i][1] for i in sorted(found)]


def url_id(url):
    """id товара кодируется в хвосте ссылки: ...-54532.html (не равен data-pid)."""
    m = re.search(r"-(\d+)\.html", url)
    return m.group(1) if m else ""


def worker(item):
    pid, url = item["id"], item["url"]
    iid = url_id(url) or pid
    try:
        html = http_get(url)
        imgs = extract_gallery(html, iid)
        return pid, imgs, None
    except Exception as e:
        return pid, [], str(e)


def main():
    data = json.load(open("grandline.json", encoding="utf-8"))
    cache = {}
    if os.path.exists(CACHE):
        cache = json.load(open(CACHE, encoding="utf-8"))
        print(f"кэш: уже есть {len(cache)} товаров", file=sys.stderr)

    todo = [x for x in data if x["id"] and x["id"] not in cache]
    print(f"к загрузке: {len(todo)} из {len(data)}", file=sys.stderr)

    done = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(worker, x): x for x in todo}
        for fut in as_completed(futs):
            pid, imgs, err = fut.result()
            with _lock:
                cache[pid] = imgs
                done += 1
                if err:
                    print(f"  ! {pid}: {err}", file=sys.stderr)
                if done % 100 == 0:
                    json.dump(cache, open(CACHE, "w", encoding="utf-8"),
                              ensure_ascii=False)
                    print(f"  ... {done}/{len(todo)}", file=sys.stderr)
    json.dump(cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)

    # вписываем галереи в основной датасет
    cnt = []
    for x in data:
        imgs = cache.get(x["id"], [])
        x["images"] = imgs
        x["images_count"] = len(imgs)
        if imgs:
            x["image_url"] = imgs[0]
            x["image_file"] = imgs[0].rsplit("/", 1)[-1]
        cnt.append(len(imgs))
    json.dump(data, open("grandline.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    cols = ["id", "type", "coating", "finish", "color", "film", "price",
            "price_unit", "name", "images_count", "image_url", "images", "url"]
    with open("grandline.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, delimiter=";", extrasaction="ignore")
        w.writeheader()
        for x in data:
            row = dict(x)
            row["images"] = " | ".join(x.get("images", []))
            w.writerow(row)

    tot = sum(cnt)
    nonzero = sum(1 for c in cnt if c)
    print(f"ГОТОВО: {len(data)} товаров, {tot} картинок; "
          f"с галереей: {nonzero}; в среднем {tot/max(nonzero,1):.1f}/товар; "
          f"максимум {max(cnt)}", file=sys.stderr)


if __name__ == "__main__":
    main()

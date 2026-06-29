#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Парсер каталога металлического сайдинга belgorod.grandline.ru.
Проходит все страницы (?limit=60&page=N), собирает карточки в одну таблицу.
Выгрузка: grandline.csv (; -разделитель) и grandline.json.
В отличие от mirkrovli — здесь есть цены (руб/м2).
"""
import csv
import json
import os
import re
import sys
import time
import urllib.request

BASE = "https://belgorod.grandline.ru/katalog/fasad/sayding/metallicheskiy-sayding/"
LIMIT = 60
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
           "Accept-Encoding": "gzip, deflate"}

# ---------- разбор названия (вокабуляр Grand Line) ----------
# (regex типа, нормализованное имя). Длинные/частные раньше.
TYPES = [
    (r"ЭкоБрус\s*3D",                 "ЭкоБрус 3D"),
    (r"ЭкоБрус\s*(?:NEW|Нью)",        "ЭкоБрус NEW"),
    (r"ЭкоБрус",                      "ЭкоБрус"),
    (r"Корабельная доска\s*XL",       "Корабельная доска XL"),
    (r"Корабельная доска\s*НН",       "Корабельная доска НН"),
    (r"Корабельная доска",            "Корабельная доска"),
    (r"Блок[\-\s]?[Хх]аус(?:\s*новый|\s*new)?", "Блок-хаус"),
    (r"Квадро\s*[Бб]рус",             "Квадро брус"),
    (r"Вертикаль(?:\s*классик|\s*line|\s*лайн)?", "Вертикаль"),
    (r"Доска?\b",                     "Доска"),
]

# (regex покрытия, нормализованное имя, финиш). Длинные раньше.
# финиш: 'глянец' | 'мат' | 'текстура/дерево'
COATINGS = [
    (r"Print[\-\s]?Double|Принт[\-\s]?Дабл", "Print-Double",      "текстура/дерево"),
    (r"Принт\s*Элит|Print\s*Elite",     "Принт Элит",        "текстура/дерево"),
    (r"Принт\s*Премиум|Print\s*Premium", "Принт Премиум",    "текстура/дерево"),
    (r"Colority\s*Print|Колорити",      "Colority Print",    "текстура/дерево"),
    (r"\bПринт\b|\bPrint\b",            "Принт",             "текстура/дерево"),
    (r"GreenCoat Pural\s*(?:BT|БТ)\s*(?:Matt|матов\w*)|Гринко\w* Пурал\w*\s*(?:БТ\s*)?(?:Мат|матов\w*)",
        "GreenCoat Pural BT Matt", "мат"),
    (r"GreenCoat Pural\s*(?:BT|БТ)?|Гринко\w* Пурал\w*", "GreenCoat Pural BT", "глянец"),
    (r"Quarzit\s*Pro Matt|Кварц\w* Про Мат", "Quarzit Pro Matt", "мат"),
    (r"Quarzit\s*Lite|Кварц\w* Лайт",   "Quarzit Lite",      "мат"),
    (r"Quarzit|Кварц\w*",               "Quarzit",           "мат"),
    (r"PurPro(?:\s*Matt)?(?:\s*275)?(?:\s*матов\w*)?|ПурПро\s*(?:Мат|матов\w*)?", "PurPro Matt 275", "мат"),
    (r"PurLite(?:\s*Matt)?(?:\s*275)?(?:\s*матов\w*)?|ПурЛайт\s*(?:Мат|матов\w*)?", "PurLite Matt", "мат"),
    (r"Rooftop(?:\s*Matte|\s*Бархат)?|Руфтоп", "Rooftop Matte", "мат"),
    (r"Полидэкстер|Polydexter",         "Полидэкстер",       "мат"),
    (r"Сатин\s*Мат|Satin\s*Matt",       "Сатин Мат",         "мат"),
    (r"Сатин|Satin",                    "Сатин",             "глянец"),
    (r"Велюр|Velur",                    "Велюр",             "мат"),
    (r"Атлас|Atlas",                    "Атлас",             "мат"),
    (r"(?:Drap|Драп)\s*(?:TX|ТХ)",      "Drap TX",           "текстура/дерево"),
    (r"(?:Drap|Драп)\s*(?:ST|СТ)",      "Drap ST",           "текстура/дерево"),
    (r"\bDrap\b|\bДрап\b",              "Drap",              "текстура/дерево"),
    (r"\bПЭ\b|\bPE\b|Полиэстер",        "ПЭ (полиэстер)",    "глянец"),
]

# служебные/шумовые слова, которые надо вычистить из цвета
COLOR_NOISE = (r"\b(?:Grand Line|Grand|Line|классик|классика|лайн|новый|new|Нью|XL|НН|3D|"
               r"TwinColor|Твинколор|TwoColor|с пленкой|с плёнкой|foil|Pural|BT|БТ|"
               r"матов\w*|глянцев\w*|Бархат|двухсторонн\w*|односторонн\w*)\b"
               r"|\b[вВ]\d{2}\b")


def fetch(url, page):
    cache = f"gl_p{page}.html"
    if os.path.exists(cache) and os.path.getsize(cache) > 1000:
        return open(cache, encoding="utf-8", errors="replace").read()
    req = urllib.request.Request(url, headers=HEADERS)
    last = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                raw = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    import gzip
                    raw = gzip.decompress(raw)
                html = raw.decode("utf-8", "replace")
            open(cache, "w", encoding="utf-8").write(html)
            return html
        except Exception as e:
            last = e
            time.sleep(2 * (attempt + 1))
    raise last


def clean(t):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", t)).strip()


def detect_type(name):
    for pat, norm in TYPES:
        if re.match(r"\s*(?:" + pat + r")", name, re.I):
            return norm, pat
    return "", ""


def detect_coating(name):
    for pat, norm, finish in COATINGS:
        if re.search(pat, name, re.I):
            return norm, finish, pat
    return "", "", None


def has_film(name):
    return "пленк" in name.lower() or "плёнк" in name.lower() or "foil" in name.lower()


def _norm(s):
    s = re.sub(r"\s+", " ", s).strip(" -–()")
    if s and s[0].islower() and re.match(r"[а-яё]", s):
        s = s[0].upper() + s[1:]
    return s


def detect_color(name, type_pat, coat_pat):
    name = re.sub(r"(\d)([А-Яа-яёЁ])", r"\1 \2", name)   # разлепить "9006бело"
    # 1) приоритет: цвет = текст после RAL/RR-кода (напр. "RAL 8017 шоколад")
    m = re.search(r"\b(?:RAL|RR)\b\s*[0-9A-Za-zНH]+\s+(.+)$", name)
    if m:
        c = m.group(1)
        c = re.split(r"\s*\(", c)[0]                       # отрезать "(RAL ... )"
        c = re.sub(r"\b(?:TwinColor|TwoColor|Твинколор)\b.*$", "", c, flags=re.I)
        c = re.sub(r"с\s*пл[её]нкой|двухсторонн\w*", "", c, flags=re.I)
        return _norm(c)
    # 2) "под дерево": цвет между покрытием и TwinColor
    s = name
    if type_pat:
        s = re.sub(r"^\s*(?:" + type_pat + r")", "", s, count=1, flags=re.I)
    if coat_pat:
        s = re.sub(coat_pat, "", s, count=1, flags=re.I)
    s = re.split(r"\b(?:TwinColor|TwoColor|Твинколор)\b", s, flags=re.I)[0]
    s = re.sub(COLOR_NOISE, "", s, flags=re.I)
    s = re.sub(r"\b(?:Слим|Проф|Гофр|ТР|ТХ|новый)\b", "", s, flags=re.I)
    s = re.sub(r"\b0[.,]\d+\b", "", s)
    s = re.sub(r"\(копия\)", "", s, flags=re.I)
    s = re.sub(r"\b\d{3,4}\b", "", s)
    return _norm(s)


def parse_cards(htmls):
    rows, seen = [], set()
    for html in htmls:
        chunks = re.split(r'class="product-item  js_c"', html)
        for ch in chunks[1:]:
            mpid = re.search(r'data-pid="(\d+)"', ch[:80])
            pid = mpid.group(1) if mpid else ""
            mt = re.search(r'class="product-item__title"[^>]*>\s*<a\s+href="([^"]+)"[^>]*>(.*?)</a>',
                           ch, re.S)
            if not mt:
                continue
            url = "https://belgorod.grandline.ru" + mt.group(1)
            name = clean(mt.group(2))
            # цена руб/м2
            mp = re.search(r'product-item__price">\s*([\d\s ]+)\s*&#8381;', ch)
            price = re.sub(r"[\s ]", "", mp.group(1)) if mp else ""
            price_unit = "руб/м2" if mp else ""
            # картинка (первая, режем суффикс размера -228x136)
            mi = re.search(r'(?:src|data-src|data-lazy)="(https://[^"]+\.(?:jpg|jpeg|png|webp))"', ch)
            img = mi.group(1) if mi else ""
            img_file = img.rsplit("/", 1)[-1] if img else ""

            if pid and pid in seen:
                continue
            seen.add(pid)

            type_norm, type_pat = detect_type(name)
            coating, finish, coat_pat = detect_coating(name)
            rows.append({
                "id": pid,
                "type": type_norm,
                "coating": coating,
                "finish": finish,
                "color": detect_color(name, type_pat, coat_pat),
                "film": "да" if has_film(name) else "",
                "price": price,
                "price_unit": price_unit,
                "name": name,
                "image_file": img_file,
                "image_url": img,
                "url": url,
            })
    return rows


def main():
    htmls = []
    page = 1
    max_pages = 60
    while page <= max_pages:
        url = f"{BASE}?limit={LIMIT}&page={page}"
        try:
            html = fetch(url, page)
        except Exception as e:
            print(f"стр.{page}: ошибка {e}", file=sys.stderr)
            break
        n = len(re.findall(r'class="product-item  js_c"', html))
        print(f"стр.{page}: карточек {n}", file=sys.stderr)
        if n == 0:
            break
        htmls.append(html)
        nums = [int(x) for x in re.findall(r"[?&]page=(\d+)", html)]
        if nums:
            max_pages = min(max_pages, max(nums))
        page += 1
        time.sleep(0.6)

    rows = parse_cards(htmls)
    print(f"ИТОГО уникальных товаров: {len(rows)}", file=sys.stderr)

    cols = ["id", "type", "coating", "finish", "color", "film", "price",
            "price_unit", "name", "image_file", "image_url", "url"]
    with open("grandline.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, delimiter=";")
        w.writeheader()
        w.writerows(rows)
    with open("grandline.json", "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    print("Сохранено: grandline.csv, grandline.json", file=sys.stderr)


if __name__ == "__main__":
    main()

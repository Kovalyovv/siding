#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Парсер каталога металлического сайдинга mirkrovli31.ru.
Проходит все страницы (?PAGEN_1=N), собирает карточки товаров в одну таблицу.
Выгрузка: siding.csv (Excel-совместимый, ; разделитель) и siding.json.
"""
import csv
import json
import re
import sys
import time
import urllib.request

BASE = "https://mirkrovli31.ru/catalog/fasadnye-materialy/metallicheskiy-sayding/"
SITE = "https://mirkrovli31.ru"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"}

# ---------- словари для разбора названия ----------
# Тип профиля. Порядок важен: длинные/частные варианты раньше.
# (паттерн-regex, нормализованное имя)
TYPES = [
    (r"ЭкоБрус\s*3D",            "ЭкоБрус 3D"),
    (r"ЭкоБрус\s*NEW",           "ЭкоБрус NEW"),
    (r"Эко\s*Брус|ЭкоБрус",      "ЭкоБрус"),
    (r"Корабельная доска\s*XL",  "Корабельная доска XL"),
    (r"Корабельная доска",       "Корабельная доска"),
    (r"Блок[\-\s]?[Хх]аус\s*(?:New|NEW)?", "Блок-хаус"),
    (r"Квадро\s*[Бб]рус",        "Квадро брус"),
    (r"Вертикаль",               "Вертикаль"),
]

# Покрытие -> (regex, нормализованное имя, финиш).
# финиш: 'глянец' | 'мат' | 'текстура/дерево'. Порядок: длинные раньше коротких.
COATINGS = [
    (r"Print[\-\s]?Double Premium", "Print-Double Premium", "текстура/дерево"),
    (r"Print[\-\s]?Double Elite",   "Print-Double Elite",   "текстура/дерево"),
    (r"Print[\-\s]?Double",         "Print-Double",         "текстура/дерево"),
    (r"Print Twincolor",            "Print Twincolor",      "текстура/дерево"),
    (r"Print Premium",              "Print Premium",        "текстура/дерево"),
    (r"Print Elite",                "Print Elite",          "текстура/дерево"),
    (r"GreenCoat Pural BT Matt",    "GreenCoat Pural BT Matt", "мат"),
    (r"GreenCoat Pural BT",         "GreenCoat Pural BT",   "глянец"),
    (r"GreenCoat Pural",            "GreenCoat Pural",      "глянец"),
    (r"Quarzit\s*Pro Matt",         "Quarzit Pro Matt",     "мат"),
    (r"Quarzit\s*Lite",             "Quarzit Lite",         "мат"),
    (r"Quarzit",                    "Quarzit",              "мат"),
    (r"PurPro Matt(?:\s*275)?",     "PurPro Matt 275",      "мат"),
    (r"PurLite Matt(?:\s*275)?",    "PurLite Matt",         "мат"),
    (r"Rooftop Matte",              "Rooftop Matte",        "мат"),
    (r"Satin Matt",                 "Satin Matt",           "мат"),
    (r"Satin",                      "Satin",                "глянец"),
    (r"Velur",                      "Velur",                "мат"),
    (r"Atlas",                      "Atlas",                "мат"),
    (r"Drap TwinColor",             "Drap TwinColor",       "текстура/дерево"),
    (r"Drap TX",                    "Drap TX",              "текстура/дерево"),
    (r"Drap ST",                    "Drap ST",              "текстура/дерево"),
    (r"Drap",                       "Drap",                 "текстура/дерево"),
    (r"Lite PE",                    "Lite PE",              "глянец"),
    (r"\bPE\b|\bРЕ\b",              "PE (полиэстер)",       "глянец"),
]


def fetch(url, page):
    """Скачать страницу с диск-кэшем (live_pN.html), чтобы не дёргать сайт повторно."""
    import os
    cache = f"live_p{page}.html"
    if os.path.exists(cache):
        return open(cache, encoding="utf-8", errors="replace").read()
    req = urllib.request.Request(url, headers=HEADERS)
    last = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                html = r.read().decode("utf-8", "replace")
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
        if re.match(r"\s*(?:" + pat + r")", name):
            return norm, pat
    return "", ""


def detect_coating(name):
    for pat, norm, finish in COATINGS:
        if re.search(pat, name, re.I):
            return norm, finish, pat
    return "", "", None


def has_film(name):
    return "пленк" in name.lower() or "плёнк" in name.lower()


def detect_color(name, type_pat, coat_pat):
    """Цвет = остаток названия после удаления типа, толщин, 'с плёнкой' и покрытия."""
    s = name
    if type_pat:
        s = re.sub(r"^\s*(?:" + type_pat + r")", "", s, count=1, flags=re.I)
    if coat_pat:
        s = re.sub(coat_pat, "", s, count=1, flags=re.I)
    s = re.sub(r"с\s*пл[её]нкой", "", s, flags=re.I)   # признак плёнки
    s = re.sub(r"\b0[.,]\d+\b", "", s)                  # толщины 0,2/0,345/0,45/0,5
    s = re.sub(r"\(копия\)", "", s)
    # служебные слова серий/модификаторов, не относящиеся к цвету
    s = re.sub(r"\b(?:Classic|Lite|new|Grand|Line|Double|Twincolor|TwinColor|GOFR|ST|TX)\b",
               "", s, flags=re.I)
    s = re.sub(r"\bRAL\b|\bRR\d+\b", "", s)             # технические коды-префиксы
    s = re.sub(r"\b\d{3,4}\b", "", s)                   # б/числовые коды цвета (8017, 9003)
    s = re.sub(r"\s+", " ", s).strip(" -–")
    # нормализация регистра первой буквы (мокрый -> Мокрый)
    if s and s[0].islower() and re.match(r"[а-яё]", s):
        s = s[0].upper() + s[1:]
    return s


def parse_cards(htmls):
    rows = []
    seen = set()
    # одна карточка = от 'catalog_item_wrapp item' до закрытия; режем по маркеру
    for html in htmls:
        chunks = re.split(r'class="catalog_item_wrapp item"', html)
        for ch in chunks[1:]:
            mid = re.search(r"bx_basket_div_(\d+)", ch)
            pid = mid.group(1) if mid else ""
            # настоящее имя — в item-title
            mt = re.search(r'class="item-title">.*?<span>(.*?)</span>', ch, re.S)
            name = clean(mt.group(1)) if mt else ""
            if not name:
                continue
            # ссылка на товар
            ml = re.search(r'class="dark_link"\s+href="([^"]+)"', ch) or \
                 re.search(r'href="([^"]+)"\s+class="dark_link"', ch)
            url = ml.group(1) if ml else ""
            if url.startswith("/"):
                url = SITE + url
            # картинка
            mi = re.search(r'<img src="([^"]+)"', ch)
            img = mi.group(1) if mi else ""
            if img.startswith("/"):
                img = SITE + img
            img_file = img.rsplit("/", 1)[-1]
            # наличие
            ma = re.search(r'class="available[^"]*">.*?</span>\s*(.*?)</span>', ch, re.S)
            avail = clean(ma.group(1)) if ma else ""

            if pid in seen:
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
                "name": name,
                "availability": avail,
                "image_file": img_file,
                "image_url": img,
                "url": url,
            })
    return rows


def main():
    htmls = []
    page = 1
    max_pages = 30
    while page <= max_pages:
        url = BASE if page == 1 else f"{BASE}?PAGEN_1={page}"
        try:
            html = fetch(url, page)
        except Exception as e:
            print(f"стр.{page}: ошибка {e}", file=sys.stderr)
            break
        n = len(re.findall(r'class="catalog_item_wrapp item"', html))
        print(f"стр.{page}: карточек {n}", file=sys.stderr)
        if n == 0:
            break
        htmls.append(html)
        # определить максимум страниц из пагинации
        nums = [int(x) for x in re.findall(r"PAGEN_1=(\d+)", html)]
        if nums:
            max_pages = min(max_pages, max(nums))
        page += 1
        time.sleep(0.5)

    rows = parse_cards(htmls)
    print(f"ИТОГО уникальных товаров: {len(rows)}", file=sys.stderr)

    cols = ["id", "type", "coating", "finish", "color", "film",
            "name", "availability", "image_file", "image_url", "url"]
    with open("siding.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, delimiter=";")
        w.writeheader()
        w.writerows(rows)
    with open("siding.json", "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    print("Сохранено: siding.csv, siding.json", file=sys.stderr)


if __name__ == "__main__":
    main()

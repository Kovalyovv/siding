#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Сводит оба источника (mirkrovli + grandline) в единый data.json для сайта.
Добавляет source, нормализует цвет, присваивает hex палитры, считает meta
(типы, финиши, цвета с hex, источники, диапазон цен).
"""
import json
import re

# ---- нормализация остаточных артефактов в названии цвета ----
COLOR_FIX = {
    "32 темно-коричневый": "Темно-коричневый",
    "Черный темный": "Черный",
    "NL805 серо-коричневый гефест": "NL серо-коричневый гефест",
}

# ---- палитра: точные имена (в нижнем регистре) -> hex (аналоги RAL) ----
COLOR_HEX = {
    # коричневые
    "шоколад": "#45322e", "темно-коричневый": "#3a2a23",
    "шоколадно-коричневый": "#3a2a23", "коричнево-красный": "#6f2f2a",
    # серые / графит
    "мокрый асфальт": "#474b4f", "темно-серый": "#4c4f53",
    "антрацитово-серый": "#373d41", "сигнальный серый": "#9a9a9a",
    "светло-серый": "#b2b5b8", "мышино-серый": "#6c6f6c",
    "nl серо-коричневый гефест": "#6f655a",
    # чёрный / белый / кость
    "черный": "#1b1b1b", "сигнальный белый": "#eeede7",
    "бело-алюминиевый": "#a6a6a6", "слоновая кость": "#e2d3ab",
    "светлая слоновая кость": "#e7d4b6",
    # красные / терракота
    "терракота": "#9d4a37", "красное вино": "#5c2127",
    "рубиново-красный": "#84191f", "оксидно-красный": "#6e342f",
    # зелёные
    "зеленый мох": "#2f4538", "лиственно-зеленый": "#33583b",
    "хромовая зелень": "#39472d",
    # синие
    "водная синь": "#2c5f7a", "сигнальный синий": "#1f466c",
    "ультрамариново-синий": "#22244f", "пастельно-синий": "#6a93b0",
    # прочее
    "оранжевый": "#c75b1e", "цинково-желтый": "#d6b338",
    "телегрей 4": "#5a5f63",
    "камень": "#8a8278", "королевский камень": "#6f6a60", "sand stone": "#c2a878",
    # дерево-принты
    "золотой дуб": "#b07a3c", "золотой дуб насыщенный фреш": "#a86f33",
    "golden wood": "#b07a3c",
    "античный дуб": "#6e4a2f", "antique wood": "#6e4a2f",
    "бразильская вишня": "#5c2e23", "бразильская вишня фреш": "#5c2e23",
    "бразильская вишня темная фреш": "#4d271f", "cherry wood": "#5c2e23",
    "рябина": "#7c3b2a", "рябина фреш": "#7c3b2a", "рябина насыщенная фреш": "#74331f",
    "rowan": "#7c3b2a",
    "медовое дерево": "#b5803f", "honey wood": "#b5803f",
    "кофейное дерево": "#4b3526", "coffee wood": "#4b3526",
    "шоколадное дерево": "#4a3326", "choco wood": "#4a3326",
    "молочное дерево": "#c9b48f", "milky wood": "#c9b48f",
    "снежное дерево": "#cdbfa6", "snow wood": "#cdbfa6",
    "white wood": "#cdbfa6", "беленый дуб": "#c7b8a0",
    "северное дерево": "#b8a888", "nordic wood": "#b8a888",
    "серое дерево": "#9a8d78",
    "миндальное дерево фреш": "#c2a06f", "almond wood fresh": "#c2a06f",
    "сосна фреш": "#c79a5e",
    "nl серо-коричневый гефест ": "#6f655a",
}


def color_to_hex(name):
    key = name.strip().lower()
    if key in COLOR_HEX:
        return COLOR_HEX[key]
    # эвристика по ключевым словам
    t = key
    rules = [
        ("шоколад", "#45322e"), ("коричнев", "#3f2d25"), ("асфальт", "#474b4f"),
        ("антрацит", "#373d41"), ("графит", "#383e42"), ("серо-коричнев", "#6f655a"),
        ("черн", "#1b1b1b"), ("бел", "#eeede7"), ("кость", "#e2d3ab"),
        ("терракот", "#9d4a37"), ("вино", "#5c2127"), ("красн", "#7a2b29"),
        ("мох", "#2f4538"), ("зелен", "#33583b"), ("син", "#1f466c"),
        ("дуб", "#8a5a30"), ("вишн", "#5c2e23"), ("дерев", "#7a5536"),
        ("камень", "#8a8278"), ("серый", "#7d7f80"), ("сер", "#7d7f80"),
        ("оранж", "#c75b1e"), ("желт", "#d6b338"),
    ]
    for k, v in rules:
        if k in t:
            return v
    return "#9b9b97"  # нейтральный фолбэк


def load(path, source, with_price):
    out = []
    for x in json.load(open(path, encoding="utf-8")):
        color = COLOR_FIX.get(x["color"], x["color"]).strip()
        if color:
            color = color[0].upper() + color[1:]
        imgs = x.get("images") or ([x["image_url"]] if x.get("image_url") else [])
        out.append({
            "source": source,
            "id": x["id"],
            "type": x["type"],
            "coating": x["coating"],
            "finish": x["finish"],
            "color": color,
            "hex": color_to_hex(color),
            "film": x.get("film", ""),
            "price": x.get("price", "") if with_price else "",
            "name": x["name"],
            "image": x["image_url"],
            "images": imgs,
            "url": x["url"],
        })
    return out


def main():
    data = load("siding.json", "mirkrovli", False) + \
           load("grandline.json", "grandline", True)

    types = sorted({x["type"] for x in data})
    finishes = sorted({x["finish"] for x in data})
    sources = sorted({x["source"] for x in data})
    # цвета с hex + частотой, отсортированы по частоте
    from collections import Counter
    cc = Counter(x["color"] for x in data)
    colors = [{"name": c, "hex": color_to_hex(c), "count": n}
              for c, n in cc.most_common()]
    prices = [int(x["price"]) for x in data if str(x["price"]).isdigit()]

    meta = {
        "total": len(data),
        "types": types,
        "finishes": finishes,
        "sources": sources,
        "colors": colors,
        "price_min": min(prices) if prices else 0,
        "price_max": max(prices) if prices else 0,
    }
    json.dump({"meta": meta, "items": data},
              open("data.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print(f"data.json: {len(data)} товаров, {len(types)} типов, "
          f"{len(colors)} цветов, цена {meta['price_min']}-{meta['price_max']}")


if __name__ == "__main__":
    main()

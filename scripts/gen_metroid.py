#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Conjunto CURADO de trajes/formas da Samus (Wikitroid). Baixa renders PNG,
recorta transparente, centraliza em 320px e monta um mosaico p/ inspeção."""
import io, json, os, urllib.parse, urllib.request
from PIL import Image, ImageDraw

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
API = "https://metroid.fandom.com/api.php"
SIZE = 320

# (code, query, tokens_obrigatorios, tokens_proibidos_extra)
TARGETS = [
    ("power_suit",    "Power Suit Samus artwork",   ["power"],   []),
    ("varia_suit",    "Varia Suit Samus artwork",   ["varia"],   []),
    ("gravity_suit",  "Gravity Suit Samus artwork", ["gravity"], []),
    ("fusion_suit",   "Fusion Suit Samus artwork",  ["fusion"],  []),
    ("omega_suit",    "Omega Suit Samus",           ["omega"],   []),
    ("metroid_suit",  "Metroid Suit Samus Fusion",  ["metroid", "suit"], []),
    ("zero_suit",     "Zero Suit Samus artwork",    ["zero"],    []),
    ("phazon_suit",   "Phazon Suit Samus artwork",  ["phazon", "suit"], ["dark samus"]),
    ("dark_suit",     "Dark Suit Samus artwork",    ["dark", "suit"], ["samus."]),
    ("light_suit",    "Light Suit Samus artwork",   ["light", "suit"], []),
    ("ped_suit",      "PED Suit Samus",             ["ped"],     []),
    ("hazard_shield", "Hazard Shield Samus Dread",  ["hazard"],  []),
    ("dark_samus",    "Dark Samus artwork render",  ["dark", "samus"], []),
    ("samus_dread",   "Samus Dread artwork",        ["dread"],   []),
]
BAD = ("cover", "comic", "page", " vs ", "vs ", "issue", "boxart", "box art",
       "manga", "screenshot", "logo", "icon", "no.", "#", "title", "poster",
       "wallpaper", "sprite", "map", "concept scan", "beta", "gif")
GOOD = ("artwork", "render", "art", "official", "dread", "prime", "hd")


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=30).read()


def find(query, need, ban):
    qs = urllib.parse.urlencode({
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": query, "gsrnamespace": "6", "gsrlimit": "24",
        "prop": "imageinfo", "iiprop": "url|size|mime", "iiurlwidth": "640",
    })
    pages = list(json.loads(get(API + "?" + qs).decode()).get("query", {}).get("pages", {}).values())
    best = None
    for p in pages:
        ii = (p.get("imageinfo") or [{}])[0]
        if ii.get("mime") != "image/png":
            continue
        w, h = ii.get("width", 0), ii.get("height", 0)
        if not w or not h or h < 220:
            continue
        t = p.get("title", "").lower()
        if any(b in t for b in BAD) or any(b in t for b in ban):
            continue
        if not all(n in t for n in need):
            continue
        score = min(h, 2000) + (sum(1500 for g in GOOD if g in t)) + (1200 if h >= w else 0)
        if best is None or score > best[0]:
            best = (score, ii.get("thumburl") or ii.get("url"), p.get("title"))
    return best


os.makedirs("/tmp/met", exist_ok=True)
ok = []
for code, query, need, ban in TARGETS:
    try:
        c = find(query, need, ban)
        if not c:
            print("MISS", code); continue
        im = Image.open(io.BytesIO(get(c[1]))).convert("RGBA")
        bb = im.getbbox()
        if bb:
            im = im.crop(bb)
        im.thumbnail((SIZE, SIZE), Image.LANCZOS)
        cv = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
        cv.paste(im, ((SIZE - im.width) // 2, (SIZE - im.height) // 2), im)
        cv.save("/tmp/met/%s.png" % code, optimize=True)
        ok.append(code); print("OK  ", code, "<-", c[2])
    except Exception as e:
        print("ERR ", code, repr(e))

cols = 4
rows = (len(ok) + cols - 1) // cols
TH = 220
m = Image.new("RGB", (cols * TH, rows * TH), (16, 22, 30))
dr = ImageDraw.Draw(m)
for i, code in enumerate(ok):
    im = Image.open("/tmp/met/%s.png" % code).convert("RGBA")
    im.thumbnail((TH - 30, TH - 30), Image.LANCZOS)
    bg = Image.new("RGB", (TH, TH), (24, 30, 40))
    bg.paste(im, ((TH - im.width) // 2, (TH - im.height) // 2 - 8), im)
    m.paste(bg, ((i % cols) * TH, (i // cols) * TH))
    dr.text(((i % cols) * TH + 6, (i // cols) * TH + TH - 16), code, fill=(220, 230, 245))
m.save("/tmp/met/_montage.png")
print("ok:", len(ok), "/", len(TARGETS))

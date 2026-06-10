#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Conjunto CURADO de Sonics em alta (renders oficiais 'Sonic Channel' + alguns
renders 3D bons). Baixa, recorta transparente, centraliza em 320px e monta um
mosaico para inspeção visual. Mantém só PNG (transparente) e nomes coerentes."""
import io, json, os, urllib.parse, urllib.request
from PIL import Image

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
API = "https://sonic.fandom.com/api.php"
SIZE = 320

# (code, query, tokens_obrigatorios, tokens_proibidos_extra)
TARGETS = [
    ("sonic_super",   "Frontiers render Super Sonic", ["super", "sonic"], []),
    ("sonic_boom",    "Sonic 3D Sonic Boom render",   ["boom", "sonic"],  ["amy", "tails", "knuckles"]),
    ("metal_sonic",   "Metal Sonic render",           ["metal", "sonic"], ["knuckles"]),
    ("shadow",        "Sonic Channel Shadow",         ["shadow"],         []),
    ("silver",        "Sonic Channel Silver",         ["silver"],         []),
    ("blaze",         "Sonic Channel Blaze",          ["blaze"],          []),
    ("tails",         "Sonic Channel Tails",          ["tails"],          []),
    ("knuckles",      "Sonic Channel Knuckles",       ["knuckles"],       ["metal"]),
    ("amy",           "Sonic Channel Amy",            ["amy"],            []),
    ("sonic_modern",  "Sonic Channel Sonic",          ["sonic"],          ["amy", "tails", "knuckles", "shadow", "metal", "silver", "blaze", "boom", "classic"]),
    ("sonic_excalibur", "Excalibur Sonic render",     ["excalibur"],      []),
    ("sonic_werehog", "Sonic Werehog render",         ["werehog"],        []),
]
BAD = ("cover", "comic", "page", " vs ", "vs ", "issue", "archie", "idw", "boxart",
       "box art", "manga", "screenshot", "scene", "logo", "icon", "no.", "#",
       "eggman", "title", "poster", "displate", "wallpaper", "skin", "dash", "sprite")


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=30).read()


def find(query, need, ban):
    qs = urllib.parse.urlencode({
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": query, "gsrnamespace": "6", "gsrlimit": "20",
        "prop": "imageinfo", "iiprop": "url|size|mime", "iiurlwidth": "640",
    })
    pages = list(json.loads(get(API + "?" + qs).decode()).get("query", {}).get("pages", {}).values())
    best = None
    for p in pages:
        ii = (p.get("imageinfo") or [{}])[0]
        if ii.get("mime") != "image/png":       # só renders transparentes
            continue
        w, h = ii.get("width", 0), ii.get("height", 0)
        if not w or not h or h < 200:
            continue
        t = p.get("title", "").lower()
        if any(b in t for b in BAD) or any(b in t for b in ban):
            continue
        if not all(n in t for n in need):
            continue
        score = min(h, 2000) + (3000 if "channel" in t else 0) + (1200 if h >= w else 0)
        if best is None or score > best[0]:
            best = (score, ii.get("thumburl") or ii.get("url"), p.get("title"))
    return best


os.makedirs("/tmp/son2", exist_ok=True)
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
        cv.save("/tmp/son2/%s.png" % code, optimize=True)
        ok.append(code); print("OK  ", code, "<-", c[2])
    except Exception as e:
        print("ERR ", code, repr(e))

cols = 4
rows = (len(ok) + cols - 1) // cols
TH = 220
m = Image.new("RGB", (cols * TH, rows * TH), (24, 18, 36))
from PIL import ImageDraw
dr = ImageDraw.Draw(m)
for i, code in enumerate(ok):
    im = Image.open("/tmp/son2/%s.png" % code).convert("RGBA")
    im.thumbnail((TH - 30, TH - 30), Image.LANCZOS)
    bg = Image.new("RGB", (TH, TH), (32, 24, 48))
    bg.paste(im, ((TH - im.width) // 2, (TH - im.height) // 2 - 8), im)
    m.paste(bg, ((i % cols) * TH, (i // cols) * TH))
    dr.text(((i % cols) * TH + 6, (i // cols) * TH + TH - 16), code, fill=(230, 220, 250))
m.save("/tmp/son2/_montage.png")
print("ok:", len(ok), "/", len(TARGETS))

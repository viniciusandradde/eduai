#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Busca renders de personagens Sonic no Sonic Fandom (MediaWiki API), baixa o
melhor candidato, recorta o transparente, centraliza em 320px e salva em
/tmp/sonout. Gera também um mosaico /tmp/sonout/_montage.png para inspeção."""
import io, json, os, urllib.parse, urllib.request
from PIL import Image

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
API = "https://sonic.fandom.com/api.php"
SIZE = 320

# (code, query, tokens-que-devem-aparecer-no-titulo)
CHARS = [
    ("sonic_classic",   "Classic Sonic render",       ["classic"]),
    ("sonic_modern",    "Sonic the Hedgehog render",   ["sonic"]),
    ("sonic_super",     "Super Sonic render",          ["super"]),
    ("sonic_hyper",     "Hyper Sonic render",          ["hyper"]),
    ("sonic_dark",      "Dark Sonic render",           ["dark"]),
    ("sonic_darkspine", "Darkspine Sonic",             ["darkspine"]),
    ("sonic_excalibur", "Excalibur Sonic",             ["excalibur"]),
    ("sonic_werehog",   "Sonic Werehog render",        ["werehog"]),
    ("sonic_cyber",     "Cyber Sonic Prime",           ["cyber"]),
    ("sonic_movie",     "Movie Sonic the Hedgehog",    ["movie", "sonic"]),
    ("sonic_prime",     "Sonic Prime profile",         ["prime", "sonic"]),
    ("sonic_boom",      "Sonic Boom Sonic render",     ["boom", "sonic"]),
    ("metal_sonic",     "Metal Sonic render",          ["metal"]),
    ("shadow",          "Shadow the Hedgehog render",  ["shadow"]),
    ("silver",          "Silver the Hedgehog render",  ["silver"]),
    ("blaze",           "Blaze the Cat render",        ["blaze"]),
    ("tails",           "Miles Tails Prower render",   ["tails"]),
    ("knuckles",        "Knuckles the Echidna render", ["knuckles"]),
    ("amy",             "Amy Rose render",             ["amy"]),
]
BAD = ("cover", "comic", "page", " vs ", "vs ", "issue", "archie", "idw",
       "boxart", "box art", "manga", "screenshot", "scene", "logo", "icon",
       "no.", "#", "eggman", "title", "poster", "displate", "wallpaper")
GOOD = ("render", "profile", "model", "art", "pose", "channel", "official")


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=30).read()


def find_image(query, tokens):
    qs = urllib.parse.urlencode({
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": query, "gsrnamespace": "6", "gsrlimit": "20",
        "prop": "imageinfo", "iiprop": "url|size|mime", "iiurlwidth": "512",
    })
    data = json.loads(get(API + "?" + qs).decode())
    pages = list(data.get("query", {}).get("pages", {}).values())
    cands = []
    for p in pages:
        ii = (p.get("imageinfo") or [{}])[0]
        mime = ii.get("mime", "")
        if not mime.startswith("image/") or mime.endswith(("gif", "svg+xml")):
            continue
        w, h = ii.get("width", 0), ii.get("height", 0)
        if not w or not h:
            continue
        title = p.get("title", "").lower()
        if any(b in title for b in BAD):
            continue
        if not all(t in title for t in tokens):   # precisa casar o personagem
            continue
        score = min(h, 2000)
        if mime == "image/png":
            score += 6000                          # render transparente
        if any(g in title for g in GOOD):
            score += 2500
        if h >= w:
            score += 1500
        cands.append((score, ii.get("thumburl") or ii.get("url"), p.get("title")))
    cands.sort(reverse=True)
    return cands[0] if cands else None


os.makedirs("/tmp/sonout", exist_ok=True)
ok = []
for code, query, tokens in CHARS:
    try:
        c = find_image(query, tokens)
        if not c:
            print("MISS", code, "(", query, ")"); continue
        _, url, title = c
        im = Image.open(io.BytesIO(get(url))).convert("RGBA")
        bbox = im.getbbox()                    # remove transparente nas bordas
        if bbox:
            im = im.crop(bbox)
        im.thumbnail((SIZE, SIZE), Image.LANCZOS)
        canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
        canvas.paste(im, ((SIZE - im.width) // 2, (SIZE - im.height) // 2), im)
        canvas.save("/tmp/sonout/%s.png" % code, optimize=True)
        ok.append((code, title))
        print("OK  ", code, "<-", title)
    except Exception as e:
        print("ERR ", code, repr(e))

# mosaico para inspeção
cols = 5
rows = (len(ok) + cols - 1) // cols
TH = 200
mont = Image.new("RGB", (cols * TH, rows * TH), (24, 18, 36))
for i, (code, _) in enumerate(ok):
    im = Image.open("/tmp/sonout/%s.png" % code).convert("RGBA")
    im.thumbnail((TH - 16, TH - 16), Image.LANCZOS)
    bg = Image.new("RGB", (TH, TH), (32, 24, 48))
    bg.paste(im, ((TH - im.width) // 2, (TH - im.height) // 2), im)
    mont.paste(bg, ((i % cols) * TH, (i // cols) * TH))
mont.save("/tmp/sonout/_montage.png")
print("total ok:", len(ok), "/", len(CHARS))

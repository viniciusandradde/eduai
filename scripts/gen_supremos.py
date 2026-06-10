#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Baixa e otimiza os avatares "supremos" (Pokémon via PokéAPI, Sonic/Metroid via
Smash Bros), centralizados num quadrado transparente 320px. Salva em /tmp/avout."""
import io, os, urllib.request
from PIL import Image

POKE = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/{}.png"
SMASH = "https://www.smashbros.com/assets_v2/img/fighter/{}/main.png"

ITEMS = [
    ("poke_pikachu",  POKE.format(25)),
    ("poke_charizard", POKE.format(6)),
    ("poke_mewtwo",   POKE.format(150)),
    ("poke_gengar",   POKE.format(94)),
    ("poke_lucario",  POKE.format(448)),
    ("poke_greninja", POKE.format(658)),
    ("sonic",         SMASH.format("sonic")),
    ("metroid_samus", SMASH.format("samus")),
    ("metroid_ridley", SMASH.format("ridley")),
]
SIZE = 320
os.makedirs("/tmp/avout", exist_ok=True)

for code, url in ITEMS:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.smashbros.com/"})
    data = urllib.request.urlopen(req, timeout=40).read()
    im = Image.open(io.BytesIO(data)).convert("RGBA")
    im.thumbnail((SIZE, SIZE), Image.LANCZOS)
    canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    canvas.paste(im, ((SIZE - im.width) // 2, (SIZE - im.height) // 2), im)
    canvas.save("/tmp/avout/%s.png" % code, optimize=True)
    print("ok", code, im.size, "->", os.path.getsize("/tmp/avout/%s.png" % code), "B")

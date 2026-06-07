#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gera os ícones PWA do VSA EduAI (pixel-art, só stdlib): livro branco em fundo roxo."""
import zlib, struct, os

GRID = 16
ROXO = (124, 58, 237)
BRANCO = (245, 247, 250)

LIVRO = [  # 8x8 — livro aberto
    "........",
    ".XXXXXX.",
    ".X.XX.X.",
    ".X.XX.X.",
    ".X.XX.X.",
    ".X.XX.X.",
    ".XXXXXX.",
    "........",
]

def png(pixels, w):
    raw = bytearray()
    for row in pixels:
        raw.append(0)
        for (r, g, b) in row:
            raw += bytes((r, g, b))
    def ch(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n'
            + ch(b'IHDR', struct.pack(">IIBBBBB", w, w, 8, 2, 0, 0, 0))
            + ch(b'IDAT', zlib.compress(bytes(raw), 9)) + ch(b'IEND', b''))

def render(scale):
    grid = [[ROXO] * GRID for _ in range(GRID)]
    for y, linha in enumerate(LIVRO):
        for x, c in enumerate(linha):
            if c == 'X':
                grid[y + 4][x + 4] = BRANCO
    out = []
    for row in grid:
        rp = []
        for px in row:
            rp += [px] * scale
        for _ in range(scale):
            out.append(list(rp))
    return png(out, GRID * scale)

dest = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app', 'static')
os.makedirs(dest, exist_ok=True)
for nome, scale in (('icon-192.png', 12), ('icon-512.png', 32)):
    open(os.path.join(dest, nome), 'wb').write(render(scale))
    print('ok:', os.path.join(dest, nome))

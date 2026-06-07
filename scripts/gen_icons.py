#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gera os ícones PWA do VSA EduAI (pixel-art, só stdlib):
pilha de livros coloridos em fundo roxo — combinando com a página inicial (📚)."""
import zlib, struct, os

GRID = 16
PAL = {
    '.': (124, 58, 237),   # roxo (fundo, tema)
    'B': (59, 130, 246),   # livro azul
    'R': (239, 68, 68),    # livro vermelho
    'G': (34, 197, 94),    # livro verde
    'W': (245, 247, 250),  # páginas (branco)
    'K': (15, 17, 23),     # lombada/sombra (escuro)
}

# Pilha de 3 livros (16x16): lombada (K) à esquerda, páginas (W) à direita.
ART = [
    "................",
    "................",
    "................",
    "..KBBBBBBBBBBW..",
    "..KBBBBBBBBBBW..",
    "..KKKKKKKKKKKK..",
    "..KRRRRRRRRRRW..",
    "..KRRRRRRRRRRW..",
    "..KKKKKKKKKKKK..",
    "..KGGGGGGGGGGW..",
    "..KGGGGGGGGGGW..",
    "..KKKKKKKKKKKK..",
    "................",
    "................",
    "................",
    "................",
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
    out = []
    for linha in ART:
        rowpix = []
        for ch in linha:
            rowpix += [PAL.get(ch, PAL['.'])] * scale
        for _ in range(scale):
            out.append(list(rowpix))
    return png(out, GRID * scale)

dest = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app', 'static')
os.makedirs(dest, exist_ok=True)
for nome, scale in (('icon-192.png', 12), ('icon-512.png', 32)):
    open(os.path.join(dest, nome), 'wb').write(render(scale))
    print('ok:', os.path.join(dest, nome))

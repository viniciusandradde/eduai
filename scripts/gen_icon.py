#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gera os ícones PWA do VSA EduAI: capelo de formatura branco sobre gradiente
roxo (full-bleed p/ maskable). Renderiza em supersampling e reduz com LANCZOS."""
from PIL import Image, ImageDraw, ImageFilter

OUT = {"icon-512.png": 512, "icon-192.png": 192}
SS = 4  # supersampling


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def render(px):
    """Desenha o ícone num canvas px×px."""
    img = Image.new("RGB", (px, px))
    d = ImageDraw.Draw(img)
    # fundo: gradiente vertical roxo (claro -> escuro)
    top, bot = (146, 86, 248), (74, 26, 158)
    for y in range(px):
        d.line([(0, y), (px, y)], fill=lerp(top, bot, y / px))
    # brilho suave no topo-esquerdo
    glow = Image.new("L", (px, px), 0)
    gd = ImageDraw.Draw(glow)
    gd.ellipse([-px * 0.35, -px * 0.45, px * 0.75, px * 0.55], fill=70)
    glow = glow.filter(ImageFilter.GaussianBlur(px * 0.10))
    img = Image.composite(Image.new("RGB", (px, px), (255, 255, 255)), img, glow)

    d = ImageDraw.Draw(img, "RGBA")
    cx, cy = px / 2, px * 0.47
    W = px * 0.40       # meia-largura do tabuleiro (mortarboard)
    H = px * 0.20       # meia-altura (losango achatado)
    white = (255, 255, 255, 255)
    shadow = (40, 12, 90, 90)

    # sombra suave do capelo
    sh = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    sd.polygon([(cx, cy - H + px*0.02), (cx + W, cy + px*0.02),
                (cx, cy + H + px*0.02), (cx - W, cy + px*0.02)], fill=shadow)
    sh = sh.filter(ImageFilter.GaussianBlur(px * 0.02))
    img = Image.alpha_composite(img.convert("RGBA"), sh).convert("RGB")
    d = ImageDraw.Draw(img, "RGBA")

    # cabeça do capelo (parte que fica na cabeça) — trapézio sob o tabuleiro
    headW = W * 0.52
    hy = cy + H * 0.15
    d.polygon([(cx - headW, hy), (cx + headW, hy),
               (cx + headW * 0.78, hy + H * 1.15), (cx - headW * 0.78, hy + H * 1.15)],
              fill=(238, 232, 252, 255))
    d.ellipse([cx - headW, hy + H * 1.15 - headW * 0.5, cx + headW, hy + H * 1.15 + headW * 0.5],
              fill=(238, 232, 252, 255))

    # tabuleiro (losango) por cima
    d.polygon([(cx, cy - H), (cx + W, cy), (cx, cy + H), (cx - W, cy)], fill=white)
    # leve face inferior para dar volume
    d.polygon([(cx - W, cy), (cx, cy + H), (cx + W, cy),
               (cx, cy + H * 1.12)], fill=(214, 198, 244, 255))

    # botão central + tassel (cordão) pendurado à direita
    btnr = px * 0.022
    d.ellipse([cx - btnr, cy - btnr, cx + btnr, cy + btnr], fill=(124, 58, 237, 255))
    tx = cx + W * 0.62
    d.line([(cx, cy), (tx, cy - H * 0.15)], fill=(255, 209, 102, 255), width=max(2, int(px*0.012)))
    d.line([(tx, cy - H * 0.15), (tx, cy + H * 0.95)], fill=(255, 209, 102, 255), width=max(2, int(px*0.012)))
    br = px * 0.030
    d.ellipse([tx - br, cy + H * 0.95 - br, tx + br, cy + H * 0.95 + br], fill=(255, 193, 7, 255))

    # faísca (toque de "AI") no canto superior direito do capelo
    sx, sy = cx + W * 0.72, cy - H * 1.15
    r1, r2 = px * 0.052, px * 0.018
    d.polygon([(sx, sy - r1), (sx + r2, sy - r2), (sx + r1, sy),
               (sx + r2, sy + r2), (sx, sy + r1), (sx - r2, sy + r2),
               (sx - r1, sy), (sx - r2, sy - r2)], fill=(255, 255, 255, 235))
    return img


for name, size in OUT.items():
    big = render(size * SS)
    big.resize((size, size), Image.LANCZOS).save("/tmp/out/" + name)
    print("ok", name, size)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_cara.py
================
Génère les images de référence des caractères depuis les polices TTF du dossier
'texte/' et les sauvegarde dans 'cara/{nom_police}/{caractere}.png'.

Usage :
    python generate_cara.py

Après exécution :
  - Ouvrez les fichiers 'cara/*_preview.png' pour comparer visuellement les polices.
  - Dans manhwa_crawler.py, mettez CARA_FONT = "nom_dossier_choisi"
    (ex. CARA_FONT = "ComicSansMS3")
"""

import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# ── Configuration ─────────────────────────────────────────────────────────────
FONTS_DIR = "texte"          # Dossier contenant les fichiers .ttf
CARA_DIR  = "cara"           # Dossier de sortie
FONT_SIZE = 80               # Taille de rendu (px) — plus grand = meilleur détail
PADDING   = 14               # Marge autour du caractère (px)

# Caractères à générer (majuscules + chiffres + quelques symboles courants)
CHARS = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!?,.'\"()-:")

# ── Helpers ────────────────────────────────────────────────────────────────────

def safe_filename(char: str) -> str:
    """Retourne un nom de fichier sûr pour le caractère donné."""
    safe = {
        '/':  '_slash',
        '\\': '_backslash',
        ':':  '_colon',
        '*':  '_star',
        '?':  '_question',
        '"':  '_dquote',
        '<':  '_lt',
        '>':  '_gt',
        '|':  '_pipe',
        '.':  '_dot',
        "'":  '_squote',
        '(':  '_lpar',
        ')':  '_rpar',
        ',':  '_comma',
        '-':  '_dash',
        '!':  '_excl',
    }
    return safe.get(char, char)


def render_char(font: ImageFont.FreeTypeFont, char: str) -> Image.Image:
    """
    Rend un caractère en noir sur fond blanc avec padding et binarisation Otsu.
    Retourne une image PIL en niveaux de gris binaire.
    """
    # Mesurer la bounding box exacte du caractère
    probe = Image.new('L', (FONT_SIZE * 4, FONT_SIZE * 4), 255)
    draw  = ImageDraw.Draw(probe)
    bbox  = draw.textbbox((FONT_SIZE, FONT_SIZE), char, font=font)
    # bbox = (left, top, right, bottom) dans l'espace de probe

    char_w = max(bbox[2] - bbox[0], 1)
    char_h = max(bbox[3] - bbox[1], 1)

    img_w = char_w + PADDING * 2
    img_h = char_h + PADDING * 2

    img  = Image.new('L', (img_w, img_h), 255)
    draw = ImageDraw.Draw(img)
    # Décaler pour que le caractère commence à (PADDING, PADDING)
    draw.text((PADDING - bbox[0] + FONT_SIZE, PADDING - bbox[1] + FONT_SIZE),
              char, font=font, fill=0)

    # Binarisation simple au seuil 128 (nettoie l'anticrénelage)
    arr = np.array(img)
    arr = np.where(arr < 128, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)


def generate_font(font_path: str, font_name: str) -> int:
    """Génère les images pour une police. Retourne le nombre de caractères générés."""
    try:
        font = ImageFont.truetype(font_path, FONT_SIZE)
    except Exception as exc:
        print(f"    [ERREUR] Impossible de charger : {exc}")
        return 0

    out_dir = os.path.join(CARA_DIR, font_name)
    os.makedirs(out_dir, exist_ok=True)

    images_for_preview: list = []
    count = 0

    for char in CHARS:
        try:
            img = render_char(font, char)
        except Exception:
            continue

        # Ignorer les images presque vides (caractère absent de la police)
        arr = np.array(img)
        if arr.min() == arr.max():   # tout blanc ou tout noir → pas de glyphe
            continue

        fname = safe_filename(char) + ".png"
        img.save(os.path.join(out_dir, fname))
        images_for_preview.append((char, img))
        count += 1

    # ── Générer la prévisualisation (strip de tous les caractères) ─────────
    if images_for_preview:
        _make_preview(images_for_preview, font_name)

    return count


def _make_preview(images: list, font_name: str) -> None:
    """Génère une image récapitulative de tous les caractères."""
    cols    = 18
    cell_w  = FONT_SIZE + PADDING * 2 + 4
    cell_h  = FONT_SIZE + PADDING * 2 + 18   # 18px pour le label en bas
    rows    = (len(images) + cols - 1) // cols

    canvas = Image.new('L', (cols * cell_w + 4, rows * cell_h + 4), 200)

    try:
        label_font = ImageFont.truetype(
            os.path.join(FONTS_DIR, os.listdir(FONTS_DIR)[0]), 12)
    except Exception:
        label_font = ImageFont.load_default()

    draw = ImageDraw.Draw(canvas)

    for idx, (char, img) in enumerate(images):
        col = idx % cols
        row = idx // cols
        ox  = col * cell_w + 2
        oy  = row * cell_h + 2

        # Fond blanc pour la cellule
        canvas.paste(255, (ox, oy, ox + cell_w - 2, oy + cell_h - 2))

        # Redimensionner le caractère pour qu'il rentre dans la cellule
        thumb = img.resize((cell_w - 4, cell_h - 22), Image.LANCZOS)
        canvas.paste(thumb, (ox + 2, oy + 2))

        # Label du caractère
        draw.text((ox + 4, oy + cell_h - 18), repr(char).strip("'"), fill=0,
                  font=label_font)

    preview_path = os.path.join(CARA_DIR, f"{font_name}_preview.png")
    canvas.save(preview_path)
    print(f"    Prévisualisation → {preview_path}")


# ── Point d'entrée ─────────────────────────────────────────────────────────────

def main() -> None:
    if not os.path.isdir(FONTS_DIR):
        sys.exit(f"[ERREUR] Dossier '{FONTS_DIR}' introuvable. "
                 f"Créez-le et placez-y vos fichiers .ttf.")

    ttfs = sorted(f for f in os.listdir(FONTS_DIR) if f.lower().endswith('.ttf'))
    if not ttfs:
        sys.exit(f"[ERREUR] Aucun fichier .ttf dans '{FONTS_DIR}'.")

    os.makedirs(CARA_DIR, exist_ok=True)
    print(f"Génération des images de référence ({len(ttfs)} police(s) détectée(s))...\n")

    for ttf in ttfs:
        font_path = os.path.join(FONTS_DIR, ttf)
        font_name = os.path.splitext(ttf)[0]
        print(f"  ► {ttf}")
        n = generate_font(font_path, font_name)
        print(f"    {n} caractère(s) générés dans cara/{font_name}/\n")

    print("=" * 60)
    print("Terminé !")
    print()
    print("Étapes suivantes :")
    print(f"  1. Ouvrez les fichiers *_preview.png dans '{CARA_DIR}/'")
    print("     pour choisir la police qui ressemble le plus au manga.")
    print()
    print("  2. Dans manhwa_crawler.py, modifiez :")
    print('     CARA_FONT = "nom_du_dossier_choisi"')
    print('     ex. CARA_FONT = "ComicSansMS3"')
    print()
    print("  3. Relancez python manhwa_crawler.py — la correction par")
    print("     template matching sera automatiquement activée.")


if __name__ == "__main__":
    main()

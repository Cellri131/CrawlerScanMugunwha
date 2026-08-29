# -*- mode: python ; coding: utf-8 -*-
#
# Build : pyinstaller installer.spec
#
# Produit MugunwHaTradInstaller.exe : un installateur autonome, à lancer UNE
# SEULE FOIS avant MugunwHaTrad.exe sur une machine qui n'a pas Tesseract OCR.
# Il embarque une copie portable de Tesseract-OCR, la copie vers un dossier
# persistant (%LOCALAPPDATA%\Programs\Tesseract-OCR), vérifie qu'elle
# fonctionne, puis se supprime lui-même (voir installer.py).
#
# Séparer cet installateur de MugunwHaTrad.exe évite d'embarquer une copie de
# Tesseract dans l'app principale : cette copie ne fonctionnait de façon
# fiable que sur le PC de build (dépendances DLL/registre non portables telles
# quelles sur une machine tierce).

import os

# Dossier d'installation de Tesseract OCR sur la machine de build. Adaptez ce
# chemin si Tesseract est installé ailleurs (ex. "C:\Program Files\Tesseract-OCR").
TESSERACT_SRC = r"C:\Users\R_BAR\AppData\Local\Programs\Tesseract-OCR"

# DLL Tesseract non nécessaires pour de l'OCR pur en ligne de commande
# (mêmes exclusions validées que pour ihm.spec, voir memory/repo).
TESSERACT_EXCLUDE_DLLS = {
    'libcairo-2.dll', 'libpango-1.0-0.dll', 'libpangocairo-1.0-0.dll',
    'libpangoft2-1.0-0.dll', 'libpangowin32-1.0-0.dll', 'libharfbuzz-0.dll',
    'libfribidi-0.dll', 'libthai-0.dll', 'libdatrie-1.dll', 'libgraphite2.dll',
    'libfontconfig-1.dll', 'libpixman-1-0.dll',
    'libarchive-13.dll', 'libb2-1.dll', 'liblz4.dll', 'liblzma-5.dll',
    'libbz2-1.dll', 'libzstd.dll',
    'libicudt75.dll', 'libicuin75.dll', 'libicuuc75.dll',
    'libgio-2.0-0.dll', 'libglib-2.0-0.dll', 'libgobject-2.0-0.dll',
    'libgmodule-2.0-0.dll', 'libffi-8.dll', 'libintl-8.dll',
    'libpcre2-8-0.dll',
}

# OCR_LANG="eng" (+ "fra" en option) dans manhwa_crawler.py ; "kor"/"osd"
# jamais utilisés.
TESSERACT_EXCLUDE_LANGS = {'osd.traineddata', 'kor.traineddata'}


def _collect_tesseract_datas(src_dir, dest_root):
    """Construit la liste de triplets TOC (dest, source, 'DATA') des fichiers
    Tesseract à embarquer sous `dest_root`, avec les mêmes exclusions que
    ihm.spec (voir ce fichier pour le détail des tests de validation)."""
    result = []
    for root, dirs, files in os.walk(src_dir):
        rel_root = os.path.relpath(root, src_dir)
        if rel_root.split(os.sep)[0] == 'doc':
            dirs[:] = []
            continue
        for fname in files:
            lower = fname.lower()
            if lower.endswith('.html'):
                continue
            if lower.endswith('.exe') and lower != 'tesseract.exe':
                continue
            if fname in TESSERACT_EXCLUDE_DLLS:
                continue
            if fname in TESSERACT_EXCLUDE_LANGS:
                continue
            src_path = os.path.join(root, fname)
            dest_dir = os.path.join(dest_root, rel_root) if rel_root != '.' else dest_root
            dest_path = os.path.join(dest_dir, fname)
            result.append((dest_path, src_path, 'DATA'))
    return result


if os.path.isdir(TESSERACT_SRC):
    tesseract_tree = _collect_tesseract_datas(TESSERACT_SRC, 'tesseract_install')
else:
    tesseract_tree = []

a = Analysis(
    ['installer.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

a.datas += tesseract_tree

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='MugunwHaTradInstaller',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['MugunwHaLogoTrad.ico'],
)

# -*- mode: python ; coding: utf-8 -*-
#
# Build : pyinstaller ihm.spec
#
# Produit un .exe --onefile totalement autonome : Tesseract OCR (moteur +
# tessdata) est embarqué depuis l'installation locale ci-dessous, ainsi que
# les templates de police (cara/) et l'icône. Aucune installation préalable
# de Python ou de Tesseract n'est nécessaire sur la machine cible.
#
# Reste hors de portée d'un simple .exe : Google Chrome doit rester installé
# sur la machine cible (Selenium pilote le navigateur système, il ne peut
# pas en embarquer un lui-même). ChromeDriver, lui, est résolu automatiquement
# au premier lancement (Selenium Manager / webdriver-manager).
#
# --- Optimisation de la taille du .exe ---------------------------------
# L'installation Tesseract-OCR complète pèse ~89 Mo, mais une bonne partie
# n'est jamais utilisée par cette appli (qui ne fait que de l'OCR anglais/
# français en ligne de commande, sans langue supplémentaire ni rendu texte
# avancé). Les éléments suivants ont été testés individuellement (copie de
# test + appels réels tesseract.exe/image_to_boxes) et confirmés inutiles :
#   - Les 17 exécutables d'entraînement (lstmtraining.exe, mftraining.exe...)
#     et la documentation (*.html, doc/) : seul tesseract.exe est utilisé.
#   - Les langues tessdata non utilisées : OCR_LANG="eng" dans
#     manhwa_crawler.py, "kor" n'est jamais référencé dans le code, et
#     "osd" (orientation/script detection) n'est jamais invoqué (pas de
#     --psm 0). eng + fra (mentionné en commentaire comme option) sont
#     conservés.
#   - Les DLL de rendu graphique Pango/Cairo/HarfBuzz/Fontconfig (~4,5 Mo) :
#     utilisées pour du rendu de texte (PDF/hOCR visuel), pas pour l'OCR.
#   - Les DLL ICU (~34 Mo, données Unicode complètes) : non requises pour
#     l'OCR eng/fra basique.
#   - Les DLL GLib (~3,7 Mo) : ne restaient que pour Pango/Fontconfig,
#     retirés ci-dessus.
#   - libarchive et ses codecs de compression (~2,3 Mo) : servent à lire des
#     tessdata compressés, non utilisé ici.
#   - libpcre2 (~0,4 Mo) : ne restait que pour GLib.
# Gain total mesuré : Tesseract embarqué ~89 Mo → ~28 Mo.
#
# opencv-python embarque aussi une DLL ffmpeg (~29 Mo) pour la lecture de
# flux vidéo (cv2.VideoCapture). Ce projet ne traite que des images statiques
# (cv2.imread/cvtColor/threshold/morphologyEx/findContours), testé et
# fonctionnel sans cette DLL : elle est donc exclue des binaires PyInstaller.
# -------------------------------------------------------------------------

import os

# Dossier d'installation de Tesseract OCR sur la machine de build. Adaptez ce
# chemin si Tesseract est installé ailleurs (ex. "C:\Program Files\Tesseract-OCR").
TESSERACT_SRC = r"C:\Users\R_BAR\AppData\Local\Programs\Tesseract-OCR"

# DLL Tesseract non nécessaires pour de l'OCR pur en ligne de commande
# (voir explication détaillée ci-dessus). Validées par test réel.
TESSERACT_EXCLUDE_DLLS = {
    # Rendu graphique Pango/Cairo/HarfBuzz — non utilisé en OCR pur
    'libcairo-2.dll', 'libpango-1.0-0.dll', 'libpangocairo-1.0-0.dll',
    'libpangoft2-1.0-0.dll', 'libpangowin32-1.0-0.dll', 'libharfbuzz-0.dll',
    'libfribidi-0.dll', 'libthai-0.dll', 'libdatrie-1.dll', 'libgraphite2.dll',
    'libfontconfig-1.dll', 'libpixman-1-0.dll',
    # libarchive + codecs de compression — non utilisé (tessdata non compressés)
    'libarchive-13.dll', 'libb2-1.dll', 'liblz4.dll', 'liblzma-5.dll',
    'libbz2-1.dll', 'libzstd.dll',
    # ICU — données Unicode complètes, non nécessaires pour eng/fra
    'libicudt75.dll', 'libicuin75.dll', 'libicuuc75.dll',
    # GLib — ne servait que pour Pango/Fontconfig, retirés ci-dessus
    'libgio-2.0-0.dll', 'libglib-2.0-0.dll', 'libgobject-2.0-0.dll',
    'libgmodule-2.0-0.dll', 'libffi-8.dll', 'libintl-8.dll',
    # PCRE2 — ne servait que pour GLib
    'libpcre2-8-0.dll',
}

# Fichiers tessdata non utilisés : OCR_LANG="eng" (+ "fra" en option dans le
# code) ; "kor" et "osd" ne sont jamais référencés dans manhwa_crawler.py.
TESSERACT_EXCLUDE_LANGS = {'osd.traineddata', 'kor.traineddata'}

datas = [
    ('MugunwHaLogoTrad.ico', '.'),
    ('MugunwHaLogoTrad.png', '.'),
]


def _collect_tesseract_datas(src_dir):
    """Construit la liste de triplets TOC (dest, source, 'DATA') des fichiers
    Tesseract à embarquer, en excluant explicitement tout ce qui n'est pas
    nécessaire au fonctionnement de tesseract.exe en ligne de commande (voir
    notes d'optimisation en tête de fichier). Format triplet requis car ces
    entrées sont ajoutées directement à `a.datas` après Analysis()."""
    result = []
    for root, dirs, files in os.walk(src_dir):
        rel_root = os.path.relpath(root, src_dir)
        # Ignore complètement le dossier de documentation
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
            dest_dir = os.path.join('tesseract', rel_root) if rel_root != '.' else 'tesseract'
            dest_path = os.path.join(dest_dir, fname)
            result.append((dest_path, src_path, 'DATA'))
    return result


if os.path.isdir(TESSERACT_SRC):
    tesseract_tree = _collect_tesseract_datas(TESSERACT_SRC)
else:
    tesseract_tree = []

a = Analysis(
    ['ihm.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'pytesseract',
        'PIL._tkinter_finder',
        'docx',
        'webdriver_manager.chrome',
        # Selenium : le hook PyInstaller ne détecte pas les imports dynamiques
        # via __getattr__ du package, on les liste explicitement.
        'selenium.webdriver.chrome.webdriver',
        'selenium.webdriver.chrome.options',
        'selenium.webdriver.chrome.service',
        'selenium.webdriver.common.by',
        'selenium.webdriver.common.action_chains',
        'selenium.webdriver.support.ui',
        'selenium.webdriver.support.expected_conditions',
        'selenium.webdriver.remote.webdriver',
        'selenium.webdriver.remote.command',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

a.datas += tesseract_tree

# opencv-python embarque opencv_videoio_ffmpeg*.dll (~29 Mo) pour la lecture
# de flux vidéo (cv2.VideoCapture). Ce projet ne traite que des images fixes
# (imread/cvtColor/threshold/morphologyEx/findContours) : testé fonctionnel
# sans cette DLL, elle est donc retirée des binaires embarqués.
a.binaries = [b for b in a.binaries if 'ffmpeg' not in os.path.basename(b[0]).lower()]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ihm',
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

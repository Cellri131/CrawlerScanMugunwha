# -*- mode: python ; coding: utf-8 -*-
#
# Build : pyinstaller ihm.spec
#
# Produit MugunwHaTrad.exe (--onefile). Depuis que l'embarquement direct de
# Tesseract OCR posait problème sur toute machine autre que celle de build
# (dépendances DLL non portables telles quelles), Tesseract N'EST PLUS
# embarqué ici : il doit être installé une seule fois via
# MugunwHaTradInstaller.exe (voir installer.py / installer.spec), qui se
# supprime lui-même une fois l'installation vérifiée. MugunwHaTrad.exe
# recherche ensuite Tesseract à cet emplacement (voir `_check_tesseract`
# dans manhwa_crawler.py).
#
# Reste hors de portée d'un simple .exe : Google Chrome doit rester installé
# sur la machine cible (Selenium pilote le navigateur système, il ne peut
# pas en embarquer un lui-même). ChromeDriver, lui, est résolu automatiquement
# au premier lancement (Selenium Manager / webdriver-manager).
#
# --- Optimisation de la taille du .exe ---------------------------------
# opencv-python embarque une DLL ffmpeg (~29 Mo) pour la lecture de
# flux vidéo (cv2.VideoCapture). Ce projet ne traite que des images statiques
# (cv2.imread/cvtColor/threshold/morphologyEx/findContours), testé et
# fonctionnel sans cette DLL : elle est donc exclue des binaires PyInstaller.
# -------------------------------------------------------------------------

import os

datas = [
    ('MugunwHaLogoTrad.ico', '.'),
    ('MugunwHaLogoTrad.png', '.'),
]

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
    name='MugunwHaTrad',
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

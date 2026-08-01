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

import os

# Dossier d'installation de Tesseract OCR sur la machine de build. Adaptez ce
# chemin si Tesseract est installé ailleurs (ex. "C:\Program Files\Tesseract-OCR").
TESSERACT_SRC = r"C:\Users\R_BAR\AppData\Local\Programs\Tesseract-OCR"

datas = [
    ('cara', 'cara'),
    ('MugunwHaLogoTrad.ico', '.'),
    ('MugunwHaLogoTrad.png', '.'),
]

if os.path.isdir(TESSERACT_SRC):
    tesseract_tree = Tree(
        TESSERACT_SRC,
        prefix='tesseract',
        excludes=['*.html', 'doc', 'doc/*', 'doc\\*'],
    )
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

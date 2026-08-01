#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
Manhwa Chapter Crawler + OCR                               manhwa_crawler.py
=============================================================================
Fonctionnement :
  1. Demande une URL de chapitre manhwa
  2. Ouvre la page avec Selenium et gère la vérification d'âge (clic "OK")
  3. Récupère les URLs de toutes les images du chapitre
  4. Télécharge chaque image et détecte les bulles de dialogue (OpenCV)
  5. Extrait le texte de chaque région via OCR (pytesseract)
  6. Écrit output.txt :
       • texte en bulle  → ligne normale
       • texte hors bulle → ligne terminée par  **
=============================================================================
Prérequis :
  pip install -r requirements.txt

  Tesseract OCR (moteur OCR, obligatoire) :
    Windows → https://github.com/UB-Mannheim/tesseract/wiki
              (cocher "Add to PATH" lors de l'installation)
    Linux   → sudo apt install tesseract-ocr
    macOS   → brew install tesseract

  ChromeDriver (même version majeure que Chrome) :
    → https://googlechromelabs.github.io/chrome-for-testing/
=============================================================================
"""

import os
import re
import sys
import time
import logging
from io import BytesIO
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin

import cv2
import numpy as np
import requests
from bs4 import BeautifulSoup
from PIL import Image
import pytesseract
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import shutil
import os

import paths

# =============================================================================
# --- CONFIGURATION ----------------------------------------------------------
# =============================================================================

# ⚠️  Windows uniquement : décommentez et ajustez si Tesseract n'est PAS dans
#    votre PATH (chemin par défaut après l'installeur UB-Mannheim) :
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

OCR_LANG         = "eng"          # Langue OCR ; "eng+fra" pour anglais + français
MIN_CONFIDENCE   = 30             # Confiance OCR minimale sur 100 (abaissé pour les petites bulles)
OUTPUT_FILE      = "output.txt"   # Nom du fichier de sortie
PAGES_DIR        = "pages"        # Dossier où les images du chapitre sont sauvegardées
DOWNLOAD_TIMEOUT = 20             # Secondes avant abandon du téléchargement d'une image
MIN_OCR_WIDTH    = 700            # Largeur minimale (px) avant agrandissement pour OCR
BLOB_TIMEOUT     = 30             # Timeout (s) pour l'extraction JavaScript d'un blob
CARA_DIR         = "cara"         # Dossier des images de référence de la police du manga
CARA_THRESHOLD   = 0.38           # Score NCC minimal pour accepter une correction de caractère

# Templates chargés une fois au démarrage (dict char → np.ndarray 25×29)
_CARA_TEMPLATES: Dict[str, np.ndarray] = {}

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# =============================================================================
# --- NAVIGATEUR SELENIUM ----------------------------------------------------
# =============================================================================

def create_driver() -> webdriver.Chrome:
    """Crée un WebDriver Chrome configuré pour imiter un vrai navigateur."""
    opts = Options()
    # Décommentez pour le mode sans interface graphique (headless) :
    # opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)

    # Utiliser webdriver-manager pour télécharger le ChromeDriver adapté
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=opts)
    except Exception:
        # Fallback : laisser Selenium gérer le driver (Selenium Manager)
        driver = webdriver.Chrome(options=opts)

    # Supprime l'indicateur "navigator.webdriver" visible par les sites
    try:
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
        )
    except Exception:
        pass
    return driver


# =============================================================================
# --- VÉRIFICATION D'ÂGE -----------------------------------------------------
# =============================================================================

# Textes courants sur les boutons de confirmation d'âge (les apostrophes sont
# gérées séparément car elles cassent les expressions XPath)
_AGE_BUTTON_TEXTS = [
    "OK", "Enter", "Confirm", "Continue", "I agree", "Yes", "Accept",
    "Enter site", "I am an adult", "Access", "Proceed", "Agree",
    "I am 18+", "I am 18 or older", "I am over 18",
]

# Sélecteurs CSS pour les modales / popups de vérification d'âge
_AGE_CSS_SELECTORS = [
    ".age-verify button",           ".age-gate button",
    ".age-gate .button",            "#age-verify button",
    "#age-gate button",             "[class*='age-verify'] button",
    "[class*='age-gate'] button",   "[class*='age'] button",
    "[id*='age'] button",           ".modal button",
    ".popup button",                ".swal2-confirm",
    ".sweetalert-button",           "[class*='confirm'] button",
    "[class*='enter-btn']",         "[id*='enter-btn']",
]


def _try_click(driver: webdriver.Chrome, elements) -> bool:
    """Tente de cliquer sur le premier élément visible et activé."""
    for elem in elements:
        try:
            if elem.is_displayed() and elem.is_enabled():
                driver.execute_script("arguments[0].click();", elem)
                time.sleep(1.5)
                return True
        except Exception:
            pass
    return False


def click_age_verification(driver: webdriver.Chrome) -> bool:
    """
    Détecte et clique sur le bouton de vérification d'âge.
    Retourne True si un bouton a été cliqué, False sinon.

    Stratégie (dans l'ordre) :
      1. Correspondance exacte sur le texte du bouton (XPath insensible à la casse)
      2. Correspondance partielle (contains)
      3. Sélecteurs CSS courants
    """
    time.sleep(2.0)   # attendre l'apparition de la modale

    # --- 1. Correspondance exacte ---
    for text in _AGE_BUTTON_TEXTS:
        try:
            upper = text.upper()
            xpath = (
                "//*[self::button or self::a or self::input]"
                "[normalize-space(translate(.,"
                " 'abcdefghijklmnopqrstuvwxyz',"
                " 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'))"
                f"='{upper}']"
            )
            if _try_click(driver, driver.find_elements(By.XPATH, xpath)):
                log.info("Vérif. d'âge : clic exact sur '%s'", text)
                return True
        except Exception:
            pass

    # --- 2. Correspondance partielle (contains) ---
    for text in _AGE_BUTTON_TEXTS:
        try:
            upper = text.upper()
            xpath = (
                "//*[self::button or self::a or self::div or self::span]"
                "[contains(translate(normalize-space(.),"
                " 'abcdefghijklmnopqrstuvwxyz',"
                " 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'),"
                f"'{upper}')]"
            )
            if _try_click(driver, driver.find_elements(By.XPATH, xpath)):
                log.info("Vérif. d'âge : clic partiel sur '%s'", text)
                return True
        except Exception:
            pass

    # --- 3. Sélecteurs CSS ---
    for sel in _AGE_CSS_SELECTORS:
        try:
            if _try_click(driver, driver.find_elements(By.CSS_SELECTOR, sel)):
                log.info("Vérif. d'âge : clic via CSS '%s'", sel)
                return True
        except Exception:
            pass

    log.info("Aucune vérification d'âge détectée.")
    return False


# =============================================================================
# --- EXTRACTION DES URLs D'IMAGES -------------------------------------------
# =============================================================================

# Sélecteurs CSS pour les images de chapitre (du plus au moins spécifique)
_CHAPTER_SELECTORS = [
    "div.reading-content img",    "div.chapter-content img",
    "div#chapter-content img",    "div.reader-area img",
    "div.read-content img",       "div[class*='chapter-img'] img",
    "div[class*='reading'] img",  "div[class*='reader'] img",
    "div[id*='chapter'] img",     "div[id*='reader'] img",
    ".wp-manga-chapter-img",      "img.wp-manga-chapter-img",
    ".page-break img",            "article img",
]

# Mots-clés dans l'URL qui signalent une image NON pertinente (icônes, logos…)
_SKIP_KEYWORDS = [
    "logo", "icon", "avatar", "banner", "thumbnail", "favicon",
    "sprite", "button", "background", "1x1", "blank", "placeholder",
    "loading", "spinner", "rating", "star", "/ad/", "advertisement",
]

_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".avif")


def _is_chapter_image(url: str) -> bool:
    """Retourne True si l'URL ressemble à une image de chapitre manhwa."""
    # Les blob: URLs sont toujours des images chargées par le navigateur
    if url.startswith("blob:"):
        return True
    u = url.lower().split("?")[0]
    if any(kw in u for kw in _SKIP_KEYWORDS):
        return False
    if any(u.endswith(ext) for ext in _IMAGE_EXTS):
        return True
    # Accepter si le nom de fichier ne contient pas d'extension tierce connue
    filename = u.split("/")[-1]
    return "." not in filename or any(ext.lstrip(".") in filename for ext in _IMAGE_EXTS)


def _best_src(tag) -> str:
    """Extrait la meilleure URL depuis les attributs d'une balise <img>."""
    for attr in ("src", "data-src", "data-lazy-src", "data-original",
                 "data-url", "data-cfsrc", "data-cdn-src"):
        val = (tag.get(attr) or "").strip()
        if val and not val.startswith("data:") and val != "about:blank":
            return val
    return ""


def _scroll_to_load(driver: webdriver.Chrome) -> None:
    """Défile lentement la page pour déclencher le chargement lazy des images."""
    pos, step = 0, 700
    while True:
        driver.execute_script(f"window.scrollTo(0, {pos});")
        time.sleep(0.25)
        total = driver.execute_script("return document.body.scrollHeight")
        pos += step
        if pos >= total:
            break
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(0.5)


def fetch_image_urls(driver: webdriver.Chrome, page_url: str) -> List[str]:
    """
    Navigue vers le chapitre, gère la vérification d'âge, défile la page
    et retourne la liste ordonnée des URLs d'images de chapitre.
    """
    log.info("Chargement : %s", page_url)
    driver.get(page_url)
    time.sleep(3)

    # Gestion automatique de la vérification d'âge
    click_age_verification(driver)

    log.info("Défilement pour charger les images lazy...")
    _scroll_to_load(driver)

    soup = BeautifulSoup(driver.page_source, "html.parser")
    seen: set = set()
    result: List[str] = []

    def add(raw: str) -> None:
        raw = raw.strip()
        if not raw or raw in seen:
            return
        # Les blob: URLs sont déjà absolues, ne pas passer par urljoin
        if raw.startswith("blob:"):
            absolute = raw
        else:
            absolute = raw if raw.startswith("http") else urljoin(page_url, raw)
        if absolute not in seen and _is_chapter_image(absolute):
            seen.add(absolute)
            result.append(absolute)

    # --- Essai avec les sélecteurs spécifiques ---
    for sel in _CHAPTER_SELECTORS:
        tags = soup.select(sel)
        if tags:
            for t in tags:
                add(_best_src(t))
            if result:
                log.info("Sélecteur '%s' → %d image(s)", sel, len(result))
                return result

    # --- Fallback HTML : toutes les balises <img> ---
    log.info("Fallback HTML : toutes les <img>")
    for t in soup.find_all("img"):
        add(_best_src(t))

    # --- Fallback JavaScript (images chargées dynamiquement) ---
    if not result:
        log.info("Fallback JS : interrogation du DOM...")
        try:
            srcs = driver.execute_script(
                "return Array.from(document.querySelectorAll('img'))"
                ".map(i => i.src || i.getAttribute('data-src') || '')"
                ".filter(Boolean);"
            )
            for s in srcs or []:
                add(s)
        except Exception as e:
            log.warning("Erreur fallback JS : %s", e)

    return result


# =============================================================================
# --- TÉLÉCHARGEMENT ---------------------------------------------------------
# =============================================================================

def download_image(url: str, session: requests.Session) -> Optional[Image.Image]:
    """Télécharge une image et retourne un objet PIL Image en RGB, ou None si erreur."""
    try:
        resp = session.get(url, timeout=DOWNLOAD_TIMEOUT)
        resp.raise_for_status()
        return Image.open(BytesIO(resp.content)).convert("RGB")
    except Exception as exc:
        log.warning("Échec téléchargement %s : %s", url, exc)
        return None


def transfer_cookies(driver: webdriver.Chrome, session: requests.Session) -> None:
    """Copie les cookies du navigateur Selenium dans la session requests."""
    for cookie in driver.get_cookies():
        session.cookies.set(cookie["name"], cookie["value"])


def blob_to_pil(driver: webdriver.Chrome, blob_url: str) -> Optional[Image.Image]:
    """
    Extrait une image blob: en utilisant JavaScript dans le navigateur.

    Les blob: URLs (ex. blob:https://mangadex.org/...) sont des objets en
    mémoire du navigateur : requests ne peut PAS y accéder directement.
    Seul le contexte JavaScript de la page peut les lire.

    Technique :
      1. fetch(blob_url) → récupère le blob dans le navigateur
      2. FileReader.readAsDataURL() → convertit en data:image/...;base64,...
      3. execute_async_script retourne la chaîne base64 à Python
      4. base64.b64decode() + PIL.Image.open() → objet PIL
    """
    import base64

    js = """
    var callback = arguments[arguments.length - 1];
    fetch(arguments[0])
        .then(function(r) { return r.blob(); })
        .then(function(blob) {
            var reader = new FileReader();
            reader.onloadend = function() { callback(reader.result); };
            reader.onerror   = function() { callback('ERROR:reader'); };
            reader.readAsDataURL(blob);
        })
        .catch(function(e) { callback('ERROR:' + e.toString()); });
    """

    try:
        driver.set_script_timeout(BLOB_TIMEOUT)
        result = driver.execute_async_script(js, blob_url)

        if not result or str(result).startswith("ERROR"):
            log.warning("Blob JS error (%s) : %s", blob_url, result)
            return None

        # Format attendu : "data:image/jpeg;base64,/9j/4AAQ..."
        if "," not in result:
            log.warning("Format blob inattendu pour %s", blob_url)
            return None

        _, b64_data = result.split(",", 1)
        img_bytes = base64.b64decode(b64_data)
        return Image.open(BytesIO(img_bytes)).convert("RGB")

    except Exception as exc:
        log.warning("Impossible d'extraire blob %s : %s", blob_url, exc)
        return None


# =============================================================================
# --- DÉTECTION DES BULLES DE DIALOGUE (OPENCV) ------------------------------
# =============================================================================

def detect_bubbles(
    cv_img: np.ndarray,
    ref_height: int = 0,
) -> List[Tuple[int, int, int, int]]:
    """
    Détecte les bulles de dialogue dans une image manhwa (format OpenCV BGR).

    `ref_height` : hauteur de référence pour le calcul des seuils d’aire.
    Quand la fonction est appelée sur une bande multi-pages, passer la
    hauteur moyenne d’UNE page évite que max_area ne devienne gigantesque.
    Si 0 (défaut), on utilise la hauteur réelle de l’image.

    Retourne [(x, y, w, h), ...].
    """
    h_img, w_img = cv_img.shape[:2]
    gray    = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # Seuils calibrés sur UNE page (pas sur la bande complète)
    ref_h    = ref_height if ref_height > 0 else h_img
    ref_pix  = w_img * ref_h
    min_area = ref_pix * 0.0002
    max_area = ref_pix * 0.40

    all_candidates: List[Tuple[int, int, int, int]] = []

    # 4 seuils : 230 → bulles très blanches, 180 → bulles légèrement teintées
    for thresh_val in (230, 215, 200, 180):
        _, binary = cv2.threshold(blurred, thresh_val, 255, cv2.THRESH_BINARY)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
        closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if not (min_area <= area <= max_area):
                continue
            x, y, w, h = cv2.boundingRect(cnt)
            ratio = (w / h) if h else 0
            if not (0.12 < ratio < 7.0):
                continue
            if w > w_img * 0.92:          # exclure le fond de panel
                continue
            hull_area = cv2.contourArea(cv2.convexHull(cnt))
            if hull_area == 0:
                continue
            # Seuil abaissé à 0.35 pour capturer les bulles avec une queue
            # (la queue réduit la solidité par rapport à une bulle pure)
            if (area / hull_area) < 0.35:
                continue
            pad = 5
            bx = max(0, x - pad)
            by = max(0, y - pad)
            bw = min(w_img, x + w + pad) - bx
            bh = min(h_img, y + h + pad) - by
            all_candidates.append((bx, by, bw, bh))

    # -- Passe supplémentaire : très petites bulles (noyau réduit) ----------
    # Cible les petites bulles de texte court ("REALLY?", onomatopées, etc.)
    # qui disparaissent avec le noyau 11×11 trop large.
    tiny_min  = ref_pix * 0.00005   # ≥ 0,005 %
    tiny_max  = ref_pix * 0.0025    # ≤ 0,25 % (au-delà la passe normale couvre)
    tiny_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    for thresh_val in (235, 220):
        _, binary = cv2.threshold(blurred, thresh_val, 255, cv2.THRESH_BINARY)
        closed  = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, tiny_kernel)
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if not (tiny_min <= area <= tiny_max):
                continue
            x, y, w, h = cv2.boundingRect(cnt)
            ratio = (w / h) if h else 0
            if not (0.15 < ratio < 6.0):
                continue
            if w > w_img * 0.80:
                continue
            hull_area = cv2.contourArea(cv2.convexHull(cnt))
            if hull_area == 0:
                continue
            if (area / hull_area) < 0.25:   # seuil plus souple pour les petites bulles
                continue
            pad = 3
            bx = max(0, x - pad)
            by = max(0, y - pad)
            bw = min(w_img, x + w + pad) - bx
            bh = min(h_img, y + h + pad) - by
            all_candidates.append((bx, by, bw, bh))

    return _remove_nested_bubbles(all_candidates)


def _overlap_ratio(r1: Tuple, r2: Tuple) -> float:
    """Calcule le ratio surface_intersection(r1,r2) / aire(r1)."""
    x1, y1, w1, h1 = r1
    x2, y2, w2, h2 = r2
    ix = max(0, min(x1 + w1, x2 + w2) - max(x1, x2))
    iy = max(0, min(y1 + h1, y2 + h2) - max(y1, y2))
    area1 = w1 * h1
    return (ix * iy) / area1 if area1 > 0 else 0.0


def _remove_nested_bubbles(bubbles: list) -> list:
    """
    Supprime les petites bulles entièrement contenues dans de plus grandes
    (évite le double comptage du texte).
    """
    bubbles = sorted(bubbles, key=lambda r: r[2] * r[3], reverse=True)
    kept: list = []
    for b in bubbles:
        if not any(_overlap_ratio(b, k) > 0.75 for k in kept):
            kept.append(b)
    return kept


# =============================================================================
# --- RECONNAISSANCE PAR TEMPLATE MATCHING (police manga) --------------------
# =============================================================================
#
# Charge les images de référence depuis cara/ (racine, pas les sous-dossiers).
# Chaque image = un caractère nommé par son fichier :
#   A.png → 'A',  deuxPoints.png → ':',  troisPoints.png → '...',  etc.
#
# Pour chaque crop de bulle :
#   1. Binarisation inverse (texte = blanc, fond = noir)
#   2. Détection des lignes de texte (projection horizontale)
#   3. Pour chaque ligne : échelle → 29 px de hauteur (= hauteur des templates)
#   4. Segmentation des caractères par projection verticale (valeurs creuses)
#   5. Chaque segment redimensionné en 25×29 et comparé via NCC à chaque template
#   6. Le caractère avec le meilleur NCC >= CARA_THRESHOLD est retenu
# Si la couverture est insuffisante (≤ CARA_MIN_COVER) → fallback Tesseract
# NE PLUS UTILISER FF CETTE MERDE, DIRECTE PASSER PAR TESSERACT
# =============================================================================

_SPECIAL_NAMES = {
    'appostrophe': "'",
    'deuxPoints':  ':',
    'point':       '.',
    'question':    '?',
    'troisPoints': '...',
    'vague':       '~',
}


def _load_cara_templates(cara_dir: str) -> Dict[str, np.ndarray]:
    """
    Charge les templates de la racine de cara/ (ignore les sous-dossiers).
    Retourne {caractère: tableau_float32_25x29}.
    Polaire : texte = 255 (blanc), fond = 0 (noir).
    """
    templates: Dict[str, np.ndarray] = {}
    if not os.path.isdir(cara_dir):
        log.warning("Template cara : dossier introuvable (%s)", cara_dir)
        return templates

    for fname in sorted(os.listdir(cara_dir)):
        fpath = os.path.join(cara_dir, fname)
        if not os.path.isfile(fpath) or not fname.lower().endswith('.png'):
            continue
        stem = os.path.splitext(fname)[0]
        char = _SPECIAL_NAMES.get(stem, stem)

        img = cv2.imread(fpath, cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue

        _, binary = cv2.threshold(img, 127, 255, cv2.THRESH_BINARY_INV)
        if binary.shape != (29, 25):
            binary = cv2.resize(binary, (25, 29), interpolation=cv2.INTER_AREA)
            _, binary = cv2.threshold(binary, 64, 255, cv2.THRESH_BINARY)

        templates[char] = binary.astype(np.float32)

    log.info("Templates cara : %d caractère(s) chargé(s) depuis %s", len(templates), cara_dir)
    return templates


def _ncc_2d(a: np.ndarray, b: np.ndarray) -> float:
    """Corrélation croisée normalisée entre deux tableaux de même taille."""
    a = a.ravel().astype(np.float64);  a -= a.mean()
    b = b.ravel().astype(np.float64);  b -= b.mean()
    na = np.linalg.norm(a);  nb = np.linalg.norm(b)
    if na < 1e-6 or nb < 1e-6:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def _correct_word_with_cara(
    word_img: Image.Image,
    ocr_word: str,
    templates: Dict[str, np.ndarray],
) -> str:
    """
    Corrige les caractères d'un mot OCR en les comparant aux templates cara/.

    Fonctionnement :
      1. image_to_boxes sur le crop du mot → boîtes par caractère.
      2. Pour chaque caractère : crop, redimensionnement 25×29, NCC contre
         tous les templates.
      3. Remplacement si un template différent score mieux d'au moins 0.05
         ET dépasse CARA_THRESHOLD.

    Ex. : Tesseract lit 'DIP' pour 'DID' → le template D.png (D miroir)
    donne un NCC élevé pour le dernier caractère → corrigé en 'D'.
    """
    if not templates or not ocr_word.strip():
        return ocr_word

    h = word_img.height
    w = word_img.width
    if h < 4 or w < 4:
        return ocr_word

    # Boîtes par caractère (Tesseract, repère bas-gauche)
    try:
        boxes_str = pytesseract.image_to_boxes(
            word_img, lang=OCR_LANG, config="--oem 3 --psm 8"
        )
    except Exception:
        return ocr_word

    if not boxes_str.strip():
        return ocr_word

    char_boxes: list = []
    for line in boxes_str.strip().split('\n'):
        parts = line.split()
        if len(parts) < 5:
            continue
        c  = parts[0]
        x1 = int(parts[1])
        y1 = h - int(parts[4])   # flip Y
        x2 = int(parts[3])
        y2 = h - int(parts[2])   # flip Y
        if x2 > x1 and y2 > y1:
            char_boxes.append((c, max(0, x1), max(0, y1), min(w, x2), min(h, y2)))

    if not char_boxes:
        return ocr_word

    # Binarisation : texte = 255, fond = 0
    arr = np.array(word_img.convert('L'))
    _, binary = cv2.threshold(arr, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Seuls les templates de caractère unique (pas '...')
    single_tmpls = {c: t for c, t in templates.items() if len(c) == 1}

    corrected: list = []
    for (c, x1, y1, x2, y2) in char_boxes:
        crop = binary[y1:y2, x1:x2]
        if crop.size == 0:
            corrected.append(c)
            continue

        crop_r = cv2.resize(crop, (25, 29), interpolation=cv2.INTER_AREA)
        _, crop_r = cv2.threshold(crop_r, 64, 255, cv2.THRESH_BINARY)
        crop_f  = crop_r.astype(np.float32)

        best_char  = c
        best_score = -2.0
        for ref_char, ref_tmpl in single_tmpls.items():
            s = _ncc_2d(crop_f, ref_tmpl)
            if s > best_score:
                best_score = s
                best_char  = ref_char

        # Score du caractère Tesseract dans les templates (pour comparaison)
        cur_score = _ncc_2d(crop_f, single_tmpls[c]) if c in single_tmpls else -2.0

        # Appliquer la correction seulement si nettement meilleur
        if (best_score >= CARA_THRESHOLD
                and best_char != c
                and best_score >= cur_score + 0.05):
            corrected.append(best_char)
        else:
            corrected.append(c)

    result = ''.join(corrected)
    return result if result else ocr_word


# =============================================================================
# --- PIPELINE BANDE COMPLÈTE (pluri-pages) -----------------------------------
# =============================================================================


def _ocr_bubble_crop(
    source: Image.Image, bx: int, by: int, bw: int, bh: int
) -> str:
    """
    Extrait le texte d'une bulle.

    Pipeline :
      1. Tesseract (psm 6) pour la segmentation et la reconnaissance des mots.
      2. Pour chaque mot, correction caractère par caractère avec les templates
         cara/ (si disponibles) via _correct_word_with_cara.
    """
    pad = 12
    x1 = max(0, bx - pad);  y1 = max(0, by - pad)
    x2 = min(source.width,  bx + bw + pad)
    y2 = min(source.height, by + bh + pad)
    crop = source.crop((x1, y1, x2, y2))

    proc, zoom = _preprocess_for_ocr(crop)
    data = pytesseract.image_to_data(
        proc, lang=OCR_LANG,
        config="--oem 3 --psm 6",
        output_type=pytesseract.Output.DICT,
    )

    words: list = []
    for i, word in enumerate(data["text"]):
        word = word.strip()
        if not word or int(data["conf"][i]) < MIN_CONFIDENCE:
            continue

        # Correction par templates : crop du mot depuis l'image procéssée
        if _CARA_TEMPLATES:
            lp = data["left"][i];   tp = data["top"][i]
            wp = data["width"][i];  hp = data["height"][i]
            if wp > 0 and hp > 0:
                word_img = proc.crop((
                    max(0, lp - 1), max(0, tp - 1),
                    min(proc.width,  lp + wp + 1),
                    min(proc.height, tp + hp + 1),
                ))
                word = _correct_word_with_cara(word_img, word, _CARA_TEMPLATES)

        words.append({
            "text":  word,
            "left":  int(data["left"][i]    / zoom),
            "top":   int(data["top"][i]     / zoom),
            "width": int(data["width"][i]   / zoom),
            "height":int(data["height"][i]  / zoom),
            "block": data["block_num"][i],
            "par":   data["par_num"][i],
            "line":  data["line_num"][i],
        })

    # if not words:
    #     return ""
    # return _clean_text(" ".join(w["text"] for w in _sort_words_reading_order(words)))
    if not words:
        return ""

    # Tri des mots dans l'ordre de lecture
    sorted_words = _sort_words_reading_order(words)

    # 🔥 Fusion en UNE SEULE ligne
    text = " ".join(w["text"] for w in sorted_words)

    # Nettoyage final
    return _clean_text(text)



def _extract_outside_text(
    pil_img: Image.Image,
    local_bubbles: List[Tuple[int, int, int, int]],
    page_y_offset: int = 0,
) -> List[Tuple[int, str, bool]]:
    """
    Extrait le texte hors-bulle d'une page (narration, légendes, texte flottant).

    Retourne [(global_y, text, is_bubble), …] où global_y est la position
    verticale dans la bande complète (pour le tri final en ordre de lecture).
    """
    proc_img, zoom = _preprocess_for_ocr(pil_img)
    data = pytesseract.image_to_data(
        proc_img, lang=OCR_LANG, config="--oem 3 --psm 3",
        output_type=pytesseract.Output.DICT,
    )

    outside_words: list = []
    for i, word in enumerate(data["text"]):
        word = word.strip()
        if not word or int(data["conf"][i]) < MIN_CONFIDENCE:
            continue
        left_o   = int(data["left"][i]   / zoom)
        top_o    = int(data["top"][i]    / zoom)
        width_o  = int(data["width"][i]  / zoom)
        height_o = int(data["height"][i] / zoom)
        cx       = left_o + width_o  // 2
        cy       = top_o  + height_o // 2

        # Ignorer les mots couverts par une bulle
        if any(bx <= cx <= bx + bw and by_ <= cy <= by_ + bh
               for (bx, by_, bw, bh) in local_bubbles):
            continue

        outside_words.append({
            "text":  word, "cx": cx, "cy": cy,
            "left":  left_o,  "top":  top_o,
            "width": width_o, "height": height_o,
            "block": data["block_num"][i],
            "par":   data["par_num"][i],
            "line":  data["line_num"][i],
        })

    results: List[Tuple[int, str, bool]] = []
    for cluster in _cluster_words_spatially(outside_words):
        brightness = [
            _region_brightness(pil_img, w["left"], w["top"], w["width"], w["height"])
            for w in cluster
        ]
        is_bubble_like = sum(brightness) / len(brightness) > 185
        text = _clean_text(" ".join(
            w["text"] for w in _sort_words_reading_order(cluster)
        ))
        if not text:
            continue
        # Rejeter le bruit pur : au moins un mot de ≥ 3 lettres
        # ou un nombre de ≥ 2 chiffres (ex. "7:30", "45").
        alpha_words = [re.sub(r'[^A-Z]', '', t) for t in text.split()]
        has_word    = any(len(w) >= 3 for w in alpha_words)
        has_number  = bool(re.search(r'\d{2,}', text))
        if not has_word and not has_number:
            continue
        global_y = min(w["top"] for w in cluster) + page_y_offset
        results.append((global_y, text, is_bubble_like))
    return results


def _dedup_lines(
    lines: List[Tuple[str, bool]]
) -> List[Tuple[str, bool]]:
    """
    Supprime les doublons dans une fenêtre glissante de 6 entrées.
    Gère le cas fréquent où la même bulle est reconnue deux fois
    (bords de page, chevauchements de détection).
    """
    result: List[Tuple[str, bool]] = []
    for entry in lines:
        window_texts = {r[0] for r in result[-6:]}
        if entry[0] not in window_texts:
            result.append(entry)
    return result


def process_full_strip(
    pil_images: List[Image.Image],
) -> List[Tuple[str, bool]]:
    """
    Pipeline principal du chapitre :

      1. Colle toutes les pages en une seule bande verticale.
      2. Détecte les bulles sur la bande complète (aucune frontière inter-pages).
      3. Pour chaque bulle : OCR du crop dans la bande → texte complet même
         si la bulle chevauche deux pages originales.
      4. Pour chaque page : OCR des zones hors-bulle (narration, légendes).
      5. Fusionne et trie par Y global pour respecter l'ordre de lecture.
    """
    if not pil_images:
        return []

    # -- 1. Couture verticale -----------------------------------------------
    max_w = max(img.width for img in pil_images)
    page_offsets: List[int] = []
    cy = 0
    for img in pil_images:
        page_offsets.append(cy)
        cy += img.height
    total_h = cy

    # Fond gris : distingue les bords des bulles blanches
    full_strip = Image.new('RGB', (max_w, total_h), (140, 140, 140))
    for img, off in zip(pil_images, page_offsets):
        full_strip.paste(img, (0, off))
    log.info("Bande complète : %d × %d px (%d page(s))", max_w, total_h, len(pil_images))

    # -- 2. Détection globale -----------------------------------------------
    cv_full = cv2.cvtColor(np.array(full_strip), cv2.COLOR_RGB2BGR)
    # ref_height = hauteur moyenne d'UNE page → les seuils d'aire restent
    # calibrés pour une page même si la bande en compte plusieurs dizaines.
    avg_page_h = total_h // len(pil_images)
    global_bubbles = detect_bubbles(cv_full, ref_height=avg_page_h)
    log.info("Bulles détectées (bande complète) : %d", len(global_bubbles))

    # -- 3. OCR bulle par bulle depuis la bande ---------------------------
    bubble_entries: List[Tuple[int, str, bool]] = []
    for bx, by, bw, bh in global_bubbles:
        text = _ocr_bubble_crop(full_strip, bx, by, bw, bh)
        if text:
            bubble_entries.append((by, text, True))

    # -- 4. OCR hors-bulle page par page ------------------------------
    outside_entries: List[Tuple[int, str, bool]] = []
    for page_idx, pil_img in enumerate(pil_images):
        page_y0 = page_offsets[page_idx]
        page_y1 = page_y0 + pil_img.height

        # Coordonnées des bulles clipées à cette page (espace local)
        local_bubbles: List[Tuple[int, int, int, int]] = []
        for (bx, by, bw, bh) in global_bubbles:
            cy0 = max(by, page_y0) - page_y0
            cy1 = min(by + bh, page_y1) - page_y0
            if cy1 > cy0:
                local_bubbles.append((bx, cy0, bw, cy1 - cy0))

        for entry in _extract_outside_text(pil_img, local_bubbles, page_y0):
            outside_entries.append(entry)
        log.info("[hors-bulle p.%d/%d] %d cluster(s)",
                 page_idx + 1, len(pil_images), len(outside_entries))

    # -- 5. Fusion + tri par Y global --------------------------------
    all_entries = bubble_entries + outside_entries
    all_entries.sort(key=lambda e: e[0])
    return [(text, is_bub) for (_, text, is_bub) in all_entries]


def _point_in_bubble(cx: int, cy: int, bubbles: list) -> bool:
    """Retourne True si le point (cx, cy) se trouve dans l'une des bulles."""
    return any(
        bx <= cx <= bx + bw and by <= cy <= by + bh
        for bx, by, bw, bh in bubbles
    )


# =============================================================================
# --- OCR ET CLASSIFICATION BULLE / HORS-BULLE -------------------------------
# =============================================================================

def _region_brightness(pil_img: Image.Image, x: int, y: int, w: int, h: int) -> float:
    """
    Retourne la luminosité du fond autour d'une zone de texte (0-255).
    Utilise le 90e percentile des pixels de la région élargie : les pixels
    sombres du texte sont exclus, il reste le fond.
      > 185 → fond clair  = bulle de dialogue probable
      ≤ 185 → fond sombre = narration / légende hors bulle
    """
    pad = 10
    x1 = max(0, x - pad)
    y1 = max(0, y - pad)
    x2 = min(pil_img.width,  x + w + pad)
    y2 = min(pil_img.height, y + h + pad)
    region = np.array(pil_img.crop((x1, y1, x2, y2)).convert("L"))
    return float(np.percentile(region, 90)) if region.size > 0 else 255.0


def _preprocess_for_ocr(pil_img: Image.Image) -> Tuple[Image.Image, float]:
    """
    Pré-traite une image pour améliorer les résultats OCR :
      1. Agrandit l'image si elle est plus petite que MIN_OCR_WIDTH
      2. Convertit en niveaux de gris
      3. Applique un seuillage Otsu (binarisation adaptative)

    Retourne (image_traitée, facteur_de_zoom).
    """
    w, h = pil_img.size
    zoom = 1.0

    if w < MIN_OCR_WIDTH:
        zoom = MIN_OCR_WIDTH / w
        pil_img = pil_img.resize((int(w * zoom), int(h * zoom)), Image.LANCZOS)

    gray_np = np.array(pil_img.convert("L"))
    _, thresh = cv2.threshold(gray_np, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return Image.fromarray(thresh), zoom


def _fix_ocr_errors(text: str) -> str:
    """
    Corrige les confusions OCR très fréquentes dans les textes manhwa.

    Confusions courantes Tesseract sur les polices de manhwa :
      ]  → I     (quasi-systématique avec certaines polices)
      |  → I     (pipe simple confondu avec majuscule I)
      $  → S     (ex. $TART → START, $O → SO)
      30 → SO    (S→3, O→0  — appliqué seulement en contexte majuscules)
      50 → SO    (S→5, O→0  — id.)
    """
    # ] et | presque toujours confondus avec I dans les bulles manhwa
    text = text.replace(']', 'I')
    text = re.sub(r'(?<!\|)\|(?!\|)', 'I', text)   # | simple → I (pas ||)

    # $ + lettre → S + lettre
    text = re.sub(r'\$([A-Za-z])', r'S\1', text)
    # $ + 0 (zéro) → SO
    text = re.sub(r'\$0', 'SO', text)
    # $ isolé → S
    text = re.sub(r'\$(?=\s|$)', 'S', text)

    # 30 / 50 / 3O / 5O → SO uniquement quand le texte est majoritairement
    # en majuscules (dialogue / bulle) pour éviter de casser les vrais nombres
    alpha = [c for c in text if c.isalpha()]
    if alpha and sum(c.isupper() for c in alpha) / len(alpha) > 0.6:
        text = re.sub(r'\b[35]0\b', 'SO', text)   # 30 ou 50 → SO
        text = re.sub(r'\b[35]O\b', 'SO', text)   # 3O ou 5O → SO

    return text


# Mots anglais courts valides (1-2 lettres, purement alphabétiques).
# Tout token alphabétique de 1-2 caractères absent de cette liste est
# considéré comme un artefact OCR et supprimé.
_VALID_SHORT_EN = frozenset({
    # 1 lettre
    'A', 'I', 'O',
    # 2 lettres
    'AM', 'AN', 'AS', 'AT', 'AH', 'AW', 'AY',
    'BE', 'BY',
    'DO',
    'GO',
    'HA', 'HE', 'HI', 'HM', 'HO',
    'IF', 'IN', 'IS', 'IT',
    'ME', 'MM', 'MY',
    'NO',
    'OF', 'OH', 'OK', 'ON', 'OR',
    'SO',
    'TO',
    'UH', 'UM', 'UP', 'US',
    'WE',
    'YA', 'YO',
})


def _is_valid_token(token: str) -> bool:
    """
    Retourne True si le token doit être conservé dans l'output.
    Les tokens purement alphabétiques de 1-2 caractères sont filtrés
    s'ils ne font pas partie des mots anglais courts reconnus.
    Tous les autres tokens (chiffres, ponctuation, mots ≥ 3 lettres)
    passent toujours.
    """
    if not token.isalpha():
        return True          # contient des chiffres / ponctuation : ok
    if len(token) <= 2:
        return token in _VALID_SHORT_EN
    return True              # mot ≥ 3 lettres : toujours accepté


def _clean_text(text: str) -> str:
    """Nettoie les artefacts OCR courants et rejette les chaînes invalides."""
    text = _fix_ocr_errors(text)                   # corrections $ → S, etc.
    text = re.sub(r"[^\x20-\x7E]", "", text)      # ASCII imprimable uniquement
    text = re.sub(r"[|_]{2,}", " ", text)           # lignes parasites
    text = re.sub(r"\s{2,}", " ", text).strip()
    if len(text) < 2 or not re.search(r"[A-Za-z0-9]", text):
        return ""
    # Force majuscules (la police du manga est toujours en caps)
    text = text.upper()
    # Filtrer les tokens alphabétiques courts non-anglais (artefacts OCR)
    tokens = [t for t in text.split() if _is_valid_token(t)]
    if not tokens:
        return ""
    text = " ".join(tokens)
    # Rejeter le bruit pur : aucune lettre (ex. "@ 4 \ \ \" depuis fond de panel)
    if not re.search(r'[A-Z]', text):
        return ""
    if len(text) < 2 or not re.search(r"[A-Z0-9]", text):
        return ""
    return text


def _sort_words_reading_order(words: list) -> list:
    """
    Trie les mots dans l'ordre de lecture (gauche→droite, haut→bas).

    Stratégie principale :
      Utiliser les numéros de ligne pytesseract (block_num / par_num / line_num)
      qui sont déjà calculés par le moteur OCR. C'est bien plus fiable qu'une
      tolérance Y car Tesseract détecte précisément les lignes de texte.

      1. Regrouper par (block, par, line) → chaque clé = une ligne visuelle.
      2. Trier les groupes par leur Y moyen (haut → bas).
      3. Trier les mots à l'intérieur de chaque ligne par `left` (gauche → droite).

    Fallback (si les métadonnées ne sont pas disponibles) :
      Regroupement par tolérance Y (60 % de la hauteur moyenne).
    """
    if not words:
        return []

    # -- Stratégie 1 : numéros de ligne pytesseract (préférée) --------------
    if "line" in words[0]:
        line_groups: Dict[tuple, list] = {}
        for w in words:
            key = (w.get("block", 0), w.get("par", 0), w.get("line", 0))
            line_groups.setdefault(key, []).append(w)

        # Trier les groupes par Y moyen croissant
        sorted_groups = sorted(
            line_groups.values(),
            key=lambda ws: sum(x["top"] for x in ws) / len(ws)
        )
        result: list = []
        for grp in sorted_groups:
            result.extend(sorted(grp, key=lambda w: w["left"]))
        return result

    # -- Fallback : regroupement par tolérance Y --------------------------
    avg_h     = sum(w.get("height", 15) for w in words) / len(words)
    tolerance = max(int(avg_h * 0.6), 6)
    by_top    = sorted(words, key=lambda w: w["top"])
    lines: list = [[by_top[0]]]
    for w in by_top[1:]:
        ref_y = sum(x["top"] for x in lines[-1]) / len(lines[-1])
        if abs(w["top"] - ref_y) <= tolerance:
            lines[-1].append(w)
        else:
            lines.append([w])
    result = []
    for line in lines:
        result.extend(sorted(line, key=lambda w: w["left"]))
    return result


def _cluster_words_spatially(words: list) -> List[list]:
    """
    Regroupe les mots en clusters selon leur proximité verticale.

    Un gap vertical > 1,5 × la hauteur moyenne d'un mot signale une
    séparation entre deux groupes (deux bulles différentes, ou bulle et
    légende, etc.).

    Retourne une liste de clusters, chacun étant une liste de mots.
    """
    if not words:
        return []

    avg_h = sum(w.get("height", 15) for w in words) / len(words)
    gap   = max(int(avg_h * 1.5), 15)

    by_top = sorted(words, key=lambda w: w["top"])
    clusters: List[list] = [[by_top[0]]]

    for w in by_top[1:]:
        last_bottom = max(x["top"] + x.get("height", 15) for x in clusters[-1])
        if w["top"] - last_bottom > gap:
            clusters.append([w])     # gap détecté → nouveau cluster
        else:
            clusters[-1].append(w)   # même cluster

    return clusters


def extract_text_lines(
    pil_img: Image.Image,
    bubbles: List[Tuple[int, int, int, int]],
) -> List[Tuple[str, bool]]:
    """
    Extrait le texte d'une page manhwa.

    Règles de sortie :
      • Bulle détectée → TOUS ses mots triés en ordre de lecture
        → UNE seule ligne (sans **)
      • Mot hors bulle détectée, fond CLAIR (≥ 186) → bulle probable non
        détectée → regroupé par cluster spatial → une ligne par cluster (sans **)
      • Mot hors bulle, fond SOMBRE (< 186) → narration / légende
        → une ligne par cluster (avec **)

    Le tri interne utilise _sort_words_reading_order pour éviter le mélange
    de mots de lignes visuelles différentes.
    """
    proc_img, zoom = _preprocess_for_ocr(pil_img)

    data: Dict = pytesseract.image_to_data(
        proc_img,
        lang=OCR_LANG,
        config="--oem 3 --psm 3",
        output_type=pytesseract.Output.DICT,
    )

    # -- 1. Collecter les mots valides avec leurs positions (espace original) --
    words_info: list = []
    for i, word in enumerate(data["text"]):
        word = word.strip()
        if not word or int(data["conf"][i]) < MIN_CONFIDENCE:
            continue

        left_o   = int(data["left"][i]   / zoom)
        top_o    = int(data["top"][i]    / zoom)
        width_o  = int(data["width"][i]  / zoom)
        height_o = int(data["height"][i] / zoom)
        words_info.append({
            "text":   word,
            "cx":     left_o + width_o  // 2,
            "cy":     top_o  + height_o // 2,
            "left":   left_o,  "top":    top_o,
            "width":  width_o, "height": height_o,
            # Métadonnées de ligne pytesseract (utilisées par _sort_words_reading_order)
            "block":  data["block_num"][i],
            "par":    data["par_num"][i],
            "line":   data["line_num"][i],
        })

    # -- 2. Affecter chaque mot à une bulle détectée ou aux mots "hors bulle" --
    bubble_groups: Dict[int, list] = {}   # bubble_idx → [mots]
    outside_words: list = []              # mots hors de toute bulle détectée

    for w in words_info:
        bi = -1
        for idx_b, (bx, by, bw, bh) in enumerate(bubbles):
            if bx <= w["cx"] <= bx + bw and by <= w["cy"] <= by + bh:
                bi = idx_b
                break
        if bi >= 0:
            bubble_groups.setdefault(bi, []).append(w)
        else:
            outside_words.append(w)

    # (min_top, min_left, texte, is_bubble)
    entries: List[Tuple[int, int, str, bool]] = []

    # -- 3. Bulles détectées : trier en ordre de lecture, une ligne par bulle --
    for ws in bubble_groups.values():
        sorted_ws = _sort_words_reading_order(ws)
        text = _clean_text(" ".join(w["text"] for w in sorted_ws))
        if text:
            entries.append((
                min(w["top"]  for w in ws),
                min(w["left"] for w in ws),
                text, True
            ))

    # -- 4. Mots hors bulle : clustering spatial + classification par luminosité --
    # Chaque cluster = un groupe de mots spatialement proches
    # (correspondant probablement à une bulle non détectée ou à une légende)
    for cluster in _cluster_words_spatially(outside_words):
        # Luminosité moyenne du fond pour ce cluster
        brightnesses = [
            _region_brightness(pil_img, w["left"], w["top"], w["width"], w["height"])
            for w in cluster
        ]
        avg_brightness = sum(brightnesses) / len(brightnesses)
        is_bubble = avg_brightness > 185   # fond clair → bulle, fond sombre → légende

        sorted_cluster = _sort_words_reading_order(cluster)
        text = _clean_text(" ".join(w["text"] for w in sorted_cluster))
        if text:
            entries.append((
                min(w["top"]  for w in cluster),
                min(w["left"] for w in cluster),
                text, is_bubble
            ))

    # Trier en ordre de lecture : haut → bas, puis gauche → droite
    entries.sort(key=lambda e: (e[0], e[1]))
    return [(text, is_bubble) for _, _, text, is_bubble in entries]


# =============================================================================
# --- PROGRAMME PRINCIPAL ----------------------------------------------------
# =============================================================================

def _check_tesseract() -> None:
    """Vérifie que Tesseract est accessible ; affiche un message d'aide sinon."""
    # 0) Copie de Tesseract embarquée dans l'application (build PyInstaller) :
    #    utilisée en priorité pour ne dépendre d'AUCUNE installation système.
    bundled_exe = paths.resource_path("tesseract", "tesseract.exe")
    if os.path.isfile(bundled_exe):
        pytesseract.pytesseract.tesseract_cmd = bundled_exe
        os.environ["TESSDATA_PREFIX"] = paths.resource_path("tesseract", "tessdata")
        try:
            pytesseract.get_tesseract_version()
            return
        except Exception:
            pass

    # 1) Si une variable d'environnement 'TESSERACT_CMD' est définie, l'utiliser
    env_path = os.environ.get("TESSERACT_CMD")
    if env_path:
        pytesseract.pytesseract.tesseract_cmd = env_path

    # 2) Essayer d'obtenir la version via pytesseract
    try:
        pytesseract.get_tesseract_version()
        return
    except Exception:
        pass

    # 3) Rechercher tesseract dans le PATH
    which_path = shutil.which("tesseract")
    if which_path:
        pytesseract.pytesseract.tesseract_cmd = which_path
        try:
            pytesseract.get_tesseract_version()
            return
        except Exception:
            pass

    # 4) Rechercher dans les chemins Windows courants
    common_win_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        # Path utilisateur signalé (parfois typo "ORC")
        r"C:\Program Files\Tesseract-ORC\tesseract.exe",
        # Chemin local d'installation pour l'utilisateur courant
        r"C:\Users\R_BAR\AppData\Local\Programs\Tesseract-OCR\tesseract.exe",
    ]
    for p in common_win_paths:
        if os.path.exists(p):
            pytesseract.pytesseract.tesseract_cmd = p
            try:
                pytesseract.get_tesseract_version()
                return
            except Exception:
                pass

    # Si on arrive ici, Tesseract n'a pas été trouvé
    raise RuntimeError(
        "Tesseract OCR est introuvable ou non accessible par Python.\n"
        "Solutions :\n"
        "  1) Installez Tesseract (Windows : UB-Mannheim build).\n"
        "     https://github.com/UB-Mannheim/tesseract/wiki\n\n"
        "  2) Ajoutez le dossier d'installation au PATH (ex. C:\\Program Files\\Tesseract-OCR).\n"
        "     Pour ajouter temporairement au PATH dans PowerShell :\n"
        "       $env:Path += \";C:\\Program Files\\Tesseract-OCR\"\n\n"
        "     Pour l'ajouter définitivement (PowerShell) :\n"
        "       [Environment]::SetEnvironmentVariable('Path', $env:Path + ';C:\\Program Files\\Tesseract-OCR', 'User')\n\n"
        "  3) Ou indiquez explicitement le chemin via la variable d'environnement 'TESSERACT_CMD' :\n"
        "       setx TESSERACT_CMD \"C:\\Program Files\\Tesseract-OCR\\tesseract.exe\"\n\n"
        "  4) Ou décommentez/ajustez la variable 'pytesseract.pytesseract.tesseract_cmd'\n"
        "     au début de `manhwa_crawler.py`.\n"
    )


def run_crawler(url: str) -> None:
    """Exécute le pipeline complet pour l'URL donnée : navigation + téléchargement
    des images, détection des bulles, OCR, écriture de `output.txt`.

    Lève une `RuntimeError` (message destiné à l'utilisateur) en cas d'échec.
    N'appelle jamais `sys.exit()` : cette fonction est conçue pour être
    appelée aussi bien en ligne de commande que depuis un thread d'IHM.
    """
    _check_tesseract()

    # -- Charger les templates de la police manga (cara/) --------------------
    global _CARA_TEMPLATES
    _CARA_TEMPLATES = _load_cara_templates(paths.resource_path(CARA_DIR))

    url = url.strip()
    if not url:
        raise RuntimeError("URL vide.")
    if not url.startswith("http"):
        url = "https://" + url

    # -- Préparer le dossier pages/ -------------------------------------------
    pages_dir = os.path.join(paths.app_dir(), PAGES_DIR)
    os.makedirs(pages_dir, exist_ok=True)
    log.info("Les images seront sauvegardées dans : %s", pages_dir)

    # -- Lancement du navigateur Chrome ---------------------------------------
    log.info("Lancement de Chrome...")
    try:
        driver = create_driver()
    except WebDriverException as exc:
        raise RuntimeError(
            f"Impossible de lancer Chrome :\n  {exc}\n\n"
            "Google Chrome doit être installé sur cette machine (Selenium ne "
            "peut pas piloter un navigateur qu'il ne trouve pas)."
        ) from exc

    pil_images: List[Image.Image] = []   # images téléchargées, dans l'ordre

    try:
        # -- Récupération des URLs d'images -----------------------------------
        image_urls = fetch_image_urls(driver, url)

        if not image_urls:
            raise RuntimeError(
                "Aucune image trouvée sur cette page.\n"
                "Vérifiez l'URL ou inspectez la structure HTML du site cible."
            )

        log.info("%d image(s) détectée(s).", len(image_urls))

        # Session requests pour les URLs normales (http/https)
        session = requests.Session()
        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer":         url,
            "Accept":          "image/webp,image/apng,image/*,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })
        transfer_cookies(driver, session)

        # -- Téléchargement des images (navigateur encore ouvert) -------------
        # ⚠️  IMPORTANT : les blob: URLs ne peuvent être lues que PENDANT
        #    la session du navigateur. Le driver ne doit pas être fermé avant
        #    d'avoir extrait tous les blobs via JavaScript.
        log.info("Téléchargement et sauvegarde dans '%s'...", pages_dir)
        for idx, img_url in enumerate(image_urls, 1):
            log.info("[%d/%d] %s", idx, len(image_urls), img_url)

            if img_url.startswith("blob:"):
                # Extraction via JavaScript dans le navigateur
                pil_img = blob_to_pil(driver, img_url)
            else:
                # Téléchargement HTTP classique
                pil_img = download_image(img_url, session)

            if pil_img is None:
                log.warning("  → Image %d ignorée (échec)", idx)
                continue

            # Sauvegarder l'image sur le disque dans pages/
            save_path = os.path.join(pages_dir, f"page_{idx:03d}.png")
            pil_img.save(save_path, "PNG")
            log.info("  → Sauvegardé : page_%03d.png (%dx%d)", idx, pil_img.width, pil_img.height)
            pil_images.append(pil_img)

    finally:
        # Fermer le navigateur dans tous les cas (erreur ou succès)
        driver.quit()
        log.info("Navigateur fermé.")

    # -- Vérification ---------------------------------------------------------
    if not pil_images:
        raise RuntimeError(
            "Aucune image n'a pu être téléchargée.\n"
            "Vérifiez la connexion réseau ou l'URL."
        )

    log.info("%d image(s) téléchargée(s) et sauvegardée(s) dans '%s'.", len(pil_images), pages_dir)

    # -- Fusion des pages via fusion.py ---------------------------------------
    from fusion import fusionner_pages as _fusionner_pages
    log.info("Fusion des pages en une ou plusieurs images...")

    try:
        page_all_paths = _fusionner_pages(pages_dir)   # maintenant une LISTE
        log.info("Images fusionnées : %s", page_all_paths)
    except Exception as exc:
        raise RuntimeError(f"Echec de la fusion des pages : {exc}") from exc

    # -- OCR Tesseract sur chaque image fusionnée -----------------------------
    all_lines: List[Tuple[str, bool]] = []

    for page_path in page_all_paths:
        log.info("Lancement de Tesseract sur : %s", page_path)

        page_img = Image.open(page_path)
        raw_text = pytesseract.image_to_string(
            page_img,
            lang=OCR_LANG,
            config="--oem 3 --psm 3",
        )

        for raw_line in raw_text.split('\n'):
            clean = _clean_text(raw_line.strip())
            if clean:
                all_lines.append((clean, True))

    # Nettoyage final
    all_lines = _dedup_lines(all_lines)
    log.info("Total : %d ligne(s) après nettoyage.", len(all_lines))

    # -- Écriture du fichier output.txt ---------------------------------------
    if not all_lines:
        raise RuntimeError(
            "Aucun texte n'a été extrait.\n"
            "Causes possibles : résolution trop faible, Tesseract mal configuré."
        )

    out_path = os.path.join(paths.app_dir(), OUTPUT_FILE)
    count = 0
    with open(out_path, "w", encoding="utf-8") as fout:
        for text, is_bubble in all_lines:
            if is_bubble:
                fout.write(text + "\n")       # texte en bulle → ligne normale
            else:
                fout.write(text + " **\n")    # texte hors bulle → marqué **
            count += 1

    log.info("%d ligne(s) écrite(s) dans '%s'", count, out_path)
    log.info("Images sauvegardées dans '%s'", pages_dir)


def main() -> None:
    """Point d'entrée en ligne de commande (usage manuel / debug)."""
    print("=" * 60)
    print("   Manhwa Chapter Crawler + OCR")
    print("=" * 60)

    url = input("\nEntrez l'URL du chapitre manhwa :\n> ").strip()
    if not url:
        sys.exit("URL vide. Arrêt.")

    try:
        run_crawler(url)
    except RuntimeError as exc:
        sys.exit(f"\n[ERREUR] {exc}")

    print("\n[TERMINE]")
    print(url)


if __name__ == "__main__":
    main()


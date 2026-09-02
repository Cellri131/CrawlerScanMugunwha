"""Installateur autonome — MugunwHaTradInstaller.exe.

À lancer UNE SEULE FOIS sur toute machine neuve, avant la première
utilisation de MugunwHaTrad. Cet exécutable :
  1. installe Tesseract OCR (copie portable embarquée, voir
     `_collect_tesseract_datas` dans installer.spec) dans un dossier
     persistant propre à l'utilisateur courant (pas besoin de droits admin) ;
  2. télécharge la dernière version publiée de MugunwHaTrad.exe depuis les
     releases GitHub du projet et l'installe dans le même type de dossier ;
  3. lance MugunwHaTrad.exe fraîchement installé ;
  4. si tout s'est bien passé, se supprime lui-même automatiquement.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import tkinter as tk
from tkinter import messagebox

import paths

# Dossiers d'installation persistants, par utilisateur, sans droits admin requis.
TESSERACT_INSTALL_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Programs", "Tesseract-OCR"
)
APP_INSTALL_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Programs", "MugunwHaTrad"
)
APP_EXE_NAME = "MugunwHaTrad.exe"

# Lien "latest" GitHub : redirige toujours vers l'asset de la toute dernière
# release publiée, sans avoir besoin d'appeler l'API GitHub.
APP_LATEST_RELEASE_URL = (
    "https://github.com/Cellri131/CrawlerScanMugunwha/releases/latest/download/"
    + APP_EXE_NAME
)


def _bundled_tesseract_dir() -> str:
    """Dossier de la copie portable de Tesseract embarquée dans cet .exe."""
    return paths.resource_path("tesseract_install")


def _tesseract_works(exe_path: str) -> bool:
    """Vérifie que `tesseract_path --version` s'exécute réellement (pas
    seulement que le fichier existe : DLL manquante = plantage silencieux)."""
    try:
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        result = subprocess.run(
            [exe_path, "--version"],
            capture_output=True,
            timeout=15,
            creationflags=creationflags,
        )
        return result.returncode == 0
    except Exception:
        return False


def _self_delete() -> None:
    """Planifie la suppression de cet .exe une fois le process terminé.

    Un exécutable en cours d'exécution ne peut pas se supprimer lui-même
    directement sous Windows (fichier verrouillé tant que le process vit).
    On écrit donc un petit script .bat, dans un dossier temporaire distinct
    de cet .exe, qui boucle en réessayant `del` jusqu'à ce que le verrou soit
    relâché (le process peut mettre plus de temps à se terminer qu'un délai
    fixe, notamment si un antivirus scanne le fichier), puis se supprime
    lui-même.
    """
    if not paths.is_frozen() or os.name != "nt":
        return
    exe_path = sys.executable
    bat_path = os.path.join(tempfile.gettempdir(), "mugunwha_installer_cleanup.bat")
    bat_content = (
        "@echo off\n"
        ":retry\n"
        f'del /f /q "{exe_path}" >nul 2>&1\n'
        f'if exist "{exe_path}" (\n'
        "  timeout /t 1 /nobreak >nul\n"
        "  goto retry\n"
        ")\n"
        'del /f /q "%~f0"\n'
    )
    with open(bat_path, "w", encoding="utf-8") as f:
        f.write(bat_content)
    subprocess.Popen(
        ["cmd", "/c", bat_path],
        creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
        close_fds=True,
    )


def install_tesseract() -> bool:
    """Copie Tesseract vers TESSERACT_INSTALL_DIR et vérifie qu'il fonctionne.
    Retourne True si Tesseract est installé et fonctionnel à la fin."""
    dest_exe = os.path.join(TESSERACT_INSTALL_DIR, "tesseract.exe")

    if os.path.isfile(dest_exe) and _tesseract_works(dest_exe):
        return True

    src = _bundled_tesseract_dir()
    if not os.path.isdir(src):
        messagebox.showerror(
            "Installation impossible",
            "Aucune copie de Tesseract OCR n'est intégrée à cet installateur.",
        )
        return False

    if os.path.isdir(TESSERACT_INSTALL_DIR):
        shutil.rmtree(TESSERACT_INSTALL_DIR, ignore_errors=True)
    shutil.copytree(src, TESSERACT_INSTALL_DIR)

    if not _tesseract_works(dest_exe):
        messagebox.showerror(
            "Échec de l'installation de Tesseract",
            "Tesseract OCR a été copié mais ne démarre pas correctement.\n"
            f"Dossier : {TESSERACT_INSTALL_DIR}\n\n"
            "Vérifiez qu'un antivirus ne bloque pas le fichier, puis relancez "
            "cet installateur.",
        )
        return False

    return True


def install_app() -> bool:
    """Télécharge la dernière version de MugunwHaTrad.exe publiée sur GitHub
    et l'installe dans APP_INSTALL_DIR. Retourne True si l'app est prête."""
    dest_exe = os.path.join(APP_INSTALL_DIR, APP_EXE_NAME)
    os.makedirs(APP_INSTALL_DIR, exist_ok=True)
    tmp_path = dest_exe + ".download"

    try:
        with urllib.request.urlopen(APP_LATEST_RELEASE_URL, timeout=60) as response:
            with open(tmp_path, "wb") as out_file:
                shutil.copyfileobj(response, out_file)
    except (urllib.error.URLError, OSError) as exc:
        if os.path.isfile(tmp_path):
            os.remove(tmp_path)
        messagebox.showerror(
            "Téléchargement impossible",
            "Impossible de télécharger la dernière version de MugunwHaTrad.\n"
            "Vérifiez votre connexion internet puis relancez cet installateur.\n\n"
            f"Détail : {exc}",
        )
        return False

    # Contrôle de cohérence : l'exécutable réel pèse plusieurs dizaines de Mo.
    if os.path.getsize(tmp_path) < 1_000_000:
        os.remove(tmp_path)
        messagebox.showerror(
            "Téléchargement invalide",
            "Le fichier téléchargé est trop petit pour être l'application.\n"
            "Réessayez plus tard.",
        )
        return False

    os.replace(tmp_path, dest_exe)
    return True


def _launch_app() -> None:
    """Lance l'application fraîchement installée."""
    dest_exe = os.path.join(APP_INSTALL_DIR, APP_EXE_NAME)
    try:
        os.startfile(dest_exe)
    except Exception:
        pass


def main() -> None:
    root = tk.Tk()
    root.withdraw()
    try:
        tesseract_ok = install_tesseract()
        app_ok = install_app() if tesseract_ok else False
    finally:
        root.destroy()

    if tesseract_ok and app_ok:
        messagebox.showinfo(
            "Installation terminée",
            "Tesseract OCR et MugunwHaTrad ont été installés avec succès.\n\n"
            "L'application va démarrer, et cet installateur va se fermer et "
            "se supprimer automatiquement.",
        )
        _launch_app()
        _self_delete()

    sys.exit(0 if (tesseract_ok and app_ok) else 1)


if __name__ == "__main__":
    main()

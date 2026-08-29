"""Installateur autonome de dépendances — MugunwHaTradInstaller.exe.

À lancer UNE SEULE FOIS, avant la première utilisation de MugunwHaTrad.exe,
sur toute machine qui n'a pas déjà Tesseract OCR installé. Cet exécutable
embarque une copie portable de Tesseract-OCR (voir `_collect_tesseract_datas`
dans installer.spec) et se contente de :
  1. la copier vers un dossier persistant propre à l'utilisateur courant
     (pas besoin de droits administrateur) ;
  2. vérifier qu'elle fonctionne réellement (appel `tesseract --version`) ;
  3. si tout est bon, se supprimer lui-même automatiquement.

MugunwHaTrad.exe (l'application principale) recherche ensuite Tesseract à cet
emplacement en priorité (voir `_check_tesseract` dans manhwa_crawler.py).
"""

import os
import shutil
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox

import paths

# Dossier d'installation persistant, par utilisateur, sans droits admin requis.
INSTALL_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Programs", "Tesseract-OCR"
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
    directement sous Windows (fichier verrouillé). On lance donc, en
    détaché, une commande qui attend quelques secondes (le temps que ce
    process se termine et libère le verrou) puis supprime le fichier.
    """
    if not paths.is_frozen() or os.name != "nt":
        return
    exe_path = sys.executable
    delayed_del = f'timeout /t 2 /nobreak >nul & del /f /q "{exe_path}"'
    subprocess.Popen(
        ["cmd", "/c", delayed_del], creationflags=subprocess.CREATE_NO_WINDOW
    )


def install() -> bool:
    """Copie Tesseract vers INSTALL_DIR et vérifie qu'il fonctionne.
    Retourne True si Tesseract est installé et fonctionnel à la fin."""
    dest_exe = os.path.join(INSTALL_DIR, "tesseract.exe")

    if os.path.isfile(dest_exe) and _tesseract_works(dest_exe):
        messagebox.showinfo(
            "Déjà installé",
            "Tesseract OCR est déjà installé et fonctionnel sur cette machine.\n"
            "Vous pouvez lancer MugunwHaTrad.exe directement.",
        )
        return True

    src = _bundled_tesseract_dir()
    if not os.path.isdir(src):
        messagebox.showerror(
            "Installation impossible",
            "Aucune copie de Tesseract OCR n'est intégrée à cet installateur.",
        )
        return False

    if os.path.isdir(INSTALL_DIR):
        shutil.rmtree(INSTALL_DIR, ignore_errors=True)
    shutil.copytree(src, INSTALL_DIR)

    if not _tesseract_works(dest_exe):
        messagebox.showerror(
            "Échec de l'installation",
            "Tesseract OCR a été copié mais ne démarre pas correctement.\n"
            f"Dossier : {INSTALL_DIR}\n\n"
            "Vérifiez qu'un antivirus ne bloque pas le fichier, puis relancez "
            "cet installateur.",
        )
        return False

    messagebox.showinfo(
        "Installation terminée",
        "Tesseract OCR a été installé avec succès.\n"
        "Vous pouvez maintenant lancer MugunwHaTrad.exe.\n\n"
        "Cet installateur va se fermer et se supprimer automatiquement.",
    )
    return True


def main() -> None:
    root = tk.Tk()
    root.withdraw()
    try:
        ok = install()
    finally:
        root.destroy()
    if ok:
        _self_delete()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

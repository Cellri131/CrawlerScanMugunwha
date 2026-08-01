"""Résolution des chemins, compatible exécution en script ET en .exe gelé
(PyInstaller --onefile).

Deux notions bien distinctes :
- `app_dir()`   : dossier où vivent les données PERSISTANTES générées par
                  l'application (pages/, output.txt, export.docx). C'est le
                  dossier de l'exécutable en mode gelé, celui du script sinon.
- `resource_path(...)` : dossier des ressources EMBARQUÉES en lecture seule
                  (cara/, icône, Tesseract portable...). En mode gelé
                  --onefile, PyInstaller les extrait dans un dossier
                  temporaire (`sys._MEIPASS`) au lancement.
"""

import os
import sys


def is_frozen() -> bool:
    """True si le code tourne depuis un exécutable PyInstaller."""
    return bool(getattr(sys, "frozen", False))


def app_dir() -> str:
    """Dossier de l'exécutable (.exe) ou du script `ihm.py`."""
    if is_frozen():
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def resource_path(*parts: str) -> str:
    """Chemin vers une ressource embarquée (lecture seule)."""
    if is_frozen():
        root = getattr(sys, "_MEIPASS", app_dir())
    else:
        root = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(root, *parts)

"""Palette de couleurs et polices partagées par toute l'interface graphique.

Centraliser ces valeurs ici permet de garder un rendu cohérent entre la
fenêtre principale (ihm.py), le tableau de texte (table_widget.py), le
panneau de traduction (translator_panel.py) et le panneau d'images
(image_panel.py).
"""

# Fond général de la fenêtre / zones neutres
BG_APP = "#eef1f6"
# Fond de la barre d'outils et des panneaux "papier"
BG_TOOLBAR = "#ffffff"
BG_PANEL = "#ffffff"
# Fond du visualiseur d'images (sombre pour faire ressortir les pages)
BG_CANVAS = "#1c1e26"

# Couleur d'accent principale (boutons, en-têtes, sélection)
ACCENT = "#4f6df5"
ACCENT_DARK = "#3d54c9"
ACCENT_SOFT = "#e4e9ff"

TEXT_DARK = "#20222b"
TEXT_MUTED = "#6b7280"
TEXT_LIGHT = "#ffffff"
TEXT_DISABLED = "#c3c8d6"

BORDER = "#d7dbe3"

FONT_FAMILY = "Segoe UI"
FONT_TEXT = (FONT_FAMILY, 10)
FONT_BOLD = (FONT_FAMILY, 10, "bold")
FONT_TITLE = (FONT_FAMILY, 11, "bold")

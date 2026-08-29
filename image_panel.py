import os
import re
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk

import theme as th


class ImagePanel(tk.Frame):
    """Affiche à la suite les pages fusionnées (page_all*.png produites par
    fusion.py), avec défilement vertical et mise à l'échelle sur toute la
    largeur disponible du panneau."""

    def __init__(self, parent, pages_folder="pages"):
        super().__init__(
            parent, bg=th.BG_CANVAS, highlightthickness=1, highlightbackground=th.BORDER
        )

        self.pages_folder = pages_folder

        ttk.Label(self, text="Pages du chapitre", style="PanelTitle.TLabel").pack(
            side="top", fill="x"
        )

        body = tk.Frame(self, bg=th.BG_CANVAS)
        body.pack(side="top", fill="both", expand=True)

        self.canvas = tk.Canvas(body, bg=th.BG_CANVAS, highlightthickness=0)
        self.v_scroll = ttk.Scrollbar(body, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.v_scroll.set)

        self.v_scroll.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.tk_photos = []
        self.pil_images = []
        self._resize_job = None

        self.canvas.bind("<Enter>", self._bind_mousewheel)
        self.canvas.bind("<Leave>", self._unbind_mousewheel)
        self.canvas.bind("<Configure>", self._on_resize)

    # ------------------------------------------------------------------
    # Chargement
    # ------------------------------------------------------------------
    def load_images(self, image_list=None):
        """Charge uniquement les pages fusionnées (page_all.png, page_all1.png,
        page_all2.png, ...) dans l'ordre, en ignorant les pages brutes."""
        files = []
        if os.path.isdir(self.pages_folder):
            pattern = re.compile(r"^page_all(\d*)\.png$", re.IGNORECASE)
            for f in os.listdir(self.pages_folder):
                match = pattern.match(f)
                if match:
                    suffix = match.group(1)
                    order = int(suffix) if suffix else 0
                    files.append((order, f))
            files.sort(key=lambda pair: pair[0])

        self.pil_images = [
            Image.open(os.path.join(self.pages_folder, name)) for _, name in files
        ]

        self._render()

    # ------------------------------------------------------------------
    # Rendu / redimensionnement
    # ------------------------------------------------------------------
    def _on_resize(self, _event):
        if not self.pil_images:
            return
        # Anti-rebond : évite de redessiner à chaque pixel pendant un glissement.
        if self._resize_job is not None:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(120, self._render)

    def _render(self):
        self._resize_job = None
        if not self.pil_images:
            return

        width = max(self.canvas.winfo_width(), 100)
        margin = 10
        target_w = max(width - 2 * margin, 50)

        self.canvas.delete("all")
        self.tk_photos = []

        y_offset = margin
        for img in self.pil_images:
            h = int(img.height * target_w / img.width)
            resized = img.resize((target_w, h), Image.LANCZOS)
            photo = ImageTk.PhotoImage(resized)
            self.tk_photos.append(photo)

            self.canvas.create_image(margin, y_offset, anchor="nw", image=photo)
            # Pas de marge entre deux page_all* : ce sont des morceaux d'une
            # même lecture continue (découpés seulement à cause de max_height
            # dans fusion.py), une marge ici créerait une fausse séparation.
            y_offset += h

        self.canvas.configure(scrollregion=(0, 0, width, y_offset + margin))

    # ------------------------------------------------------------------
    # Molette de la souris
    # ------------------------------------------------------------------
    def _bind_mousewheel(self, _event):
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel)

    def _unbind_mousewheel(self, _event):
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")

    def _on_mousewheel(self, event):
        if event.num == 4:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.canvas.yview_scroll(1, "units")
        else:
            self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")


import sys
import os
import subprocess
import threading

import tkinter as tk
from tkinter import ttk, messagebox

import theme as th
from image_panel import ImagePanel
from table_widget import EditableTable
from translator_panel import TranslatorPanel
from exporter import export_docx


class App(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("MugunwHa Trad")
        self.geometry("1500x900")
        self.minsize(1100, 650)
        self.configure(bg=th.BG_APP)

        try:
            self.iconbitmap("MugunwHaLogoTrad.ico")
        except Exception:
            pass

        self._setup_style()

        self.url_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Prêt.")

        self.translation_shown = False

        # Barre d'outils
        toolbar = ttk.Frame(self, style="Toolbar.TFrame", padding=(16, 12))
        toolbar.pack(fill="x")

        ttk.Label(toolbar, text="URL du chapitre :", style="Toolbar.TLabel").pack(
            side="left", padx=(0, 8)
        )
        ttk.Entry(toolbar, textvariable=self.url_var, width=55).pack(
            side="left", padx=(0, 10), ipady=3
        )

        self.btn_run = ttk.Button(
            toolbar, text="▶  Lancer", command=self.run_crawler, style="Accent.TButton"
        )
        self.btn_run.pack(side="left", padx=4)

        self.btn_translate = ttk.Button(
            toolbar, text="🌐  Traduire", command=self.show_translation, style="Accent.TButton"
        )
        self.btn_translate.pack(side="left", padx=4)

        ttk.Label(toolbar, textvariable=self.status_var, style="Status.TLabel").pack(
            side="left", padx=16
        )

        ttk.Button(
            toolbar, text="Aide", command=self.show_help, style="Ghost.TButton"
        ).pack(side="right", padx=(4, 0))
        ttk.Button(
            toolbar, text="⬇  Exporter DOCX", command=self.export_doc, style="Secondary.TButton"
        ).pack(side="right", padx=4)

        ttk.Separator(self, orient="horizontal").pack(fill="x")

        # Main layout : PanedWindow horizontal, chaque volet est redimensionnable
        # en largeur en faisant glisser la barre (sash) qui le sépare du suivant.
        self.paned = tk.PanedWindow(
            self,
            orient="horizontal",
            sashrelief="flat",
            sashwidth=6,
            sashpad=0,
            bg=th.BG_APP,
            bd=0,
        )
        self.paned.pack(fill="both", expand=True, padx=10, pady=10)

        # Panel images
        self.left_panel = ImagePanel(self.paned)
        self.paned.add(self.left_panel, minsize=250, width=550, stretch="never")

        # Panel texte (anglais)
        text_frame = tk.Frame(
            self.paned, bg=th.BG_PANEL, highlightthickness=1, highlightbackground=th.BORDER
        )

        ttk.Label(
            text_frame, text="Texte extrait (anglais)", style="PanelTitle.TLabel"
        ).pack(side="top", fill="x")

        x_scroll = ttk.Scrollbar(text_frame, orient="horizontal")
        x_scroll.pack(side="bottom", fill="x")

        y_scroll = ttk.Scrollbar(text_frame, orient="vertical")
        y_scroll.pack(side="right", fill="y")

        self.right_panel = EditableTable(text_frame)
        self.right_panel.pack(side="left", fill="both", expand=True, padx=1, pady=(0, 1))

        self.right_panel.configure(
            xscrollcommand=x_scroll.set,
            yscrollcommand=y_scroll.set
        )
        x_scroll.config(command=self.right_panel.xview)
        y_scroll.config(command=self.right_panel.yview)

        self.paned.add(text_frame, minsize=300, width=650, stretch="always")

        # Panel traduction : créé tout de suite, ajouté au paned seulement à la demande
        self.translator_frame = tk.Frame(
            self.paned, bg=th.BG_PANEL, highlightthickness=1, highlightbackground=th.BORDER
        )

        ttk.Label(
            self.translator_frame, text="Traduction (français)", style="PanelTitle.TLabel"
        ).pack(side="top", fill="x")

        tx_scroll = ttk.Scrollbar(self.translator_frame, orient="horizontal")
        tx_scroll.pack(side="bottom", fill="x")

        ty_scroll = ttk.Scrollbar(self.translator_frame, orient="vertical")
        ty_scroll.pack(side="right", fill="y")

        self.translator_panel = TranslatorPanel(self.translator_frame)
        self.translator_panel.pack(side="left", fill="both", expand=True, padx=1, pady=(0, 1))

        self.translator_panel.configure(
            xscrollcommand=tx_scroll.set,
            yscrollcommand=ty_scroll.set
        )
        tx_scroll.config(command=self.translator_panel.xview)
        ty_scroll.config(command=self.translator_panel.yview)

    def _setup_style(self):
        """Configure un thème ttk cohérent pour toute l'application."""
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("TFrame", background=th.BG_APP)
        style.configure("Toolbar.TFrame", background=th.BG_TOOLBAR)

        style.configure(
            "Toolbar.TLabel",
            background=th.BG_TOOLBAR,
            foreground=th.TEXT_DARK,
            font=th.FONT_TEXT,
        )
        style.configure(
            "Status.TLabel",
            background=th.BG_TOOLBAR,
            foreground=th.TEXT_MUTED,
            font=(th.FONT_FAMILY, 9, "italic"),
        )
        style.configure(
            "PanelTitle.TLabel",
            background=th.ACCENT,
            foreground=th.TEXT_LIGHT,
            font=th.FONT_BOLD,
            padding=(10, 6),
        )

        style.configure(
            "TEntry",
            fieldbackground="#ffffff",
            bordercolor=th.BORDER,
            lightcolor=th.BORDER,
            darkcolor=th.BORDER,
            padding=6,
        )
        style.map("TEntry", bordercolor=[("focus", th.ACCENT)])

        # Boutons d'action principale (accent plein)
        style.configure(
            "Accent.TButton",
            background=th.ACCENT,
            foreground=th.TEXT_LIGHT,
            font=th.FONT_BOLD,
            borderwidth=0,
            padding=(14, 8),
        )
        style.map(
            "Accent.TButton",
            background=[("active", th.ACCENT_DARK), ("disabled", th.TEXT_DISABLED)],
            foreground=[("disabled", "#f3f4f7")],
        )

        # Boutons secondaires (contour)
        style.configure(
            "Secondary.TButton",
            background=th.BG_TOOLBAR,
            foreground=th.ACCENT,
            bordercolor=th.ACCENT,
            borderwidth=1,
            font=th.FONT_TEXT,
            padding=(12, 7),
        )
        style.map(
            "Secondary.TButton",
            background=[("active", th.ACCENT_SOFT)],
            foreground=[("disabled", th.TEXT_DISABLED)],
        )

        # Boutons discrets (texte seul)
        style.configure(
            "Ghost.TButton",
            background=th.BG_TOOLBAR,
            foreground=th.TEXT_MUTED,
            borderwidth=0,
            font=th.FONT_TEXT,
            padding=(10, 7),
        )
        style.map("Ghost.TButton", foreground=[("active", th.ACCENT)])

        # Barres de défilement
        for orient in ("Vertical", "Horizontal"):
            style.configure(
                f"{orient}.TScrollbar",
                background=th.BG_APP,
                troughcolor=th.BG_APP,
                bordercolor=th.BORDER,
                arrowcolor=th.TEXT_MUTED,
                relief="flat",
            )

        # Tableaux (Treeview) : base commune, personnalisée ensuite par
        # table_widget.py / translator_panel.py pour la taille de police.
        style.configure(
            "Treeview",
            background=th.BG_PANEL,
            fieldbackground=th.BG_PANEL,
            foreground=th.TEXT_DARK,
            bordercolor=th.BORDER,
            borderwidth=0,
            relief="flat",
        )
        style.configure(
            "Treeview.Heading",
            background=th.ACCENT,
            foreground=th.TEXT_LIGHT,
            font=th.FONT_BOLD,
            relief="flat",
            padding=(8, 6),
        )
        style.map("Treeview.Heading", background=[("active", th.ACCENT_DARK)])
        style.map(
            "Treeview",
            background=[("selected", th.ACCENT_SOFT)],
            foreground=[("selected", th.TEXT_DARK)],
        )

    def show_help(self):
        messagebox.showinfo(
            "Aide",
            "Fonctionnalités :\n\n"
            "- Lancer : télécharge les images et extrait le texte anglais.\n"
            "- Traduire : traduit le texte anglais en français.\n"
            "- Exporter DOCX : exporte le texte (français si traduit).\n\n"
            "Raccourcis (tableau) :\n"
            "- Double-clic : éditer une cellule.\n"
            "- Entrée : insérer une ligne vide sous la ligne sélectionnée.\n"
            "- Retour arrière : fusionner avec la ligne précédente.\n"
            "- Suppr : supprimer la ligne sélectionnée.\n"
        )

    # -------------------------------------------------------------------
    # Crawler
    # -------------------------------------------------------------------
    def run_crawler(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("URL manquante", "Veuillez saisir l'URL du chapitre.")
            return

        self.btn_run.config(state="disabled")
        self.status_var.set("Crawl en cours...")

        threading.Thread(target=self._run_crawler_thread, args=(url,), daemon=True).start()

    def _run_crawler_thread(self, url):
        try:
            process = subprocess.Popen(
                [sys.executable, "manhwa_crawler.py"],
                stdin=subprocess.PIPE,
                text=True,
            )
            process.communicate(url)
            returncode = process.returncode
        except Exception as exc:
            self.after(0, self._on_crawler_error, str(exc))
            return

        if returncode != 0:
            self.after(
                0,
                self._on_crawler_error,
                f"Le crawler s'est terminé avec une erreur (code {returncode}).",
            )
            return

        self.after(0, self._on_crawler_done)

    def _on_crawler_error(self, message):
        self.status_var.set("Erreur lors du crawl.")
        self.btn_run.config(state="normal")
        messagebox.showerror("Erreur crawler", message)

    def _on_crawler_done(self):
        self.left_panel.load_images()

        if os.path.isfile("output.txt"):
            self.right_panel.load_from_file("output.txt")
            self.status_var.set("Crawl terminé.")
        else:
            self.status_var.set("Crawl terminé, mais aucun texte n'a été extrait.")

        self.btn_run.config(state="normal")

    # -------------------------------------------------------------------
    # Traduction
    # -------------------------------------------------------------------
    def show_translation(self):
        if not self.right_panel.get_children():
            messagebox.showinfo(
                "Traduction",
                "Aucun texte à traduire. Lancez d'abord le crawler.",
            )
            return

        if not self.translation_shown:
            self.paned.add(self.translator_frame, minsize=300, width=500, stretch="always")
            self.translation_shown = True

        self.btn_translate.config(state="disabled")
        self.status_var.set("Traduction en cours...")

        self.translator_panel.translate_from_table(
            self.right_panel, on_done=self._on_translation_done
        )

    def _on_translation_done(self):
        self.status_var.set("Traduction terminée.")
        self.btn_translate.config(state="normal")

    def export_doc(self):
        # Exporte le français si la traduction a été faite, sinon l'anglais.
        if self.translation_shown and self.translator_panel.get_children():
            source = self.translator_panel
        else:
            source = self.right_panel

        export_docx(source)
        messagebox.showinfo("OK", "Exporté en DOCX.")


if __name__ == "__main__":
    app = App()
    app.mainloop()


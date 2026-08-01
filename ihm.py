import sys
import os
import subprocess
import threading

import tkinter as tk
from tkinter import messagebox

from image_panel import ImagePanel
from table_widget import EditableTable
from translator_panel import TranslatorPanel
from exporter import export_docx


class App(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("MugunwHa Trad")
        self.geometry("1500x900")

        try:
            self.iconbitmap("MugunwHaLogoTrad.ico")
        except Exception:
            pass

        self.url_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Prêt.")

        self.translation_shown = False

        # Top bar
        top = tk.Frame(self)
        top.pack(fill="x", pady=10)

        tk.Label(top, text="URL :").pack(side="left", padx=5)
        tk.Entry(top, textvariable=self.url_var, width=50).pack(side="left", padx=5)

        self.btn_run = tk.Button(top, text="Lancer", command=self.run_crawler)
        self.btn_run.pack(side="left", padx=5)

        self.btn_translate = tk.Button(top, text="Traduire", command=self.show_translation)
        self.btn_translate.pack(side="left", padx=10)

        tk.Label(top, textvariable=self.status_var, fg="#555555").pack(side="left", padx=10)

        tk.Button(top, text="Exporter DOCX", command=self.export_doc).pack(side="right", padx=5)

        tk.Button(top, text="HELP", command=self.show_help).pack(side="right", padx=10)

        # Main layout
        main = tk.Frame(self)
        main.pack(fill="both", expand=True)

        main.grid_columnconfigure(0, weight=0)
        main.grid_columnconfigure(1, weight=1)
        main.grid_columnconfigure(2, weight=1)
        main.grid_rowconfigure(0, weight=1)

        # Panel images
        self.left_panel = ImagePanel(main)
        self.left_panel.grid(row=0, column=0, sticky="nsw", padx=5, pady=5)

        # Panel texte (anglais)
        text_frame = tk.Frame(main)
        text_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)

        x_scroll = tk.Scrollbar(text_frame, orient="horizontal")
        x_scroll.pack(side="bottom", fill="x")

        y_scroll = tk.Scrollbar(text_frame, orient="vertical")
        y_scroll.pack(side="right", fill="y")

        self.right_panel = EditableTable(text_frame)
        self.right_panel.pack(side="left", fill="both", expand=True)

        self.right_panel.configure(
            xscrollcommand=x_scroll.set,
            yscrollcommand=y_scroll.set
        )
        x_scroll.config(command=self.right_panel.xview)
        y_scroll.config(command=self.right_panel.yview)

        # Panel traduction (créé tout de suite, affiché seulement à la demande)
        self.translator_frame = tk.Frame(main)

        tx_scroll = tk.Scrollbar(self.translator_frame, orient="horizontal")
        tx_scroll.pack(side="bottom", fill="x")

        ty_scroll = tk.Scrollbar(self.translator_frame, orient="vertical")
        ty_scroll.pack(side="right", fill="y")

        self.translator_panel = TranslatorPanel(self.translator_frame)
        self.translator_panel.pack(side="left", fill="both", expand=True)

        self.translator_panel.configure(
            xscrollcommand=tx_scroll.set,
            yscrollcommand=ty_scroll.set
        )
        tx_scroll.config(command=self.translator_panel.xview)
        ty_scroll.config(command=self.translator_panel.yview)

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
        if os.path.isdir("pages"):
            images = sorted(os.listdir("pages"))
            self.left_panel.load_images(images)

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
            self.translator_frame.grid(row=0, column=2, sticky="nsew", padx=5, pady=5)
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
        export_docx(self.right_panel)
        messagebox.showinfo("OK", "Exporté en DOCX.")


if __name__ == "__main__":
    app = App()
    app.mainloop()


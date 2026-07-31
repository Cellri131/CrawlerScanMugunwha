import tkinter as tk
from tkinter import ttk, messagebox
import threading
import subprocess
import time
import queue
import os

from splash import SplashScreen
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
        except:
            pass

        self.url_var = tk.StringVar()

        self.crawl_queue = queue.Queue()
        self.trans_queue = queue.Queue()
        self.image_queue = queue.Queue()

        self.after(50, self._poll_crawl_queue)
        self.after(50, self._poll_trans_queue)
        self.after(50, self._poll_image_queue)

        # Top bar
        top = tk.Frame(self)
        top.pack(fill="x", pady=10)

        tk.Label(top, text="URL :").pack(side="left", padx=5)
        tk.Entry(top, textvariable=self.url_var, width=50).pack(side="left", padx=5)

        tk.Button(top, text="Lancer", command=self.run_crawler).pack(side="left", padx=5)

        self.progress_crawl = ttk.Progressbar(top, length=100)
        self.progress_crawl.pack(side="left", padx=10)

        tk.Button(top, text="Traduire", command=self.show_translation).pack(side="left", padx=10)

        self.progress_trans = ttk.Progressbar(top, length=100)
        self.progress_trans.pack(side="left", padx=10)

        tk.Button(top, text="Exporter DOCX", command=self.export_doc).pack(side="right", padx=5)

        tk.Button(top, text="HELP", command=self.show_help).pack(side="right", padx=10)

        # Main layout
        main = tk.Frame(self)
        main.pack(fill="both", expand=True)

        main.grid_columnconfigure(0, weight=0)
        main.grid_columnconfigure(1, weight=1)
        main.grid_rowconfigure(0, weight=1)

        # Panel images
        self.left_panel = ImagePanel(main)
        self.left_panel.grid(row=0, column=0, sticky="nsw", padx=5, pady=5)

        # Panel texte
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

        self.translator_panel = None
        self.translated_text = None

    def show_help(self):
        messagebox.showinfo(
            "Aide",
            "Fonctionnalités :\n\n"
            "- Lancer : télécharge les images et extrait le texte anglais.\n"
            "- Traduire : traduit le texte anglais en français.\n"
            "- Exporter DOCX : exporte le texte (français si traduit).\n"
            "- Zoom +/- : agrandit ou réduit le texte.\n"
            "- Mode : clair / sombre.\n\n"
            "Raccourcis :\n"
            "- Clic + E : éditer une cellule.\n"
            "- Clic + Entrée : valider l’édition.\n"
            "- Clic droit : options avancées.\n"
        )

    def _poll_crawl_queue(self):
        try:
            while True:
                value, text = self.crawl_queue.get_nowait()
                if value == "DONE":
                    self.progress_crawl["value"] = 100
                else:
                    self.progress_crawl["value"] = value * 100
        except queue.Empty:
            pass
        self.after(50, self._poll_crawl_queue)

    def _poll_trans_queue(self):
        try:
            while True:
                value = self.trans_queue.get_nowait()
                self.progress_trans["value"] = value * 100
        except queue.Empty:
            pass
        self.after(50, self._poll_trans_queue)

    def _poll_image_queue(self):
        try:
            while True:
                images = self.image_queue.get_nowait()
                self.left_panel.load_images(images)
        except queue.Empty:
            pass
        self.after(50, self._poll_image_queue)

    def run_crawler(self):
        self.progress_crawl["value"] = 0

        # Lire l’URL dans le thread principal (sécurisé)
        url = self.url_var.get().strip()

        # Lancer le thread avec l’URL
        threading.Thread(target=self._run_crawler_thread, args=(url,), daemon=True).start()

    def _run_crawler_thread(self, url):
        if not url:
            self.crawl_queue.put((0.0, "Erreur : URL manquante"))
            return

        self.crawl_queue.put((0.1, "Analyse de l'URL..."))

        process = subprocess.Popen(
            ["python", "manhwa_crawler.py"],
            stdin=subprocess.PIPE,
            text=True
        )
        process.communicate(url)

        self.crawl_queue.put((0.4, "Téléchargement des images..."))
        time.sleep(0.3)

        images = sorted(os.listdir("pages"))
        self.image_queue.put(images)

        self.crawl_queue.put((0.9, "Extraction du texte..."))

        self.right_panel.load_from_file("output.txt")

        self.crawl_queue.put(("DONE", "Terminé"))

    def show_translation(self):
        self.progress_trans["value"] = 0

        if self.translator_panel is None:
            self.translator_panel = TranslatorPanel(self)
            self.translator_panel.pack(fill="both", expand=True)

        threading.Thread(target=self._run_translation_thread, daemon=True).start()

    def _run_translation_thread(self):
        for item in self.right_panel.get_children():
            val = self.right_panel.item(item, "values")
            text = val[0] if val else ""
            translated = self.translator_panel.google_translate(text)
            self.trans_queue.put(0.5)
            self.translator_panel.insert("", "end", values=(translated,))
        self.trans_queue.put(1.0)

    def export_doc(self):
        export_docx(self.right_panel)
        messagebox.showinfo("OK", "Exporté en DOCX.")

if __name__ == "__main__":
    splash = SplashScreen()
    splash.update()
    time.sleep(1)
    splash.destroy()   # IMPORTANT : on détruit la fenêtre Tk du splash
    
    app = App()
    app.mainloop()



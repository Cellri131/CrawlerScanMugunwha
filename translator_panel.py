import tkinter as tk
from tkinter import ttk
import threading
import requests

class TranslatorPanel(ttk.Treeview):
    def __init__(self, parent):
        super().__init__(parent, columns=("fr"), show="headings")
        self.heading("fr", text="Traduction FR")

        self.font_size = 14
        self.configure_style()

    def configure_style(self):
        style = ttk.Style()
        style.configure(
            "Translator.Treeview",
            font=("Calibri", self.font_size),
            rowheight=self.font_size + 10
        )
        self.configure(style="Translator.Treeview")

    def zoom_in(self):
        self.font_size += 2
        self.configure_style()

    def zoom_out(self):
        if self.font_size > 10:
            self.font_size -= 2
            self.configure_style()

    def google_translate(self, text):
        if not text.strip():
            return ""

        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            "client": "gtx",
            "sl": "auto",
            "tl": "fr",
            "dt": "t",
            "q": text
        }

        try:
            r = requests.get(url, params=params)
            r.raise_for_status()
            return r.json()[0][0][0]
        except Exception:
            return "[Erreur traduction]"

    def translate_from_table(self, table, on_done=None):
        """Traduit le contenu de `table` en arrière-plan puis remplit ce panneau.

        Les appels réseau (lents) sont exécutés dans un thread séparé ; toute
        mise à jour du widget Tkinter est renvoyée sur le thread principal via
        `after()`, car Tkinter n'est pas thread-safe.
        """
        rows = [table.item(item, "values") for item in table.get_children()]
        texts = [val[0] if val else "" for val in rows]

        self.delete(*self.get_children())

        def worker():
            for text in texts:
                translated = self.google_translate(text)
                self.after(0, lambda t=translated: self.insert("", "end", values=(t,)))
            if on_done:
                self.after(0, on_done)

        threading.Thread(target=worker, daemon=True).start()


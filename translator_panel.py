import tkinter as tk
from tkinter import ttk
import threading
import requests

import theme as th

class TranslatorPanel(ttk.Treeview):
    def __init__(self, parent):
        super().__init__(parent, columns=("fr"), show="headings")
        self.heading("fr", text="")
        self.column("fr", anchor="w")

        self.font_size = 12
        self.configure_style()

        self.tag_configure("even", background=th.BG_PANEL)
        self.tag_configure("odd", background="#f4f6fb")

    def configure_style(self):
        style = ttk.Style()
        style.configure(
            "Translator.Treeview",
            background=th.BG_PANEL,
            fieldbackground=th.BG_PANEL,
            foreground=th.TEXT_DARK,
            borderwidth=0,
            font=(th.FONT_FAMILY, self.font_size),
            rowheight=self.font_size + 14,
        )
        style.configure(
            "Translator.Treeview.Heading",
            background=th.ACCENT,
            foreground=th.TEXT_LIGHT,
            font=(th.FONT_FAMILY, self.font_size - 1, "bold"),
            relief="flat",
            padding=(8, 6),
        )
        style.map("Translator.Treeview.Heading", background=[("active", th.ACCENT_DARK)])
        style.map(
            "Translator.Treeview",
            background=[("selected", th.ACCENT_SOFT)],
            foreground=[("selected", th.TEXT_DARK)],
        )
        self.configure(style="Translator.Treeview")

    def _restripe(self):
        for idx, item in enumerate(self.get_children()):
            self.item(item, tags=("even" if idx % 2 == 0 else "odd",))

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
                self.after(0, lambda t=translated: self._insert_translated(t))
            if on_done:
                self.after(0, on_done)

        threading.Thread(target=worker, daemon=True).start()

    def _insert_translated(self, text):
        self.insert("", "end", values=(text,))
        self._restripe()


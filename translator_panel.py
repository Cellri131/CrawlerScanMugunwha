import tkinter as tk
from tkinter import ttk
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

    def translate_from_table(self, table):
        self.delete(*self.get_children())

        for item in table.get_children():
            val = table.item(item, "values")
            text = val[0] if val else ""
            translated = self.google_translate(text)
            self.insert("", "end", values=(translated,))

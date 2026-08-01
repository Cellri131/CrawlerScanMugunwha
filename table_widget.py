import tkinter as tk
from tkinter import ttk

import theme as th

class EditableTable(ttk.Treeview):
    def __init__(self, parent):
        super().__init__(parent, columns=("text"), show="headings")
        self.heading("text", text="")
        self.column("text", anchor="w")

        self.font_size = 12
        self.configure_style()

        self.tag_configure("even", background=th.BG_PANEL)
        self.tag_configure("odd", background="#f4f6fb")

        self.bind("<Double-1>", self.edit_cell)
        self.bind("<Return>", self.insert_empty_below)
        self.bind("<BackSpace>", self.merge_with_previous)
        self.bind("<Delete>", self.delete_line)
        self.bind("e", self.append_stars)

        self.editor = None

    def configure_style(self):
        style = ttk.Style()
        style.configure(
            "EditableTable.Treeview",
            background=th.BG_PANEL,
            fieldbackground=th.BG_PANEL,
            foreground=th.TEXT_DARK,
            borderwidth=0,
            font=(th.FONT_FAMILY, self.font_size),
            rowheight=self.font_size + 14,
        )
        style.configure(
            "EditableTable.Treeview.Heading",
            background=th.ACCENT,
            foreground=th.TEXT_LIGHT,
            font=(th.FONT_FAMILY, self.font_size - 1, "bold"),
            relief="flat",
            padding=(8, 6),
        )
        style.map("EditableTable.Treeview.Heading", background=[("active", th.ACCENT_DARK)])
        style.map(
            "EditableTable.Treeview",
            background=[("selected", th.ACCENT_SOFT)],
            foreground=[("selected", th.TEXT_DARK)],
        )
        self.configure(style="EditableTable.Treeview")

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

    def load_from_file(self, file_path="output.txt"):
        self.delete(*self.get_children())
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f.readlines():
                clean = line.rstrip("\n")
                self.insert("", "end", values=(clean,))
        self._restripe()

    def edit_cell(self, event):
        item = self.identify_row(event.y)
        if not item:
            return

        col = self.identify_column(event.x)
        x, y, w, h = self.bbox(item, col)

        text = self.item(item, "values")
        text = text[0] if text else ""

        self.editor = tk.Entry(
            self,
            font=(th.FONT_FAMILY, self.font_size),
            bg="#ffffff",
            fg=th.TEXT_DARK,
            relief="solid",
            borderwidth=1,
            highlightthickness=1,
            highlightcolor=th.ACCENT,
            highlightbackground=th.ACCENT,
        )
        self.editor.place(x=x, y=y, width=w, height=h)
        self.editor.insert(0, text)
        self.editor.focus()

        def save_edit(event=None):
            new_text = self.editor.get()
            self.item(item, values=(new_text,))
            self.editor.destroy()
            self.editor = None

        self.editor.bind("<Return>", save_edit)
        self.editor.bind("<FocusOut>", save_edit)

    def insert_empty_below(self, event):
        item = self.focus()
        if not item:
            return
        idx = self.index(item)
        self.insert("", idx + 1, values=(""))
        self._restripe()

    def merge_with_previous(self, event):
        item = self.focus()
        if not item:
            return

        prev = self.prev(item)
        if not prev:
            return

        prev_val = self.item(prev, "values")
        cur_val = self.item(item, "values")

        prev_text = prev_val[0] if prev_val else ""
        cur_text = cur_val[0] if cur_val else ""

        merged = (prev_text + " " + cur_text).strip()

        self.item(prev, values=(merged,))
        self.delete(item)
        self._restripe()

    def delete_line(self, event):
        item = self.focus()
        if item:
            self.delete(item)
            self._restripe()

    def append_stars(self, event):
        item = self.focus()
        if not item:
            return

        val = self.item(item, "values")
        text = val[0] if val else ""

        self.item(item, values=(text + " **",))

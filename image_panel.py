import os
import tkinter as tk
from PIL import Image, ImageTk

class ImagePanel(tk.Frame):
    def __init__(self, parent, pages_folder="pages"):
        super().__init__(parent, bg="#1a1a1a")

        self.pages_folder = pages_folder

        self.canvas = tk.Canvas(self, bg="#1a1a1a", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.tk_photos = []
        self.to_load = []

    def load_images(self, image_list):
        self.canvas.delete("all")
        self.tk_photos[:] = []
        self.to_load = image_list[:]

        self.y_offset = 10
        self._load_next_image()

    def _load_next_image(self):
        if not self.to_load:
            return

        file = self.to_load.pop(0)
        path = os.path.join(self.pages_folder, file)

        if os.path.isfile(path):
            img = Image.open(path)
            w = 600
            h = int(img.height * w / img.width)
            img = img.resize((w, h))

            photo = ImageTk.PhotoImage(img)
            self.tk_photos.append(photo)

            self.canvas.create_image(10, self.y_offset, anchor="nw", image=photo)
            self.y_offset += h + 20

        self.after(5, self._load_next_image)

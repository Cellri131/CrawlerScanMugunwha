import tkinter as tk
from PIL import Image, ImageTk

class SplashScreen(tk.Tk):
    def __init__(self):
        super().__init__()

        self.overrideredirect(True)
        self.configure(bg="#1a1a1a")

        w, h = 500, 300
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        x, y = (sw - w) // 2, (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

        frame = tk.Frame(self, bg="#1a1a1a")
        frame.pack(expand=True, fill="both")

        try:
            img = Image.open("MugunwHaLogoTrad.png")
            img = img.resize((120, 120))
            self.photo = ImageTk.PhotoImage(img)

            tk.Label(frame, image=self.photo, bg="#1a1a1a").pack(pady=10)
        except:
            tk.Label(frame, text="MugunwHa Trad", fg="white", bg="#ffffff", font=("Calibri", 28)).pack(pady=20)

        tk.Label(frame, text="Chargement...", fg="white", bg="#ffffff", font=("Calibri", 22)).pack(pady=10)

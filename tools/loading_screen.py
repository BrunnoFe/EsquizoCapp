from itertools import cycle
import tkinter as tk
import os

class LoadingScreen:
    def __init__(self, width: int = 640, height: int = 360, transparent_color: str = '#70448f', tvelocity: int = 15) -> None:

        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.wm_attributes('-transparentcolor', transparent_color)

        self.user_screen_height: int = self.root.winfo_screenheight()
        self.user_screen_width: int = self.root.winfo_screenwidth()

        self.app_width: int = width
        self.app_heigth: int = height
        self.transition_velocity: int = tvelocity
        
        self.root.geometry(f"{self.app_width}x{self.app_heigth}+{(self.user_screen_width//2)-(self.app_width//2)}+{(self.user_screen_height//2)-(self.app_heigth//2)}")
        
        self.images_list: list = []
        
        self.label = tk.Label(master=self.root, background=transparent_color, width=self.app_width, height=self.app_heigth, anchor=tk.CENTER)
        self.label.pack(fill=tk.BOTH, anchor=tk.CENTER, expand=True)
            
    def create_img_cycle(self, folderpath: str| None = None) -> None:
        for caminho, _, arquivos in os.walk(folderpath):
            for arquivo in arquivos:
                self.images_list.append(rf'{caminho}\{arquivo}')
        self.images_list.sort(key=len)
        self.img_cycle = cycle(self.images_list)

    def change_img(self) -> None:
        self.img = tk.PhotoImage(file=next(self.img_cycle))
        self.label.configure(image=self.img)
        self.root.after(ms=self.transition_velocity, func=self.change_img)
    
    def execute(self, folderpath: str, duration: int = 5000) -> None:
        self.create_img_cycle(folderpath=folderpath)
        self.root.after(ms=10, func=self.change_img)
        self.root.after(ms=duration, func=self.root.destroy)
        self.root.mainloop()
        
if __name__ == '__main__':
    app = LoadingScreen()
    app.execute(folderpath=r'C:\Users\Alguém\Documents\0_EsquizoCap\images\gif')
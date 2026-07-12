from ctypes import windll
from tkinter.font import Font

import ttkbootstrap as ttk

# A partir do ttkbootstrap 1.20 o pacote raiz deixou de reexportar as constantes
# de ancoragem (não existe mais `ttk.N`) nem o módulo `font` do tkinter: as
# constantes vivem em `ttkbootstrap.constants` e a fonte vem do próprio tkinter.
from ttkbootstrap.constants import NE, NSEW, W


class CreateCustomGui:
    def __init__(self, iconpath: str, themename: str = 'solar', width: int = 1680, heigth: int = 100) -> None:       
        self.root = ttk.Window(themename=themename, overrideredirect=True, minsize=(1366,960)) # root (your app doesn't go in root, it goes in window)
        self.root.iconbitmap(bitmap=r'images\\esquizo_ico.ico')
        self.root.iconbitmap(default=r'images\\esquizo_ico.ico')
        
        self.user_screen_width: int = self.root.winfo_screenwidth()
        self.user_screen_height: int = self.root.winfo_screenheight()
        self.root.geometry(f"{width}x{heigth}+{(self.user_screen_width//2)-(width//2)}+{(self.user_screen_height//2)-(heigth//2)}")
        
        self.root.grid_columnconfigure(index=[0,1,2,3,4], weight=1)
        self.root.grid_rowconfigure(index=[1,2,3,4,5,6,7,8], weight=1)
        
        self.root.minimized = False # only to know if root is minimized
        self.root.maximized = False # only to know if root is maximized

        self.scale: float = 1.0
        
        self.title_bar = ttk.Frame(self.root, relief='flat')
        self.title_bar.grid(columnspan=5, row=0, sticky=NSEW)
        self.title_bar.grid_columnconfigure(0, weight=1)
        
        self.scale_frame = ttk.Frame(self.title_bar)
        self.scale_frame.grid(column=1, row=0, sticky=NSEW)
        
        self.main_window = ttk.Frame(self.root, relief='flat')
        
        self.close_button = ttk.Button(self.title_bar, text='  ×  ', command=self.root.destroy)
        self.expand_button = ttk.Button(self.title_bar, text=' 🗖 ', command=self.maximize_me)
        self.minimize_button = ttk.Button(self.title_bar, text=' 🗕 ', command=self.minimize_me)
        self.upscale_button = ttk.Button(self.scale_frame, text=' + ')
        self.downscale_button = ttk.Button(self.scale_frame, text=' - ')
        self.title_bar_title = ttk.Label(self.title_bar, text='EsquizoCap', compound='left')

        self.close_button.grid(column=5, row=0, sticky=NE)
        self.expand_button.grid(column=4, row=0, sticky=NE)
        self.minimize_button.grid(column=3, row=0, sticky=NE)
        self.upscale_button.grid(column=1, row=0, sticky=NE)
        self.downscale_button.grid(column=0, row=0, sticky=NE)
        self.title_bar_title.grid(row=0, sticky=W, padx=10)
        
        self.main_window.grid(columnspan=5, rowspan=9, sticky=NSEW)
        self.main_window.grid_columnconfigure(index=[0,1,2,3,4], weight=1)
        self.main_window.grid_rowconfigure(index=[0,1,2,3,4,5,6,7,8], weight=1)
        
        self.font = Font(family = "Calibri", size = 12, weight='normal', slant='roman')
        self.main_window.option_add("*TCombobox*Listbox.font", self.font)
        self.main_window.option_add("*TCombobox.font", self.font)

        self.title_bar.bind('<Button-1>', self.get_pos) # so you can drag the window from the title bar
        self.title_bar_title.bind('<Button-1>', self.get_pos) # so you can drag the window from the title

    def set_appwindow(self) -> None: # to display the window icon on the taskbar
        GWL_EXSTYLE = -20
        WS_EX_APPWINDOW = 0x00040000
        WS_EX_TOOLWINDOW = 0x00000080
        hwnd = windll.user32.GetParent(self.root.winfo_id())
        stylew = windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        stylew = stylew & ~WS_EX_TOOLWINDOW
        stylew = stylew | WS_EX_APPWINDOW
        res = windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, stylew)
        self.root.wm_withdraw()
        self.root.after(10, lambda: self.root.wm_deiconify())
        
    def minimize_me(self) -> None:
        self.root.attributes("-alpha", 0)  # so you can't see the window when is minimized
        self.root.minimized = True       

    def deminimize(self, event):
        self.root.focus() 
        self.root.attributes("-alpha", 1) # so you can see the window when is not minimized
        if self.root.minimized == True:
            self.root.minimized = False                              
            
    def maximize_me(self) -> None:
        if self.root.maximized == False: # if the window was not maximized
            self.root.normal_size = self.root.geometry()
            self.expand_button.config(text=" 🗗 ")
            self.root.geometry(f"{self.root.winfo_screenwidth()}x{self.root.winfo_screenheight()}+0+0")
            self.root.maximized = not self.root.maximized # now it's maximized

        else: # if the window was maximized
            self.expand_button.config(text=" 🗖 ")
            self.root.geometry(self.root.normal_size)
            self.root.maximized = not self.root.maximized # now it is not maximized
            
    def get_pos(self, event) -> None: # this is executed when the title bar is clicked to move the window
        if self.root.maximized == False:
            self.xwin: int = self.root.winfo_x()
            self.ywin: int = self.root.winfo_y()
            self.startx: int = event.x_root
            self.starty: int = event.y_root
            self.ywin = self.ywin - self.starty
            self.xwin = self.xwin - self.startx

            def move_window(event) -> None: # runs when window is dragged
                self.root.geometry(f'+{event.x_root + self.xwin}+{event.y_root + self.ywin}')
                
            self.title_bar.bind('<B1-Motion>', move_window)
            self.title_bar_title.bind('<B1-Motion>', move_window)
        else:
            self.expand_button.config(text=" 🗖 ")
            self.root.maximized = not self.root.maximized
"""入口：只做一件事——启动主窗口"""
import tkinter as tk
from gui import App


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()

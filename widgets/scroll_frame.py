"""竖向可滚动容器：页面整体放进 inner，内容超高时出滚动条

滚轮不在本控件内绑定——gui.py 在 App 级统一 bind_all("<MouseWheel>")，
按指针位置向上找最近的 Canvas 滚动，避免多个页面互相抢 bind_all。
"""
import tkinter as tk
from tkinter import ttk


class ScrollFrame(ttk.Frame):

    def __init__(self, parent, **kw):
        super().__init__(parent, **kw)
        self.canvas = tk.Canvas(self, highlightthickness=0)
        sb = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas)
        self.inner.bind("<Configure>",
                        lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=sb.set)
        # 内容宽度跟随画布（fill=X 的行铺满可用宽），内容本身更宽时保持自然宽
        self.canvas.bind("<Configure>", self._sync_width)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

    def _sync_width(self, event):
        self.canvas.itemconfigure(self._win, width=max(event.width, self.inner.winfo_reqwidth()))

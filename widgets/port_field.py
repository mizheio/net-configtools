"""端口选择控件：类型下拉 + 编号输入，输出完整接口名"""
import tkinter as tk
from tkinter import ttk

from modules.base import PORT_TYPES, port_name


class PortField(ttk.Frame):
    """GE/ETH 下拉 + 编号输入框的组合控件。

    get() 返回拼好的完整接口名（如 GigabitEthernet1/0/1），编号为空时返回空串。
    将来扩展 XGE 等类型只需在 modules.base.PORT_TYPE_MAP 加条目，所有用到本控件
    的页面自动带出，生成函数零改动。
    """

    def __init__(self, parent, type_width=5, num_width=9, **kw):
        super().__init__(parent, **kw)
        self._types = PORT_TYPES
        self.type_var = tk.StringVar(value=self._types[0])
        self.num_var = tk.StringVar()
        self.type_box = ttk.Combobox(self, textvariable=self.type_var, values=self._types,
                                     width=type_width, state="readonly")
        self.type_box.pack(side=tk.LEFT, padx=(0, 2))
        ttk.Entry(self, textvariable=self.num_var, width=num_width).pack(side=tk.LEFT)

    def set(self, type_token, num):
        if type_token in self._types:
            self.type_var.set(type_token)
        self.num_var.set(str(num))

    def get(self):
        num = self.num_var.get().strip()
        return port_name(self.type_var.get(), num) if num else ""

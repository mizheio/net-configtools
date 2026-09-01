"""轻量的"添加一行 / 删除一行"表单，供 VRRP、MSTP、OSPF、ACL、链路聚合共用。

列类型 kind：
  None      普通输入框
  "ip"      IP 库可编辑下拉
  "vlan"    VLAN 库可编辑下拉
  (a, b)    固定选项只读下拉
  "port"    端口选择（PortField），values() 返回完整接口名
"""
import tkinter as tk
from tkinter import ttk

from .port_field import PortField


class RowsEditor:

    def __init__(self, parent, columns):
        self.columns = columns  # (字段名, 标题, 宽度, 类型/可选值)
        self.rows = []
        self.next_grid_row = 1
        self.ip_values, self.vlan_values = [], []
        self.area = ttk.Frame(parent)
        self.area.pack(fill=tk.X, pady=(2, 4))
        # 表头与输入控件共用同一个 grid，避免 Label 和 Combobox 宽度不同造成列错位。
        for col, (_, label, _, _) in enumerate(columns):
            ttk.Label(self.area, text=label, anchor=tk.W).grid(row=0, column=col, padx=2, sticky="ew")
        ttk.Label(self.area, text="").grid(row=0, column=len(columns), padx=2)

    def add(self, defaults=None):
        defaults = defaults or {}
        grid_row = self.next_grid_row
        self.next_grid_row += 1
        row = {"widgets": {}}
        for col, (key, _, width, kind) in enumerate(self.columns):
            if kind == "port":
                widget = PortField(self.area, num_width=width)
                value = defaults.get(key)
                if isinstance(value, tuple):
                    widget.set(*value)
                elif value:
                    widget.set("GE", value)
            else:
                var = tk.StringVar(value=defaults.get(key, ""))
                row[key] = var
                if kind == "ip":
                    widget = ttk.Combobox(self.area, textvariable=var, values=self.ip_values, width=width)
                elif kind == "vlan":
                    widget = ttk.Combobox(self.area, textvariable=var, values=self.vlan_values, width=width)
                elif isinstance(kind, tuple):
                    widget = ttk.Combobox(self.area, textvariable=var, values=kind, width=width, state="readonly")
                else:
                    widget = ttk.Entry(self.area, textvariable=var, width=width)
            widget.grid(row=grid_row, column=col, padx=2, pady=1, sticky="ew")
            row["widgets"][key] = widget
            if kind == "port":
                row[key] = widget
        delete_button = ttk.Button(self.area, text="删", width=3, command=lambda: self.delete(row))
        delete_button.grid(row=grid_row, column=len(self.columns), padx=2, pady=1)
        row["delete_button"] = delete_button
        self.rows.append(row)

    def delete(self, row):
        for widget in row["widgets"].values():
            widget.destroy()
        row["delete_button"].destroy()
        self.rows.remove(row)

    def values(self):
        rows = []
        for row in self.rows:
            item = {}
            for key, _, _, kind in self.columns:
                if kind == "port":
                    item[key] = row[key].get()
                else:
                    item[key] = row[key].get().strip()
            rows.append(item)
        return rows

    def set_lib_values(self, ip_list, vlan_list):
        self.ip_values, self.vlan_values = list(ip_list), list(vlan_list)
        for row in self.rows:
            for key, _, _, kind in self.columns:
                if kind == "ip":
                    row["widgets"][key]["values"] = self.ip_values
                elif kind == "vlan":
                    row["widgets"][key]["values"] = self.vlan_values

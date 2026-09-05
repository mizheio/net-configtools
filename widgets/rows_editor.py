"""轻量的"添加一行 / 删除一行"表单，供 VRRP、MSTP、OSPF、ACL、链路聚合共用。

列类型 kind：
  None      普通输入框
  "ip"      IP 库可编辑下拉
  "vlan"    VLAN 库可编辑下拉
  (a, b)    固定选项只读下拉
  "port"    端口选择（PortField），values() 返回完整接口名
  "check"   勾选框，values() 返回 True/False

groups=[(组标题, 跨列数), ...] 可在列头上方渲染分组标题行（如 本端设备/对端设备），
跨列数之和须等于列数；不传则与原版布局一致。
"""
import tkinter as tk
from tkinter import ttk

from .port_field import PortField


class RowsEditor:

    def __init__(self, parent, columns, groups=None):
        self.columns = columns  # (字段名, 标题, 宽度, 类型/可选值)
        self.groups = groups    # [(组标题, 跨列数), ...]，跨列数之和须等于列数；None = 不分组
        self.rows = []
        # 分组时第 0 行放组标题、第 1 行放列头，数据行从第 2 行起
        self.next_grid_row = 2 if groups else 1
        self.ip_values, self.vlan_values = [], []
        self.area = ttk.Frame(parent)
        self.area.pack(fill=tk.X, pady=(2, 4))
        # 表头与输入控件共用同一个 grid，避免 Label 和 Combobox 宽度不同造成列错位。
        header_row = 0
        if groups:
            col = 0
            for title, span in groups:
                ttk.Label(self.area, text=f"── {title} ──", anchor=tk.CENTER)\
                    .grid(row=0, column=col, columnspan=span, padx=2, sticky="ew")
                col += span
            header_row = 1
        for col, (_, label, _, _) in enumerate(columns):
            ttk.Label(self.area, text=label, anchor=tk.W).grid(row=header_row, column=col, padx=2, sticky="ew")
        ttk.Label(self.area, text="").grid(row=header_row, column=len(columns), padx=2)

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
            elif kind == "check":
                var = tk.BooleanVar(value=bool(defaults.get(key, False)))
                row[key] = var
                widget = ttk.Checkbutton(self.area, variable=var)
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
                elif kind == "check":
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

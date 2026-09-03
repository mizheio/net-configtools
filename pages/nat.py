"""路由器 NAT 页面（Easy IP / nat outbound）

页面契约见 gui.py 顶部注释。ACL 匹配允许上网的私网网段，出接口引用之，
可选配指向运营商的默认静态路由。
"""
import ipaddress
import tkinter as tk
from tkinter import ttk

from modules import nat
from widgets import PortField, RowsEditor


class NatPage:
    TITLE = "NAT"

    def __init__(self, parent, app=None):
        self.frame = ttk.Frame(parent, padding=6)
        self.enabled = tk.BooleanVar(value=True)
        bar = ttk.Frame(self.frame)
        bar.pack(fill=tk.X)
        ttk.Button(bar, text="添加网段", command=self.add_row).pack(side=tk.LEFT, padx=2)
        ttk.Checkbutton(bar, text="参与汇总", variable=self.enabled).pack(side=tk.RIGHT)

        f = ttk.Frame(self.frame)
        f.pack(fill=tk.X, pady=1)
        ttk.Label(f, text="ACL 编号", width=12).pack(side=tk.LEFT)
        self.acl_number = tk.StringVar(value="2000")
        ttk.Entry(f, textvariable=self.acl_number, width=10).pack(side=tk.LEFT)
        self.out_port = self._port_field("出接口（公网口）", "GE", "0/0/0")
        self.next_hop = self._field("默认路由下一跳（可空）", "")

        self.editor = RowsEditor(self.frame, [
            ("source", "源地址", 18, "ip"), ("wildcard", "反掩码", 18, None),
        ])
        self.add_row()

    def _field(self, label, default):
        f = ttk.Frame(self.frame)
        f.pack(fill=tk.X, pady=1)
        ttk.Label(f, text=label, width=22).pack(side=tk.LEFT)
        var = tk.StringVar(value=default)
        ttk.Entry(f, textvariable=var, width=20).pack(side=tk.LEFT)
        return var

    def _port_field(self, label, port_type, num):
        f = ttk.Frame(self.frame)
        f.pack(fill=tk.X, pady=1)
        ttk.Label(f, text=label, width=22).pack(side=tk.LEFT)
        field = PortField(f)
        field.set(port_type, num)
        field.pack(side=tk.LEFT)
        return field

    def add_row(self):
        self.editor.add({"wildcard": "0.0.0.255"})

    def set_lib_values(self, ip_list, vlan_list):
        self.editor.set_lib_values(ip_list, vlan_list)

    def collect(self):
        return {"acl_number": self.acl_number.get().strip(),
                "out_interface": self.out_port.get(),
                "next_hop": self.next_hop.get().strip(),
                "rules": self.editor.values()}, []

    def validate(self, params):
        errors = []
        if not params["out_interface"]:
            errors.append("NAT: 请填写出接口编号")
        if not params["acl_number"].isdigit():
            errors.append("NAT: ACL 编号必须是数字")
        if params["next_hop"]:
            try:
                ipaddress.ip_address(params["next_hop"])
            except ValueError:
                errors.append(f"NAT: 下一跳 {params['next_hop']} 不是合法IP")
        rules = [row for row in params["rules"] if row.get("source")]
        if not rules:
            errors.append("NAT: 至少填写一行允许转换的源网段")
        for row in rules:
            try:
                ipaddress.ip_address(row["source"])
            except ValueError:
                errors.append(f"NAT: 源地址 {row['source'] or '(空)'} 不是合法IP")
            try:
                ipaddress.ip_address(row.get("wildcard", ""))
            except ValueError:
                errors.append(f"NAT: 反掩码 {row.get('wildcard') or '(空)'} 不是合法掩码")
        return errors

    def render(self, params):
        return nat.generate(params)

    def render_summary(self, params):
        return nat.generate(params)

    def summary_vlans(self, params):
        return set()

    def is_empty(self, params):
        return not any(row.get("source") for row in params["rules"])

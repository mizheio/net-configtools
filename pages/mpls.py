"""路由器 MPLS 页面（文档 4.6 基础配置）

单台设备视角：LSR-ID（一般取回环口地址）+ 接口列表逐一启用 mpls/mpls ldp；
可勾选生成 LoopBack0（IP 取 LSR-ID，掩码 32 位）与 route recursive-lookup
tunnel（PE 设备解决 BGP 路由黑洞，默认不勾）。接口 IP 与 OSPF 分别由
"接口IP配置 / OSPF"页生成，本页不重复，汇总时可拼接成完整脚本。
"""
import ipaddress
import tkinter as tk
from tkinter import ttk

from modules import mpls
from widgets import RowsEditor


class MplsPage:
    TITLE = "MPLS"

    def __init__(self, parent, app=None):
        self.frame = ttk.Frame(parent, padding=6)
        self.enabled = tk.BooleanVar(value=True)
        self.gen_loopback = tk.BooleanVar(value=True)
        self.recursive_tunnel = tk.BooleanVar(value=False)
        self._ip_combos = []
        self._ip_values = []

        bar = ttk.Frame(self.frame)
        bar.pack(fill=tk.X)
        ttk.Button(bar, text="添加接口", command=lambda: self.editor.add()).pack(side=tk.LEFT, padx=2)
        ttk.Checkbutton(bar, text="生成 LoopBack0（IP=LSR-ID，掩码 32）",
                        variable=self.gen_loopback).pack(side=tk.LEFT, padx=8)
        ttk.Checkbutton(bar, text="route recursive-lookup tunnel（PE设备）",
                        variable=self.recursive_tunnel).pack(side=tk.LEFT, padx=8)
        ttk.Checkbutton(bar, text="参与汇总", variable=self.enabled).pack(side=tk.RIGHT)

        f = ttk.Frame(self.frame)
        f.pack(fill=tk.X, pady=1)
        ttk.Label(f, text="LSR-ID（回环口地址）", width=18).pack(side=tk.LEFT)
        self.lsr_id = tk.StringVar()
        cb = ttk.Combobox(f, textvariable=self.lsr_id, values=self._ip_values, width=18)
        cb.pack(side=tk.LEFT)
        self._ip_combos.append(cb)

        self.editor = RowsEditor(self.frame, [("port", "使能 MPLS 的接口", 14, "port")])
        self.editor.add()

    def set_lib_values(self, ip_list, vlan_list):
        self._ip_values = list(ip_list)
        for cb in self._ip_combos:
            cb["values"] = self._ip_values

    def collect(self):
        return {"lsr_id": self.lsr_id.get().strip(),
                "interfaces": self.editor.values(),
                "gen_loopback": self.gen_loopback.get(),
                "recursive_tunnel": self.recursive_tunnel.get()}, []

    def validate(self, params):
        errors = []
        if not params["lsr_id"]:
            errors.append("MPLS: 请填写 LSR-ID")
        else:
            try:
                ipaddress.ip_address(params["lsr_id"])
            except ValueError:
                errors.append(f"MPLS: LSR-ID {params['lsr_id']} 不是合法IP")
        return errors

    def render(self, params):
        return mpls.generate(params)

    def render_summary(self, params):
        return mpls.generate(params)

    def summary_vlans(self, params):
        return set()

    def is_empty(self, params):
        return not (params["lsr_id"] or any(row.get("port") for row in params["interfaces"]))

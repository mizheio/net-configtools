"""路由器 GRE 页面

页面契约见 gui.py 顶部注释。GRE 两端成对配置：默认只生成本端，勾选
"生成对端脚本"后展开对端区（对端 Tunnel IP + 对端内网网段列表），
一次输出两台设备的脚本，source/destination 自动互换。
"""
import ipaddress
import tkinter as tk
from tkinter import ttk

from modules import gre
from widgets import RowsEditor


class GrePage:
    TITLE = "GRE"

    def __init__(self, parent, app=None):
        self.frame = ttk.Frame(parent, padding=6)
        self.enabled = tk.BooleanVar(value=True)
        self.gen_peer = tk.BooleanVar(value=False)
        self._ip_combos = []
        self._ip_values = []
        self._rows = {}

        bar = ttk.Frame(self.frame)
        bar.pack(fill=tk.X)
        ttk.Button(bar, text="添加路由", command=self.add_row).pack(side=tk.LEFT, padx=2)
        ttk.Checkbutton(bar, text="生成对端脚本", variable=self.gen_peer).pack(side=tk.LEFT, padx=8)
        ttk.Checkbutton(bar, text="参与汇总", variable=self.enabled).pack(side=tk.RIGHT)

        # 字段行：创建时只建不排，_sync_fields 按固定顺序重排显示
        self.v_tunnel = self._field("tunnel", "Tunnel口编号", "0/0/1")
        self.v_ip = self._field("ip", "本端 Tunnel IP", kind="ip")
        self.v_mask = self._field("mask", "掩码", "255.255.255.252")
        self.v_src = self._field("src", "本端公网地址", kind="ip")
        self.v_dst = self._field("dst", "对端公网地址", kind="ip")
        self.editor = RowsEditor(self.frame, [
            ("network", "本端目的网段", 20, "ip"), ("mask", "掩码", 16, None),
        ])

        self.peer_head = ttk.Frame(self.frame)
        ttk.Label(self.peer_head, text="—— 对端设备 ——", foreground="gray").pack(side=tk.LEFT)
        ttk.Button(self.peer_head, text="添加对端路由",
                   command=lambda: self.peer_editor.add({"mask": "255.255.255.0"})).pack(side=tk.LEFT, padx=8)
        self.v_peer_ip = self._field("peer_ip", "对端 Tunnel IP", kind="ip")
        self.peer_editor = RowsEditor(self.frame, [
            ("network", "对端目的网段", 20, "ip"), ("mask", "掩码", 16, None),
        ])
        self.add_row()
        self.gen_peer.trace_add("write", lambda *_: self._sync_fields())
        self._sync_fields()

    def _field(self, key, label, default="", kind=None):
        var = tk.StringVar(value=default)
        f = ttk.Frame(self.frame)
        ttk.Label(f, text=label, width=14).pack(side=tk.LEFT)
        if kind == "ip":
            cb = ttk.Combobox(f, textvariable=var, values=self._ip_values, width=18)
            cb.pack(side=tk.LEFT)
            self._ip_combos.append(cb)
        else:
            ttk.Entry(f, textvariable=var, width=18).pack(side=tk.LEFT)
        self._rows[key] = f
        return var

    def _sync_fields(self):
        """勾选"生成对端脚本"时展开对端区；先收起再按固定顺序重排，行序稳定"""
        for f in self._rows.values():
            f.pack_forget()
        self.editor.area.pack_forget()
        self.peer_head.pack_forget()
        self.peer_editor.area.pack_forget()
        for key in ("tunnel", "ip", "mask", "src", "dst"):
            self._rows[key].pack(fill=tk.X, pady=1)
        self.editor.area.pack(fill=tk.X, pady=(2, 4))
        if self.gen_peer.get():
            if not self.peer_editor.rows:
                self.peer_editor.add({"mask": "255.255.255.0"})
            self.peer_head.pack(fill=tk.X, pady=(6, 1))
            self._rows["peer_ip"].pack(fill=tk.X, pady=1)
            self.peer_editor.area.pack(fill=tk.X, pady=(2, 4))

    def add_row(self):
        self.editor.add({"mask": "255.255.255.0"})

    def set_lib_values(self, ip_list, vlan_list):
        self._ip_values = list(ip_list)
        for cb in self._ip_combos:
            cb["values"] = self._ip_values
        self.editor.set_lib_values(ip_list, vlan_list)
        self.peer_editor.set_lib_values(ip_list, vlan_list)

    def collect(self):
        return {"tunnel_num": self.v_tunnel.get().strip(),
                "local_tunnel_ip": self.v_ip.get().strip(),
                "local_mask": self.v_mask.get().strip(),
                "local_source": self.v_src.get().strip(),
                "local_destination": self.v_dst.get().strip(),
                "routes": self.editor.values(),
                "gen_peer": self.gen_peer.get(),
                "peer_tunnel_ip": self.v_peer_ip.get().strip(),
                "peer_routes": self.peer_editor.values()}, []

    @staticmethod
    def _check_route(errors, row, side):
        try:
            ipaddress.ip_address(row["network"])
        except ValueError:
            errors.append(f"GRE: {side}路由网段 {row['network'] or '(空)'} 不是合法IP")
        try:
            ipaddress.ip_address(gre.normalize_mask(row.get("mask", "")))
        except ValueError:
            errors.append(f"GRE: {side}路由掩码 {row.get('mask') or '(空)'} 不是合法掩码")

    def validate(self, params):
        errors = []

        def ip_chk(value, name):
            if not value:
                errors.append(f"GRE: 缺少{name}")
                return
            try:
                ipaddress.ip_address(value)
            except ValueError:
                errors.append(f"GRE: {name} {value} 不是合法IP")

        if not params["tunnel_num"]:
            errors.append("GRE: 请填写Tunnel口编号")
        mask = params["local_mask"].strip()
        try:
            ipaddress.ip_address(gre.normalize_mask(mask))
        except ValueError:
            errors.append(f"GRE: 掩码 {mask or '(空)'} 不是合法掩码")
        ip_chk(params["local_tunnel_ip"], "本端Tunnel IP")
        ip_chk(params["local_source"], "本端公网地址")
        ip_chk(params["local_destination"], "对端公网地址")
        for row in params["routes"]:
            if row.get("network"):
                self._check_route(errors, row, "本端")
        if params["gen_peer"]:
            ip_chk(params["peer_tunnel_ip"], "对端Tunnel IP")
            for row in params["peer_routes"]:
                if row.get("network"):
                    self._check_route(errors, row, "对端")
        return errors

    def render(self, params):
        return gre.generate(params)

    def render_summary(self, params):
        # 汇总只取本端，对端脚本属于另一台设备
        return gre.generate_local(params)

    def summary_vlans(self, params):
        return set()

    def is_empty(self, params):
        return not any([params["local_tunnel_ip"], params["local_source"],
                        params["local_destination"],
                        *(row.get("network") for row in params["routes"])])

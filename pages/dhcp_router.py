"""路由器DHCP页面

页面契约见 gui.py 顶部注释。路由器DHCP使用物理接口。
"""
import ipaddress
import tkinter as tk
from tkinter import ttk

from modules import dhcp_router
from widgets import PortField, RowsEditor


class DhcpRouterPage:
    TITLE = "DHCP"

    def __init__(self, parent, app=None):
        self.frame = ttk.Frame(parent, padding=6)
        self.enabled = tk.BooleanVar(value=True)
        self._ip_combos = []
        self._vlan_combos = []
        self._ip_values = []
        self._vlan_values = []

        bar = ttk.Frame(self.frame)
        bar.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(bar, text="模式").pack(side=tk.LEFT)
        self.mode = tk.StringVar(value="global")
        ttk.Combobox(bar, textvariable=self.mode, width=10, state="readonly",
                     values=("global", "relay")).pack(side=tk.LEFT, padx=(2, 10))
        ttk.Checkbutton(bar, text="参与汇总", variable=self.enabled).pack(side=tk.RIGHT)

        # 字段行：创建时记录 row frame，_sync_fields 按固定顺序重排显示
        self._rows = {}
        self.port_field = self._port_row("if_port", "物理接口")
        self.v_gw = self._field("gw", "网关IP")
        self.v_net = self._field("net", "网段")
        self.v_mask = self._field("mask", "掩码", default="255.255.255.0", kind=None)
        self.v_dns = self._field("dns", "DNS")
        self.v_lease = self._field("lease", "租期(天)", default="7", kind=None)
        self.v_relay = self._field("relay", "中继服务器IP")

        self.mode.trace_add("write", lambda *_: self._sync_fields())
        self._sync_fields()

    def _field(self, key, label, default="", kind="ip"):
        var = tk.StringVar(value=default)
        f = ttk.Frame(self.frame)
        f.pack(fill=tk.X, pady=1)
        ttk.Label(f, text=label, width=12).pack(side=tk.LEFT)
        if kind is None:
            ttk.Entry(f, textvariable=var, width=18).pack(side=tk.LEFT)
        else:
            values = self._ip_values if kind == "ip" else self._vlan_values
            cb = ttk.Combobox(f, textvariable=var, values=values, width=18)
            cb.pack(side=tk.LEFT)
            (self._ip_combos if kind == "ip" else self._vlan_combos).append(cb)
        self._rows[key] = f
        return var

    def _port_row(self, key, label):
        f = ttk.Frame(self.frame)
        f.pack(fill=tk.X, pady=1)
        ttk.Label(f, text=label, width=12).pack(side=tk.LEFT)
        field = PortField(f)
        field.set("GE", "0/0/1")
        field.pack(side=tk.LEFT)
        self._rows[key] = f
        return field

    def _sync_fields(self):
        """按模式决定显示哪些行；先收起再按固定顺序重排，行序稳定"""
        for row in self._rows.values():
            row.pack_forget()
        if self.mode.get() == "relay":
            keys = ["if_port", "relay"]
        else:
            keys = ["if_port", "gw", "net", "mask", "dns", "lease"]
        for key in keys:
            self._rows[key].pack(fill=tk.X, pady=1)

    def set_lib_values(self, ip_list, vlan_list):
        self._ip_values, self._vlan_values = list(ip_list), list(vlan_list)
        for cb in self._ip_combos:
            cb["values"] = self._ip_values
        for cb in self._vlan_combos:
            cb["values"] = self._vlan_values

    def collect(self):
        return {"mode": self.mode.get(),
                "if_kind": "port",
                "if_vlan": "",
                "if_port": self.port_field.get(),
                "gateway": self.v_gw.get().strip(),
                "network": self.v_net.get().strip(),
                "mask": self.v_mask.get().strip(),
                "dns": self.v_dns.get().strip(),
                "lease": self.v_lease.get().strip() or "7",
                "relay_ip": self.v_relay.get().strip()}, []

    def validate(self, params):
        errors = []

        def ip_chk(value, name):
            if not value:
                errors.append(f"DHCP: 缺少{name}")
                return
            try:
                ipaddress.ip_address(value)
            except ValueError:
                errors.append(f"DHCP: {name} {value} 不是合法IP")

        if not params.get("if_port"):
            errors.append("DHCP: 请填写物理接口编号")
            
        if params["mode"] == "relay":
            ip_chk(params["relay_ip"], "中继服务器IP")
        else:
            ip_chk(params["gateway"], "网关IP")
            ip_chk(params["network"], "网段")
            ip_chk(params["dns"], "DNS")
            if not params["lease"].isdigit():
                errors.append("DHCP: 租期必须是数字")
        return errors

    def render(self, params):
        return dhcp_router.generate(params)

    def render_summary(self, params):
        return dhcp_router.generate(params)

    def summary_vlans(self, params):
        # 路由器不涉及VLAN，返回空集合
        return set()
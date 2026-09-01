"""双栖页面：DHCP / OSPF / ACL（交换机与路由器通用）

页面契约见 gui.py 顶部注释。与交换机专有页的差异：配置绑定的接口既可能是
Vlanif（交换机）也可能是物理接口（路由器），页面内自行处理。
"""
import ipaddress
import tkinter as tk
from tkinter import ttk

from modules import dhcp, ospf, acl
from widgets import PortField, RowsEditor


# ============================================================ DHCP 页（仅全局地址池）
class DhcpPage:
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
        ttk.Label(bar, text="DHCP 全局地址池").pack(side=tk.LEFT)
        ttk.Checkbutton(bar, text="参与汇总", variable=self.enabled).pack(side=tk.RIGHT)

        self.v_if = self._field("VLAN ID", kind="vlan")
        self.v_gw = self._field("网关IP")
        self.v_net = self._field("网段")
        self.v_mask = self._field("掩码", default="255.255.255.0", kind=None)
        self.v_dns = self._field("DNS")
        self.v_lease = self._field("租期(天)", default="7", kind=None)

    def _field(self, label, default="", kind="ip"):
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
        return var

    def set_lib_values(self, ip_list, vlan_list):
        self._ip_values, self._vlan_values = list(ip_list), list(vlan_list)
        for cb in self._ip_combos:
            cb["values"] = self._ip_values
        for cb in self._vlan_combos:
            cb["values"] = self._vlan_values

    def collect(self):
        return {"if_vlan": self.v_if.get().strip(),
                "gateway": self.v_gw.get().strip(),
                "network": self.v_net.get().strip(),
                "mask": self.v_mask.get().strip(),
                "dns": self.v_dns.get().strip(),
                "lease": self.v_lease.get().strip() or "7"}, []

    def is_empty(self, params):
        keys = [k for k in params if k != "lease"]
        return all(not str(params[k]) for k in keys)

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

        if not params.get("if_vlan", "").isdigit():
            errors.append("DHCP: VLAN ID 必须是数字")
        ip_chk(params["gateway"], "网关IP")
        ip_chk(params["network"], "网段")
        ip_chk(params["dns"], "DNS")
        if not params["lease"].isdigit():
            errors.append("DHCP: 租期必须是数字")
        return errors

    def render(self, params):
        return dhcp.generate(params)

    def render_summary(self, params):
        return dhcp.generate(params)

    def summary_vlans(self, params):
        if params.get("if_vlan", "").isdigit():
            return {int(params["if_vlan"])}
        return set()


# ============================================================ OSPF 页
class OspfPage:
    TITLE = "OSPF"

    def __init__(self, parent, app=None):
        self.frame = ttk.Frame(parent, padding=6)
        self.enabled = tk.BooleanVar(value=True)
        bar = ttk.Frame(self.frame)
        bar.pack(fill=tk.X)
        ttk.Button(bar, text="添加 network", command=self.add_row).pack(side=tk.LEFT, padx=2)
        ttk.Checkbutton(bar, text="参与汇总", variable=self.enabled).pack(side=tk.RIGHT)
        self.process_id = self._field("进程号", "1")
        self.router_id = self._field("Router-ID", "10.1.1.1")
        self.area = self._field("Area", "0.0.0.0")
        self.editor = RowsEditor(self.frame, [
            ("network", "网络地址", 20, "ip"), ("wildcard", "反掩码", 18, None),
        ])
        self.add_row()

    def _field(self, label, default):
        f = ttk.Frame(self.frame)
        f.pack(fill=tk.X, pady=1)
        ttk.Label(f, text=label, width=12).pack(side=tk.LEFT)
        var = tk.StringVar(value=default)
        ttk.Entry(f, textvariable=var, width=20).pack(side=tk.LEFT)
        return var

    def add_row(self):
        self.editor.add({"wildcard": "0.0.0.255"})

    def set_lib_values(self, ip_list, vlan_list):
        self.editor.set_lib_values(ip_list, vlan_list)

    def collect(self):
        return {"process_id": self.process_id.get().strip(), "router_id": self.router_id.get().strip(),
                "area": self.area.get().strip(), "networks": self.editor.values()}, []

    def validate(self, params):
        return []

    def render(self, params):
        return ospf.generate(params)

    def render_summary(self, params):
        return ospf.generate(params)

    def summary_vlans(self, params):
        return set()


# ============================================================ ACL 页
class AclPage:
    TITLE = "ACL"

    def __init__(self, parent, app=None):
        self.frame = ttk.Frame(parent, padding=6)
        self.enabled = tk.BooleanVar(value=True)
        bar = ttk.Frame(self.frame)
        bar.pack(fill=tk.X)
        ttk.Button(bar, text="添加规则", command=self.add_row).pack(side=tk.LEFT, padx=2)
        ttk.Checkbutton(bar, text="参与汇总", variable=self.enabled).pack(side=tk.RIGHT)
        f = ttk.Frame(self.frame)
        f.pack(fill=tk.X, pady=1)
        ttk.Label(f, text="ACL 类型", width=12).pack(side=tk.LEFT)
        self.acl_type = tk.StringVar(value="advanced")
        ttk.Combobox(f, textvariable=self.acl_type, values=("basic", "advanced"), width=12, state="readonly").pack(side=tk.LEFT)
        ttk.Label(f, text="ACL 编号").pack(side=tk.LEFT, padx=(12, 2))
        self.acl_number = tk.StringVar(value="3000")
        ttk.Entry(f, textvariable=self.acl_number, width=10).pack(side=tk.LEFT)
        self.bind_port = self._port_field("绑定接口（可空）", "GE", "0/0/1")
        self.direction = self._field("过滤方向", "inbound")
        ttk.Label(self.frame, text="普通 ACL 忽略目的地址列；高级 ACL 使用来源与目的地址。", foreground="gray").pack(anchor=tk.W)
        self.editor = RowsEditor(self.frame, [
            ("action", "动作", 8, ("permit", "deny")), ("source", "源地址", 16, "ip"),
            ("source_wildcard", "源反掩码", 16, None), ("destination", "目的地址", 16, "ip"),
            ("destination_wildcard", "目的反掩码", 16, None),
        ])
        self.add_row()
        self.acl_type.trace_add("write", lambda *_: self._update_type())
        self._update_type()

    def _field(self, label, default):
        f = ttk.Frame(self.frame)
        f.pack(fill=tk.X, pady=1)
        ttk.Label(f, text=label, width=18).pack(side=tk.LEFT)
        var = tk.StringVar(value=default)
        ttk.Entry(f, textvariable=var, width=28).pack(side=tk.LEFT)
        return var

    def _port_field(self, label, port_type, num):
        f = ttk.Frame(self.frame)
        f.pack(fill=tk.X, pady=1)
        ttk.Label(f, text=label, width=18).pack(side=tk.LEFT)
        field = PortField(f)
        field.set(port_type, num)
        field.pack(side=tk.LEFT)
        return field

    def add_row(self):
        self.editor.add({"action": "permit", "source_wildcard": "0.0.0.255", "destination_wildcard": "0.0.0.255"})
        self._update_type()

    def _update_type(self):
        """基础 ACL 不需要目的地址；选择高级 ACL 后开放相关字段。"""
        advanced = self.acl_type.get() == "advanced"
        for row in self.editor.rows:
            for key in ("destination", "destination_wildcard"):
                row["widgets"][key].configure(state=tk.NORMAL if advanced else tk.DISABLED)

    def set_lib_values(self, ip_list, vlan_list):
        self.editor.set_lib_values(ip_list, vlan_list)

    def collect(self):
        return {"acl_type": self.acl_type.get().strip(), "acl_number": self.acl_number.get().strip(),
                "bind_interface": self.bind_port.get(), "direction": self.direction.get().strip(),
                "rules": self.editor.values()}, []

    def validate(self, params):
        return []

    def render(self, params):
        return acl.generate(params)

    def render_summary(self, params):
        return acl.generate(params)

    def summary_vlans(self, params):
        return set()

"""双栖页面：OSPF / ACL（交换机与路由器通用）

页面契约见 gui.py 顶部注释。与交换机专有页的差异：配置绑定的接口既可能是
Vlanif（交换机）也可能是物理接口（路由器），页面内自行处理。
"""
import ipaddress
import tkinter as tk
from tkinter import ttk

from modules import ospf, acl
from widgets import PortField, RowsEditor


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
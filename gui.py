"""界面骨架：左侧 IP/VLAN 库 + 顶部模块页签 + 底部输出预览

页面契约（每个模块页签固定三件事）：
  collect()  -> (params, errors)   收集表单值
  validate(params) -> errors       校验（IP/VLAN 格式）
  render(params) -> str            调 modules 里的纯生成函数
  set_lib_values(ip_list, vlan_list)  库变化时刷新本页所有下拉框
生成按钮固定流程：collect -> validate -> generate -> 预览区
"""
import ipaddress
import json
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

import variables as varlib
from modules import if_vlan, vlanif, dhcp, vrrp, mstp, eth_trunk, ospf, acl
from modules.base import collect_vlans, render_vlan_batch


# ============================================================ IP / VLAN 库面板
class LibraryPanel:
    """左侧库：IP/网段 和 VLAN 两类条目，供各输入框下拉选择后手改"""

    def __init__(self, parent, on_change):
        self.frame = ttk.LabelFrame(parent, text=" IP / VLAN 库 ")
        self.frame.rowconfigure(0, weight=1)
        self.frame.columnconfigure(0, weight=1)
        self.lib = varlib.load()
        self.on_change = on_change

        self.tree = ttk.Treeview(self.frame, columns=("type", "value"), show="headings", height=22)
        self.tree.heading("type", text="类型")
        self.tree.heading("value", text="值")
        self.tree.column("type", width=55, anchor=tk.W)
        self.tree.column("value", width=180, anchor=tk.W)
        self.tree.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)

        btns = ttk.Frame(self.frame)
        btns.grid(row=1, column=0, sticky="ew", padx=4, pady=2)
        ttk.Button(btns, text="新增IP", width=7, command=lambda: self.add("ip", "IP / 网段")).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="新增VLAN", width=8, command=lambda: self.add("vlan", "VLAN")).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="删除", width=6, command=self.delete).pack(side=tk.LEFT, padx=2)
        ttk.Label(self.frame, text="输入框下拉选值后可直接改\n（如选 192.168.10.0 改成 .1）",
                  foreground="gray", justify=tk.LEFT).grid(row=2, column=0, pady=2, sticky=tk.W)
        self.refresh()

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for v in self.lib["vlan"]:
            self.tree.insert("", "end", iid=f"vlan|{v}", values=("VLAN", v))
        for v in self.lib["ip"]:
            self.tree.insert("", "end", iid=f"ip|{v}", values=("IP/网段", v))

    def add(self, kind, label):
        value = simpledialog.askstring(f"新增{label}", f"{label}值：", parent=self.frame)
        if not value:
            return
        value = value.strip()
        if value not in self.lib[kind]:
            self.lib[kind].append(value)
            varlib.save(self.lib)
            self.refresh()
            self.on_change()

    def delete(self):
        sel = self.tree.selection()
        if not sel:
            return
        kind, value = sel[0].split("|", 1)
        self.lib[kind].remove(value)
        varlib.save(self.lib)
        self.refresh()
        self.on_change()


# ============================================================ 接口 VLAN 页
class IfVlanPage:
    def __init__(self, parent):
        self.frame = ttk.Frame(parent, padding=6)
        self.rows = []
        self.enabled = tk.BooleanVar(value=True)
        self._vlan_combos = []
        self._vlan_values = []

        bar = ttk.Frame(self.frame)
        bar.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(bar, text="端口类型:").pack(side=tk.LEFT)
        self.type_var = tk.StringVar(value="GE")
        ttk.Combobox(bar, textvariable=self.type_var, values=("GE", "ETH"), width=5, state="readonly").pack(side=tk.LEFT, padx=(2, 8))
        ttk.Label(bar, text="起始口:").pack(side=tk.LEFT)
        self.start_var = tk.IntVar(value=1)
        ttk.Spinbox(bar, from_=1, to=48, textvariable=self.start_var, width=4).pack(side=tk.LEFT, padx=2)
        ttk.Label(bar, text="结束口:").pack(side=tk.LEFT)
        self.end_var = tk.IntVar(value=10)
        ttk.Spinbox(bar, from_=1, to=48, textvariable=self.end_var, width=4).pack(side=tk.LEFT, padx=(2, 8))
        ttk.Button(bar, text="生成接口列表", command=self.build_rows).pack(side=tk.LEFT, padx=2)
        ttk.Button(bar, text="全选access", command=lambda: self.set_all("access")).pack(side=tk.LEFT, padx=2)
        ttk.Button(bar, text="全选trunk", command=lambda: self.set_all("trunk")).pack(side=tk.LEFT, padx=2)
        ttk.Checkbutton(bar, text="参与汇总", variable=self.enabled).pack(side=tk.RIGHT)

        head = ttk.Frame(self.frame)
        head.pack(fill=tk.X)
        for col, text, w in ((0, "勾选", 5), (1, "接口", 17), (2, "模式", 8),
                             (3, "VLAN", 8), (4, "PVID", 8), (5, "allow-pass", 22)):
            ttk.Label(head, text=text, width=w).grid(row=0, column=col, padx=2, sticky=tk.W)
        head.columnconfigure(5, weight=1)

        wrap = ttk.Frame(self.frame)
        wrap.pack(fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(wrap, highlightthickness=0)
        sb = ttk.Scrollbar(wrap, orient=tk.VERTICAL, command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas)
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=sb.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._wheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))
        self.build_rows()

    def _wheel(self, event):
        self.canvas.yview_scroll(int(-event.delta / 120), "units")

    def build_rows(self):
        for w in self.inner.winfo_children():
            w.destroy()
        self.rows = []
        self._vlan_combos = []
        token = self.type_var.get()
        for num in range(self.start_var.get(), self.end_var.get() + 1):
            row = {
                "token": token, "num": num,
                "check": tk.BooleanVar(value=False),
                "mode": tk.StringVar(value="access"),
                "vlan": tk.StringVar(value=""),
                "pvid": tk.StringVar(value=""),
                "allow": tk.StringVar(value=""),
            }
            row["mode"].trace_add("write", lambda *_, r=row: self._update_row_state(r))
            r = len(self.rows)
            ttk.Checkbutton(self.inner, variable=row["check"]).grid(row=r, column=0, padx=2)
            ttk.Label(self.inner, text=f"{token}0/0/{num}", width=15).grid(row=r, column=1, padx=2, sticky=tk.W)
            ttk.Combobox(self.inner, textvariable=row["mode"], values=("access", "trunk"), width=7, state="readonly").grid(row=r, column=2, padx=2)
            vlan_w = ttk.Combobox(self.inner, textvariable=row["vlan"], width=6)
            vlan_w.grid(row=r, column=3, padx=2)
            pvid_w = ttk.Combobox(self.inner, textvariable=row["pvid"], width=6)
            pvid_w.grid(row=r, column=4, padx=2)
            allow_w = ttk.Combobox(self.inner, textvariable=row["allow"], width=24)
            allow_w.grid(row=r, column=5, padx=2, sticky=tk.W)
            row["vlan_w"], row["pvid_w"], row["allow_w"] = vlan_w, pvid_w, allow_w
            self._vlan_combos += [vlan_w, pvid_w, allow_w]
            self._update_row_state(row)
            self.rows.append(row)
        self._apply_values()

    def _update_row_state(self, row):
        """access: 只能填 VLAN；trunk: 只能填 PVID 和 allow-pass，其余置灰"""
        access = row["mode"].get() == "access"
        row["vlan_w"].configure(state=tk.NORMAL if access else tk.DISABLED)
        row["pvid_w"].configure(state=tk.DISABLED if access else tk.NORMAL)
        row["allow_w"].configure(state=tk.DISABLED if access else tk.NORMAL)

    def _apply_values(self):
        for cb in self._vlan_combos:
            cb["values"] = self._vlan_values

    def set_lib_values(self, ip_list, vlan_list):
        self._vlan_values = list(vlan_list)
        self._apply_values()

    def set_all(self, mode):
        for row in self.rows:
            row["mode"].set(mode)

    def collect(self):
        ports = []
        for row in self.rows:
            if not row["check"].get():
                continue
            port = {"type": row["token"], "num": row["num"], "mode": row["mode"].get()}
            if port["mode"] == "access":
                port["vlan"] = row["vlan"].get().strip()
            else:
                pvid = row["pvid"].get().strip()
                if pvid:
                    port["pvid"] = pvid
                port["allow"] = row["allow"].get().strip()
            ports.append(port)
        return {"ports": ports}, []

    def validate(self, params):
        errors = []
        for p in params["ports"]:
            label = f"{p['type']}0/0/{p['num']}"
            if p["mode"] == "access":
                if not str(p.get("vlan", "")).isdigit():
                    errors.append(f"{label}: access 模式必须填数字 VLAN")
            else:
                if not p.get("allow"):
                    errors.append(f"{label}: trunk 模式必须填 allow-pass VLAN（空格分隔）")
                for v in str(p.get("allow", "")).split():
                    if not v.isdigit():
                        errors.append(f"{label}: allow-pass 含非数字值 {v}")
                if p.get("pvid") and not str(p["pvid"]).isdigit():
                    errors.append(f"{label}: PVID 必须是数字")
        return errors

    def render(self, params):
        return if_vlan.generate_full(params)


# ============================================================ 三层网关页
class VlanifPage:
    def __init__(self, parent):
        self.frame = ttk.Frame(parent, padding=6)
        self.rows = []
        self.enabled = tk.BooleanVar(value=True)
        self._ip_combos = []
        self._vlan_combos = []
        self._ip_values = []
        self._vlan_values = []

        bar = ttk.Frame(self.frame)
        bar.pack(fill=tk.X, pady=(0, 4))
        ttk.Button(bar, text="添加一行", command=self.add_row).pack(side=tk.LEFT, padx=2)
        ttk.Checkbutton(bar, text="参与汇总", variable=self.enabled).pack(side=tk.RIGHT)

        head = ttk.Frame(self.frame)
        head.pack(fill=tk.X)
        ttk.Label(head, text="VLAN ID", width=10).grid(row=0, column=0, padx=2)
        ttk.Label(head, text="IP 地址", width=24).grid(row=0, column=1, padx=2)
        ttk.Label(head, text="掩码", width=18).grid(row=0, column=2, padx=2)

        self.area = ttk.Frame(self.frame)
        self.area.pack(fill=tk.BOTH, expand=True)
        self.add_row()

    def add_row(self):
        row = {"vlan": tk.StringVar(), "ip": tk.StringVar(), "mask": tk.StringVar(value="255.255.255.0")}
        f = ttk.Frame(self.area)
        f.pack(fill=tk.X, pady=1)
        vlan_w = ttk.Combobox(f, textvariable=row["vlan"], width=8, values=self._vlan_values)
        vlan_w.pack(side=tk.LEFT, padx=2)
        ip_w = ttk.Combobox(f, textvariable=row["ip"], width=22, values=self._ip_values)
        ip_w.pack(side=tk.LEFT, padx=2)
        ttk.Entry(f, textvariable=row["mask"], width=16).pack(side=tk.LEFT, padx=2)
        ttk.Button(f, text="删", width=3, command=lambda: self.del_row(row)).pack(side=tk.LEFT, padx=2)
        row["frame"] = f
        self._vlan_combos.append(vlan_w)
        self._ip_combos.append(ip_w)
        self.rows.append(row)

    def del_row(self, row):
        row["frame"].destroy()
        self.rows.remove(row)

    def set_lib_values(self, ip_list, vlan_list):
        self._ip_values, self._vlan_values = list(ip_list), list(vlan_list)
        for cb in self._ip_combos:
            cb["values"] = self._ip_values
        for cb in self._vlan_combos:
            cb["values"] = self._vlan_values

    def collect(self):
        ifaces = []
        for row in self.rows:
            vlan = row["vlan"].get().strip()
            ip = row["ip"].get().strip()
            if vlan or ip:
                ifaces.append({"vlan": vlan, "ip": ip, "mask": row["mask"].get().strip()})
        return {"ifaces": ifaces}, []

    def validate(self, params):
        errors = []
        for i in params["ifaces"]:
            if not i["vlan"].isdigit():
                errors.append(f"Vlanif: VLAN ID {i['vlan'] or '(空)'} 必须是数字")
            for field in ("ip", "mask"):
                try:
                    ipaddress.ip_address(i[field])
                except ValueError:
                    errors.append(f"Vlanif{i['vlan']}: {field} {i[field]} 不是合法地址")
        return errors

    def render(self, params):
        return vlanif.generate(params)


# ============================================================ DHCP 页（仅全局地址池）
class DhcpPage:
    def __init__(self, parent):
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


# ============================================================ 通用动态行编辑器
class RowsEditor:
    """轻量的“添加一行 / 删除一行”表单，供 VRRP、MSTP、OSPF、ACL 共用。"""

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
        return [{key: row[key].get().strip() for key, *_ in self.columns} for row in self.rows]

    def set_lib_values(self, ip_list, vlan_list):
        self.ip_values, self.vlan_values = list(ip_list), list(vlan_list)
        for row in self.rows:
            for key, _, _, kind in self.columns:
                if kind == "ip":
                    row["widgets"][key]["values"] = self.ip_values
                elif kind == "vlan":
                    row["widgets"][key]["values"] = self.vlan_values


# ============================================================ VRRP 页
class VrrpPage:
    def __init__(self, parent):
        self.frame = ttk.Frame(parent, padding=6)
        self.enabled = tk.BooleanVar(value=True)
        bar = ttk.Frame(self.frame)
        bar.pack(fill=tk.X)
        ttk.Button(bar, text="添加 VLANIF", command=self.add_row).pack(side=tk.LEFT, padx=2)
        ttk.Checkbutton(bar, text="参与汇总", variable=self.enabled).pack(side=tk.RIGHT)
        self.priority = self._field("主设备优先级", "120", 8)
        self.preempt_delay = self._field("抢占延时(秒)", "10", 8)
        self.track_interface = self._field("跟踪接口", "GigabitEthernet0/0/6", 24)
        self.track_reduced = self._field("跟踪降级值", "50", 8)
        self.auth = self._field("认证密码", "admin123", 16)
        ttk.Label(self.frame, text="角色设为主设备时才生成优先级、抢占与接口跟踪。", foreground="gray").pack(anchor=tk.W, pady=(2, 0))
        self.editor = RowsEditor(self.frame, [
            ("vlan", "VLAN", 8, "vlan"), ("ip", "本机 IP", 18, "ip"),
            ("mask", "掩码", 16, None), ("virtual_ip", "虚拟 IP", 18, "ip"),
            ("role", "角色", 10, ("primary", "secondary")),
        ])
        self.add_row()
        self.add_row()

    def _field(self, label, default, width):
        f = ttk.Frame(self.frame)
        f.pack(fill=tk.X, pady=1)
        ttk.Label(f, text=label, width=16).pack(side=tk.LEFT)
        var = tk.StringVar(value=default)
        ttk.Entry(f, textvariable=var, width=width).pack(side=tk.LEFT)
        return var

    def add_row(self):
        self.editor.add({"mask": "255.255.255.0", "role": "secondary"})

    def set_lib_values(self, ip_list, vlan_list):
        self.editor.set_lib_values(ip_list, vlan_list)

    def collect(self):
        return {"priority": self.priority.get().strip(), "preempt_delay": self.preempt_delay.get().strip(),
                "track_interface": self.track_interface.get().strip(), "track_reduced": self.track_reduced.get().strip(),
                "auth": self.auth.get().strip(), "ifaces": self.editor.values()}, []

    def validate(self, params):
        return []

    def render(self, params):
        return vrrp.generate_full(params)


# ============================================================ MSTP 页
class MstpPage:
    def __init__(self, parent):
        self.frame = ttk.Frame(parent, padding=6)
        self.enabled = tk.BooleanVar(value=True)
        bar = ttk.Frame(self.frame)
        bar.pack(fill=tk.X)
        ttk.Button(bar, text="添加实例", command=self.add_row).pack(side=tk.LEFT, padx=2)
        ttk.Checkbutton(bar, text="参与汇总", variable=self.enabled).pack(side=tk.RIGHT)
        f = ttk.Frame(self.frame)
        f.pack(fill=tk.X, pady=3)
        ttk.Label(f, text="区域名", width=12).pack(side=tk.LEFT)
        self.region_name = tk.StringVar(value="HUAWEI")
        ttk.Entry(f, textvariable=self.region_name, width=20).pack(side=tk.LEFT)
        self.editor = RowsEditor(self.frame, [
            ("instance", "实例", 8, None), ("vlan", "VLAN", 8, "vlan"),
            ("root", "本机根桥角色", 12, ("primary", "secondary")),
        ])
        self.add_row("1", "10", "primary")
        self.add_row("2", "20", "secondary")

    def add_row(self, instance="", vlan="", root="primary"):
        self.editor.add({"instance": instance, "vlan": vlan, "root": root})

    def set_lib_values(self, ip_list, vlan_list):
        self.editor.set_lib_values(ip_list, vlan_list)

    def collect(self):
        return {"region_name": self.region_name.get().strip(), "instances": self.editor.values()}, []

    def validate(self, params):
        return []

    def render(self, params):
        return mstp.generate_full(params)


# ============================================================ 链路聚合页
class EthTrunkPage:
    def __init__(self, parent):
        self.frame = ttk.Frame(parent, padding=6)
        self.enabled = tk.BooleanVar(value=True)
        bar = ttk.Frame(self.frame)
        bar.pack(fill=tk.X)
        ttk.Checkbutton(bar, text="参与汇总", variable=self.enabled).pack(side=tk.RIGHT)
        self.vars = {}
        self._field("聚合口编号", "trunk_id", "1")
        self._field("允许 VLAN（空格分隔）", "allow", "10 20")
        self._field("成员口（空格分隔）", "members", "22 23 24")

    def _field(self, label, key, default):
        f = ttk.Frame(self.frame)
        f.pack(fill=tk.X, pady=1)
        ttk.Label(f, text=label, width=20).pack(side=tk.LEFT)
        self.vars[key] = tk.StringVar(value=default)
        ttk.Entry(f, textvariable=self.vars[key], width=30).pack(side=tk.LEFT)

    def set_lib_values(self, ip_list, vlan_list):
        pass

    def collect(self):
        return {key: var.get().strip() for key, var in self.vars.items()}, []

    def validate(self, params):
        return []

    def render(self, params):
        return eth_trunk.generate_full(params)


# ============================================================ OSPF 页
class OspfPage:
    def __init__(self, parent):
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


# ============================================================ ACL 页
class AclPage:
    def __init__(self, parent):
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
        self.bind_interface = self._field("绑定接口（可空）", "GigabitEthernet0/0/1")
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
                "bind_interface": self.bind_interface.get().strip(), "direction": self.direction.get().strip(),
                "rules": self.editor.values()}, []

    def validate(self, params):
        return []

    def render(self, params):
        return acl.generate(params)


# ============================================================ 主窗口
class App:
    def __init__(self, root):
        self.root = root
        root.title("华为 eNSP 配置生成工具 v0.2")
        root.geometry("1020x720")

        paned = ttk.PanedWindow(root, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True)

        top = ttk.PanedWindow(paned, orient=tk.HORIZONTAL)
        paned.add(top, weight=3)

        self.lib_panel = LibraryPanel(top, on_change=self._sync_lib)
        top.add(self.lib_panel.frame, weight=1)

        self.nb = ttk.Notebook(top)
        top.add(self.nb, weight=3)
        self.page_if = IfVlanPage(self.nb)
        self.page_vlanif = VlanifPage(self.nb)
        self.page_dhcp = DhcpPage(self.nb)
        self.page_vrrp = VrrpPage(self.nb)
        self.page_mstp = MstpPage(self.nb)
        self.page_trunk = EthTrunkPage(self.nb)
        self.page_ospf = OspfPage(self.nb)
        self.page_acl = AclPage(self.nb)
        self.nb.add(self.page_if.frame, text=" 接口VLAN ")
        self.nb.add(self.page_vlanif.frame, text=" 三层网关 ")
        self.nb.add(self.page_dhcp.frame, text=" DHCP ")
        self.nb.add(self.page_vrrp.frame, text=" VRRP ")
        self.nb.add(self.page_mstp.frame, text=" MSTP ")
        self.nb.add(self.page_trunk.frame, text=" 链路聚合 ")
        self.nb.add(self.page_ospf.frame, text=" OSPF ")
        self.nb.add(self.page_acl.frame, text=" ACL ")
        self._sync_lib()

        bottom = ttk.Frame(paned, padding=4)
        paned.add(bottom, weight=2)

        btns = ttk.Frame(bottom)
        btns.pack(fill=tk.X)
        ttk.Button(btns, text="生成当前模块", command=self.generate_current).pack(side=tk.LEFT, padx=3)
        ttk.Button(btns, text="汇总生成全部", command=self.generate_all).pack(side=tk.LEFT, padx=3)
        ttk.Button(btns, text="复制到剪贴板", command=self.copy_out).pack(side=tk.LEFT, padx=15)
        ttk.Button(btns, text="保存为 .cfg", command=self.save_cfg).pack(side=tk.LEFT, padx=3)
        ttk.Button(btns, text="清空", command=lambda: self.set_preview("")).pack(side=tk.LEFT, padx=3)

        self.preview = tk.Text(bottom, font=("Consolas", 10), state=tk.DISABLED, wrap=tk.NONE)
        ysb = ttk.Scrollbar(bottom, orient=tk.VERTICAL, command=self.preview.yview)
        self.preview.configure(yscrollcommand=ysb.set)
        ysb.pack(side=tk.RIGHT, fill=tk.Y)
        self.preview.pack(fill=tk.BOTH, expand=True)

        self.last_params = {}

    def _sync_lib(self):
        """库变化时把 IP / VLAN 选项刷新到所有页面的下拉框"""
        lib = self.lib_panel.lib
        for page in (self.page_if, self.page_vlanif, self.page_dhcp, self.page_vrrp,
                     self.page_mstp, self.page_trunk, self.page_ospf, self.page_acl):
            page.set_lib_values(lib["ip"], lib["vlan"])

    # ---------- 生成流程：collect -> validate -> generate ----------
    def _prepare(self, page):
        params, errors = page.collect()
        errors += page.validate(params)
        return params, errors

    def generate_current(self):
        pages = (self.page_if, self.page_vlanif, self.page_dhcp, self.page_vrrp,
                 self.page_mstp, self.page_trunk, self.page_ospf, self.page_acl)
        page = pages[self.nb.index(self.nb.select())]
        params, errors = self._prepare(page)
        if errors:
            messagebox.showwarning("无法生成", "\n".join(errors))
            return
        text = page.render(params)
        if not text.strip():
            messagebox.showinfo("提示", "当前页没有勾选/填写任何内容")
            return
        self.last_params = params
        self.set_preview(text)

    def generate_all(self):
        blocks, errors, vlans, all_params = [], [], set(), {}

        if self.page_if.enabled.get():
            params, errs = self._prepare(self.page_if)
            errors += errs
            if params["ports"]:
                all_params["if_vlan"] = params
                blocks.append(if_vlan.generate(params))
                vlans |= set(collect_vlans(params["ports"]))

        if self.page_vlanif.enabled.get():
            params, errs = self._prepare(self.page_vlanif)
            errors += errs
            if params["ifaces"]:
                all_params["vlanif"] = params
                blocks.append(vlanif.generate(params))
                vlans |= {int(i["vlan"]) for i in params["ifaces"]}

        if self.page_dhcp.enabled.get():
            params, errs = self._prepare(self.page_dhcp)
            errors += errs
            if not self.page_dhcp.is_empty(params):
                all_params["dhcp"] = params
                blocks.append(dhcp.generate(params))
                if params.get("if_vlan", "").isdigit():
                    vlans.add(int(params["if_vlan"]))

        # v0.2 三层交换机模块。模块自身只生成正文，汇总时在这里统一生成 vlan batch。
        extra_pages = (
            ("vrrp", self.page_vrrp, vrrp.generate, vrrp.collect_vlans),
            ("mstp", self.page_mstp, mstp.generate, mstp.collect_vlans),
            ("eth_trunk", self.page_trunk, eth_trunk.generate, eth_trunk.collect_vlans),
            ("ospf", self.page_ospf, ospf.generate, None),
            ("acl", self.page_acl, acl.generate, None),
        )
        for name, page, generator, vlan_collector in extra_pages:
            if not page.enabled.get():
                continue
            params, errs = self._prepare(page)
            errors += errs
            block = generator(params)
            if block:
                all_params[name] = params
                blocks.append(block)
                if vlan_collector:
                    vlans |= set(vlan_collector(params))

        if errors:
            messagebox.showwarning("无法生成", "\n".join(errors))
            return
        if not blocks:
            messagebox.showinfo("提示", "没有任何模块内容（勾选'参与汇总'并填写内容）")
            return

        header = render_vlan_batch(sorted(vlans))
        text = (header + "\n" if header else "") + "\n#\n".join(blocks)
        self.last_params = all_params
        self.set_preview(text)

    # ---------- 输出区 ----------
    def set_preview(self, text):
        self.preview.configure(state=tk.NORMAL)
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", text)
        self.preview.configure(state=tk.DISABLED)

    def copy_out(self):
        content = self.preview.get("1.0", "end").strip()
        if not content:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(content)

    def save_cfg(self):
        content = self.preview.get("1.0", "end").strip()
        if not content:
            messagebox.showinfo("提示", "输出区为空，请先生成配置")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".cfg", initialfile="config.cfg",
            filetypes=[("配置脚本", "*.cfg"), ("所有文件", "*.*")])
        if not path:
            return
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            # 参数注释头：这份文件可直接作为给 AI 的"参数->配置"标准范例
            f.write("# 生成参数: " + json.dumps(self.last_params, ensure_ascii=False) + "\n")
            f.write(content + "\n")
        messagebox.showinfo("已保存", path)

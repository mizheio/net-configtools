"""交换机页面：接口VLAN / 三层网关 / VRRP / MSTP / 链路聚合

页面契约见 gui.py 顶部注释。加新交换机页面：本文件写类 + pages/__init__.py 注册。
"""
import ipaddress
import tkinter as tk
from tkinter import ttk

from modules import if_vlan, vlanif, vrrp, mstp, eth_trunk
from modules.base import PORT_TYPES, collect_vlans, port_name
from widgets import PortField, RowsEditor


# ============================================================ 接口 VLAN 页
class IfVlanPage:
    TITLE = "接口VLAN"
    OWN_SCROLL = True  # 自带行区滚动画布，App 装配时不再包外层 ScrollFrame

    def __init__(self, parent, app=None):
        self.frame = ttk.Frame(parent, padding=6)
        self.rows = []
        self.enabled = tk.BooleanVar(value=True)
        self._vlan_combos = []
        self._vlan_values = []

        bar = ttk.Frame(self.frame)
        bar.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(bar, text="端口类型:").pack(side=tk.LEFT)
        self.type_var = tk.StringVar(value="GE")
        ttk.Combobox(bar, textvariable=self.type_var, values=("GE", "ETH"), width=5, state="readonly").pack(side=tk.LEFT, padx=(2, 6))
        ttk.Label(bar, text="槽位:").pack(side=tk.LEFT)
        self.slot_var = tk.StringVar(value="0/0")
        ttk.Entry(bar, textvariable=self.slot_var, width=5).pack(side=tk.LEFT, padx=(2, 8))
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
        for col, text, w in ((0, "勾选", 5), (1, "类型", 6), (2, "编号", 10), (3, "模式", 8),
                             (4, "VLAN", 8), (5, "PVID", 8), (6, "allow-pass", 22)):
            ttk.Label(head, text=text, width=w).grid(row=0, column=col, padx=2, sticky=tk.W)
        head.columnconfigure(6, weight=1)

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
        self.build_rows()

    def build_rows(self):
        # 重建前快照已填内容，批量调整端口范围/槽位时按行号保留，不再清空
        saved = [{k: row[k].get() for k in ("check", "type", "num", "mode", "vlan", "pvid", "allow")}
                 for row in self.rows]
        for w in self.inner.winfo_children():
            w.destroy()
        self.rows = []
        self._vlan_combos = []
        token = self.type_var.get()
        slot = self.slot_var.get().strip().strip("/")
        for num in range(self.start_var.get(), self.end_var.get() + 1):
            row = {
                "type": tk.StringVar(value=token),
                "num": tk.StringVar(value=f"{slot}/{num}" if slot else str(num)),
                "check": tk.BooleanVar(value=False),
                "mode": tk.StringVar(value="access"),
                "vlan": tk.StringVar(value=""),
                "pvid": tk.StringVar(value=""),
                "allow": tk.StringVar(value=""),
            }
            row["mode"].trace_add("write", lambda *_, r=row: self._update_row_state(r))
            r = len(self.rows)
            ttk.Checkbutton(self.inner, variable=row["check"]).grid(row=r, column=0, padx=2)
            ttk.Combobox(self.inner, textvariable=row["type"], values=("GE", "ETH"),
                         width=5, state="readonly").grid(row=r, column=1, padx=2)
            ttk.Entry(self.inner, textvariable=row["num"], width=9).grid(row=r, column=2, padx=2)
            ttk.Combobox(self.inner, textvariable=row["mode"], values=("access", "trunk"), width=7, state="readonly").grid(row=r, column=3, padx=2)
            vlan_w = ttk.Combobox(self.inner, textvariable=row["vlan"], width=6)
            vlan_w.grid(row=r, column=4, padx=2)
            pvid_w = ttk.Combobox(self.inner, textvariable=row["pvid"], width=6)
            pvid_w.grid(row=r, column=5, padx=2)
            allow_w = ttk.Combobox(self.inner, textvariable=row["allow"], width=24)
            allow_w.grid(row=r, column=6, padx=2, sticky=tk.W)
            row["vlan_w"], row["pvid_w"], row["allow_w"] = vlan_w, pvid_w, allow_w
            self._vlan_combos += [vlan_w, pvid_w, allow_w]
            self._update_row_state(row)
            self.rows.append(row)
        for row, snap in zip(self.rows, saved):
            for k in ("type", "num", "vlan", "pvid", "allow"):
                row[k].set(snap[k])
            row["check"].set(snap["check"])
            row["mode"].set(snap["mode"])
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
            port = {"type": row["type"].get(), "num": row["num"].get().strip(), "mode": row["mode"].get()}
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
            label = port_name(p["type"], p["num"])
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

    def render_summary(self, params):
        return if_vlan.generate(params)

    def summary_vlans(self, params):
        return set(collect_vlans(params["ports"]))


# ============================================================ 三层网关页
class VlanifPage:
    TITLE = "三层网关"

    def __init__(self, parent, app=None):
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

    def render_summary(self, params):
        return vlanif.generate(params)

    def summary_vlans(self, params):
        return {int(i["vlan"]) for i in params["ifaces"] if i["vlan"].isdigit()}


# ============================================================ VRRP 双机热备页
class VrrpPage:
    TITLE = "VRRP"

    def __init__(self, parent, app=None):
        self.frame = ttk.Frame(parent, padding=6)
        self.enabled = tk.BooleanVar(value=True)
        self.app = app

        bar = ttk.Frame(self.frame)
        bar.pack(fill=tk.X)
        ttk.Button(bar, text="添加 VLAN", command=self.add_plan).pack(side=tk.LEFT, padx=2)
        ttk.Button(bar, text="生成设备 1", command=lambda: self.app.generate_vrrp_device("device1")).pack(side=tk.LEFT, padx=2)
        ttk.Button(bar, text="生成设备 2", command=lambda: self.app.generate_vrrp_device("device2")).pack(side=tk.LEFT, padx=2)
        ttk.Button(bar, text="一键生成两台", command=lambda: self.app.generate_vrrp_device("pair")).pack(side=tk.LEFT, padx=2)
        ttk.Checkbutton(bar, text="参与汇总", variable=self.enabled).pack(side=tk.RIGHT)

        common = ttk.Frame(self.frame)
        common.pack(fill=tk.X, pady=2)
        ttk.Label(common, text="认证密码", width=12).pack(side=tk.LEFT)
        self.auth = tk.StringVar(value="admin123")
        ttk.Entry(common, textvariable=self.auth, width=18).pack(side=tk.LEFT)
        ttk.Label(common, text="汇总设备", width=10).pack(side=tk.LEFT, padx=(18, 0))
        self.summary_role = tk.StringVar(value="设备 1")
        ttk.Combobox(common, textvariable=self.summary_role, values=("设备 1", "设备 2"),
                     width=12, state="readonly").pack(side=tk.LEFT)

        ttk.Label(self.frame, text="VRRP VLAN 规划（每行分别设置设备 1、设备 2 的 VRRP 主/备角色）", foreground="gray").pack(anchor=tk.W, pady=(4, 0))
        self.plan_editor = RowsEditor(self.frame, [
            ("vlan", "VLAN", 8, "vlan"), ("mask", "掩码", 16, None),
            ("virtual_ip", "虚拟 IP", 16, "ip"), ("device1_ip", "设备 1 IP", 16, "ip"),
            ("device1_role", "设备 1 角色", 10, ("主", "备")), ("device2_ip", "设备 2 IP", 16, "ip"),
            ("device2_role", "设备 2 角色", 10, ("主", "备")),
        ])
        self.add_plan("10", "192.168.10.254", "192.168.10.252", "主", "192.168.10.253", "备")
        self.add_plan("20", "192.168.20.254", "192.168.20.252", "备", "192.168.20.253", "主")

        primary = ttk.LabelFrame(self.frame, text=" 所有“主”角色接口的通用参数 ", padding=5)
        primary.pack(fill=tk.X, pady=(7, 0))
        self.priority = self._card_field(primary, "优先级", "120")
        self.preempt_delay = self._card_field(primary, "抢占延时(秒)", "10")
        self.track_port = self._card_port(primary, "跟踪接口", "GE", "0/0/6")
        self.track_reduced = self._card_field(primary, "跟踪降级值", "50")

    def _card_field(self, parent, label, default):
        f = ttk.Frame(parent)
        f.pack(fill=tk.X, pady=1)
        ttk.Label(f, text=label, width=14).pack(side=tk.LEFT)
        var = tk.StringVar(value=default)
        ttk.Entry(f, textvariable=var, width=22).pack(side=tk.LEFT)
        return var

    def _card_port(self, parent, label, port_type, num):
        f = ttk.Frame(parent)
        f.pack(fill=tk.X, pady=1)
        ttk.Label(f, text=label, width=14).pack(side=tk.LEFT)
        field = PortField(f)
        field.set(port_type, num)
        field.pack(side=tk.LEFT)
        return field

    def add_plan(self, vlan="", virtual_ip="", device1_ip="", device1_role="主", device2_ip="", device2_role="备"):
        self.plan_editor.add({"vlan": vlan, "mask": "255.255.255.0", "virtual_ip": virtual_ip,
                              "device1_ip": device1_ip, "device1_role": device1_role,
                              "device2_ip": device2_ip, "device2_role": device2_role})

    def set_lib_values(self, ip_list, vlan_list):
        self.plan_editor.set_lib_values(ip_list, vlan_list)

    def collect(self):
        plans = self.plan_editor.values()
        for row in plans:
            row["device1_role"] = "primary" if row["device1_role"] == "主" else "secondary"
            row["device2_role"] = "primary" if row["device2_role"] == "主" else "secondary"
        return {"priority": self.priority.get().strip(), "preempt_delay": self.preempt_delay.get().strip(),
                "track_interface": self.track_port.get(), "track_reduced": self.track_reduced.get().strip(),
                "auth": self.auth.get().strip(),
                "summary_role": "device1" if self.summary_role.get() == "设备 1" else "device2",
                "plans": plans}, []

    def validate(self, params):
        return []

    def render(self, params):
        return vrrp.generate_pair(params)

    def render_summary(self, params):
        return vrrp.generate_device(params, params["summary_role"])

    def summary_vlans(self, params):
        return set(vrrp.collect_vlans(params))


# ============================================================ MSTP 页
class MstpPage:
    TITLE = "MSTP"

    def __init__(self, parent, app=None):
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

    def render_summary(self, params):
        return mstp.generate(params)

    def summary_vlans(self, params):
        return set(mstp.collect_vlans(params))


# ============================================================ 链路聚合页
class EthTrunkPage:
    TITLE = "链路聚合"

    def __init__(self, parent, app=None):
        self.frame = ttk.Frame(parent, padding=6)
        self.enabled = tk.BooleanVar(value=True)
        self.app = app
        bar = ttk.Frame(self.frame)
        bar.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(bar, text="聚合口编号").pack(side=tk.LEFT)
        self.trunk_id = tk.StringVar(value="1")
        ttk.Entry(bar, textvariable=self.trunk_id, width=5).pack(side=tk.LEFT, padx=(2, 10))
        ttk.Button(bar, text="添加 VLAN", command=self.add_vlan).pack(side=tk.LEFT, padx=2)
        ttk.Button(bar, text="添加成员接口", command=self.add_member).pack(side=tk.LEFT, padx=2)
        ttk.Checkbutton(bar, text="参与汇总", variable=self.enabled).pack(side=tk.RIGHT)

        ttk.Label(self.frame, text="放行 VLAN（每行一个）", foreground="gray").pack(anchor=tk.W, pady=(5, 0))
        self.vlan_editor = RowsEditor(self.frame, [("vlan", "VLAN", 12, "vlan")])
        self.add_vlan("10")
        self.add_vlan("20")

        ttk.Label(self.frame, text="成员接口（每行一个；选择接口类型和编号）", foreground="gray").pack(anchor=tk.W, pady=(5, 0))
        self.member_editor = RowsEditor(self.frame, [
            ("port_type", "接口类型", 8, PORT_TYPES), ("port_num", "接口编号", 12, None),
        ])
        self.add_member("GE", "0/0/22")
        self.add_member("ETH", "0/0/23")
        self.add_member("GE", "0/0/24")

    
    def add_vlan(self, vlan=""):
        self.vlan_editor.add({"vlan": vlan})

    def add_member(self, port_type="GE", num=""):
        self.member_editor.add({"port_type": port_type, "port_num": num})

    def set_lib_values(self, ip_list, vlan_list):
        self.vlan_editor.set_lib_values(ip_list, vlan_list)

    def collect(self):
        members = []
        for row in self.member_editor.values():
            port_type = row.get("port_type", "GE")
            port_num = row.get("port_num", "")
            if port_type and port_num:
                members.append({"type": port_type, "num": port_num})
        
        return {"trunk_id": self.trunk_id.get().strip(),
                "vlans": self.vlan_editor.values(), "members": members}, []

    def validate(self, params):
        errors = []
        
        # 验证聚合口编号
        if not params.get("trunk_id").isdigit():
            errors.append("聚合口编号必须是数字")
        
        # 验证成员接口
        for i, member in enumerate(params.get("members", [])):
            if not member.get("type"):
                errors.append(f"第{i+1}个成员接口缺少类型")
            if not member.get("num"):
                errors.append(f"第{i+1}个成员接口缺少编号")
        
        return errors

    def render(self, params):
        return eth_trunk.generate_full(params)

    def render_summary(self, params):
        return eth_trunk.generate(params)

    def summary_vlans(self, params):
        return set(eth_trunk.collect_vlans(params))

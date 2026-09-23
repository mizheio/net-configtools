"""防火墙 GRE VPN 页面（文档 5.7 点到点 GRE 隧道）

页面契约见 gui.py 顶部注释。本端参数只填一次，勾选"生成对端脚本"后展开对端段，
隧道 source/destination 与两侧业务网段自动互换。安全策略两段由程序固定生成。
"""
import ipaddress
import tkinter as tk
from tkinter import ttk

from modules import fw_gre
from modules.fw_ipsec import parse_net

# 隧道所在安全域；内网侧 trust、公网侧 untrust 按文档 5.7 固定在安全策略里
ZONES = ("dmz", "trust", "untrust")


class FwGrePage:
    """防火墙 GRE VPN（文档 5.7）：GRE 隧道 + 加入安全域 + 静态路由 + 安全策略两段"""

    TITLE = "GRE VPN"

    def __init__(self, parent, app=None):
        self.frame = ttk.Frame(parent, padding=6)
        self.enabled = tk.BooleanVar(value=True)
        self.gen_peer = tk.BooleanVar(value=False)
        self._ip_combos = []
        self._ip_values = []

        bar = ttk.Frame(self.frame)
        bar.pack(fill=tk.X, pady=(0, 4))
        ttk.Checkbutton(bar, text="生成对端脚本", variable=self.gen_peer).pack(side=tk.LEFT, padx=2)
        ttk.Checkbutton(bar, text="参与汇总", variable=self.enabled).pack(side=tk.RIGHT)

        # —— GRE 隧道（分两行，避免把窗口横向撑宽）——
        box = self._section("GRE 隧道")
        row1 = ttk.Frame(box)
        row1.pack(fill=tk.X)
        self.v_tunnel_num = self._field(row1, "隧道号", "1", 6)
        self.v_tunnel_ip = self._field(row1, "隧道 IP", "", 16, ip=True)
        self.v_tunnel_mask = self._field(row1, "子网掩码", fw_gre.SUBNET_MASKS[0], 17,
                                         editable=fw_gre.SUBNET_MASKS)
        row2 = ttk.Frame(box)
        row2.pack(fill=tk.X, pady=(3, 0))
        self.v_source = self._field(row2, "source 本端公网", "", 15, ip=True)
        self.v_destination = self._field(row2, "destination 对端公网", "", 15, ip=True)
        self.v_zone = self._field(row2, "安全区域", "dmz", 8, values=ZONES)

        # —— 静态路由与业务网段 ——
        box = self._section("静态路由")
        self.v_default_nh = self._field(box, "默认路由下一跳", "", 16, ip=True)
        self.v_local_net = self._field(box, "本端内网网段", "", 18, ip=True)
        self.v_remote_net = self._field(box, "对端内网网段", "", 18, ip=True)

        # —— 对端设备（勾选“生成对端脚本”后展开）——
        self.peer_box = self._section("对端设备")
        self.v_peer_tunnel_ip = self._field(self.peer_box, "对端隧道 IP", "", 16, ip=True)
        self.v_peer_default_nh = self._field(self.peer_box, "对端默认路由下一跳", "", 16, ip=True)

        self.note = ttk.Label(self.frame, foreground="gray", justify=tk.LEFT, text=(
            "隧道口写作 Tunnel 1。\n"
            "安全策略两段由程序生成。\n"
            "对端参数按对端侧实际填。"))
        self.gen_peer.trace_add("write", lambda *_: self._sync_peer())
        self._sync_peer()

    # ---------------------------------------------------------------- 构件
    def _section(self, title):
        box = ttk.LabelFrame(self.frame, text=f" {title} ", padding=4)
        box.pack(fill=tk.X, pady=3)
        return box

    def _field(self, parent, label, default="", width=16, values=None, ip=False, editable=None):
        """在所在分节内平铺一个输入项。

        ip=True 用 IP 库可编辑下拉；values 用只读下拉；editable 用"能选也能手输"的下拉。
        """
        var = tk.StringVar(value=default)
        f = ttk.Frame(parent)
        if label:
            ttk.Label(f, text=label).pack(side=tk.LEFT)
        if ip:
            cb = ttk.Combobox(f, textvariable=var, values=self._ip_values, width=width)
            cb.pack(side=tk.LEFT, padx=(2, 12))
            self._ip_combos.append(cb)
        elif editable is not None:
            ttk.Combobox(f, textvariable=var, values=list(editable),
                         width=width).pack(side=tk.LEFT, padx=(2, 12))
        elif values is not None:
            ttk.Combobox(f, textvariable=var, values=list(values), width=width,
                         state="readonly").pack(side=tk.LEFT, padx=(2, 12))
        else:
            ttk.Entry(f, textvariable=var, width=width).pack(side=tk.LEFT, padx=(2, 12))
        f.pack(side=tk.LEFT)
        return var

    def _sync_peer(self):
        """勾选“生成对端脚本”时展开对端段；重新 pack 说明文字保证它始终在最下方"""
        if self.gen_peer.get():
            self.peer_box.pack(fill=tk.X, pady=3)
        else:
            self.peer_box.pack_forget()
        self.note.pack(fill=tk.X, pady=(4, 0))

    def set_lib_values(self, ip_list, vlan_list):
        self._ip_values = list(ip_list)
        for cb in self._ip_combos:
            cb["values"] = self._ip_values

    # ---------------------------------------------------------------- 契约
    def collect(self):
        params = {
            "tunnel_num": self.v_tunnel_num.get().strip(),
            "tunnel_ip": self.v_tunnel_ip.get().strip(),
            "tunnel_mask": self.v_tunnel_mask.get().strip(),
            "source": self.v_source.get().strip(),
            "destination": self.v_destination.get().strip(),
            "zone": self.v_zone.get().strip(),
            "default_next_hop": self.v_default_nh.get().strip(),
            "local_net": self.v_local_net.get().strip(),
            "remote_net": self.v_remote_net.get().strip(),
            "gen_peer": self.gen_peer.get(),
            "peer_tunnel_ip": self.v_peer_tunnel_ip.get().strip(),
            "peer_default_next_hop": self.v_peer_default_nh.get().strip(),
        }
        return params, []

    def is_empty(self, params):
        return not any([params["tunnel_ip"], params["source"], params["destination"],
                        params["local_net"], params["remote_net"]])

    def validate(self, params):
        # 整页未填时保持惰性，不阻塞“汇总生成全部”
        if self.is_empty(params):
            return []
        errors = []
        if not params["tunnel_num"]:
            errors.append("GRE: 隧道号不能为空")
        for key, zh in (("tunnel_ip", "隧道 IP"), ("source", "本端公网 source"),
                        ("destination", "对端公网 destination"),
                        ("default_next_hop", "默认路由下一跳")):
            if not params[key]:
                errors.append(f"GRE: {zh}不能为空")
                continue
            try:
                ipaddress.ip_address(params[key])
            except ValueError:
                errors.append(f"GRE: {zh} {params[key]} 不是合法 IP")
        if params["tunnel_mask"]:
            try:
                fw_gre.normalize_mask(params["tunnel_mask"])
            except ValueError:
                errors.append(f"GRE: 子网掩码 {params['tunnel_mask']} 不是合法掩码")
        else:
            errors.append("GRE: 子网掩码不能为空")
        if params["zone"] and params["zone"] not in ZONES:
            errors.append(f"GRE: 安全区域 {params['zone']} 不在 {', '.join(ZONES)} 之内")
        for key, zh in (("local_net", "本端内网网段"), ("remote_net", "对端内网网段")):
            if not params[key]:
                errors.append(f"GRE: {zh}不能为空")
                continue
            try:
                parse_net(params[key])
            except ValueError as e:
                errors.append(f"GRE: {zh} {e}")
        if params["gen_peer"]:
            for key, zh in (("peer_tunnel_ip", "对端隧道 IP"),
                            ("peer_default_next_hop", "对端默认路由下一跳")):
                if not params[key]:
                    errors.append(f"GRE: {zh}不能为空（生成对端脚本时必填）")
                    continue
                try:
                    ipaddress.ip_address(params[key])
                except ValueError:
                    errors.append(f"GRE: {zh} {params[key]} 不是合法 IP")
        return errors

    def render(self, params):
        if self.is_empty(params):
            return ""
        return fw_gre.generate(params)

    def render_summary(self, params):
        # 汇总只取本端：对端脚本属于另一台设备（与 GRE/BGP 同规则）
        return "" if self.is_empty(params) else fw_gre.generate_local(params)

    def summary_vlans(self, params):
        return set()

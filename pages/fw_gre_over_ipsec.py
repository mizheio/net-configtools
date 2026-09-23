"""防火墙 GRE over IPsec 页面（文档 5.9）

页面契约见 gui.py 顶部注释。本节封装顺序与 5.8 相反：先 GRE 封装、后 IPsec 加密 ——
ACL 匹配 permit gre 的公网流量、IPsec 挂公网物理口、remote-address 用对端公网 IP。
文档 5.9 末尾的「额外NAT策略配置」本页不生成，请用「安全策略」「NAT配置」页配置。
"""
import ipaddress
import tkinter as tk
from tkinter import ttk

from modules import fw_gre_over_ipsec as m
from modules.base import PORT_TYPES
from modules.fw_gre import SUBNET_MASKS  # 隧道掩码备选项复用 fw_gre 的那份，避免两处维护
from modules.fw_ipsec import parse_net

# 隧道所在安全域
ZONES = ("dmz", "trust", "untrust")


class FwGreOverIpsecPage:
    """GRE over IPsec（文档 5.9）：GRE 隧道 + IPsec 保护 GRE 流量 + 安全策略四段"""

    TITLE = "GRE over IPsec"

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
        self.v_tunnel_mask = self._field(row1, "子网掩码", SUBNET_MASKS[0], 17,
                                         editable=SUBNET_MASKS)
        row2 = ttk.Frame(box)
        row2.pack(fill=tk.X, pady=(3, 0))
        self.v_source = self._field(row2, "本端公网 source", "", 15, ip=True)
        self.v_destination = self._field(row2, "对端公网 destination", "", 15, ip=True)
        self.v_zone = self._field(row2, "安全区域", "dmz", 8, values=ZONES)

        # —— 感兴趣流（ACL 源目自动取上面两个公网地址）——
        box = self._section("感兴趣流")
        self.v_acl = self._field(box, "ACL 编号", "3000", 8)
        self.v_acl_rule = self._field(box, "规则号", "5", 6)

        # —— IPsec proposal / policy ——
        box = self._section("IPsec proposal / policy")
        self.v_ipsec_prop = self._field(box, "proposal 名", "tran1", 8)
        self.v_policy = self._field(box, "policy 名", "map1", 8)
        self.v_policy_seq = self._field(box, "序号", "10", 6)

        # —— IKE proposal / peer ——
        box = self._section("IKE proposal / peer")
        self.v_ike_prop = self._field(box, "IKE 编号", "10", 6)
        self.v_local_peer = self._field(box, "本端 peer 名", "ike1", 8)
        self.v_psk = self._field(box, "预共享密钥", "test123", 12)

        # —— 应用接口（公网口，IPsec 挂在这里）——
        box = self._section("应用接口")
        self.v_if_type = self._field(box, "公网接口", "GE", 6, values=PORT_TYPES)
        self.v_if_num = self._field(box, "", "1/0/0", 9)

        # —— 业务网段 ——
        box = self._section("业务网段")
        self.v_local_net = self._field(box, "本端内网网段", "", 18, ip=True)
        self.v_remote_net = self._field(box, "对端内网网段", "", 18, ip=True)

        # —— 对端设备（勾选“生成对端脚本”后展开）——
        self.peer_box = self._section("对端设备")
        self.v_peer_tunnel_num = self._field(self.peer_box, "对端隧道号", "", 6)
        self.v_peer_tunnel_ip = self._field(self.peer_box, "对端隧道 IP", "", 16, ip=True)
        self.v_peer_if_type = self._field(self.peer_box, "对端公网口", "GE", 6, values=PORT_TYPES)
        self.v_peer_if_num = self._field(self.peer_box, "", "", 9)

        self.note = ttk.Label(self.frame, foreground="gray", justify=tk.LEFT, text=(
            "先 GRE 封装、后加密。\n"
            "remote-address = 对端公网 IP。\n"
            "额外 NAT 策略本页不生成。\n"
            "算法按文档 5.9 写死。"))
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
            "acl_num": self.v_acl.get().strip(),
            "acl_rule": self.v_acl_rule.get().strip(),
            "ipsec_proposal": self.v_ipsec_prop.get().strip(),
            "policy_name": self.v_policy.get().strip(),
            "policy_seq": self.v_policy_seq.get().strip(),
            "ike_proposal": self.v_ike_prop.get().strip(),
            "local_peer": self.v_local_peer.get().strip(),
            "psk": self.v_psk.get().strip(),
            "if_type": self.v_if_type.get().strip(),
            "if_num": self.v_if_num.get().strip(),
            "local_net": self.v_local_net.get().strip(),
            "remote_net": self.v_remote_net.get().strip(),
            "gen_peer": self.gen_peer.get(),
            "peer_tunnel_num": self.v_peer_tunnel_num.get().strip(),
            "peer_tunnel_ip": self.v_peer_tunnel_ip.get().strip(),
            "peer_if_type": self.v_peer_if_type.get().strip(),
            "peer_if_num": self.v_peer_if_num.get().strip(),
        }
        params.update(m.DEFAULTS)  # 算法项写死，页面不暴露
        return params, []

    def is_empty(self, params):
        return not any([params["tunnel_ip"], params["source"], params["destination"]])

    def validate(self, params):
        # 整页未填时保持惰性，不阻塞“汇总生成全部”
        if self.is_empty(params):
            return []
        errors = []
        if not params["tunnel_num"]:
            errors.append("GRE over IPsec: 隧道号不能为空")
        for key, zh in (("tunnel_ip", "隧道 IP"), ("source", "本端公网 source"),
                        ("destination", "对端公网 destination")):
            if not params[key]:
                errors.append(f"GRE over IPsec: {zh}不能为空")
                continue
            try:
                ipaddress.ip_address(params[key])
            except ValueError:
                errors.append(f"GRE over IPsec: {zh} {params[key]} 不是合法 IP")
        if params["tunnel_mask"]:
            try:
                m.normalize_mask(params["tunnel_mask"])
            except ValueError:
                errors.append(f"GRE over IPsec: 子网掩码 {params['tunnel_mask']} 不是合法掩码")
        else:
            errors.append("GRE over IPsec: 子网掩码不能为空")
        if params["zone"] and params["zone"] not in ZONES:
            errors.append(f"GRE over IPsec: 安全区域 {params['zone']} "
                          f"不在 {', '.join(ZONES)} 之内")
        for key, zh in (("acl_num", "ACL 编号"), ("ike_proposal", "IKE 编号"),
                        ("local_peer", "本端 IKE peer 名"), ("psk", "预共享密钥"),
                        ("ipsec_proposal", "IPsec proposal 名"),
                        ("policy_name", "IPsec policy 名")):
            if not params[key]:
                errors.append(f"GRE over IPsec: {zh}不能为空")
        for key, zh in (("acl_rule", "ACL 规则号"), ("policy_seq", "IPsec policy 序号")):
            if params[key] and not params[key].isdigit():
                errors.append(f"GRE over IPsec: {zh} {params[key]} 必须是数字")
        if not params["if_num"]:
            errors.append("GRE over IPsec: 公网接口序号不能为空")
        for key, zh in (("local_net", "本端内网网段"), ("remote_net", "对端内网网段")):
            if not params[key]:
                errors.append(f"GRE over IPsec: {zh}不能为空")
                continue
            try:
                parse_net(params[key])
            except ValueError as e:
                errors.append(f"GRE over IPsec: {zh} {e}")
        if params["gen_peer"]:
            if not params["peer_tunnel_ip"]:
                errors.append("GRE over IPsec: 对端隧道 IP 不能为空（生成对端脚本时必填）")
            else:
                try:
                    ipaddress.ip_address(params["peer_tunnel_ip"])
                except ValueError:
                    errors.append(f"GRE over IPsec: 对端隧道 IP {params['peer_tunnel_ip']} "
                                  "不是合法 IP")
        return errors

    def render(self, params):
        if self.is_empty(params):
            return ""
        return m.generate(params)

    def render_summary(self, params):
        # 汇总只取本端：对端脚本属于另一台设备（与 GRE/BGP 同规则）
        return "" if self.is_empty(params) else m.generate_local(params)

    def summary_vlans(self, params):
        return set()

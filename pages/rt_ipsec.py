"""路由器 IPsec VPN 页面（文档 4.8 点到点 IPsec VPN）

页面契约见 gui.py 顶部注释。两端共用参数（ACL 编号、IKE/IPsec 名称、预共享密钥、
算法）只填一次，勾选"生成对端脚本"后展开对端段，源/目网段、remote-address、
接口与静态路由网段自动互换。算法按文档 4.8 写死、页面不暴露，取值见
modules/rt_ipsec.py 的 DEFAULTS；NAT 豁免为可选段，勾选后才生成。

「应用接口」节里另有一行"生成 ip address"勾选（默认不勾）：勾上后接口段会在
`interface X` 与 ` ipsec policy X` 之间多出一行 ` ip address <地址> <掩码>`，
此时本端接口 IP 与子网掩码必填；不勾则接口段与文档 4.8 一致，也不强制填接口 IP。
"""
import ipaddress
import tkinter as tk
from tkinter import ttk

from modules import rt_ipsec
from modules.base import PORT_TYPES
from widgets import RowsEditor

ROUTE_COLUMNS = [("network", "目的网段", 18, "ip"), ("mask", "掩码", 16, None),
                 ("next_hop", "下一跳", 16, "ip")]
NET_COLUMNS = [("network", "其他允许上网的网段", 24, "ip")]


class RouterIpsecPage:
    """路由器 IPsec VPN（文档 4.8）：本端 + 可选对端 + 可选 NAT 豁免"""

    TITLE = "IPsec VPN"

    def __init__(self, parent, app=None):
        self.frame = ttk.Frame(parent, padding=6)
        self.enabled = tk.BooleanVar(value=True)
        self.gen_peer = tk.BooleanVar(value=False)
        self.exempt = tk.BooleanVar(value=False)
        self.ip_addr_enable = tk.BooleanVar(value=False)
        self._ip_combos = []
        self._ip_values = []

        bar = ttk.Frame(self.frame)
        bar.pack(fill=tk.X, pady=(0, 4))
        ttk.Checkbutton(bar, text="生成对端脚本", variable=self.gen_peer).pack(side=tk.LEFT, padx=2)
        ttk.Checkbutton(bar, text="参与汇总", variable=self.enabled).pack(side=tk.RIGHT)

        # —— 感兴趣流 ——
        box = self._section("感兴趣流（ACL，对端源目自动互换）")
        self.v_acl = self._field(box, "ACL 编号", "3000", 8)
        self.v_acl_rule = self._field(box, "规则号", "5", 6)
        self.v_local_net = self._field(box, "本端网段", "", 18, ip=True)
        self.v_remote_net = self._field(box, "对端网段", "", 18, ip=True)

        # —— IPsec proposal / policy（算法全部写死，见 modules/rt_ipsec.py 的 DEFAULTS）——
        box = self._section("IPsec proposal / policy（算法取文档 4.8 标准块，全部写死）")
        self.v_ipsec_prop = self._field(box, "proposal 名", "1", 8)
        self.v_policy = self._field(box, "policy 名", "map1", 8)
        self.v_policy_seq = self._field(box, "序号", "1", 6)

        # —— IKE proposal / peer（算法同样写死）——
        box = self._section("IKE proposal / peer（算法取文档 4.8 标准块，全部写死）")
        self.v_ike_prop = self._field(box, "IKE 编号", "1", 6)
        self.v_local_peer = self._field(box, "本端 peer 名", "1", 8)
        self.v_peer_ip = self._field(box, "对端公网 IP", "", 16, ip=True)
        self.v_psk = self._field(box, "预共享密钥", "123456", 12)

        # —— 应用接口 ——
        box = self._section("应用接口（勾选后由本页生成 ip address，否则接口 IP 由“接口IP配置”页配置）")
        row1 = ttk.Frame(box)
        row1.pack(fill=tk.X)
        self.v_local_if_type = self._field(row1, "本端接口", "GE", 6, values=PORT_TYPES)
        self.v_local_if_num = self._field(row1, "", "0/0/0", 9)
        row2 = ttk.Frame(box)
        row2.pack(fill=tk.X, pady=(3, 0))
        ttk.Checkbutton(row2, text="生成 ip address",
                        variable=self.ip_addr_enable).pack(side=tk.LEFT, padx=2)
        self.v_local_ip = self._field(row2, "本端接口 IP", "", 14, ip=True)
        self.v_subnet_mask = self._field(row2, "子网掩码", rt_ipsec.SUBNET_MASKS[0], 14,
                                         editable=rt_ipsec.SUBNET_MASKS)

        # —— 静态路由 ——
        box = self._section("静态路由（指向对端内网，网段或下一跳为空的行跳过）")
        ttk.Button(box, text="添加路由", command=self.add_route).pack(anchor=tk.W, padx=2)
        self.routes = RowsEditor(box, ROUTE_COLUMNS)
        self.add_route()

        # —— NAT 豁免（可选段）——
        box = self._section("NAT 豁免（文档 4.8 第二段，勾选后才生成）")
        ttk.Checkbutton(box, text="生成 NAT 豁免段（deny 走 VPN 的流量，其余网段走 Easy IP）",
                        variable=self.exempt).pack(anchor=tk.W, padx=2)
        self.v_exempt_acl = self._field(box, "豁免 ACL 编号", "3001", 8)
        ttk.Button(box, text="添加其他上网网段",
                   command=self.add_exempt_net).pack(anchor=tk.W, padx=2, pady=(2, 0))
        self.exempt_nets = RowsEditor(box, NET_COLUMNS)

        # —— 对端设备（勾选“生成对端脚本”后展开）——
        self.peer_box = self._section(
            "对端设备（peer 名与接口留空则沿用本端；对端下一跳按对端侧实际填）")
        self.v_peer_peer = self._field(self.peer_box, "对端 peer 名", "", 8)
        self.v_peer_if_type = self._field(self.peer_box, "对端接口", "GE", 6, values=PORT_TYPES)
        self.v_peer_if_num = self._field(self.peer_box, "", "0/0/0", 9)
        ttk.Button(self.peer_box, text="添加对端路由",
                   command=self.add_peer_route).pack(anchor=tk.W, padx=2, pady=(2, 0))
        self.peer_routes = RowsEditor(self.peer_box, ROUTE_COLUMNS)
        ttk.Button(self.peer_box, text="添加对端上网网段",
                   command=self.add_peer_exempt_net).pack(anchor=tk.W, padx=2, pady=(2, 0))
        self.peer_exempt_nets = RowsEditor(self.peer_box, NET_COLUMNS)

        self.note = ttk.Label(self.frame, foreground="gray", justify=tk.LEFT, text=(
            "两端共用参数（ACL 编号、IKE/IPsec 名称、预共享密钥）只需填一次，"
            "对端脚本的源/目网段、remote-address、接口与路由网段自动互换。\n"
            "算法按文档 4.8 标准块写死、不开放修改：3des-cbc / md5 / group2，"
            "ESP 为 md5 + 3des；IKE 版本固定 v2，预共享密钥固定 simple 写法。\n"
            "接口段默认只出 interface + ipsec policy（接口 IP 用“接口IP配置”页配）；"
            "勾选“生成 ip address”后，接口下会多出一行 ip address，"
            "此时本端接口 IP 与子网掩码必填（掩码可手输 /24、24 等写法）。\n"
            "缩进一律 1 空格、接口段前不加 #（均照文档 4.8）。\n"
            "NAT 豁免最后一条 permit（本端网段）由程序自动追加；对端段按文档原文带 "
            "undo  nat outbound 2000。文档 4.8 标注需在模拟器审核，生成结果请在 eNSP 中验证。"))
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
            if self.gen_peer.get() and not self.peer_routes.rows:
                self.add_peer_route()
        else:
            self.peer_box.pack_forget()
        self.note.pack(fill=tk.X, pady=(4, 0))

    def add_route(self):
        self.routes.add({"mask": "255.255.255.0"})

    def add_peer_route(self):
        self.peer_routes.add({"mask": "255.255.255.0"})

    def add_exempt_net(self):
        self.exempt_nets.add()

    def add_peer_exempt_net(self):
        self.peer_exempt_nets.add()

    def set_lib_values(self, ip_list, vlan_list):
        self._ip_values = list(ip_list)
        for cb in self._ip_combos:
            cb["values"] = self._ip_values
        for editor in (self.routes, self.peer_routes, self.exempt_nets, self.peer_exempt_nets):
            editor.set_lib_values(ip_list, vlan_list)

    # ---------------------------------------------------------------- 契约
    def collect(self):
        params = {
            "acl_num": self.v_acl.get().strip(),
            "acl_rule": self.v_acl_rule.get().strip(),
            "local_net": self.v_local_net.get().strip(),
            "remote_net": self.v_remote_net.get().strip(),
            "ike_proposal": self.v_ike_prop.get().strip(),
            "local_peer": self.v_local_peer.get().strip(),
            "peer_ip": self.v_peer_ip.get().strip(),
            "psk": self.v_psk.get().strip(),
            "ipsec_proposal": self.v_ipsec_prop.get().strip(),
            "policy_name": self.v_policy.get().strip(),
            "policy_seq": self.v_policy_seq.get().strip(),
            "local_if_type": self.v_local_if_type.get().strip(),
            "local_if_num": self.v_local_if_num.get().strip(),
            "local_ip": self.v_local_ip.get().strip(),
            "ip_addr_enable": self.ip_addr_enable.get(),
            "subnet_mask": self.v_subnet_mask.get().strip(),
            "routes": self.routes.values(),
            "exempt": self.exempt.get(),
            "exempt_acl": self.v_exempt_acl.get().strip(),
            "extra_nets": self.exempt_nets.values(),
            "gen_peer": self.gen_peer.get(),
            "peer_peer": self.v_peer_peer.get().strip(),
            "peer_if_type": self.v_peer_if_type.get().strip(),
            "peer_if_num": self.v_peer_if_num.get().strip(),
            "peer_routes": self.peer_routes.values(),
            "peer_extra_nets": self.peer_exempt_nets.values(),
        }
        params.update(rt_ipsec.DEFAULTS)  # 算法项写死，页面不暴露
        return params, []

    def is_empty(self, params):
        return not any([params["local_net"], params["remote_net"],
                        params["local_ip"], params["peer_ip"]])

    def _check_routes(self, errors, rows, side):
        for row in rows:
            network = row.get("network", "")
            next_hop = row.get("next_hop", "")
            if network:
                try:
                    rt_ipsec.parse_net(f"{network} {row.get('mask', '')}")
                except ValueError as e:
                    errors.append(f"IPsec: {side}路由 {network} {e}")
                if not next_hop:
                    errors.append(f"IPsec: {side}路由 {network} 缺下一跳")
            if next_hop:
                try:
                    ipaddress.ip_address(next_hop)
                except ValueError:
                    errors.append(f"IPsec: {side}路由下一跳 {next_hop} 不是合法 IP")

    def _check_nets(self, errors, rows, side):
        for row in rows:
            network = row.get("network", "")
            if not network:
                continue
            try:
                rt_ipsec.parse_net(network)
            except ValueError as e:
                errors.append(f"IPsec: {side}豁免网段 {e}")

    def validate(self, params):
        # 整页未填时保持惰性，不阻塞“汇总生成全部”
        if self.is_empty(params):
            return []
        errors = []
        for key, zh in (("acl_num", "ACL 编号"), ("ike_proposal", "IKE 编号"),
                        ("local_peer", "本端 IKE peer 名"), ("psk", "预共享密钥"),
                        ("ipsec_proposal", "IPsec proposal 名"), ("policy_name", "IPsec policy 名"),
                        ("peer_ip", "对端公网 IP")):
            if not params[key]:
                errors.append(f"IPsec: {zh}不能为空")
        for key, zh in (("acl_rule", "ACL 规则号"), ("policy_seq", "IPsec policy 序号")):
            if params[key] and not params[key].isdigit():
                errors.append(f"IPsec: {zh} {params[key]} 必须是数字")
        for key, zh in (("local_net", "本端网段"), ("remote_net", "对端网段")):
            if not params[key]:
                errors.append(f"IPsec: {zh}不能为空")
                continue
            try:
                rt_ipsec.parse_net(params[key])
            except ValueError as e:
                errors.append(f"IPsec: {zh} {e}")
        try:
            ipaddress.ip_address(params["peer_ip"])
        except ValueError:
            errors.append(f"IPsec: 对端公网 IP {params['peer_ip'] or '(空)'} 不是合法 IP")
        # 本端接口 IP / 子网掩码：只在真正会被用到时才要求填（这也是它此前"填了不进脚本却必填"的修正）
        #   勾了"生成 ip address" -> 接口段要输出，IP 与掩码都必填
        #   只勾"生成对端脚本"    -> IP 用作对端脚本的 remote-address，必填；掩码用不到
        #   两个都没勾            -> 不填也不报错
        if params["ip_addr_enable"] or params["gen_peer"]:
            if not params["local_ip"]:
                errors.append("IPsec: 本端接口 IP 不能为空"
                              "（勾选“生成 ip address”或“生成对端脚本”时必填）")
            else:
                try:
                    rt_ipsec.normalize_ip(params["local_ip"])
                except ValueError as e:
                    errors.append(f"IPsec: 本端接口 IP {e}")
        if params["ip_addr_enable"]:
            if not params["subnet_mask"]:
                errors.append("IPsec: 子网掩码不能为空")
            else:
                try:
                    rt_ipsec.normalize_mask(params["subnet_mask"])
                except ValueError:
                    errors.append(f"IPsec: 子网掩码 {params['subnet_mask']} 不是合法掩码")
        if not params["local_if_num"]:
            errors.append("IPsec: 本端接口序号不能为空")
        self._check_routes(errors, params["routes"], "本端")
        if params["exempt"]:
            if not params["exempt_acl"].isdigit():
                errors.append(f"IPsec: 豁免 ACL 编号 {params['exempt_acl'] or '(空)'} 必须是数字")
            self._check_nets(errors, params["extra_nets"], "本端")
        if params["gen_peer"]:
            self._check_routes(errors, params["peer_routes"], "对端")
            if params["exempt"]:
                self._check_nets(errors, params["peer_extra_nets"], "对端")
        return errors

    def render(self, params):
        if self.is_empty(params):
            return ""
        return rt_ipsec.generate(params)

    def render_summary(self, params):
        # 汇总只取本端：对端脚本属于另一台设备（与 GRE/BGP 同规则）
        return "" if self.is_empty(params) else rt_ipsec.generate_local(params)

    def summary_vlans(self, params):
        return set()

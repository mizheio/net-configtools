"""防火墙页面：接口IP与安全域（文档 5.1）、NAT配置（文档 5.4）、安全策略（文档 5.2）、
IPsec VPN（文档 5.5）

页面契约见 gui.py 顶部注释。
FirewallIfPage：每行一个接口 = 接口类型(GE/ETH 下拉) + 序号 + IP + 子网掩码 +
安全区域（trust/untrust/dmz 只读下拉，留空 = 暂不加入域）。
NatPolicyPage：每行一条 NAT 策略 = 规则名 + 源/目的区域（可不限）+
源/目的地址（IP库下拉，归一为文档 5.4 的 "IP 反掩码"）+ 动作。
SecurityPolicyPage：每行一条策略 = 规则名 + 源域/目的域（下拉）+
源/目的地址（IP库下拉，兼容 /24、24、点分掩码写法，归一为 "IP 前缀长度"）+ 动作。
IpsecPage：点到点 IPsec VPN，字段按 感兴趣流 / IKE proposal / IKE peer /
IPsec proposal·policy / 应用接口 / 安全区域 分节平铺（两端共用参数只填一次，
算法项按文档 5.5 写死不开放），勾选"生成对端脚本"展开对端段，
一次输出 ##本端 / ##对端 两段配置。
生成走 modules/fw_if / fw_policy / fw_nat / fw_ipsec。
"""

import ipaddress
import tkinter as tk
from tkinter import ttk

from modules import fw_if, fw_ipsec, fw_nat, fw_policy
from modules.base import PORT_TYPES, port_name
from pages.interface import _normalize_mask

# 安全区域固定选项；空串 = 暂不加入安全域（只配 IP）
ZONES = ("trust", "untrust", "dmz", "")


class FirewallIfPage:
    TITLE = "接口IP与安全域"

    def __init__(self, parent, app=None):
        self.frame = ttk.Frame(parent, padding=6)
        self.rows = []
        self.enabled = tk.BooleanVar(value=True)
        self._ip_combos = []
        self._ip_values = []

        bar = ttk.Frame(self.frame)
        bar.pack(fill=tk.X, pady=(0, 4))
        ttk.Button(bar, text="添加接口配置", command=self.add_row).pack(side=tk.LEFT, padx=2)
        ttk.Checkbutton(bar, text="参与汇总", variable=self.enabled).pack(side=tk.RIGHT)

        head = ttk.Frame(self.frame)
        head.pack(fill=tk.X)
        ttk.Label(head, text="接口类型", width=10).grid(row=0, column=0, padx=2, sticky=tk.W)
        ttk.Label(head, text="序号", width=12).grid(row=0, column=1, padx=2, sticky=tk.W)
        ttk.Label(head, text="IP 地址", width=24).grid(row=0, column=2, padx=2, sticky=tk.W)
        ttk.Label(head, text="子网掩码", width=18).grid(row=0, column=3, padx=2, sticky=tk.W)
        ttk.Label(head, text="安全区域", width=14).grid(row=0, column=4, padx=2, sticky=tk.W)

        self.area = ttk.Frame(self.frame)
        self.area.pack(fill=tk.BOTH, expand=True)
        self.add_row()

    def add_row(self):
        first = not self.rows
        row = {
            "type": tk.StringVar(value="GE"),
            "num": tk.StringVar(value="1/0/0" if first else ""),
            "ip": tk.StringVar(),
            "mask": tk.StringVar(value="255.255.255.0"),
            "zone": tk.StringVar(value="trust"),
        }
        f = ttk.Frame(self.area)
        f.pack(fill=tk.X, pady=1)
        ttk.Combobox(f, textvariable=row["type"], values=PORT_TYPES,
                     width=7, state="readonly").pack(side=tk.LEFT, padx=2)
        ttk.Entry(f, textvariable=row["num"], width=10).pack(side=tk.LEFT, padx=2)
        ip_w = ttk.Combobox(f, textvariable=row["ip"], width=22, values=self._ip_values)
        ip_w.pack(side=tk.LEFT, padx=2)
        ttk.Entry(f, textvariable=row["mask"], width=16).pack(side=tk.LEFT, padx=2)
        zone_values = [z for z in ZONES if z] + ["（暂不入域）"]
        zone_w = ttk.Combobox(f, textvariable=row["zone"], width=10,
                              values=zone_values, state="readonly")
        zone_w.pack(side=tk.LEFT, padx=2)
        ttk.Button(f, text="删", width=3, command=lambda: self.del_row(row)).pack(side=tk.LEFT, padx=2)
        row["frame"] = f
        row["zone_w"] = zone_w
        self._ip_combos.append(ip_w)
        self.rows.append(row)

    def del_row(self, row):
        row["frame"].destroy()
        self.rows.remove(row)

    def set_lib_values(self, ip_list, vlan_list):
        self._ip_values = list(ip_list)
        for cb in self._ip_combos:
            cb["values"] = self._ip_values

    def collect(self):
        ifaces = []
        for row in self.rows:
            num = row["num"].get().strip()
            ip = row["ip"].get().strip()
            if not (num or ip):
                continue  # 整行未填，跳过
            zone = row["zone"].get().strip()
            ifaces.append({"type": row["type"].get(), "num": num, "ip": ip,
                           "mask": _normalize_mask(row["mask"].get()),
                           "zone": "" if zone == "（暂不入域）" else zone})
        return {"ifaces": ifaces}, []

    def validate(self, params):
        errors = []
        for idx, i in enumerate(params["ifaces"]):
            label = port_name(i["type"], i["num"]) if i["num"] else f"第{idx + 1}行"
            if not i["num"]:
                errors.append(f"{label}: 接口序号不能为空")
            try:
                ipaddress.ip_address(i["ip"])
            except ValueError:
                errors.append(f"{label}: IP {i['ip'] or '(空)'} 不是合法地址")
            try:
                ipaddress.ip_address(i["mask"])
            except ValueError:
                errors.append(f"{label}: 掩码 {i['mask'] or '(空)'} 不是合法掩码")
            if i["zone"] and i["zone"] not in fw_if.ZONE_ORDER:
                errors.append(f"{label}: 安全区域 {i['zone']} 不在 {', '.join(fw_if.ZONE_ORDER)} 之内")
        return errors

    def render(self, params):
        return fw_if.generate(params)

    def render_summary(self, params):
        return fw_if.generate(params)

    def summary_vlans(self, params):
        return set()

    def is_empty(self, params):
        return not params["ifaces"]


class SecurityPolicyPage:
    TITLE = "安全策略"

    def __init__(self, parent, app=None):
        self.frame = ttk.Frame(parent, padding=6)
        self.rows = []
        self.enabled = tk.BooleanVar(value=True)
        self._ip_combos = []
        self._ip_values = []

        bar = ttk.Frame(self.frame)
        bar.pack(fill=tk.X, pady=(0, 4))
        ttk.Button(bar, text="添加策略", command=self.add_row).pack(side=tk.LEFT, padx=2)
        ttk.Checkbutton(bar, text="参与汇总", variable=self.enabled).pack(side=tk.RIGHT)

        head = ttk.Frame(self.frame)
        head.pack(fill=tk.X)
        for col, (text, width) in enumerate(
                [("规则名", 10), ("源区域", 9), ("目的区域", 9),
                 ("源地址", 20), ("目的地址", 20), ("动作", 7)]):
            ttk.Label(head, text=text, width=width).grid(row=0, column=col, padx=2, sticky=tk.W)

        self.area = ttk.Frame(self.frame)
        self.area.pack(fill=tk.BOTH, expand=True)
        self.add_row()

        ttk.Label(self.frame, foreground="gray", justify=tk.LEFT,
                  text="地址写法兼容 192.168.10.0/24、192.168.10.0 24、192.168.10.0 255.255.255.0，"
                       "生成时统一为文档 5.2 的 \"IP 前缀长度\" 写法。\n"
                       "文档 5.2 标注\"需要在模拟器审核\"，生成结果请在 eNSP 中验证。"
                  ).pack(anchor=tk.W)

    def add_row(self):
        row = {
            "name": tk.StringVar(value=f"policy{len(self.rows) + 1}"),
            "src_zone": tk.StringVar(value="trust"),
            "dst_zone": tk.StringVar(value="untrust"),
            "src_addr": tk.StringVar(),
            "dst_addr": tk.StringVar(),
            "action": tk.StringVar(value="permit"),
        }
        f = ttk.Frame(self.area)
        f.pack(fill=tk.X, pady=1)
        ttk.Entry(f, textvariable=row["name"], width=10).pack(side=tk.LEFT, padx=2)
        for key in ("src_zone", "dst_zone"):
            ttk.Combobox(f, textvariable=row[key], values=[z for z in ZONES if z],
                         width=8, state="readonly").pack(side=tk.LEFT, padx=2)
        # 地址为可编辑下拉：下拉选 IP 库条目后可直接改掩码部分
        for key in ("src_addr", "dst_addr"):
            cb = ttk.Combobox(f, textvariable=row[key], width=16, values=self._ip_values)
            cb.pack(side=tk.LEFT, padx=2)
            self._ip_combos.append(cb)
        ttk.Combobox(f, textvariable=row["action"], values=list(fw_policy.ACTIONS),
                     width=7, state="readonly").pack(side=tk.LEFT, padx=2)
        ttk.Button(f, text="删", width=3, command=lambda: self.del_row(row)).pack(side=tk.LEFT, padx=2)
        row["frame"] = f
        self.rows.append(row)

    def del_row(self, row):
        row["frame"].destroy()
        self.rows.remove(row)

    def set_lib_values(self, ip_list, vlan_list):
        self._ip_values = list(ip_list)
        for cb in self._ip_combos:
            cb["values"] = self._ip_values

    def collect(self):
        rules = []
        for row in self.rows:
            name = row["name"].get().strip()
            src = row["src_addr"].get().strip()
            dst = row["dst_addr"].get().strip()
            if not (name or src or dst):
                continue  # 整行未填，跳过
            rules.append({
                "name": name,
                "src_zone": row["src_zone"].get().strip(),
                "dst_zone": row["dst_zone"].get().strip(),
                # 归一失败的地址原样带回，交由 validate 弹窗拦截，不在 collect 崩溃
                "src_addr": self._norm_addr(src),
                "dst_addr": self._norm_addr(dst),
                "action": row["action"].get().strip(),
            })
        return {"rules": rules}, []

    @staticmethod
    def _norm_addr(text):
        try:
            return fw_policy.normalize_addr(text)
        except ValueError:
            return text

    def validate(self, params):
        errors = []
        for idx, r in enumerate(params["rules"], 1):
            label = f"第{idx}行({r['name'] or '未命名'})"
            if not r["name"]:
                errors.append(f"{label}: 规则名不能为空")
            for key, zh in (("src_addr", "源地址"), ("dst_addr", "目的地址")):
                if not r[key]:
                    errors.append(f"{label}: {zh}不能为空")
                    continue
                try:
                    fw_policy.normalize_addr(r[key])
                except ValueError as e:
                    errors.append(f"{label}: {zh} {e}")
            if r["src_zone"] not in fw_if.ZONE_ORDER:
                errors.append(f"{label}: 源区域 {r['src_zone']} 不在 {', '.join(fw_if.ZONE_ORDER)} 之内")
            if r["dst_zone"] not in fw_if.ZONE_ORDER:
                errors.append(f"{label}: 目的区域 {r['dst_zone']} 不在 {', '.join(fw_if.ZONE_ORDER)} 之内")
            if r["action"] not in fw_policy.ACTIONS:
                errors.append(f"{label}: 动作 {r['action']} 不在 {', '.join(fw_policy.ACTIONS)} 之内")
        return errors

    def render(self, params):
        return fw_policy.generate(params)

    def render_summary(self, params):
        return fw_policy.generate(params)

    def summary_vlans(self, params):
        return set()

    def is_empty(self, params):
        return not params["rules"]


class NatPolicyPage:
    TITLE = "NAT配置"

    def __init__(self, parent, app=None):
        self.frame = ttk.Frame(parent, padding=6)
        self.rows = []
        self.enabled = tk.BooleanVar(value=True)
        self._ip_combos = []
        self._ip_values = []

        bar = ttk.Frame(self.frame)
        bar.pack(fill=tk.X, pady=(0, 4))
        ttk.Button(bar, text="添加策略", command=self.add_row).pack(side=tk.LEFT, padx=2)
        ttk.Checkbutton(bar, text="参与汇总", variable=self.enabled).pack(side=tk.RIGHT)

        head = ttk.Frame(self.frame)
        head.pack(fill=tk.X)
        for col, (text, width) in enumerate(
                [("规则名", 14), ("源区域", 10), ("目的区域", 10),
                 ("源地址", 20), ("目的地址(可空)", 20), ("动作", 15)]):
            ttk.Label(head, text=text, width=width).grid(row=0, column=col, padx=2, sticky=tk.W)

        self.area = ttk.Frame(self.frame)
        self.area.pack(fill=tk.BOTH, expand=True)
        self.add_row()

        ttk.Label(self.frame, foreground="gray", justify=tk.LEFT,
                  text="地址为 NAT 策略的反掩码写法：输入 /24、24、255.255.255.0 或直接 0.0.0.255，"
                       "生成统一为 \"IP 反掩码\"（文档 5.4）。\n"
                       "区域选\"（不限）\"或目的地址留空则该行不输出对应字段（如 VPN 豁免规则）；"
                       "NAT 豁免（no-nat）需排在源 NAT 之前，建议从上往下填写。"
                  ).pack(anchor=tk.W)

    def add_row(self):
        row = {
            "name": tk.StringVar(value=f"policy{len(self.rows) + 1}"),
            "src_zone": tk.StringVar(value="trust"),
            "dst_zone": tk.StringVar(value="untrust"),
            "src_addr": tk.StringVar(),
            "dst_addr": tk.StringVar(),
            "action": tk.StringVar(value="source-nat easy-ip"),
        }
        f = ttk.Frame(self.area)
        f.pack(fill=tk.X, pady=1)
        ttk.Entry(f, textvariable=row["name"], width=14).pack(side=tk.LEFT, padx=2)
        for key in ("src_zone", "dst_zone"):
            ttk.Combobox(f, textvariable=row[key], width=9, state="readonly",
                         values=[z for z in ZONES if z] + ["（不限）"]).pack(side=tk.LEFT, padx=2)
        for key in ("src_addr", "dst_addr"):
            cb = ttk.Combobox(f, textvariable=row[key], width=18, values=self._ip_values)
            cb.pack(side=tk.LEFT, padx=2)
            self._ip_combos.append(cb)
        ttk.Combobox(f, textvariable=row["action"], width=15, state="readonly",
                     values=list(fw_nat.ACTIONS)).pack(side=tk.LEFT, padx=2)
        ttk.Button(f, text="删", width=3, command=lambda: self.del_row(row)).pack(side=tk.LEFT, padx=2)
        row["frame"] = f
        self.rows.append(row)

    def del_row(self, row):
        row["frame"].destroy()
        self.rows.remove(row)

    def set_lib_values(self, ip_list, vlan_list):
        self._ip_values = list(ip_list)
        for cb in self._ip_combos:
            cb["values"] = self._ip_values

    def collect(self):
        rules = []
        for row in self.rows:
            name = row["name"].get().strip()
            src = row["src_addr"].get().strip()
            dst = row["dst_addr"].get().strip()
            if not (name or src or dst):
                continue  # 整行未填，跳过
            rules.append({
                "name": name,
                "src_zone": self._zone(row["src_zone"].get().strip()),
                "dst_zone": self._zone(row["dst_zone"].get().strip()),
                # 归一失败的地址原样带回，交由 validate 弹窗拦截，不在 collect 崩溃
                "src_addr": self._norm_addr(src),
                "dst_addr": self._norm_addr(dst),
                "action": row["action"].get().strip(),
            })
        return {"rules": rules}, []

    @staticmethod
    def _zone(text):
        return "" if text == "（不限）" else text

    @staticmethod
    def _norm_addr(text):
        try:
            return fw_nat.normalize_wildcard(text)
        except ValueError:
            return text

    def validate(self, params):
        errors = []
        for idx, r in enumerate(params["rules"], 1):
            label = f"第{idx}行({r['name'] or '未命名'})"
            if not r["name"]:
                errors.append(f"{label}: 规则名不能为空")
            if not r["src_addr"]:
                errors.append(f"{label}: 源地址不能为空")
            for key, zh in (("src_addr", "源地址"), ("dst_addr", "目的地址")):
                if r[key]:
                    try:
                        fw_nat.normalize_wildcard(r[key])
                    except ValueError as e:
                        errors.append(f"{label}: {zh} {e}")
            if r["src_zone"] and r["src_zone"] not in fw_if.ZONE_ORDER:
                errors.append(f"{label}: 源区域 {r['src_zone']} 不在 {', '.join(fw_if.ZONE_ORDER)} 之内")
            if r["dst_zone"] and r["dst_zone"] not in fw_if.ZONE_ORDER:
                errors.append(f"{label}: 目的区域 {r['dst_zone']} 不在 {', '.join(fw_if.ZONE_ORDER)} 之内")
            if r["action"] not in fw_nat.ACTIONS:
                errors.append(f"{label}: 动作 {r['action']} 不在 {', '.join(fw_nat.ACTIONS)} 之内")
        return errors

    def render(self, params):
        return fw_nat.generate(params)

    def render_summary(self, params):
        return fw_nat.generate(params)

    def summary_vlans(self, params):
        return set()

    def is_empty(self, params):
        return not params["rules"]


class IpsecPage:
    """点到点 IPsec VPN（文档 5.5）：两端共用参数只填一次，对端可一键带出"""

    TITLE = "IPsec VPN"

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

        # —— 感兴趣流 ——
        box = self._section("感兴趣流（ACL，对端源目自动互换）")
        self.v_acl = self._field(box, "ACL 编号", "3000", 8)
        self.v_acl_rule = self._field(box, "规则号", "5", 6)
        self.v_local_net = self._field(box, "本端网段", "", 18, ip=True)
        self.v_remote_net = self._field(box, "对端网段", "", 18, ip=True)

        # —— IKE proposal（算法全部写死，见 modules/fw_ipsec.py 的 DEFAULTS）——
        box = self._section("IKE proposal（算法取文档 5.5 标准块，authentication-method 固定 pre-share）")
        self.v_ike_prop = self._field(box, "编号", "10", 6)

        # —— IKE peer（对端公网 IP 即 peer 的 remote-address，同排显示）——
        box = self._section("IKE peer")
        self.v_local_peer = self._field(box, "本端 peer 名", "ike1", 10)
        self.v_psk = self._field(box, "预共享密钥", "test123", 14)
        self.v_peer_ip = self._field(box, "对端公网 IP", "", 16, ip=True)

        # —— IPsec proposal / policy（ESP 算法同样写死）——
        box = self._section("IPsec proposal / policy（算法取文档 5.5 标准块）")
        self.v_ipsec_prop = self._field(box, "proposal 名", "tran1", 9)
        self.v_policy = self._field(box, "policy 名", "map1", 8)
        self.v_policy_seq = self._field(box, "序号", "10", 6)

        # —— 应用接口 ——
        box = self._section("应用接口（接口 IP 由“接口IP与安全域”页配置）")
        self.v_local_if_type = self._field(box, "接口", "GE", 6, values=PORT_TYPES)
        self.v_local_if_num = self._field(box, "", "1/0/0", 9)
        self.v_local_ip = self._field(box, "本端接口 IP", "", 16, ip=True)

        # —— 安全区域 ——
        box = self._section("安全区域")
        self.v_local_zone = self._field(box, "内网区域", "trust", 8,
                                        values=[z for z in ZONES if z])
        self.v_remote_zone = self._field(box, "外网区域", "untrust", 8,
                                         values=[z for z in ZONES if z])

        # —— 对端设备（勾选“生成对端脚本”后展开）——
        self.peer_box = self._section("对端设备")
        self.v_peer_peer = self._field(self.peer_box, "对端 peer 名", "ike2", 10)
        self.v_peer_if_type = self._field(self.peer_box, "对端接口", "GE", 6, values=PORT_TYPES)
        self.v_peer_if_num = self._field(self.peer_box, "", "1/0/0", 9)

        self.note = ttk.Label(self.frame, foreground="gray", justify=tk.LEFT, text=(
            "两端共用参数（ACL 编号、IKE/IPsec 名称、预共享密钥）只需在本页填一次，"
            "对端脚本的源/目网段、remote-address、接口地址自动互换。\n"
            "算法按文档 5.5 标准块写死、不开放修改：aes-256 / group14 / sha2-256 / "
            "hmac-sha2-256（IKE 与 ESP 同套）。\n"
            "接口段只出 interface + ipsec policy，接口 IP 请用“接口IP与安全域”页配置，"
            "NAT 豁免请用“NAT配置”页。\n"
            "安全策略段按文档 5.5 原文生成（source-address ... mask ... 写法）；"
            "文档 5.5 标注需在模拟器审核，生成结果请在 eNSP 中验证。"))
        self.gen_peer.trace_add("write", lambda *_: self._sync_peer())
        self._sync_peer()

    def _section(self, title):
        box = ttk.LabelFrame(self.frame, text=f" {title} ", padding=4)
        box.pack(fill=tk.X, pady=3)
        return box

    def _field(self, parent, label, default="", width=16, values=None, ip=False):
        """在所在分节内平铺一个输入项；ip=True 用 IP 库可编辑下拉，values 用只读下拉"""
        var = tk.StringVar(value=default)
        f = ttk.Frame(parent)
        if label:
            ttk.Label(f, text=label).pack(side=tk.LEFT)
        if ip:
            cb = ttk.Combobox(f, textvariable=var, values=self._ip_values, width=width)
            cb.pack(side=tk.LEFT, padx=(2, 12))
            self._ip_combos.append(cb)
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

    def collect(self):
        params = {
            "acl_num": self.v_acl.get().strip(),
            "acl_rule": self.v_acl_rule.get().strip(),
            "local_net": self.v_local_net.get().strip(),
            "remote_net": self.v_remote_net.get().strip(),
            "ike_proposal": self.v_ike_prop.get().strip(),
            "psk": self.v_psk.get().strip(),
            "ipsec_proposal": self.v_ipsec_prop.get().strip(),
            "policy_name": self.v_policy.get().strip(),
            "policy_seq": self.v_policy_seq.get().strip(),
            "local_peer": self.v_local_peer.get().strip(),
            "local_if_type": self.v_local_if_type.get().strip(),
            "local_if_num": self.v_local_if_num.get().strip(),
            "local_ip": self.v_local_ip.get().strip(),
            "peer_ip": self.v_peer_ip.get().strip(),
            "local_zone": self.v_local_zone.get().strip(),
            "remote_zone": self.v_remote_zone.get().strip(),
            "gen_peer": self.gen_peer.get(),
            "peer_peer": self.v_peer_peer.get().strip(),
            "peer_if_type": self.v_peer_if_type.get().strip(),
            "peer_if_num": self.v_peer_if_num.get().strip(),
        }
        params.update(fw_ipsec.DEFAULTS)  # 算法项写死，页面不暴露
        return params, []

    def is_empty(self, params):
        return not any([params["local_net"], params["remote_net"],
                        params["local_ip"], params["peer_ip"]])

    def validate(self, params):
        # 整页未填时保持惰性，不阻塞“汇总生成全部”
        if self.is_empty(params):
            return []
        errors = []
        for key, zh in (("acl_num", "ACL 编号"), ("ike_proposal", "IKE proposal 编号"),
                        ("ipsec_proposal", "IPsec proposal 名"), ("policy_name", "IPsec policy 名"),
                        ("local_peer", "本端 IKE peer 名"), ("psk", "预共享密钥")):
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
                fw_ipsec.parse_net(params[key])
            except ValueError as e:
                errors.append(f"IPsec: {zh} {e}")
        for key, zh in (("local_ip", "本端接口 IP"), ("peer_ip", "对端公网 IP")):
            if not params[key]:
                errors.append(f"IPsec: {zh}不能为空")
                continue
            try:
                ipaddress.ip_address(params[key])
            except ValueError:
                errors.append(f"IPsec: {zh} {params[key]} 不是合法 IP")
        if not params["local_if_num"]:
            errors.append("IPsec: 本端接口序号不能为空")
        for key, zh in (("local_zone", "内网区域"), ("remote_zone", "外网区域")):
            if params[key] and params[key] not in fw_if.ZONE_ORDER:
                errors.append(f"IPsec: {zh} {params[key]} 不在 {', '.join(fw_if.ZONE_ORDER)} 之内")
        if params["gen_peer"]:
            if not params["peer_peer"]:
                errors.append("IPsec: 对端 IKE peer 名不能为空")
            if not params["peer_if_num"]:
                errors.append("IPsec: 对端接口序号不能为空")
        return errors

    def render(self, params):
        if self.is_empty(params):
            return ""
        return fw_ipsec.generate(params)

    def render_summary(self, params):
        # 汇总只取本端：对端脚本属于另一台设备（与 GRE/BGP 同规则）
        return "" if self.is_empty(params) else fw_ipsec.generate_local(params)

    def summary_vlans(self, params):
        return set()

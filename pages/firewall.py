"""防火墙页面：接口IP与安全域（文档 5.1）、NAT配置（文档 5.4）、安全策略（文档 5.2）

页面契约见 gui.py 顶部注释。
FirewallIfPage：每行一个接口 = 接口类型(GE/ETH 下拉) + 序号 + IP + 子网掩码 +
安全区域（trust/untrust/dmz 只读下拉，留空 = 暂不加入域）。
NatPolicyPage：每行一条 NAT 策略 = 规则名 + 源/目的区域（可不限）+
源/目的地址（IP库下拉，归一为文档 5.4 的 "IP 反掩码"）+ 动作。
SecurityPolicyPage：每行一条策略 = 规则名 + 源域/目的域（下拉）+
源/目的地址（IP库下拉，兼容 /24、24、点分掩码写法，归一为 "IP 前缀长度"）+ 动作。
生成走 modules/fw_if / fw_policy / fw_nat。
"""

import ipaddress
import tkinter as tk
from tkinter import ttk

from modules import fw_if, fw_nat, fw_policy
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

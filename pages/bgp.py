"""路由器 BGP 页面（文档 4.5 基础三场景）

无全局"本机 AS"：每行邻居自带 AS 号，每行即一台设备的配置依据。
EBGP 每两行为一条链路（两行互指）；IBGP 同 AS 行成组两两环回口互指；
RR 同 AS 行勾选一台反射器，对组内其余出 reflect-client。
生成结果按 AS 归并，每台设备一段（##AS <n> 注释）。
"""
import ipaddress
import tkinter as tk
from tkinter import ttk

from modules import bgp
from widgets import RowsEditor


class BgpPage:
    TITLE = "BGP"

    def __init__(self, parent, app=None):
        self.frame = ttk.Frame(parent, padding=6)
        self.enabled = tk.BooleanVar(value=True)
        bar = ttk.Frame(self.frame)
        bar.pack(fill=tk.X)
        ttk.Label(bar, text="BGP 邻居（每行自带 AS 号，生成结果按 AS 归并成段）").pack(side=tk.LEFT)
        ttk.Checkbutton(bar, text="参与汇总", variable=self.enabled).pack(side=tk.RIGHT)

        self._section("EBGP 邻居（每两行为一条链路：第一行=一端 AS+互联IP，第二行=另一端）",
                      "添加一端", self.ebgp_add)
        self.ebgp_editor = RowsEditor(self.frame, [
            ("as", "AS", 8, None), ("ip", "互联IP", 15, "ip"),
        ])

        self._section("IBGP 邻居（同 AS 的行组成一组，组内两两环回口互指）", "添加一端", self.ibgp_add)
        self.ibgp_editor = RowsEditor(self.frame, [
            ("as", "AS", 8, None), ("ip", "环回口IP", 15, "ip"),
            ("next_hop_local", "下一跳本机", 9, "check"),
        ])

        self._section("RR 反射器（同 AS 的行组成一组，勾选其中一台为 RR，其余为客户端）", "添加一端", self.rr_add)
        self.rr_editor = RowsEditor(self.frame, [
            ("as", "AS", 8, None), ("ip", "环回口IP", 15, "ip"),
            ("is_rr", "RR反射器", 9, "check"),
        ])

        ttk.Label(self.frame, text="IBGP/RR 组内建邻固定 connect-interface LoopBack0；IBGP 行勾\"下一跳本机\"出 next-hop-local"
                                   "（该行设备同时跑 EBGP 时需要）。",
                  foreground="gray").pack(anchor=tk.W)
        self.ebgp_add()
        self.ebgp_add()
        self.ibgp_add()
        self.ibgp_add()
        self.rr_add()
        self.rr_add()

    def _section(self, text, button_text, command):
        f = ttk.Frame(self.frame)
        f.pack(fill=tk.X, pady=(8, 0))
        ttk.Label(f, text=text).pack(side=tk.LEFT)
        ttk.Button(f, text=button_text, command=command).pack(side=tk.LEFT, padx=6)

    def ebgp_add(self):
        self.ebgp_editor.add()

    def ibgp_add(self):
        self.ibgp_editor.add()

    def rr_add(self):
        self.rr_editor.add()

    def set_lib_values(self, ip_list, vlan_list):
        for editor in (self.ebgp_editor, self.ibgp_editor, self.rr_editor):
            editor.set_lib_values(ip_list, vlan_list)

    def collect(self):
        return {"ebgp_peers": self.ebgp_editor.values(),
                "ibgp_peers": self.ibgp_editor.values(),
                "rr_clients": self.rr_editor.values()}, []

    def validate(self, params):
        errors = []
        filled_ebgp = 0
        for key, label in (("ebgp_peers", "EBGP"), ("ibgp_peers", "IBGP"), ("rr_clients", "RR")):
            for row in params[key]:
                as_num, ip = row["as"].strip(), row["ip"].strip()
                if not as_num and not ip:
                    continue
                if not as_num or not ip:
                    errors.append(f"BGP: {label} 行的 AS 和 IP 需都填写")
                    continue
                if not as_num.isdigit():
                    errors.append(f"BGP: {label} 的 AS 号 {as_num} 必须是数字")
                try:
                    ipaddress.ip_address(ip)
                except ValueError:
                    errors.append(f"BGP: {label} 的 IP {ip} 不是合法IP")
                if key == "ebgp_peers":
                    filled_ebgp += 1
        if filled_ebgp % 2 == 1:
            errors.append("BGP: EBGP 每两行为一条链路，当前已填行数为奇数")
        rr_groups = {}
        for row in params["rr_clients"]:
            as_num = row["as"].strip()
            if as_num.isdigit() and row["ip"].strip():
                rr_groups.setdefault(as_num, 0)
                if row["is_rr"]:
                    rr_groups[as_num] += 1
        for as_num, cnt in rr_groups.items():
            if cnt != 1:
                errors.append(f"BGP: RR 组 AS {as_num} 需要恰好勾选一台 RR 反射器（当前 {cnt} 台）")
        return errors

    def render(self, params):
        return bgp.generate(params)

    def render_summary(self, params):
        return bgp.generate(params)

    def summary_vlans(self, params):
        return set()

    def is_empty(self, params):
        has_ebgp = any(row["ip"] or row["as"] for row in params["ebgp_peers"])
        has_ibgp = any(row["ip"] or row["as"] for row in params["ibgp_peers"])
        has_rr = any(row["ip"] or row["as"] for row in params["rr_clients"])
        return not (has_ebgp or has_ibgp or has_rr)

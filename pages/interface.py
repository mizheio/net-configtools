"""路由器页面：接口IP配置

页面契约见 gui.py 顶部注释。布局对齐交换机的三层网关页：
每行一个接口 = 接口类型(GE/ETH 下拉) + 序号 + IP + 子网掩码 + 描述(可选)，
"添加接口配置"逐行加，"删"逐行删。
"""

import ipaddress
import tkinter as tk
from tkinter import ttk

from modules import router_if
from modules.base import PORT_TYPES, port_name


def _normalize_mask(mask):
    """兼容 /24、24 两种前缀写法，统一转成点分十进制掩码"""
    mask = mask.strip().lstrip("/")
    if mask.isdigit():
        return str(ipaddress.ip_network(f"0.0.0.0/{int(mask)}").netmask)
    return mask


class InterfacePage:
    TITLE = "接口IP配置"

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
        ttk.Label(head, text="描述（可选）", width=20).grid(row=0, column=4, padx=2, sticky=tk.W)

        self.area = ttk.Frame(self.frame)
        self.area.pack(fill=tk.BOTH, expand=True)
        self.add_row()

    def add_row(self):
        first = not self.rows
        row = {
            "type": tk.StringVar(value="GE"),
            "num": tk.StringVar(value="0/0/0" if first else ""),
            "ip": tk.StringVar(),
            "mask": tk.StringVar(value="255.255.255.0"),
            "desc": tk.StringVar(),
        }
        f = ttk.Frame(self.area)
        f.pack(fill=tk.X, pady=1)
        ttk.Combobox(f, textvariable=row["type"], values=PORT_TYPES,
                     width=7, state="readonly").pack(side=tk.LEFT, padx=2)
        ttk.Entry(f, textvariable=row["num"], width=10).pack(side=tk.LEFT, padx=2)
        ip_w = ttk.Combobox(f, textvariable=row["ip"], width=22, values=self._ip_values)
        ip_w.pack(side=tk.LEFT, padx=2)
        ttk.Entry(f, textvariable=row["mask"], width=16).pack(side=tk.LEFT, padx=2)
        ttk.Entry(f, textvariable=row["desc"], width=18).pack(side=tk.LEFT, padx=2)
        ttk.Button(f, text="删", width=3, command=lambda: self.del_row(row)).pack(side=tk.LEFT, padx=2)
        row["frame"] = f
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
            desc = row["desc"].get().strip()
            if not (num or ip or desc):
                continue  # 整行未填，跳过
            ifaces.append({"type": row["type"].get(), "num": num, "ip": ip,
                           "mask": _normalize_mask(row["mask"].get()), "desc": desc})
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
        return errors

    def render(self, params):
        return router_if.generate(params)

    def render_summary(self, params):
        return router_if.generate(params)

    def summary_vlans(self, params):
        return set()

    def is_empty(self, params):
        return not params["ifaces"]

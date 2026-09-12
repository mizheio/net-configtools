"""扩展工具页面：子网计算（网段划分计算器）

页面契约见 gui.py 顶部注释。四种模式单选：
  1) 划分为 N 个子网        2) 每个子网需要 N 个信息点
  3) 查询本网段信息         4) 按部门分配（自定义每部门信息点，出子网划分表）
计算口径见 modules/subnet_calc.py docstring。
本页是计算工具，不生成设备配置：enabled 默认 False、is_empty 恒真、
render_summary 恒空，"汇总生成全部"永远不会把计算文本混进配置脚本。
输出走 app.set_preview 到底部预览区，可直接复制/保存。
"""
import tkinter as tk
from tkinter import ttk, messagebox

from modules import subnet_calc
from widgets import RowsEditor


class SubnetCalcPage:
    TITLE = "子网计算"

    def __init__(self, parent, app=None):
        self.frame = ttk.Frame(parent, padding=6)
        self.app = app
        self.enabled = tk.BooleanVar(value=False)
        self.mode = tk.StringVar(value="count")

        bar = ttk.Frame(self.frame)
        bar.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(bar, text="网段:").pack(side=tk.LEFT)
        self.net_var = tk.StringVar(value="192.168.10.0/24")
        ttk.Entry(bar, textvariable=self.net_var, width=26).pack(side=tk.LEFT, padx=(2, 10))
        ttk.Button(bar, text="计 算", command=self.do_calc).pack(side=tk.LEFT, padx=4)
        ttk.Checkbutton(bar, text="参与汇总", variable=self.enabled).pack(side=tk.RIGHT)

        opts = ttk.Frame(self.frame)
        opts.pack(fill=tk.X, pady=(2, 4))
        ttk.Radiobutton(opts, text="划分为", variable=self.mode, value="count",
                        command=self._toggle).pack(side=tk.LEFT)
        self.count_var = tk.StringVar(value="4")
        ttk.Entry(opts, textvariable=self.count_var, width=7).pack(side=tk.LEFT, padx=(2, 2))
        ttk.Label(opts, text="个子网").pack(side=tk.LEFT, padx=(0, 14))

        ttk.Radiobutton(opts, text="每个子网需要", variable=self.mode, value="points",
                        command=self._toggle).pack(side=tk.LEFT)
        self.points_var = tk.StringVar(value="50")
        ttk.Entry(opts, textvariable=self.points_var, width=7).pack(side=tk.LEFT, padx=(2, 2))
        ttk.Label(opts, text="个信息点").pack(side=tk.LEFT, padx=(0, 14))

        ttk.Radiobutton(opts, text="查询本网段信息", variable=self.mode, value="info",
                        command=self._toggle).pack(side=tk.LEFT, padx=(0, 14))
        ttk.Radiobutton(opts, text="按部门分配（划分表）", variable=self.mode, value="alloc",
                        command=self._toggle).pack(side=tk.LEFT)

        # 模式四专用：部门表（选"按部门分配"时显示）
        self.dept_frame = ttk.LabelFrame(self.frame, text=" 部门表（信息点数必填，部门名/VLAN 选填） ")
        dbar = ttk.Frame(self.dept_frame)
        dbar.pack(fill=tk.X, pady=(2, 0))
        ttk.Button(dbar, text="添加部门", command=lambda: self.editor.add()).pack(side=tk.LEFT, padx=2)
        self.editor = RowsEditor(self.dept_frame, columns=[
            ("name", "部门名", 12, None),
            ("points", "信息点数", 9, None),
            ("vlan", "VLAN(选填)", 8, None),
        ])
        self.editor.add({"name": "", "points": "", "vlan": ""})
        self.hint = ttk.Label(self.frame, foreground="gray", justify=tk.LEFT,
                              text="网段支持 192.168.10.0/24 或 192.168.10.0 255.255.255.0 两种写法，"
                                   "填主机地址自动按所在网段算；\n"
                                   "信息点数 = 可用主机数（扣网络/广播地址）；个数/点数不是 2 的幂时向上取整，"
                                   "划分最小到 /30；按部门分配时网关取每段第一个可用地址，\n"
                                   "子网按边界对齐切分，建议信息点从大到小填写以减少碎片。")
        # hint 先占位，显示部门表时用 before= 插到它前面
        self.hint.pack(anchor=tk.W)

    def _toggle(self):
        """按部门分配时在提示行上方展开部门表，其余模式收起"""
        if self.mode.get() == "alloc":
            self.dept_frame.pack(fill=tk.X, before=self.hint)
        else:
            self.dept_frame.pack_forget()

    # ---------- 计算入口（与"生成当前模块"共用 collect -> validate -> render） ----------
    def do_calc(self):
        params, errors = self.collect()
        errors += self.validate(params)
        if errors:
            messagebox.showwarning("无法计算", "\n".join(errors))
            return
        if self.app:
            self.app.set_preview(self.render(params))

    def collect(self):
        # 部门表整行全空的跳过，校验/渲染口径一致
        depts = [r for r in self.editor.values() if any(str(v).strip() for v in r.values())]
        return {
            "net": self.net_var.get().strip(),
            "mode": self.mode.get(),
            "count": self.count_var.get().strip(),
            "points": self.points_var.get().strip(),
            "depts": depts,
        }, []

    def validate(self, params):
        errors = []
        try:
            net = subnet_calc.parse_net(params["net"])
        except ValueError as e:
            return [str(e)]
        if params["mode"] == "count":
            if not params["count"].isdigit():
                errors.append(f"子网个数 {params['count'] or '(空)'} 需为正整数")
            else:
                try:
                    subnet_calc.plan_prefix_by_count(net, int(params["count"]))
                except ValueError as e:
                    errors.append(str(e))
        elif params["mode"] == "points":
            if not params["points"].isdigit():
                errors.append(f"信息点数 {params['points'] or '(空)'} 需为正整数")
            else:
                try:
                    subnet_calc.plan_prefix_by_points(net, int(params["points"]))
                except ValueError as e:
                    errors.append(str(e))
        elif params["mode"] == "alloc":
            if not params["depts"]:
                errors.append("请先在部门表里至少填写一行（信息点数必填）")
            for seq, d in enumerate(params["depts"], 1):
                if not str(d["points"]).strip().isdigit():
                    name = d["name"] or f"部门{seq}"
                    errors.append(f"第 {seq} 行（{name}）信息点数需为正整数")
            if not errors:
                try:
                    subnet_calc.alloc_departments(net, params["depts"])
                except ValueError as e:
                    errors.append(str(e))
        return errors

    def render(self, params):
        return subnet_calc.render_calc(params)

    # ---------- 契约：本页永不参与汇总 ----------
    def render_summary(self, params):
        return ""

    def summary_vlans(self, params):
        return set()

    def is_empty(self, params):
        return True

    def set_lib_values(self, ip_list, vlan_list):
        pass  # 网段直接手填/手改，不依赖 IP 库下拉

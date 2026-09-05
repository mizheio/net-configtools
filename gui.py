"""主窗口骨架：左侧 IP/VLAN 库 + 顶部模块页签 + 底部输出预览

页面清单来自 pages/__init__.py 的 CATEGORY_PAGES 注册表，本文件不硬编码任何页面。
页面契约（pages/ 下每个页类固定实现）：
  TITLE                            页签标题
  collect()  -> (params, errors)   收集表单值
  validate(params) -> errors       校验
  render(params) -> str            单页生成（可含 vlan batch 头）
  render_summary(params) -> str    汇总用正文（vlan batch 由 App 统一放头部）
  summary_vlans(params) -> set     本页用到的 VLAN，供汇总头部去重
  set_lib_values(ip_list, vlan_list)
  enabled (tk.BooleanVar)          是否参与汇总
  is_empty(params) -> bool（可选） 汇总时跳过空页
生成按钮固定流程：collect -> validate -> generate -> 预览区
"""
import json
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

import variables as varlib
from modules import eth_trunk, vrrp
from modules.base import render_vlan_batch
from pages import CATEGORY_PAGES
from pages.switch import EthTrunkPage, VrrpPage
from widgets import ScrollFrame
from version import __version__


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


# ============================================================ 主窗口
class App:
    def __init__(self, root):
        self.root = root
        root.title(f"华为 eNSP 配置生成工具 v{__version__}")
        root.geometry("1020x720")

        paned = ttk.PanedWindow(root, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True)

        top = ttk.PanedWindow(paned, orient=tk.HORIZONTAL)
        paned.add(top, weight=3)

        self.lib_panel = LibraryPanel(top, on_change=self._sync_lib)
        top.add(self.lib_panel.frame, weight=1)

        right = ttk.Frame(top)
        top.add(right, weight=3)

        # 设备类别切换：页签按 CATEGORY_PAGES 过滤，页面实例常驻（切走再切回不丢表单）
        bar = ttk.Frame(right)
        bar.pack(fill=tk.X)
        ttk.Label(bar, text="设备类型:").pack(side=tk.LEFT)
        self.category_var = tk.StringVar(value="交换机")
        self.category_box = ttk.Combobox(bar, textvariable=self.category_var,
                                         values=tuple(CATEGORY_PAGES), width=8, state="readonly")
        self.category_box.pack(side=tk.LEFT, padx=(2, 8))
        self.category_box.bind("<<ComboboxSelected>>", lambda *_: self._rebuild_tabs())

        self.nb = ttk.Notebook(right)
        self.nb.pack(fill=tk.BOTH, expand=True)

        # 按注册表装配页面；双栖页面（DHCP/OSPF/ACL）在两个类别间共享同一实例。
        # 默认每页包一层 ScrollFrame 支持上下滚动；OWN_SCROLL 页（接口VLAN）自带行区滚动
        self._page_by_cls = {}
        self._page_wrap = {}
        for category, classes in CATEGORY_PAGES.items():
            for cls in classes:
                if cls not in self._page_by_cls:
                    if getattr(cls, "OWN_SCROLL", False):
                        page = cls(self.nb, app=self)
                        wrap = None
                    else:
                        wrap = ScrollFrame(self.nb)
                        page = cls(wrap.inner, app=self)
                        page.frame.pack(fill=tk.BOTH, expand=True)
                    self._page_by_cls[cls] = page
                    self._page_wrap[page] = wrap
        self._rebuild_tabs()
        self._sync_lib()

        # 滚轮统一路由：从指针下的控件向上找最近的滚动画布（含接口VLAN页自带画布）
        root.bind_all("<MouseWheel>", self._on_wheel)

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

    # ---------- 页签装配 ----------
    def _current_pages(self):
        """当前设备类别的页面实例列表（页签顺序即注册表顺序）"""
        return [self._page_by_cls[cls] for cls in CATEGORY_PAGES[self.category_var.get()]]

    def _rebuild_tabs(self):
        print(f"Rebuilding tabs for category: {self.category_var.get()}")
        selected = self.nb.select()
        last_title = self.nb.tab(selected, "text").strip() if selected else None
        tabs = self.nb.tabs()
        print(f"Current tabs: {tabs}")
        if tabs:
            for tab in tabs[:]:
                print(f"Forgetting tab: {tab}")
                self.nb.forget(tab)
        current_pages = self._current_pages()
        print(f"Current pages: {[p.TITLE for p in current_pages]}")
        for page in current_pages:
            print(f"Adding page: {page.TITLE}")
            self.nb.add(self._page_wrap.get(page) or page.frame, text=f" {page.TITLE} ")
        if last_title:
            for i in range(self.nb.index("end")):
                if self.nb.tab(i, "text").strip() == last_title:
                    self.nb.select(i)
                    print(f"Restoring last selected tab: {last_title}")
                    break

    def _sync_lib(self):
        """库变化时把 IP / VLAN 选项刷新到所有页面的下拉框"""
        lib = self.lib_panel.lib
        for page in self._page_by_cls.values():
            page.set_lib_values(lib["ip"], lib["vlan"])

    def _on_wheel(self, event):
        """滚轮统一路由：指针下的控件向上找最近的 Canvas，找到就滚动它。
        输出预览 Text、库面板 Treeview 等自带滚动的控件走各自的原生滚动。"""
        w = self.root.winfo_containing(event.x_root, event.y_root)
        if w is None or w.winfo_toplevel() is not self.root:
            return  # 下拉列表、弹窗等其他 toplevel 不接管
        while w is not None:
            if isinstance(w, tk.Canvas):
                w.yview_scroll(int(-event.delta / 120), "units")
                return
            w = w.master

    # ---------- 生成流程：collect -> validate -> generate ----------
    def _prepare(self, page):
        params, errors = page.collect()
        errors += page.validate(params)
        return params, errors

    def generate_current(self):
        page = self._current_pages()[self.nb.index(self.nb.select())]
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

    def generate_vrrp_device(self, target):
        """VRRP 页专用按钮：生成主、备之一，或在预览中并列显示两份脚本。"""
        page = self._page_by_cls[VrrpPage]
        params, errors = self._prepare(page)
        if errors:
            messagebox.showwarning("无法生成", "\n".join(errors))
            return
        if target == "pair":
            text = vrrp.generate_pair(params)
        else:
            text = vrrp.generate_device_full(params, target)
        if not text.strip():
            messagebox.showinfo("提示", "请至少填写一行 VRRP VLAN 规划")
            return
        self.last_params = {"vrrp": params, "target": target}
        self.set_preview(text)

    
    def generate_all(self):
        """按当前设备类别汇总：正文拼接，VLAN 去重后统一放头部 vlan batch"""
        blocks, errors, vlans, all_params = [], [], set(), {}
        for page in self._current_pages():
            if not page.enabled.get():
                continue
            params, errs = self._prepare(page)
            errors += errs
            if getattr(page, "is_empty", None) and page.is_empty(params):
                continue
            block = page.render_summary(params)
            if block:
                all_params[page.TITLE] = params
                blocks.append(block)
                vlans |= page.summary_vlans(params)

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

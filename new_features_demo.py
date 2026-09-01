#!/usr/bin/env python3
"""
华为eNSP配置工具新功能演示

此脚本展示了路由器接口IP配置页面的新功能：
1. 支持多个接口配置的添加和删除
2. 每个接口可以选择GE或ETH类型
3. 支持可选的VLAN绑定和描述功能
"""

import sys
import tkinter as tk
from tkinter import ttk, messagebox
sys.path.append('.')

from pages.interface import InterfacePage
from gui import App


def demo_new_features():
    """演示新功能"""
    print("=== 华为eNSP配置工具新功能演示 ===\n")
    
    # 创建主窗口
    root = tk.Tk()
    root.title("新功能演示")
    root.geometry("800x600")
    
    # 创建主应用实例
    app = App(root)
    
    # 显示欢迎信息
    welcome_text = """
🎉 华为eNSP配置工具新功能演示

✨ 新增功能：
1. 交换机链路聚合支持GE/ETH接口类型自由选择
2. 路由器接口IP配置支持动态添加多个接口
3. 每个接口支持可选的VLAN绑定和描述功能

📋 使用方法：
1. 在"路由器"标签页中找到"接口IP配置"
2. 点击"添加接口配置"按钮添加新的接口
3. 为每个接口选择接口类型(GE/ETH)和编号
4. 设置IP地址、可选的VLAN和描述
5. 点击"生成当前模块"查看配置结果

💡 提示：
- 支持从IP/VLAN库中快速选择值
- 可以随时删除不需要的接口配置
- 生成的配置可以直接粘贴到eNSP中使用
"""
    
    # 创建演示界面
    demo_frame = ttk.Frame(root, padding=10)
    demo_frame.pack(fill=tk.BOTH, expand=True)
    
    # 添加欢迎文本
    text_widget = tk.Text(demo_frame, wrap=tk.WORD, font=("微软雅黑", 10))
    text_widget.pack(fill=tk.BOTH, expand=True)
    text_widget.insert(1.0, welcome_text)
    text_widget.config(state=tk.DISABLED)
    
    # 添加按钮框架
    button_frame = ttk.Frame(demo_frame)
    button_frame.pack(fill=tk.X, pady=10)
    
    # 功能测试按钮
    def show_instructions():
        """显示使用说明"""
        instructions = """
🎯 新功能使用说明

✅ 交换机链路聚合功能：
- 已支持GE和ETH接口类型自由选择
- 在链路聚合页面可以选择接口类型和编号

✅ 路由器接口IP配置功能：
- 支持动态添加多个接口配置
- 每个接口可选择GE/ETH类型
- 支持可选的VLAN绑定和描述功能
- 可随时添加、删除接口配置

📋 使用步骤：
1. 在主界面切换到"路由器"设备类型
2. 选择"接口IP配置"页签
3. 点击"添加接口配置"按钮
4. 选择接口类型(GE/ETH)和编号
5. 设置IP地址、可选VLAN和描述
6. 重复步骤3-5添加更多接口
7. 点击"生成当前模块"查看配置结果

💡 提示：
- 生成的配置可直接复制到eNSP中使用
- 支持从左侧IP/VLAN库中选择值
- 可以随时删除不需要的接口配置
        """
        messagebox.showinfo("新功能使用说明", instructions)
    
    # 添加按钮
    ttk.Button(button_frame, text="查看使用说明", command=show_instructions).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="切换到接口配置页", 
              command=lambda: app.notebook.select("接口IP配置")).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="测试基本配置", command=lambda: messagebox.showinfo("测试", "请在界面中手动测试基本配置功能")).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="测试多接口配置", command=lambda: messagebox.showinfo("测试", "请在界面中手动测试多接口配置功能")).pack(side=tk.LEFT, padx=5)
    
    # 运行应用
    root.mainloop()


if __name__ == "__main__":
    demo_new_features()
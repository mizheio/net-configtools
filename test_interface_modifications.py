#!/usr/bin/env python3
"""测试路由器接口IP配置新功能"""

import sys
sys.path.append('.')

from pages.interface import InterfacePage

def test_interface_page():
    """测试接口页面功能"""
    print("=== 测试路由器接口IP配置页面 ===")
    
    # 创建模拟界面（不显示窗口）
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()  # 隐藏窗口
    
    # 创建接口页面
    interface_page = InterfacePage(root)
    
    # 设置库值
    interface_page.set_lib_values(["192.168.1.0", "192.168.2.0", "192.168.10.0"], 
                                ["10", "20", "100", "110"])
    
    # 测试1：基本配置测试
    print("\n--- 测试1：基本接口配置 ---")
    # 清空现有配置，只添加一个
    interface_page.clear_all()
    interface_page.add_interface_config()
    
    # 设置第一个配置的值
    widget_data = interface_page.config_widgets[0]
    widget_data['interface_field'].set("GE", "0/0/0")
    widget_data['ip_entry'].delete(0, tk.END)
    widget_data['ip_entry'].insert(0, "192.168.1.1/24")
    widget_data['vlan_var'].set("10")
    widget_data['desc_entry'].delete(0, tk.END)
    widget_data['desc_entry'].insert(0, "管理接口")
    
    # 收集参数
    params, errors = interface_page.collect()
    
    print(f"收集参数: {params}")
    print(f"错误信息: {errors}")
    
    if params and len(params) == 1 and not errors:
        print("✅ 基本配置测试通过")
        print(f"生成的配置:\n{interface_page.render(params)}")
    else:
        print("❌ 基本配置测试失败")
    
    # 测试2：多接口配置测试
    print("\n--- 测试2：多接口配置 ---")
    
    # 清空并添加三个配置
    interface_page.clear_all()
    interface_page.add_interface_config()
    interface_page.add_interface_config()
    interface_page.add_interface_config()
    
    # 设置三个配置的值
    configs = [
        ("GE", "0/0/0", "192.168.1.1/24", "10", "管理接口"),
        ("GE", "0/0/1", "192.168.2.1/24", "20", ""),
        ("GE", "0/0/2", "10.1.1.1/24", "100", "业务接口")
    ]
    
    for i, (port_type, num, ip, vlan, desc) in enumerate(configs):
        widget_data = interface_page.config_widgets[i]
        widget_data['interface_field'].set(port_type, num)
        widget_data['ip_entry'].delete(0, tk.END)
        widget_data['ip_entry'].insert(0, ip)
        if vlan:
            widget_data['vlan_var'].set(vlan)
        if desc:
            widget_data['desc_entry'].delete(0, tk.END)
            widget_data['desc_entry'].insert(0, desc)
    
    # 收集参数
    params, errors = interface_page.collect()
    
    print(f"收集参数: {params}")
    print(f"错误信息: {errors}")
    
    if params and len(params) == 3 and not errors:
        print("✅ 多接口配置测试通过")
        print(f"生成的配置:\n{interface_page.render(params)}")
        print(f"摘要: {interface_page.render_summary(params)}")
        print(f"VLAN集合: {interface_page.summary_vlans(params)}")
    else:
        print("❌ 多接口配置测试失败")
        print(f"配置数量: {len(params) if params else 0}")
    
    # 测试3：错误处理测试
    print("\n--- 测试3：错误处理测试 ---")
    
    # 清空并添加一个空的配置
    interface_page.clear_all()
    interface_page.add_interface_config()
    
    # 不设置接口名称和IP地址
    widget_data = interface_page.config_widgets[0]
    widget_data['ip_entry'].delete(0, tk.END)
    widget_data['interface_field'].set("", "")  # 清空接口
    
    # 收集参数
    params, errors = interface_page.collect()
    
    print(f"收集参数: {params}")
    print(f"错误信息: {errors}")
    
    if errors and len(errors) > 0:
        print("✅ 错误处理测试通过")
    else:
        print("❌ 错误处理测试失败")
    
    # 测试4：简单VLAN功能测试（不依赖库绑定）
    print("\n--- 测试4：VLAN功能测试 ---")
    
    # 创建一个独立的VLAN测试实例
    vlan_test_page = InterfacePage(root, app=None)
    
    # 清空并添加一个配置
    vlan_test_page.clear_all()
    vlan_test_page.add_interface_config()
    widget_data = vlan_test_page.config_widgets[0]
    widget_data['interface_field'].set("GE", "0/0/0")
    widget_data['ip_entry'].delete(0, tk.END)
    widget_data['ip_entry'].insert(0, "192.168.1.1/24")
    
    # 设置VLAN值
    widget_data['vlan_var'].set("20")
    print(f"设置的VLAN值: {widget_data['vlan_var'].get()}")
    
    params, errors = vlan_test_page.collect()
    
    if params and len(params) == 1 and not errors and 'vlan' in params[0] and params[0]['vlan'] == '20':
        print("✅ VLAN功能测试通过")
        print(f"VLAN选择结果: {params[0]['vlan']}")
        print(f"生成的配置:\n{vlan_test_page.render(params)}")
    else:
        print("❌ VLAN功能测试失败")
        print(f"参数: {params}")
        print(f"错误: {errors}")
    
    # 清理
    root.destroy()
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    test_interface_page()
#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试脚本：验证接口IP配置是否已添加到路由器页面
"""

import tkinter as tk
from pages.router import InterfacePage, DhcpRouterPage

def test_interface_page():
    """测试接口IP页面"""
    print("=== 测试路由器接口IP页面 ===")
    
    # 创建测试窗口
    test_window = tk.Toplevel()
    test_window.title("测试 - 接口IP配置")
    
    # 创建接口IP页面实例
    interface_page = InterfacePage(test_window)
    interface_page.frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    # 测试基本功能
    interface_page.set_lib_values(
        ip_list=["192.168.1.1/24", "10.0.0.1/24"],
        vlan_list=["100", "200", "300"]
    )
    
    # 获取参数
    params, errors = interface_page.collect()
    
    print("接口IP页面参数收集结果:")
    if params:
        for key, value in params.items():
            print(f"  {key}: {value}")
    else:
        print("  未收集到参数")
    
    if errors:
        print("错误信息:")
        for error in errors:
            print(f"  - {error}")
    
    print("\n接口IP页面完成测试\n")
    
    # 显示窗口（仅用于视觉验证，1秒后自动关闭）
    test_window.update()
    test_window.after(1500, test_window.destroy)
    test_window.mainloop()

def test_dhcp_router_page():
    """测试DHCP路由器页面"""
    print("=== 测试DHCP路由器页面 ===")
    
    # 创建测试窗口
    test_window = tk.Toplevel()
    test_window.title("测试 - DHCP路由器配置")
    
    # 创建DHCP路由器页面实例
    dhcp_page = DhcpRouterPage(test_window)
    dhcp_page.frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    # 测试基本功能
    dhcp_page.set_lib_values(
        ip_list=["192.168.1.1/24", "10.0.0.1/24"],
        vlan_list=["100", "200", "300"]
    )
    
    # 获取参数
    params, errors = dhcp_page.collect()
    
    print("DHCP路由器页面参数收集结果:")
    if params:
        for key, value in params.items():
            print(f"  {key}: {value}")
    else:
        print("  未收集到参数")
    
    if errors:
        print("错误信息:")
        for error in errors:
            print(f"  - {error}")
    
    print("\nDHCP路由器页面完成测试\n")
    
    # 显示窗口（仅用于视觉验证，1秒后自动关闭）
    test_window.update()
    test_window.after(1500, test_window.destroy)
    test_window.mainloop()

def test_eth_trunk_interfaces():
    """测试链路聚合ETH接口支持"""
    print("=== 测试链路聚合ETH接口支持 ===")
    
    # 创建测试窗口
    test_window = tk.Toplevel()
    test_window.title("测试 - 链路聚合配置")
    
    # 导入EthTrunkPage
    from pages.switch import EthTrunkPage
    
    # 创建链路聚合页面实例
    eth_trunk_page = EthTrunkPage(test_window)
    eth_trunk_page.frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    # 获取参数
    params, errors = eth_trunk_page.collect()
    
    print("链路聚合页面参数收集结果:")
    if params:
        for key, value in params.items():
            print(f"  {key}: {value}")
    else:
        print("  未收集到参数")
    
    if errors:
        print("错误信息:")
        for error in errors:
            print(f"  - {error}")
    
    # 检查成员接口类型
    members = eth_trunk_page.collect_members()
    print(f"\n成员接口列表:")
    for member in members:
        print(f"  - {member}")
    
    print("\n链路聚合页面完成测试\n")
    
    # 显示窗口（仅用于视觉验证，1秒后自动关闭）
    test_window.update()
    test_window.after(1500, test_window.destroy)
    test_window.mainloop()

def main():
    """主测试函数"""
    print("开始测试所有修改...")
    
    # 检查模块导入
    try:
        from pages.router import InterfacePage, DhcpRouterPage
        from pages.switch import EthTrunkPage
        print("✓ 所有页面模块导入成功")
    except Exception as e:
        print(f"✗ 模块导入失败: {e}")
        return
    
    # 运行测试
    test_interface_page()
    test_dhcp_router_page()
    test_eth_trunk_interfaces()
    
    print("所有测试完成！")

if __name__ == "__main__":
    main()
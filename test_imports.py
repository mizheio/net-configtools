#!/usr/bin/env python3
"""测试所有模块导入"""
import sys
import os

# 添加当前路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """测试所有模块导入"""
    try:
        # 测试模块导入
        print("测试模块导入...")
        from modules import eth_trunk, vrrp
        from modules.dhcp_switch import generate as dhcp_switch_generate
        from modules.dhcp_router import generate as dhcp_router_generate
        print("✓ 所有模块导入成功")
        
        # 测试页面导入
        print("测试页面导入...")
        from pages.switch import IfVlanPage, VlanifPage, VrrpPage, MstpPage, EthTrunkPage
        from pages.dhcp_switch import DhcpSwitchPage
        from pages.dhcp_router import DhcpRouterPage
        from pages.common import OspfPage, AclPage
        print("✓ 所有页面导入成功")
        
        # 测试注册表导入
        print("测试注册表导入...")
        from pages import CATEGORY_PAGES
        print("✓ 注册表导入成功")
        
        # 测试生成函数
        print("测试生成函数...")
        
        # 测试链路聚合
        eth_params = {
            "trunk_id": "1",
            "vlans": [{"vlan": "10"}, {"vlan": "20"}],
            "members": [{"type": "GE", "num": "0/0/1"}, {"type": "GE", "num": "0/0/2"}]
        }
        eth_result = eth_trunk.generate_full(eth_params)
        print("✓ 链路聚合生成成功")
        
        # 测试交换机DHCP
        dhcp_switch_params = {
            "mode": "global",
            "if_vlan": "10",
            "gateway": "192.168.10.1",
            "network": "192.168.10.0",
            "mask": "255.255.255.0",
            "dns": "8.8.8.8"
        }
        dhcp_switch_result = dhcp_switch_generate(dhcp_switch_params)
        print("✓ 交换机DHCP生成成功")
        
        # 测试路由器DHCP
        dhcp_router_params = {
            "mode": "global",
            "if_port": "GigabitEthernet0/0/1",
            "gateway": "192.168.10.1",
            "network": "192.168.10.0",
            "mask": "255.255.255.0",
            "dns": "8.8.8.8"
        }
        dhcp_router_result = dhcp_router_generate(dhcp_router_params)
        print("✓ 路由器DHCP生成成功")
        
        print("\n🎉 所有测试通过！")
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)
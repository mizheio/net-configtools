#!/usr/bin/env python3
"""测试路由器类别页面"""
import sys
import os

# 添加当前路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_router_pages():
    """测试路由器类别页面"""
    try:
        from pages import CATEGORY_PAGES
        
        # 检查路由器类别页面
        router_pages = CATEGORY_PAGES.get("路由器", [])
        print("路由器类别页面:")
        for page in router_pages:
            print(f"  - {page.TITLE}")
        
        # 验证DHCP页面
        if any("DhcpRouterPage" in str(page) for page in router_pages):
            print("✅ 路由器DHCP页面存在")
        else:
            print("❌ 路由器DHCP页面不存在")
            return False
            
        # 验证交换机DHCP页面
        switch_pages = CATEGORY_PAGES.get("交换机", [])
        if any("DhcpSwitchPage" in str(page) for page in switch_pages):
            print("✅ 交换机DHCP页面存在")
        else:
            print("❌ 交换机DHCP页面不存在")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_router_pages()
    sys.exit(0 if success else 1)
#!/usr/bin/env python3
"""测试程序启动"""
import sys
import os

# 添加当前路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_startup():
    """测试程序启动"""
    try:
        # 导入必要的模块
        import tkinter as tk
        from gui import App
        
        # 创建主窗口（但不显示）
        root = tk.Tk()
        root.withdraw()  # 隐藏窗口
        
        # 创建App实例
        app = App(root)
        
        # 销毁窗口
        root.destroy()
        
        print("✅ 程序启动测试成功")
        return True
        
    except Exception as e:
        print(f"❌ 程序启动测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_startup()
    sys.exit(0 if success else 1)
"""IP / VLAN 库：读写 variables.json

结构:
{"ip": ["192.168.10.0", ...], "vlan": ["10", "20", ...]}
"""
import json
import os
import sys

# PyInstaller -F 打包后 __file__ 指向临时解压目录，必须改用 exe 所在目录，
# 否则每次退出变量库都会丢
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

VAR_FILE = os.path.join(BASE_DIR, "variables.json")


def load():
    """读取库文件，不存在/损坏/格式不对时返回空库（绝不抛异常）"""
    try:
        with open(VAR_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("ip"), list) and isinstance(data.get("vlan"), list):
            return {
                "ip": [str(x).strip() for x in data["ip"] if str(x).strip()],
                "vlan": [str(x).strip() for x in data["vlan"] if str(x).strip()],
            }
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return {"ip": [], "vlan": []}


def save(library):
    with open(VAR_FILE, "w", encoding="utf-8") as f:
        json.dump(library, f, ensure_ascii=False, indent=2)

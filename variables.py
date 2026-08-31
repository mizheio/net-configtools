"""IP / VLAN 库：读写 variables.json

结构:
{"ip": ["192.168.10.0", ...], "vlan": ["10", "20", ...]}
"""
import json
import os

VAR_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "variables.json")


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

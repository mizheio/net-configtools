"""基础 Eth-Trunk 链路聚合配置生成（对应文档 2.4）。

成员接口两种写法二选一：
  {"port": "GigabitEthernet0/0/22"}   完整接口名（界面 PortField 的输出格式）
  {"type": "GE", "num": "22"}         缩写+编号（num 纯数字补 0/0/，含 / 原样使用）
"""
from .base import port_name, render_vlan_batch


def collect_vlans(params):
    return sorted({int(row["vlan"]) for row in params.get("vlans", []) if str(row.get("vlan", "")).isdigit()})


def generate(params):
    members = [row for row in params.get("members", []) if row.get("num") or row.get("port")]
    if not members:
        return ""
    trunk_id = params["trunk_id"]
    allow = " ".join(row["vlan"] for row in params.get("vlans", []) if row.get("vlan"))
    lines = [
        f"interface Eth-Trunk{trunk_id}",
        " port link-type trunk",
        f" port trunk allow-pass vlan {allow}",
    ]
    for member in members:
        name = member["port"] if member.get("port") else port_name(member.get("type"), member["num"])
        lines += [f"interface {name}", f" eth-trunk {trunk_id}"]
    return "\n".join(lines)


def generate_full(params):
    body = generate(params)
    if not body:
        return ""
    header = render_vlan_batch(collect_vlans(params))
    return f"{header}\n{body}" if header else body

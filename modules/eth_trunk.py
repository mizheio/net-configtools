"""基础 Eth-Trunk 链路聚合配置生成（对应文档 2.4）。"""
from .base import render_vlan_batch

TYPE_MAP = {"GE": "GigabitEthernet", "ETH": "Ethernet"}


def collect_vlans(params):
    return sorted({int(row["vlan"]) for row in params.get("vlans", []) if str(row.get("vlan", "")).isdigit()})


def generate(params):
    members = [row for row in params.get("members", []) if row.get("num")]
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
        port_type = TYPE_MAP.get(member.get("type"), member.get("type", "GigabitEthernet"))
        lines += [f"interface {port_type}0/0/{member['num']}", f" eth-trunk {trunk_id}"]
    return "\n".join(lines)


def generate_full(params):
    body = generate(params)
    if not body:
        return ""
    header = render_vlan_batch(collect_vlans(params))
    return f"{header}\n{body}" if header else body

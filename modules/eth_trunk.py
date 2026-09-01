"""Eth-Trunk 链路聚合配置生成（对应文档 2.4）。

基础聚合模式：Eth-Trunk trunk + 成员口绑定
成员接口有两种写法：
  {"port": "GigabitEthernet0/0/22"}   完整接口名（界面 PortField 的输出格式）
  {"type": "GE/ETH", "num": "22"}     缩写+编号（num 纯数字补 0/0/，含 / 原样使用）
"""
from .base import port_name, render_vlan_batch


def collect_vlans(params):
    return sorted({int(row["vlan"]) for row in params.get("vlans", []) if str(row.get("vlan", "")).isdigit()})


def _member_name(member):
    return member["port"] if member.get("port") else port_name(member.get("type"), member["num"])


def _trunk_head(params):
    allow = " ".join(row["vlan"] for row in params.get("vlans", []) if row.get("vlan"))
    lines = [
        f"interface Eth-Trunk{params['trunk_id']}",
        " port link-type trunk",
        f" port trunk allow-pass vlan {allow}",
    ]
    return lines


def _member_lines(params, members):
    lines = []
    for member in members:
        name = _member_name(member)
        lines.append(f"interface {name}")
        lines.append(f" eth-trunk {params['trunk_id']}")
    return lines


def generate(params):
    """基础聚合正文"""
    members = [row for row in params.get("members", []) if row.get("num") or row.get("port")]
    if not members:
        return ""
    return "\n".join(_trunk_head(params) + _member_lines(params, members))


def generate_full(params):
    body = generate(params)
    if not body:
        return ""
    header = render_vlan_batch(collect_vlans(params))
    return f"{header}\n{body}" if header else body
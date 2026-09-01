"""接口 VLAN 配置生成（对应文档 1.1 / 1.2 / 1.3）

params 示例:
{
  "ports": [
    {"type": "GE", "num": "0/0/1", "mode": "access", "vlan": "10"},
    {"type": "ETH", "num": "0/0/1", "mode": "trunk", "pvid": "100", "allow": "110 100"},
  ]
}
num 也兼容旧格式纯数字（如 1，自动补 0/0/ 槽位），或含板卡号的 "1/0/1"。
"""
from .base import collect_vlans, port_name, render_vlan_batch


def generate(params):
    """生成接口配置正文（不含 vlan batch 头部）"""
    blocks = []
    for p in params["ports"]:
        lines = [f"interface {port_name(p.get('type'), p['num'])}"]
        if p["mode"] == "access":
            lines.append(" port link-type access")
            lines.append(f" port default vlan {p['vlan']}")
        else:  # trunk
            lines.append(" port link-type trunk")
            if p.get("pvid"):
                lines.append(f" port trunk pvid vlan {p['pvid']}")
            lines.append(f" port trunk allow-pass vlan {p['allow']}")
        blocks.append("\n".join(lines))
    return "\n#\n".join(blocks)


def generate_full(params):
    """正文 + 自动汇总的 vlan 创建头部"""
    body = generate(params)
    if not body:
        return ""
    header = render_vlan_batch(collect_vlans(params["ports"]))
    return f"{header}\n{body}" if header else body

"""接口 VLAN 配置生成（对应文档 1.1 / 1.2 / 1.3）

params 示例:
{
  "ports": [
    {"type": "GE", "num": 1, "mode": "access", "vlan": "10"},
    {"type": "ETH", "num": 1, "mode": "trunk", "pvid": "100", "allow": "110 100"},
  ]
}
"""
from .base import collect_vlans, render_vlan_batch

TYPE_MAP = {"GE": "GigabitEthernet", "ETH": "Ethernet"}


def generate(params):
    """生成接口配置正文（不含 vlan batch 头部）"""
    blocks = []
    for p in params["ports"]:
        itype = TYPE_MAP.get(p.get("type"), str(p.get("type")))
        lines = [f"interface {itype}0/0/{p['num']}"]
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

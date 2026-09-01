"""路由器接口 IP 配置生成（对应文档 4.1）

params 示例:
{
  "ifaces": [
    {"type": "GE", "num": "0/0/0", "ip": "192.168.10.1",
     "mask": "255.255.255.0", "desc": "to-core"},
  ]
}
"""
from .base import port_name


def generate(params):
    blocks = []
    for i in params["ifaces"]:
        lines = [f"interface {port_name(i['type'], i['num'])}"]
        if i.get("desc"):
            lines.append(f" description {i['desc']}")
        lines.append(f" ip address {i['ip']} {i['mask']}")
        blocks.append("\n".join(lines))
    return "\n#\n".join(blocks)

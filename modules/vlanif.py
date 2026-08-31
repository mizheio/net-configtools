"""Vlanif 三层网关配置生成（对应文档 2.1）

params 示例:
{
  "ifaces": [
    {"vlan": "10", "ip": "192.168.10.1", "mask": "255.255.255.0"},
    {"vlan": "20", "ip": "192.168.20.1", "mask": "255.255.255.0"},
  ]
}
"""


def generate(params):
    blocks = []
    for i in params["ifaces"]:
        blocks.append(
            f"interface Vlanif{i['vlan']}\n"
            f" ip address {i['ip']} {i['mask']}"
        )
    return "\n#\n".join(blocks)

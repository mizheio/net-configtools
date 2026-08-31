"""DHCP 全局地址池配置生成（对应文档 2.6 基础二层配置）

params 示例:
{"if_vlan": "10", "gateway": "192.168.10.1", "network": "192.168.10.0",
 "mask": "255.255.255.0", "dns": "192.168.200.88", "lease": "7"}
"""


def generate(params):
    return "\n".join([
        "dhcp enable",
        "#",
        f"ip pool pool-vlan{params['if_vlan']}",
        f" gateway-list {params['gateway']}",
        f" network {params['network']} mask {params['mask']}",
        f" dns-list {params['dns']}",
        f" lease day {params['lease']}",
        "#",
        f"interface Vlanif{params['if_vlan']}",
        " dhcp select global",
    ])

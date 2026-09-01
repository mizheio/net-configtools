"""DHCP 配置生成 - 路由器（对应文档 4.11）

路由器DHCP配置：使用物理接口
"""
import ipaddress


def _pool_name(params):
    return f"pool-vlan{str(params.get('network', '')).split('.')[-2]}"


def _pool_lines(params, with_lease=True):
    """地址池正文"""
    lines = [
        f"ip pool {_pool_name(params)}",
        f" gateway-list {params['gateway']}",
        f" network {params['network']} mask {params['mask']}",
        f" dns-list {params['dns']}",
    ]
    if with_lease and params.get("lease"):
        lines.append(f" lease day {params['lease']}")
    return lines


def generate_global(params):
    return "\n".join([
        "dhcp enable",
        "#",
        *_pool_lines(params),
        "#",
        f"interface {params.get('if_port', '')}",
        " dhcp select global",
    ])


def generate_relay(params):
    """中继配置"""
    return "\n".join([
        "dhcp enable",
        "#",
        f"interface {params.get('if_port', '')}",
        " dhcp select relay",
        f" dhcp relay server-ip {params.get('relay_ip', '')}",
    ])


def generate(params):
    """DHCP生成函数"""
    if params.get("mode") == "relay":
        return generate_relay(params)
    return generate_global(params)
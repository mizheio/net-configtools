"""GRE VPN 配置生成（对应文档 4.9）。

GRE 隧道两端成对配置：对端的 source/destination 与本端互换，两端各自把
对方内网网段的静态路由指向隧道口。generate 按需输出本端（可附带对端
脚本，加 ##本端设备 / ##对端设备 注释）；汇总生成只取本端，避免把另一台
设备的配置混进单台汇总。
"""
import ipaddress


def normalize_mask(mask):
    """兼容 /30、30 两种前缀写法，统一转成点分十进制掩码"""
    mask = mask.strip().lstrip("/")
    if mask.isdigit():
        return str(ipaddress.ip_network(f"0.0.0.0/{int(mask)}").netmask)
    return mask


def _route_lines(routes, tunnel_name):
    lines = []
    for row in routes:
        if row.get("network"):
            lines.append(f"ip route-static {row['network']} {normalize_mask(row.get('mask', ''))} {tunnel_name}")
    return lines


def _device_block(tunnel_num, tunnel_ip, mask, source, destination, routes):
    tunnel_name = f"Tunnel{tunnel_num}"
    lines = [
        f"interface {tunnel_name}",
        f" ip address {tunnel_ip} {normalize_mask(mask)}",
        " tunnel-protocol gre",
        f" source {source}",
        f" destination {destination}",
        "#",
    ]
    lines += _route_lines(routes, tunnel_name)
    return "\n".join(lines)


def generate_local(params):
    """本端设备脚本：Tunnel 口 + 指向对端内网网段的静态路由"""
    return _device_block(params["tunnel_num"], params["local_tunnel_ip"], params["local_mask"],
                         params["local_source"], params["local_destination"], params["routes"])


def generate_peer(params):
    """对端设备脚本：source/destination 与本端互换，路由用对端网段列表"""
    return _device_block(params["tunnel_num"], params["peer_tunnel_ip"], params["local_mask"],
                         params["local_destination"], params["local_source"], params["peer_routes"])


def generate(params):
    blocks = [generate_local(params)]
    if params.get("gen_peer") and params.get("peer_tunnel_ip"):
        blocks.append(generate_peer(params))
    if len(blocks) == 1:
        return blocks[0]
    return "##本端设备\n" + blocks[0] + "\n\n##对端设备\n" + blocks[1]

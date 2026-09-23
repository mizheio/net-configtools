"""防火墙 GRE VPN（文档 5.7）：GRE 隧道 + 加域 + 静态路由 + 安全策略两段。

params:
  tunnel_num / tunnel_ip / tunnel_mask / source / destination / zone
  default_next_hop / local_net / remote_net
  gen_peer / peer_tunnel_ip / peer_default_next_hop

缩进照 5.7：属性行 1 空格，security-policy 的 rule name 1 空格 / 属性 2 空格。
Tunnel 口名统一为 Tunnel 1（文档三节写法不一）。
"""

from .fw_ipsec import parse_net  # 网段归一复用（/24、24、点分掩码、反掩码）

# 隧道子网掩码备选项：页面做成可编辑下拉，既能选也能手输
SUBNET_MASKS = ("255.255.255.252", "255.255.255.0", "255.255.255.248",
                "255.255.255.240", "255.255.255.224", "255.255.255.192",
                "255.255.255.128", "255.255.255.254", "255.255.0.0", "255.0.0.0")


def normalize_mask(mask):
    """子网掩码归一：/30、30、点分掩码、反掩码 -> 点分掩码（复用 parse_net）"""
    return parse_net(f"0.0.0.0 {mask}")[2]


def tunnel_name(num):
    """Tunnel 口名统一为 Tunnel 1（文档三节写法不一）"""
    return f"Tunnel {str(num).strip()}"


def _side(params, local):
    """本端/对端差异字段：隧道地址、源目公网、默认路由下一跳、指向的对方内网"""
    if local:
        return {"tunnel_ip": params["tunnel_ip"], "source": params["source"],
                "destination": params["destination"],
                "default_next_hop": params["default_next_hop"],
                "peer_net": params["remote_net"],
                "tunnel": tunnel_name(params["tunnel_num"])}
    return {"tunnel_ip": params.get("peer_tunnel_ip", ""),
            "source": params["destination"], "destination": params["source"],
            "default_next_hop": params.get("peer_default_next_hop", ""),
            "peer_net": params["local_net"],
            "tunnel": tunnel_name(params.get("peer_tunnel_num") or params["tunnel_num"])}


def _device_block(params, side):
    """单台设备脚本：GRE 隧道 -> 加域 -> 静态路由 -> security-policy 两段，段间 "#" 分隔"""
    net_ip, _, net_mask = parse_net(side["peer_net"])
    zone = params["zone"]
    return "\n".join([
        f"interface {side['tunnel']}",
        f" ip address {side['tunnel_ip']} {normalize_mask(params['tunnel_mask'])}",
        " tunnel-protocol gre",
        f" source {side['source']}",
        f" destination {side['destination']}",
        "#",
        f"firewall zone {zone}",
        f" add interface {side['tunnel']}",
        "#",
        f"ip route-static 0.0.0.0 0.0.0.0 {side['default_next_hop']}",
        f"ip route-static {net_ip} {net_mask} {side['tunnel']}",
        "#",
        "security-policy",
        " rule name gre_vpn",
        f"  source-zone {zone}",
        "  source-zone trust",
        f"  destination-zone {zone}",
        "  destination-zone trust",
        "  action permit",
        " rule name gre_tunnel",
        "  source-zone local",
        "  source-zone untrust",
        "  destination-zone local",
        "  destination-zone untrust",
        "  service gre",
        "  action permit",
    ])


def generate_local(params):
    """本端设备脚本（汇总生成只取本端，对端属另一台设备）"""
    return _device_block(params, _side(params, True))


def generate(params):
    """默认只出本端；勾选 gen_peer 时附对端，两段分别标注 ##本端 / ##对端"""
    blocks = [generate_local(params)]
    if params.get("gen_peer"):
        blocks.append(_device_block(params, _side(params, False)))
    if len(blocks) == 1:
        return blocks[0]
    return "##本端\n" + blocks[0] + "\n\n##对端\n" + blocks[1]

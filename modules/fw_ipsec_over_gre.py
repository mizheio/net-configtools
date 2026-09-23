"""防火墙 IPsec over GRE（文档 5.8）：GRE 隧道 + IPsec 挂隧道口 + 安全策略三段。

params:
  tunnel_num / tunnel_ip / tunnel_mask / source / destination / zone
  default_next_hop / local_net / remote_net
  acl_num / acl_rule / ike_proposal / local_peer / psk
  ipsec_proposal / policy_name / policy_seq
  peer_tunnel_ip（对端隧道 IP，即 ike peer 的 remote-address）
  gen_peer / peer_peer / peer_tunnel_num / peer_default_next_hop

要点：先 IPsec 加密、后 GRE 封装 —— ACL 匹配业务网段、IPsec 挂 Tunnel 口、
remote-address 用对端隧道 IP。缩进照 5.8：IKE 属性 2 空格、IPsec 属性 1 空格。
"""

from .fw_gre import normalize_mask, tunnel_name  # 掩码归一 + Tunnel 口名归一
from .fw_ipsec import parse_net

# 算法备选值：页面当前把这套算法写死为下方 DEFAULTS，保留清单备查
IKE_ENCRYPTIONS = ("aes-256", "aes-192", "aes-128", "3des-cbc", "des-cbc")
IKE_DH_GROUPS = ("group14", "group2", "group5", "group1", "group19", "group20", "group21")
IKE_AUTH_ALGS = ("sha2-256", "sha2-384", "sha2-512", "sha1", "md5")
IKE_INTEGRITY_ALGS = ("hmac-sha2-256", "hmac-sha2-384", "hmac-sha2-512", "hmac-sha1", "hmac-md5")
IKE_PRF_ALGS = ("hmac-sha2-256", "hmac-sha2-384", "hmac-sha2-512")
ESP_AUTH_ALGS = ("sha2-256", "sha2-384", "sha2-512", "sha1", "md5")
ESP_ENCRYPTIONS = ("aes-256", "aes-192", "aes-128", "3des", "des")

# 页面写死的算法取值（即文档 5.8 标准块）
DEFAULTS = {
    "ike_encryption": "aes-256",
    "ike_dh": "group14",
    "ike_auth": "sha2-256",
    "ike_integrity": "hmac-sha2-256",
    "ike_prf": "hmac-sha2-256",
    "esp_auth": "sha2-256",
    "esp_enc": "aes-256",
}


def _side(params, local):
    """本端/对端差异字段：隧道地址、公网源目、两侧网段、remote-address"""
    if local:
        return {"tunnel": tunnel_name(params["tunnel_num"]),
                "tunnel_ip": params["tunnel_ip"],
                "source": params["source"], "destination": params["destination"],
                "next_hop": params.get("default_next_hop", ""),
                "src_net": params["local_net"], "dst_net": params["remote_net"],
                "peer_name": params["local_peer"],
                "remote_addr": params["peer_tunnel_ip"]}
    return {"tunnel": tunnel_name(params.get("peer_tunnel_num") or params["tunnel_num"]),
            "tunnel_ip": params["peer_tunnel_ip"],
            "source": params["destination"], "destination": params["source"],
            "next_hop": params.get("peer_default_next_hop", ""),
            "src_net": params["remote_net"], "dst_net": params["local_net"],
            "peer_name": params.get("peer_peer") or params["local_peer"],
            "remote_addr": params["tunnel_ip"]}


def _routes(side):
    """静态路由：默认路由（下一跳留空则不出）+ 指向对端内网、出接口 Tunnel"""
    dst_ip, _, dst_mask = parse_net(side["dst_net"])
    lines = []
    if side["next_hop"]:
        lines.append(f"ip route-static 0.0.0.0 0.0.0.0 {side['next_hop']}")
    lines.append(f"ip route-static {dst_ip} {dst_mask} {side['tunnel']}")
    return lines


def _device_block(params, side):
    """单台设备：GRE 隧道 -> 加域 -> ACL -> IKE -> IPsec -> 隧道口应用 -> 静态路由 -> 策略三段"""
    src_ip, src_wc, _ = parse_net(side["src_net"])
    dst_ip, dst_wc, _ = parse_net(side["dst_net"])
    zone = params["zone"]
    lines = [
        f"interface {side['tunnel']}",
        f" ip address {side['tunnel_ip']} {normalize_mask(params['tunnel_mask'])}",
        " tunnel-protocol gre",
        f" source {side['source']}",
        f" destination {side['destination']}",
        "#",
        f"firewall zone {zone}",
        f" add interface {side['tunnel']}",
        "#",
        f"acl number {params['acl_num']}",
        f" rule {params['acl_rule']} permit ip source {src_ip} {src_wc}"
        f" destination {dst_ip} {dst_wc}",
        "#",
        f"ike proposal {params['ike_proposal']}",
        f"  encryption-algorithm {params['ike_encryption']}",
        f"  dh {params['ike_dh']}",
        f"  authentication-algorithm {params['ike_auth']}",
        "  authentication-method pre-share",
        f"  integrity-algorithm {params['ike_integrity']}",
        f"  prf {params['ike_prf']}",
        "#",
        f"ike peer {side['peer_name']}",
        f"  pre-shared-key {params['psk']}",
        f"  ike-proposal {params['ike_proposal']}",
        f"  remote-address {side['remote_addr']}",
        "#",
        f"ipsec proposal {params['ipsec_proposal']}",
        f" esp authentication-algorithm {params['esp_auth']}",
        f" esp encryption-algorithm {params['esp_enc']}",
        "#",
        f"ipsec policy {params['policy_name']} {params['policy_seq']} isakmp",
        f" security acl {params['acl_num']}",
        f" ike-peer {side['peer_name']}",
        f" proposal {params['ipsec_proposal']}",
        "#",
        f"interface {side['tunnel']}",
        f" ipsec policy {params['policy_name']}",
        "#",
    ]
    lines += _routes(side)
    lines += [
        "#",
        "security-policy",
        " rule name gre_vpn",
        f"  source-zone {zone}",
        "  source-zone trust",
        f"  destination-zone {zone}",
        "  destination-zone trust",
        "  action permit",
        " rule name gre_ipsec_tunnel",
        f"  source-zone {zone}",
        "  source-zone local",
        "  source-zone untrust",
        f"  destination-zone {zone}",
        "  destination-zone local",
        "  destination-zone untrust",
        "  action permit",
        " rule name gre_tunnel",
        "  source-zone local",
        "  source-zone untrust",
        "  destination-zone local",
        "  destination-zone untrust",
        "  service gre",
        "  action permit",
    ]
    return "\n".join(lines)


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

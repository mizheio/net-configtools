"""防火墙 GRE over IPsec（文档 5.9）：GRE 隧道 + IPsec 保护 GRE 流量 + 安全策略四段。

params:
  tunnel_num / tunnel_ip / tunnel_mask / source / destination / zone
  acl_num / acl_rule / ike_proposal / local_peer / psk
  ipsec_proposal / policy_name / policy_seq / if_type / if_num
  local_net / remote_net
  gen_peer / peer_tunnel_ip / peer_tunnel_num / peer_if_type / peer_if_num

要点：先 GRE 封装、后 IPsec 加密 —— ACL 匹配 permit gre 的公网流量、
IPsec 挂公网物理口、remote-address 用对端公网 IP。缩进全部 1 空格。
文档 5.9 末尾的「额外NAT策略配置」本模块不生成。
"""

from .base import port_name
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

# 页面写死的算法取值（即文档 5.9 标准块）
DEFAULTS = {
    "ike_encryption": "aes-256",
    "ike_dh": "group14",
    "ike_auth": "sha2-256",
    "ike_integrity": "hmac-sha2-256",
    "ike_prf": "hmac-sha2-256",
    "esp_auth": "sha2-256",
    "esp_enc": "aes-256",
}

# GRE 感兴趣流 ACL 的地址反掩码（照文档 5.9 原文）
ACL_WILDCARD = "0.0.0.255"
# ike_esp_out / ike_esp_in 作用于公网接口地址，固定 /32
HOST_MASK = "255.255.255.255"


def _side(params, local):
    """本端/对端差异字段：隧道地址、公网源目、内外网网段、公网口两端互换"""
    if local:
        return {"tunnel_ip": params["tunnel_ip"], "source": params["source"],
                "destination": params["destination"],
                "src_net": params["local_net"], "dst_net": params["remote_net"],
                "peer_name": params["local_peer"],
                "tunnel": tunnel_name(params["tunnel_num"]),
                "if_name": port_name(params["if_type"], params["if_num"])}
    return {"tunnel_ip": params.get("peer_tunnel_ip", ""),
            "source": params["destination"], "destination": params["source"],
            "src_net": params["remote_net"], "dst_net": params["local_net"],
            "peer_name": params.get("peer_peer") or params["local_peer"],
            "tunnel": tunnel_name(params.get("peer_tunnel_num") or params["tunnel_num"]),
            "if_name": port_name(params.get("peer_if_type") or params["if_type"],
                                 params.get("peer_if_num") or params["if_num"])}


def _device_block(params, side):
    """单台设备：GRE 隧道 -> 加域 -> ACL -> IKE -> IPsec -> 公网口应用 -> 静态路由 -> 策略四段"""
    pub, peer_pub = side["source"], side["destination"]
    s_ip, _, s_mask = parse_net(side["src_net"])
    d_ip, _, d_mask = parse_net(side["dst_net"])
    zone = params["zone"]
    return "\n".join([
        f"interface {side['tunnel']}",
        f" ip address {side['tunnel_ip']} {normalize_mask(params['tunnel_mask'])}",
        " tunnel-protocol gre",
        f" source {pub}",
        f" destination {peer_pub}",
        "#",
        f"firewall zone {zone}",
        f" add interface {side['tunnel']}",
        "#",
        f"acl number {params['acl_num']}",
        f" rule {params['acl_rule']} permit gre source {pub} {ACL_WILDCARD}"
        f" destination {peer_pub} {ACL_WILDCARD}",
        "#",
        f"ike proposal {params['ike_proposal']}",
        f" encryption-algorithm {params['ike_encryption']}",
        f" dh {params['ike_dh']}",
        f" authentication-algorithm {params['ike_auth']}",
        " authentication-method pre-share",
        f" integrity-algorithm {params['ike_integrity']}",
        f" prf {params['ike_prf']}",
        "#",
        f"ike peer {side['peer_name']}",
        f" pre-shared-key {params['psk']}",
        f" ike-proposal {params['ike_proposal']}",
        f" remote-address {peer_pub}",
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
        f"interface {side['if_name']}",
        f" ipsec policy {params['policy_name']}",
        "#",
        f"ip route-static {d_ip} {d_mask} {side['tunnel']}",
        "#",
        "security-policy",
        " rule name ike_esp_out",
        "  source-zone local",
        "  destination-zone untrust",
        f"  source-address {pub} mask {HOST_MASK}",
        f"  destination-address {peer_pub} mask {HOST_MASK}",
        "  action permit",
        " rule name ike_esp_in",
        "  source-zone untrust",
        "  destination-zone local",
        f"  source-address {peer_pub} mask {HOST_MASK}",
        f"  destination-address {pub} mask {HOST_MASK}",
        "  action permit",
        " rule name vpn_trust_to_dmz",
        "  source-zone trust",
        f"  destination-zone {zone}",
        f"  source-address {s_ip} mask {s_mask}",
        f"  destination-address {d_ip} mask {d_mask}",
        "  action permit",
        " rule name vpn_dmz_to_trust",
        f"  source-zone {zone}",
        "  destination-zone trust",
        f"  source-address {d_ip} mask {d_mask}",
        f"  destination-address {s_ip} mask {s_mask}",
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

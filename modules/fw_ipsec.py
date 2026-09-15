"""防火墙 IPsec VPN 配置生成（对应文档 5.5 点到点 IPsec VPN）

params 示例:
{
  # ---- 两端共用 ----
  "acl_num": "3000", "acl_rule": "5",
  "local_net": "192.168.10.0/24", "remote_net": "172.16.10.0/24",
  "ike_proposal": "10", "ike_encryption": "aes-256", "ike_dh": "group14",
  "ike_auth": "sha2-256", "ike_integrity": "hmac-sha2-256", "ike_prf": "hmac-sha2-256",
  "psk": "test123",
  "ipsec_proposal": "tran1", "esp_auth": "sha2-256", "esp_enc": "aes-256",
  "policy_name": "map1", "policy_seq": "10",
  # ---- 本端 ----
  "local_peer": "ike1",
  "local_if_type": "GE", "local_if_num": "1/0/0",
  "local_ip": "1.1.3.1", "peer_ip": "1.1.5.1",
  "local_zone": "trust", "remote_zone": "untrust",
  # ---- 对端（勾选 gen_peer 时生效）----
  "gen_peer": True, "peer_peer": "ike2",
  "peer_if_type": "GE", "peer_if_num": "1/0/0",
}
生成结构（与文档 5.5 逐行一致）：感兴趣流 ACL -> IKE proposal -> IKE peer ->
IPsec proposal -> IPsec policy -> 接口应用 -> security-policy 四段，
各段之间用 "#" 分隔；勾选对端时输出 ##本端 / ##对端 两段，
ACL 源目网段与 remote-address 自动互换。

说明：
- 缩进照文档 5.5 原样：`ike proposal` / `ike peer` 的属性 2 空格，
  `ipsec proposal` / `ipsec policy` 的属性 1 空格（文档自身如此，不要"拉齐"）。
- 加密/DH/认证/完整性/PRF/ESP 算法由**页面写死**为文档 5.5 标准值（见 DEFAULTS），
  生成函数本身仍照 params 取值，命令行调用可自行传任意算法。
- 接口段只出 `interface X` + `ipsec policy map1`，接口 IP 由"接口IP与安全域"页配置，本模块不重复输出。
- 这里的 security-policy 严格照文档 5.5 原文（source-address ... mask ...、
  rule name 2 空格 / 属性 4 空格缩进），与文档 5.2 的 "IP 前缀长度" 写法不同，
  属配置依据文档自身的差异，生成时以 5.5 为准。
"""
import ipaddress

from .base import port_name

# 算法备选值（来自文档 5.5 与 4.8）：页面当前把这套算法**全部写死**为下方 DEFAULTS、未开放修改；
# 这里保留备选清单，以后要放开下拉或换一套参数时直接引用，不用回头翻文档
IKE_ENCRYPTIONS = ("aes-256", "aes-192", "aes-128", "3des-cbc", "des-cbc")
IKE_DH_GROUPS = ("group14", "group2", "group5", "group1", "group19", "group20", "group21")
IKE_AUTH_ALGS = ("sha2-256", "sha2-384", "sha2-512", "sha1", "md5")
IKE_INTEGRITY_ALGS = ("hmac-sha2-256", "hmac-sha2-384", "hmac-sha2-512", "hmac-sha1", "hmac-md5")
IKE_PRF_ALGS = ("hmac-sha2-256", "hmac-sha2-384", "hmac-sha2-512")
ESP_AUTH_ALGS = ("sha2-256", "sha2-384", "sha2-512", "sha1", "md5")
ESP_ENCRYPTIONS = ("aes-256", "aes-192", "aes-128", "3des", "des")

# 页面写死的算法取值（即文档 5.5 标准块）：页面 collect() 把本字典合并进 params，
# 生成函数与校验逻辑不变，拿到的仍是完整 params
DEFAULTS = {
    "ike_encryption": "aes-256",
    "ike_dh": "group14",
    "ike_auth": "sha2-256",
    "ike_integrity": "hmac-sha2-256",
    "ike_prf": "hmac-sha2-256",
    "esp_auth": "sha2-256",
    "esp_enc": "aes-256",
}

# policy3/policy4 作用于本端公网接口地址，固定 /32
HOST_MASK = "255.255.255.255"


def parse_net(text):
    """网段归一：任意写法 -> (IP, 反掩码, 点分掩码)。

    感兴趣流 ACL 用反掩码（source ... 0.0.0.255），security-policy 用点分掩码
    （source-address ... mask 255.255.255.0），两种写法一次算好。
    兼容前缀（/24、24）、点分掩码（255.255.255.0）、直接反掩码（0.0.0.255）。
    非法抛 ValueError，交由页面 validate 弹窗拦截。
    """
    text = str(text).strip().replace("/", " ")
    parts = text.split()
    if not parts:
        raise ValueError("不能为空")
    ip = parts[0]
    if len(parts) == 1:
        raise ValueError(f"{text} 需带掩码，如 192.168.10.0/24")
    mask = " ".join(parts[1:])
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        raise ValueError(f"{ip} 不是合法 IP")
    if mask.startswith("0."):
        # 直接填反掩码：反转成点分掩码交给 ipaddress 校验连续性
        try:
            netmask = str(ipaddress.ip_address(
                int(ipaddress.ip_address(mask)) ^ 0xFFFFFFFF))
            net = ipaddress.ip_network(f"{ip}/{netmask}", strict=False)
        except ValueError:
            raise ValueError(f"反掩码 {mask} 不是合法反掩码（须为连续 0）")
    else:
        try:
            net = ipaddress.ip_network(f"{ip}/{mask}", strict=False)
        except ValueError:
            raise ValueError(f"掩码 {mask} 不是合法掩码")
    return ip, str(net.hostmask), str(net.netmask)


def _side(params, local):
    """本端/对端各自的差异字段；网段、peer 名、对端地址、接口、本方公网地址两端互换"""
    if local:
        return {"src_net": params["local_net"], "dst_net": params["remote_net"],
                "peer_name": params["local_peer"], "remote_addr": params["peer_ip"],
                "if_name": port_name(params["local_if_type"], params["local_if_num"]),
                "local_pub_ip": params["local_ip"]}
    return {"src_net": params["remote_net"], "dst_net": params["local_net"],
            "peer_name": params["peer_peer"], "remote_addr": params["local_ip"],
            "if_name": port_name(params["peer_if_type"], params["peer_if_num"]),
            "local_pub_ip": params["peer_ip"]}


def _device_block(params, side):
    """单台设备脚本：ACL -> IKE -> IPsec -> 接口 -> security-policy，段间 "#" 分隔"""
    src_ip, src_wc, src_mask = parse_net(side["src_net"])
    dst_ip, dst_wc, dst_mask = parse_net(side["dst_net"])
    tz, uz = params["local_zone"], params["remote_zone"]
    pub = side["local_pub_ip"]
    return "\n".join([
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
        f"interface {side['if_name']}",
        f" ipsec policy {params['policy_name']}",
        "#",
        "security-policy",
        "  rule name policy1",
        f"    source-zone {tz}",
        f"    destination-zone {uz}",
        f"    source-address {src_ip} mask {src_mask}",
        f"    destination-address {dst_ip} mask {dst_mask}",
        "    action permit",
        "  rule name policy2",
        f"    source-zone {uz}",
        f"    destination-zone {tz}",
        f"    source-address {dst_ip} mask {dst_mask}",
        f"    destination-address {src_ip} mask {src_mask}",
        "    action permit",
        "  rule name policy3",
        "    source-zone local",
        f"    destination-zone {uz}",
        f"    source-address {pub} mask {HOST_MASK}",
        "    action permit",
        "  rule name policy4",
        f"    source-zone {uz}",
        "    destination-zone local",
        f"    destination-address {pub} mask {HOST_MASK}",
        "    action permit",
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

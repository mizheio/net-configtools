"""路由器 IPsec VPN 配置生成（对应文档 4.8 点到点 IPsec VPN）

params 示例:
{
  # ---- 感兴趣流 ----
  "acl_num": "3000", "acl_rule": "5",
  "local_net": "192.168.21.0/24", "remote_net": "192.168.22.0/24",
  # ---- IKE / IPsec 命名项（算法见 DEFAULTS，页面写死）----
  "ike_proposal": "1", "local_peer": "1", "psk": "123456",
  "ipsec_proposal": "1", "policy_name": "map1", "policy_seq": "1",
  # ---- 本端 ----
  "local_if_type": "GE", "local_if_num": "0/0/0",
  "local_ip": "10.0.12.1", "peer_ip": "10.0.56.6",
  # 勾选"生成 ip address"时，接口段多出一行 ip address（掩码可写 /24、24、点分掩码）
  "ip_addr_enable": False, "subnet_mask": "255.255.255.0",
  "routes": [{"network": "192.168.22.0", "mask": "255.255.255.0", "next_hop": "10.0.12.2"}],
  # ---- 对端（gen_peer=True 时生效）----
  "gen_peer": True, "peer_peer": "", "peer_if_type": "GE", "peer_if_num": "0/0/0",
  "peer_routes": [{"network": "192.168.21.0", "mask": "255.255.255.0", "next_hop": "10.0.56.5"}],
  # ---- NAT 豁免（exempt=True 时在 IPsec 主体后追加一段）----
  "exempt": False, "exempt_acl": "3001",
  "extra_nets": [{"network": "192.168.10.0/24"}],
  "peer_extra_nets": [{"network": "192.168.20.0/24"}],
}
生成结构（与文档 4.8 逐行一致）：感兴趣流 ACL -> IKE proposal -> IKE peer ->
IPsec proposal -> IPsec policy -> 接口应用 + 静态路由；勾选豁免时追加
ACL(easy-ip 豁免) + 接口 nat outbound 一段。勾选对端时输出 ##本端 / ##对端 两段，
ACL 源目网段、remote-address、接口、路由网段自动互换。

说明（文档 4.8 与防火墙 5.5 写法不同，此处一律以 4.8 为准）：
- 属性行**全部 1 空格**缩进（5.5 是 ike proposal/peer 2 空格）。
- IKE peer 带 IKE 版本 `ike peer <名> v2`；预共享密钥带 `simple` 关键字。
- IKE proposal 只有 4 行（encryption / authentication / authentication-method / dh），
  **没有 integrity-algorithm 与 prf**（5.5 有）。
- `interface X` 段**前不加 `#`**（5.5 加了 `#`）。默认只出 `interface X` + ` ipsec policy X`
  （与文档 4.8 一致）；勾选 `ip_addr_enable`（页面上的"生成 ip address"）时在两者之间插入
  ` ip address <local_ip> <subnet_mask>`（掩码经 normalize_mask 归一，可写 /24、24、点分掩码），
  此时接口地址由本模块输出、无需再用"接口IP配置"页配；对端段文档 4.8 无此行，恒不输出。
- 文档 4.8 里对端 IKE peer 段的分隔符写的是 ` #`（带前导空格）、` ipsec policy map1` 带一长串
  尾随空格，生成时统一归一为 `#` 与无尾随空格。
- NAT 豁免的对端段按文档原文带 `undo  nat outbound 2000`（**两个空格**，照抄）、
  本端段文档未列此行、故本端不输出；豁免 ACL 里最后一条 permit 是本端网段，由本模块自动追加，
  规则号从 10 起、步长 5。
- 算法取值集中在 DEFAULTS（即文档 4.8 的 3des-cbc / md5 / group2 与 ESP md5 / 3des），
  生成函数本身仍照 params 取值，命令行调用可自行传任意算法。
"""
import ipaddress

from .base import port_name

# 算法备选值（取自文档 4.8 与 5.5）：页面当前把这套算法**全部写死**为下方 DEFAULTS、未开放修改；
# 这里保留备选清单，以后要放开下拉或换一套参数时直接引用，不用回头翻文档
IKE_ENCRYPTIONS = ("3des-cbc", "aes-256", "aes-192", "aes-128", "des-cbc")
IKE_AUTH_ALGS = ("md5", "sha1", "sha2-256", "sha2-384", "sha2-512")
IKE_DH_GROUPS = ("group2", "group1", "group5", "group14", "group19", "group20", "group21")
IKE_INTEGRITY_ALGS = ("hmac-md5", "hmac-sha1", "hmac-sha2-256", "hmac-sha2-384")
IKE_PRF_ALGS = ("hmac-md5", "hmac-sha1", "hmac-sha2-256", "hmac-sha2-384")
ESP_AUTH_ALGS = ("md5", "sha1", "sha2-256", "sha2-384", "sha2-512")
ESP_ENCRYPTIONS = ("3des", "des", "aes-256", "aes-192", "aes-128")
IKE_VERSIONS = ("v2", "v1")
PSK_TYPES = ("simple", "cipher")

# 页面写死的取值（即文档 4.8 标准块）：页面 collect() 把本字典合并进 params，
# 生成函数与校验逻辑不变，拿到的仍是完整 params
DEFAULTS = {
    "ike_encryption": "3des-cbc",
    "ike_auth": "md5",
    "ike_dh": "group2",
    "esp_auth": "md5",
    "esp_enc": "3des",
    "ike_version": "v2",
    "psk_type": "simple",
}

# 豁免 ACL 里"其他可上网网段"的起始规则号与步长（文档 4.8：deny=5，permits=10、15）
EXEMPT_DENY_RULE = 5
EXEMPT_PERMIT_START = 10
EXEMPT_RULE_STEP = 5

# 文档 4.8 对端豁免段原文，照抄不"修正"：行首 1 空格缩进（接口下属性行），
# "undo" 与 "nat" 之间是两个空格
UNDO_NAT_LINE = " undo  nat outbound 2000"

# 「在接口下生成 ip address」用的常用子网掩码备选。页面做成**可编辑**下拉：
# 既能从这些值里选，也能手输 /24、24、点分掩码、反掩码等写法，统一由 normalize_mask 归一
SUBNET_MASKS = ("255.255.255.0", "255.255.255.252", "255.255.255.248", "255.255.255.240",
                "255.255.255.224", "255.255.255.192", "255.255.255.128", "255.255.255.254",
                "255.255.0.0", "255.0.0.0")


def parse_net(text):
    """网段归一：任意写法 -> (IP, 反掩码, 点分掩码)。

    感兴趣流 ACL 与豁免 ACL 用反掩码（source ... 0.0.0.255），
    静态路由用点分掩码（ip route-static ... 255.255.255.0），两种写法一次算好。
    兼容前缀（/24、24）、点分掩码（255.255.255.0）、直接反掩码（0.0.0.255）。
    非法抛 ValueError，交由页面 validate 弹窗拦截。
    """
    text = str(text).strip().replace("/", " ")
    parts = text.split()
    if not parts:
        raise ValueError("不能为空")
    ip = parts[0]
    if len(parts) == 1:
        raise ValueError(f"{text} 需带掩码，如 192.168.21.0/24")
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


def normalize_mask(mask):
    """子网掩码归一：/24、24、点分掩码（255.255.255.0）、反掩码（0.0.0.255）-> 点分掩码。

    复用 parse_net（拿 0.0.0.0 当占位 IP），非法掩码抛 ValueError 交页面 validate 拦截。
    """
    return parse_net(f"0.0.0.0 {mask}")[2]


def normalize_ip(ip):
    """接口地址归一：允许带 /xx（只取 IP 部分），非法抛 ValueError"""
    text = str(ip).strip().split("/")[0].strip()
    if not text:
        raise ValueError("不能为空")
    try:
        ipaddress.ip_address(text)
    except ValueError:
        raise ValueError(f"{text} 不是合法 IP")
    return text


def _side(params, local):
    """本端/对端各自的差异字段：网段、peer 名、对端地址、接口、路由表两端互换。
    对端 peer 名与接口留空时回退用本端的（文档 4.8 两端同名同接口）。

    ip_addr：接口下要输出的 `ip address <地址> <掩码>`，空串表示不输出该行。
    只有本端支持（勾选"在接口下生成 ip address"时生效）；对端段文档 4.8 无此行，恒为空。
    """
    if local:
        ip_addr = ""
        if params.get("ip_addr_enable"):
            ip_addr = f"{normalize_ip(params['local_ip'])} {normalize_mask(params['subnet_mask'])}"
        return {"src_net": params["local_net"], "dst_net": params["remote_net"],
                "peer_name": params["local_peer"], "remote_addr": params["peer_ip"],
                "if_name": port_name(params["local_if_type"], params["local_if_num"]),
                "routes": params["routes"], "extra_nets": params["extra_nets"],
                "ip_addr": ip_addr, "undo_nat": False}
    fallback_peer = params.get("peer_peer") or params["local_peer"]
    if_num = params.get("peer_if_num") or params["local_if_num"]
    if_type = params.get("peer_if_type") or params["local_if_type"]
    return {"src_net": params["remote_net"], "dst_net": params["local_net"],
            "peer_name": fallback_peer, "remote_addr": params["local_ip"],
            "if_name": port_name(if_type, if_num),
            "routes": params.get("peer_routes", []),
            "extra_nets": params.get("peer_extra_nets", []),
            "ip_addr": "", "undo_nat": True}


def _route_lines(routes):
    """静态路由行：目的网段 + 点分掩码 + 下一跳；网段或下一跳为空的行跳过"""
    lines = []
    for row in routes or []:
        network = str(row.get("network", "")).strip()
        next_hop = str(row.get("next_hop", "")).strip()
        if not network or not next_hop:
            continue
        ip, _, mask = parse_net(f"{network} {row.get('mask', '')}")
        lines.append(f"ip route-static {ip} {mask} {next_hop}")
    return lines


def _exempt_block(params, side):
    """NAT 豁免段（文档 4.8 第二块）：deny 掉走 VPN 的流量，其余网段正常 Easy IP。
    最后一条 permit 自动追加本端网段，规则号自 EXEMPT_PERMIT_START 起步长 5。"""
    acl = params["exempt_acl"]
    src_ip, src_wc, _ = parse_net(side["src_net"])
    dst_ip, dst_wc, _ = parse_net(side["dst_net"])
    lines = [
        f"acl number {acl}",
        f" rule {EXEMPT_DENY_RULE} deny ip source {src_ip} {src_wc}"
        f" destination {dst_ip} {dst_wc}",
    ]
    number = EXEMPT_PERMIT_START
    for row in side["extra_nets"] or []:
        network = str(row.get("network", "")).strip()
        if not network:
            continue
        ip, wc, _ = parse_net(network)
        lines.append(f" rule {number} permit ip source {ip} {wc}")
        number += EXEMPT_RULE_STEP
    lines.append(f" rule {number} permit ip source {src_ip} {src_wc}")

    lines.append(f"interface {side['if_name']}")
    if side["undo_nat"]:
        lines.append(UNDO_NAT_LINE)
    lines.append(f" nat outbound {acl}")
    return "\n".join(lines)


def _device_block(params, side):
    """单台设备脚本：ACL -> IKE -> IPsec -> 接口应用 + 静态路由（段间 "#" 分隔，
    接口段前按文档 4.8 不加 "#"）；勾选豁免时在其后追加豁免段。

    接口段在勾选"在接口下生成 ip address"时多出一行 ` ip address <地址> <掩码>`，
    排在 ` ipsec policy` 之前（与文档 5.5 防火墙接口段的顺序一致）。
    """
    src_ip, src_wc, _ = parse_net(side["src_net"])
    dst_ip, dst_wc, _ = parse_net(side["dst_net"])
    lines = [
        f"acl number {params['acl_num']}",
        f" rule {params['acl_rule']} permit ip source {src_ip} {src_wc}"
        f" destination {dst_ip} {dst_wc}",
        "#",
        f"ike proposal {params['ike_proposal']}",
        f" encryption-algorithm {params['ike_encryption']}",
        f" authentication-algorithm {params['ike_auth']}",
        " authentication-method pre-share",
        f" dh {params['ike_dh']}",
        "#",
        f"ike peer {side['peer_name']} {params['ike_version']}",
        f" pre-shared-key {params['psk_type']} {params['psk']}",
        f" ike-proposal {params['ike_proposal']}",
        f" remote-address {side['remote_addr']}",
        "#",
        f"ipsec proposal {params['ipsec_proposal']}",
        f" esp authentication-algorithm {params['esp_auth']}",
        f" esp encryption-algorithm {params['esp_enc']}",
        "#",
        f"ipsec policy {params['policy_name']} {params['policy_seq']} isakmp",
        f" security acl {params['acl_num']}",
        f" ike-peer {side['peer_name']}",
        f" proposal {params['ipsec_proposal']}",
        f"interface {side['if_name']}",
    ]
    if side["ip_addr"]:
        lines.append(f" ip address {side['ip_addr']}")
    lines.append(f" ipsec policy {params['policy_name']}")
    body = "\n".join(lines)
    routes = _route_lines(side["routes"])
    if routes:
        body += "\n" + "\n".join(routes)
    if params.get("exempt"):
        body += "\n" + _exempt_block(params, side)
    return body


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

"""防火墙 NAT 策略配置生成（对应文档 5.4）

params 示例:
{
  "rules": [
    {"name": "policy_vpn", "src_zone": "", "dst_zone": "",
     "src_addr": "192.168.10.0 0.0.0.255", "dst_addr": "172.16.10.0 0.0.0.255",
     "action": "no-nat"},
    {"name": "policy_internet", "src_zone": "trust", "dst_zone": "untrust",
     "src_addr": "192.168.10.0 0.0.0.255", "dst_addr": "",
     "action": "source-nat easy-ip"},
  ]
}
区域可空（NAT 豁免规则常不限定区域）；目的地址可空（easy-ip 出方向只看源）。
地址写法：normalize_wildcard 兼容 /24、24、点分掩码、直接填反掩码四种，
统一归一为文档 5.4 的 "IP 反掩码" 写法。
"""
import ipaddress

# NAT 策略动作固定选项（文档 5.4：源 NAT easy-ip / 不做 NAT 豁免）
ACTIONS = ("source-nat easy-ip", "no-nat")


def normalize_wildcard(text):
    """策略地址归一：任意写法 -> "IP 反掩码"（文档 5.4 写法）。

    支持前缀（/24、24）、点分掩码（255.255.255.0）、直接反掩码（0.0.0.255）。
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
            inverted = ipaddress.ip_address(int(ipaddress.ip_address(mask)) ^ 0xFFFFFFFF)
            prefix = ipaddress.ip_network(f"0.0.0.0/{inverted}").prefixlen
        except ValueError:
            raise ValueError(f"反掩码 {mask} 不是合法反掩码（须为连续 0）")
    elif mask.isdigit():
        prefix = int(mask)
        if not 0 <= prefix <= 32:
            raise ValueError(f"掩码前缀 {mask} 超出 0~32")
    else:
        try:
            prefix = ipaddress.ip_network(f"0.0.0.0/{mask}").prefixlen
        except ValueError:
            raise ValueError(f"掩码 {mask} 不是合法掩码")
    wildcard = ipaddress.ip_network((0, prefix)).hostmask   # 0.0.0.0/24 -> 0.0.0.255
    return f"{ip} {wildcard}"


def generate(params):
    """nat-policy 块：缩进与文档 5.2/5.4 一致（rule 1 空格、属性 2 空格），
    区域与目的地址仅在有值时输出"""
    lines = ["nat-policy"]
    for r in params["rules"]:
        if not r.get("name"):
            continue  # 未填规则名的行跳过
        lines.append(f" rule name {r['name']}")
        if r.get("src_zone"):
            lines.append(f"  source-zone {r['src_zone']}")
        if r.get("dst_zone"):
            lines.append(f"  destination-zone {r['dst_zone']}")
        lines.append(f"  source-address {r['src_addr']}")
        if r.get("dst_addr"):
            lines.append(f"  destination-address {r['dst_addr']}")
        lines.append(f"  action {r.get('action') or 'source-nat easy-ip'}")
    return "\n".join(lines)

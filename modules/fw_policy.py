"""防火墙基础安全策略配置生成（对应文档 5.2 基础安全策略）

params 示例:
{
  "rules": [
    {"name": "policy1", "src_zone": "trust", "dst_zone": "untrust",
     "src_addr": "192.168.10.0 24", "dst_addr": "192.168.30.0 24",
     "action": "permit"},
  ]
}
地址写法：normalize_addr 兼容 192.168.10.0/24、192.168.10.0 24、
192.168.10.0 255.255.255.0，统一归一为文档写法 "IP 前缀长度"。
"""
import ipaddress

# 策略动作固定选项
ACTIONS = ("permit", "deny")


def normalize_addr(text):
    """策略地址归一：任意写法 -> "IP 前缀长度"（文档 5.2 写法）。

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
    if mask.isdigit():
        prefix = int(mask)
        if not 0 <= prefix <= 32:
            raise ValueError(f"掩码前缀 {mask} 超出 0~32")
    else:
        try:
            prefix = ipaddress.ip_network(f"0.0.0.0/{mask}").prefixlen
        except ValueError:
            raise ValueError(f"掩码 {mask} 不是合法掩码")
    return f"{ip} {prefix}"


def generate(params):
    """security-policy 块：缩进与文档 5.2 一致（rule 1 空格、属性 2 空格）"""
    lines = ["security-policy"]
    for r in params["rules"]:
        if not r.get("name"):
            continue  # 未填规则名的行跳过
        lines.append(f" rule name {r['name']}")
        lines.append(f"  source-zone {r['src_zone']}")
        lines.append(f"  destination-zone {r['dst_zone']}")
        lines.append(f"  source-address {r['src_addr']}")
        lines.append(f"  destination-address {r['dst_addr']}")
        lines.append(f"  action {r.get('action') or 'permit'}")
    return "\n".join(lines)

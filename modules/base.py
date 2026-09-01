"""公共工具：VLAN 汇总、vlan batch 头部生成、接口名拼接"""

# 接口类型缩写 -> 华为完整接口名前缀。加新类型（如 XGE）只改这一个映射，
# 所有 PortField 控件与 port_name() 自动带出
PORT_TYPE_MAP = {"GE": "GigabitEthernet", "ETH": "Ethernet"}
PORT_TYPES = tuple(PORT_TYPE_MAP)


def port_name(type_token, num):
    """拼接完整接口名。num 含 '/'（如 1/0/1）时原样使用，纯数字时补默认槽位 0/0/。"""
    itype = PORT_TYPE_MAP.get(type_token, str(type_token))
    num = str(num).strip()
    return f"{itype}{num}" if "/" in num else f"{itype}0/0/{num}"


def collect_vlans(port_list):
    """从接口配置列表收集所有 VLAN 号，去重排序。

    port_list: [{"mode": "access", "vlan": 10}, {"mode": "trunk", "pvid": 100, "allow": "110 100"}, ...]
    """
    vlans = set()
    for p in port_list:
        if p.get("mode") == "access":
            if p.get("vlan"):
                vlans.add(int(p["vlan"]))
        elif p.get("mode") == "trunk":
            if p.get("pvid"):
                vlans.add(int(p["pvid"]))
            for v in str(p.get("allow", "")).split():
                vlans.add(int(v))
    return sorted(vlans)


def render_vlan_batch(vlans):
    """生成头部 vlan 创建行：单个用 vlan N，多个用 vlan batch（与文档写法一致）"""
    if not vlans:
        return ""
    if len(vlans) == 1:
        return f"vlan {vlans[0]}"
    return "vlan batch " + " ".join(str(v) for v in vlans)

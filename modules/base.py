"""公共工具：VLAN 汇总、vlan batch 头部生成"""


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

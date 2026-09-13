"""防火墙接口 IP 与安全域配置生成（对应文档 5.1）

params 示例:
{
  "ifaces": [
    {"type": "GE", "num": "1/0/0", "ip": "10.37.1.252",
     "mask": "255.255.255.0", "zone": "dmz"},
  ]
}
zone: trust/untrust/dmz，空串 = 暂不加入安全域（只配 IP）
"""
from .base import port_name

# 域归组输出顺序（文档 5.1 出现顺序：dmz、trust、untrust）
ZONE_ORDER = ("dmz", "trust", "untrust")


def generate(params):
    ifaces = [i for i in params["ifaces"] if i.get("num")]
    # 接口段：连续排列，与文档 5.1 第一部分一致
    lines = []
    for i in ifaces:
        lines.append(f"interface {port_name(i['type'], i['num'])}")
        lines.append(f" ip address {i['ip']} {i['mask']}")

    # 安全域段：按 ZONE_ORDER 归组，同域多条 add interface；
    # 各域块连续排列，接口段与安全域段之间用 ## 分隔（与文档 5.1 一致）
    by_zone = {}
    for i in ifaces:
        if i.get("zone"):
            by_zone.setdefault(i["zone"], []).append(port_name(i["type"], i["num"]))
    zone_blocks = [
        f"firewall zone {zone}\n" + "\n".join(
            f" add interface {n}" for n in by_zone[zone])
        for zone in ZONE_ORDER if by_zone.get(zone)
    ]
    if lines and zone_blocks:
        return "\n".join(lines) + "\n##\n" + "\n".join(zone_blocks)
    return "\n".join(lines + zone_blocks)

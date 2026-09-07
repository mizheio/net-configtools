"""MPLS 基础配置生成（对应文档 4.6）。

单台设备视角：全局使能 MPLS/LDP（lsr-id 一般取回环口地址），再对指定
接口逐一启用 mpls / mpls ldp。PE 设备可追加 route recursive-lookup
tunnel，让无标签公网路由迭代到 LSP 隧道转发（解决 BGP 路由黑洞）。
接口 IP 与 OSPF 由"接口IP配置 / OSPF"页生成，本模块不重复。

params 格式:
{
    "lsr_id": "10.255.1.4",            # LSR-ID，通常为 LoopBack0 地址
    "interfaces": [                    # 每行一个接口，port 为完整接口名
        {"port": "GigabitEthernet0/0/0"},
        {"port": "GigabitEthernet0/0/1"},
    ],
    "gen_loopback": True,              # 生成 interface LoopBack0（IP 取 lsr_id，掩码 32 位）
    "recursive_tunnel": False,         # 末尾追加 route recursive-lookup tunnel
}
"""


def generate(params):
    lsr_id = (params.get("lsr_id") or "").strip()
    if not lsr_id:
        return ""
    blocks = [[f"mpls lsr-id {lsr_id}", "mpls"], ["mpls ldp"]]
    for row in params.get("interfaces", []):
        port = (row.get("port") or "").strip()
        if port:
            blocks.append([f"interface {port}", " mpls", " mpls ldp"])
    if params.get("gen_loopback"):
        blocks.append(["interface LoopBack0", f" ip address {lsr_id} 255.255.255.255"])
    if params.get("recursive_tunnel"):
        blocks.append(["route recursive-lookup tunnel"])
    return "\n#\n".join("\n".join(b) for b in blocks)

"""BGP 配置生成（对应文档 4.5，基础三场景：EBGP / IBGP / RR 反射器）。

params 格式（每行邻居自带 AS 号，无全局"本机 AS"概念）:
{
    "ebgp_peers": [                      # 每两行为一条链路，两行互指
        {"as": "100", "ip": "202.10.10.2"},
        {"as": "65001", "ip": "202.10.10.1"},
    ],
    "ibgp_peers": [                      # 同 AS 行成组，组内两两环回口互指
        {"as": "100", "ip": "2.2.2.2", "next_hop_local": False},
    ],
    "rr_clients": [                      # 同 AS 行成组，勾 RR 的一台对其余出 reflect-client
        {"as": "200", "ip": "5.5.5.5", "is_rr": True},
        {"as": "200", "ip": "6.6.6.6", "is_rr": False},
    ],
}

输出：所有行按 AS 归并，同一 AS 的全部 peer 合并进一个块（跨 EBGP/IBGP/RR 区），
块前标注 "##AS <n>"，块间空行。IBGP/RR 组内建邻固定 connect-interface LoopBack0。
"""


def _rows(rows, *keys):
    """过滤掉指定关键列全为空的行"""
    out = []
    for row in rows or []:
        if any((row.get(k) or "").strip() for k in keys):
            out.append(row)
    return out


def _complete(rows):
    """只保留 as/ip 都填了的行（页面校验保证不出现半填行，这里兜底跳过）"""
    return [r for r in rows if (r.get("as") or "").strip() and (r.get("ip") or "").strip()]


def generate(params):
    edges = {}  # as -> [(peer_ip, peer_as, connect_if, next_hop_local, reflect_client)]

    def add(local_as, peer_ip, peer_as, connect_if="", nhl=False, reflect=False):
        edges.setdefault(local_as, []).append(
            (peer_ip, peer_as, connect_if, bool(nhl), bool(reflect)))

    # EBGP：按输入顺序两行一条链路，两行互指
    ebgp = _complete(_rows(params.get("ebgp_peers", []), "as", "ip"))
    for i in range(0, len(ebgp) - 1, 2):
        a, b = ebgp[i], ebgp[i + 1]
        add(a["as"].strip(), b["ip"].strip(), b["as"].strip())
        add(b["as"].strip(), a["ip"].strip(), a["as"].strip())

    # IBGP：同 AS 行成组，组内两两互指
    groups = {}
    for r in _complete(_rows(params.get("ibgp_peers", []), "as", "ip")):
        groups.setdefault(r["as"].strip(), []).append(r)
    for as_num, members in groups.items():
        for r in members:
            for other in members:
                if other is r:
                    continue
                add(as_num, other["ip"].strip(), as_num,
                    connect_if="LoopBack0", nhl=r.get("next_hop_local"))

    # RR：同 AS 行成组，勾 RR 的一台对其余出 reflect-client，客户端只 peer RR
    groups = {}
    for r in _complete(_rows(params.get("rr_clients", []), "as", "ip")):
        groups.setdefault(r["as"].strip(), []).append(r)
    for as_num, members in groups.items():
        rrs = [r for r in members if r.get("is_rr")]
        clients = [r for r in members if not r.get("is_rr")]
        for rr_row in rrs:
            for c in clients:
                add(as_num, c["ip"].strip(), as_num,
                    connect_if="LoopBack0", reflect=True)
        for c in clients:
            for rr_row in rrs:
                add(as_num, rr_row["ip"].strip(), as_num,
                    connect_if="LoopBack0")

    if not edges:
        return ""
    blocks = []
    for as_num, records in edges.items():
        seen, lines = set(), [f"bgp {as_num}"]
        for peer_ip, peer_as, connect_if, nhl, reflect in records:
            key = (peer_ip, peer_as, connect_if, nhl, reflect)
            if key in seen:
                continue
            seen.add(key)
            lines.append(f" peer {peer_ip} as-number {peer_as}")
            if connect_if:
                lines.append(f" peer {peer_ip} connect-interface {connect_if}")
            if nhl:
                lines.append(f" peer {peer_ip} next-hop-local")
            if reflect:
                lines.append(f" peer {peer_ip} reflect-client")
        blocks.append(f"##AS {as_num}\n" + "\n".join(lines))
    return "\n\n".join(blocks)

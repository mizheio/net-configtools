"""网段划分计算（纯计算，不生成设备配置，modules 层零界面依赖）

三种模式：
{"net": "192.168.10.0/24", "mode": "count",  "count": 4}    # 等分为 N 个子网
{"net": "192.168.10.0/24", "mode": "points", "points": 50}  # 每子网需要 N 个信息点
{"net": "192.168.10.0/24", "mode": "info"}                  # 查询单网段信息
{"net": "192.168.10.0/24", "mode": "alloc",
 "depts": [{"name": "财务部", "points": "50", "vlan": "10"}]}  # 按部门不等长分配，出划分表

口径：信息点数 = 可用主机数（扣网络地址与广播地址）；划分最小到 /30
（1~2 个信息点都按 /30 处理）；子网个数/信息点数不是 2 的幂时向上取整；
按部门分配时按行顺序从低地址往高地址切，每部门取能容纳的最小子网，
网关习惯取每段第一个可用地址（DHCP 池范围即该段可用主机起止）。
"""
import ipaddress
from itertools import islice

# 子网列表最多列出的个数，超出只列前 64 个并注明总数
MAX_SHOW = 64

# 划分允许的最小子网前缀：/30（2 个信息点），不引入 /31、/32 口径
MIN_PREFIX = 30

# RFC1918 私网段（用于地址类别标注）
_PRIVATE_NETS = [ipaddress.ip_network(n) for n in
                 ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")]


def normalize_mask(mask):
    """掩码归一化：/24、24、点分十进制 -> 前缀长度 int；非法返回 None"""
    text = str(mask).strip().lstrip("/")
    try:
        if text.isdigit():
            prefix = int(text)
            return prefix if 0 <= prefix <= 32 else None
        # 点分掩码交给 ipaddress 校验（非连续掩码如 255.0.255.0 会抛 ValueError）
        return ipaddress.ip_network(f"0.0.0.0/{text}").prefixlen
    except ValueError:
        return None


def parse_net(text):
    """网段文本 -> ip_network（strict=False，主机地址自动吸附到所在网段）。

    支持 "192.168.10.0/24"、"192.168.10.0 255.255.255.0"（空格/逗号分隔）、
    "192.168.10.77/24"（按所在网段算）。格式非法抛 ValueError。
    """
    text = str(text).strip().replace("，", " ").replace(",", " ")
    parts = text.split()
    if len(parts) == 1:
        if "/" not in text:
            raise ValueError("网段需带掩码，如 192.168.10.0/24 或 192.168.10.0 255.255.255.0")
        ip, mask = text.split("/", 1)
    elif len(parts) == 2:
        ip, mask = parts
    else:
        raise ValueError("网段格式无法识别，请按 192.168.10.0/24 或 192.168.10.0 255.255.255.0 填写")
    prefix = normalize_mask(mask)
    if prefix is None:
        raise ValueError(f"掩码 {mask} 不是合法掩码")
    try:
        return ipaddress.ip_network(f"{ip}/{prefix}", strict=False)
    except ValueError:
        raise ValueError(f"IP {ip} 不是合法地址")


def usable(prefix):
    """前缀对应的可用信息点数：/31=2（RFC 3021）、/32=1，其余 2^h-2"""
    if prefix >= 32:
        return 1
    if prefix == 31:
        return 2
    return (1 << (32 - prefix)) - 2


def _addr_class(ip):
    """地址类别：A/B/C/D/E + 是否 RFC1918 私网"""
    first = int(str(ip).split(".")[0])
    if first == 127:
        return "A 类（环回）"
    if first < 1:
        return "保留地址"
    if first <= 126:
        base = "A 类"
    elif first <= 191:
        base = "B 类"
    elif first <= 223:
        base = "C 类"
    elif first <= 239:
        return "D 类（组播）"
    else:
        return "E 类（保留）"
    if any(ipaddress.ip_address(ip) in net for net in _PRIVATE_NETS):
        return f"{base} · 私网地址"
    return base


def plan_prefix_by_count(base, count):
    """按子网个数求新前缀：向上取整到 2 的幂。返回 (新前缀, 实际子网数)。

    划分后前缀会小于 MIN_PREFIX（无可用信息点）时抛 ValueError。
    """
    if count < 2:
        raise ValueError("划分个数需大于 1（只查单网段信息请选“查询本网段信息”）")
    bits = (count - 1).bit_length()          # 借位数，向上取整
    new_prefix = base.prefixlen + bits
    if new_prefix > MIN_PREFIX:
        raise ValueError(
            f"划分为 {count} 个子网需要 /{new_prefix}，已小于最小可用网段 /{MIN_PREFIX}"
            f"（每段仅 {usable(new_prefix)} 个信息点），请减少子网个数或扩大原网段")
    return new_prefix, 1 << bits


def plan_prefix_by_points(base, points):
    """按每子网信息点数求新前缀：找能容纳的最小子网（不小于 /30）。

    返回 (新前缀, 可划分子网数)。信息点数超网段总容量抛 ValueError。
    """
    if points < 1:
        raise ValueError("信息点数需为正整数")
    if points > usable(base.prefixlen):
        raise ValueError(f"每子网 {points} 个信息点已超过网段总容量 "
                         f"{usable(base.prefixlen)}（/{base.prefixlen}），请扩大原网段")
    prefix = MIN_PREFIX
    while usable(prefix) < points:
        prefix -= 1
    return prefix, 1 << (prefix - base.prefixlen)


def render_info(net):
    """模式三：单网段信息文本块（掩码/反掩码/网络广播/范围/网关建议/类别）"""
    lines = [
        f"网段信息: {net.with_prefixlen}",
        f"  子网掩码   {str(net.netmask):<16}(/{net.prefixlen})",
        f"  反掩码     {str(net.hostmask):<16}<- OSPF network / ACL rule 可直接抄",
        f"  网络地址   {net.network_address}",
        f"  广播地址   {net.broadcast_address}",
    ]
    if net.prefixlen >= 31:
        lines.append(f"  可用主机   共 {usable(net.prefixlen)} 个地址"
                     "（点对点/主机段，无传统可用主机范围）")
    else:
        lines.append(f"  可用主机   {net.network_address + 1} ~ {net.broadcast_address - 1}"
                     f"   (共 {usable(net.prefixlen)} 个)")
        lines.append(f"  网关建议   {net.network_address + 1}          (习惯取第一个可用地址)")
    lines.append(f"  地址类别   {_addr_class(str(net.network_address))}")
    return "\n".join(lines)


def render_plan(net, count=None, points=None):
    """模式一/二：网段划分文本块。count（子网个数）与 points（每子网信息点数）二选一"""
    if count is not None:
        new_prefix, n_subnets = plan_prefix_by_count(net, count)
        head = f"网段划分: {net.with_prefixlen} → 划分为 {count} 个子网"
        if n_subnets != count:
            head += f"（向上取整到 {n_subnets} 个）"
        detail = f"  每子网可用  {usable(new_prefix)} 个信息点"
    else:
        new_prefix, n_subnets = plan_prefix_by_points(net, points)
        head = f"网段划分: {net.with_prefixlen} → 每子网需要 {points} 个信息点"
        detail = (f"  可划分为    {n_subnets} 个子网"
                  f"（每子网可用 {usable(new_prefix)} 个信息点，余量 {usable(new_prefix) - points} 个）")

    shown = list(islice(net.subnets(new_prefix=new_prefix), MAX_SHOW))
    truncated = n_subnets > MAX_SHOW
    new_net = ipaddress.ip_network(f"0.0.0.0/{new_prefix}")   # 划分后的掩码，不是原网段的
    lines = [
        head,
        f"  子网前缀    /{new_prefix}   (掩码 {new_net.netmask}，反掩码 {new_net.hostmask})",
        detail,
    ]
    for n, s in enumerate(shown, 1):
        rng = f"{s.network_address + 1} ~ {s.broadcast_address - 1}"
        lines.append(f"  {n:>2}) {s.with_prefixlen:<24}{rng:<36} 广播 {s.broadcast_address}")
    if truncated:
        lines.append(f"  ……（共 {n_subnets} 个子网，仅列出前 {MAX_SHOW} 个）")
    return "\n".join(lines)


def render_calc(params):
    """按 params 的 mode 分发到四种输出"""
    net = parse_net(params["net"])
    mode = params.get("mode", "info")
    if mode == "count":
        return render_plan(net, count=int(params["count"]))
    if mode == "points":
        return render_plan(net, points=int(params["points"]))
    if mode == "alloc":
        return render_alloc(net, params.get("depts") or [])
    return render_info(net)


# ------------------------------------------------------------ 按部门分配（划分表）

def _disp_w(text):
    """显示宽度：CJK 等全角字符按 2 列计，用于表格对齐"""
    return sum(2 if ord(ch) > 0x2E7F else 1 for ch in str(text))


def _pad(text, width):
    return f"{text}{' ' * max(0, width - _disp_w(text))}"


def alloc_departments(net, depts):
    """按部门行顺序做首次适配分配：每部门取能容纳的最小子网（不小于 /30），
    从低到高找第一个放得下的空闲段切一刀（子网必须落在自身对齐边界上）。

    depts: [{"name": "财务部"(可空,缺省"部门N"), "points": "50"(必填), "vlan": "10"(可空)}, ...]
    返回 (分配列表, 空闲段列表)。分配项:
      {"seq","name","vlan","points","subnet","gw","first","last","usable"}
    空闲段为 [(起始地址, 结束地址), ...]（对齐空隙 + 未分配尾部，含单地址段）。
    信息点数超网段总容量或空间不足时抛 ValueError（指明行号）。
    """
    allocs = []
    free = [(int(net.network_address), int(net.broadcast_address))]
    for seq, d in enumerate(depts, 1):
        name = str(d.get("name") or f"部门{seq}")
        try:
            points = int(str(d.get("points")).strip())
        except (TypeError, ValueError):
            raise ValueError(f"第 {seq} 行（{name}）信息点数需为正整数")
        if points < 1:
            raise ValueError(f"第 {seq} 行（{name}）信息点数需为正整数")
        if points > usable(net.prefixlen):
            raise ValueError(f"第 {seq} 行（{name}）需要 {points} 个信息点，"
                             f"超过网段总容量 {usable(net.prefixlen)}（/{net.prefixlen}）")
        prefix = max(net.prefixlen, MIN_PREFIX)
        while usable(prefix) < points:
            prefix -= 1
        size = 1 << (32 - prefix)
        placed = None
        for gi, (lo, hi) in enumerate(free):
            start = (lo + size - 1) & ~(size - 1)        # 向上对齐到子网边界
            if start + size - 1 <= hi:
                placed = (gi, start, lo, hi)
                break
        if placed is None:
            raise ValueError(f"第 {seq} 行（{name}）{points} 个信息点需要 /{prefix}"
                             f" 共 {size} 个地址（含边界对齐），网段剩余空间不足，"
                             f"请扩大原网段、压缩信息点或调整部门顺序")
        gi, start, lo, hi = placed
        free.pop(gi)                      # 切开空闲段：前面零头 + 子网 + 后面零头
        if start > lo:
            free.insert(gi, (lo, start - 1))
            gi += 1
        if start + size <= hi:
            free.insert(gi, (start + size, hi))
        subnet = ipaddress.ip_network((start, prefix))
        allocs.append({
            "seq": seq, "name": name, "vlan": str(d.get("vlan") or ""),
            "points": points, "subnet": subnet,
            "gw": str(subnet.network_address + 1),          # 习惯取第一个可用地址
            "first": str(subnet.network_address + 1),
            "last": str(subnet.broadcast_address - 1),
            "usable": usable(prefix),
        })
    return allocs, free


def render_alloc(net, depts):
    """模式四：按部门分配，输出子网划分表（纯制表，不生成设备配置）"""
    allocs, remain = alloc_departments(net, depts)
    used = sum(1 << (32 - a["subnet"].prefixlen) for a in allocs)
    head = (f"子网划分表: {net.with_prefixlen} → 按部门分配"
            f"（共 {len(allocs)} 个部门，占用 {used} 个地址）")
    cols = ["序号", "VLAN", "部门", "子网", "掩码", "反掩码", "网关",
            "DHCP 地址池范围", "广播", "信息点"]
    rows = []
    for a in allocs:
        s = a["subnet"]
        rows.append([str(a["seq"]), a["vlan"] or "-", a["name"], s.with_prefixlen,
                     str(s.netmask), str(s.hostmask), a["gw"],
                     f"{a['first']} ~ {a['last']}", str(s.broadcast_address),
                     f"{a['points']}→{a['usable']}"])
    widths = [max(_disp_w(cols[i]), *(_disp_w(r[i]) for r in rows)) for i in range(len(cols))]
    lines = [head, "  " + "  ".join(_pad(c, widths[i]) for i, c in enumerate(cols))]
    for r in rows:
        lines.append("  " + "  ".join(_pad(c, widths[i]) for i, c in enumerate(r)))
    if remain:
        total = sum(b - a + 1 for a, b in remain)
        parts = "、".join(f"{ipaddress.ip_address(a)} ~ {ipaddress.ip_address(b)}"
                          if a != b else str(ipaddress.ip_address(a)) for a, b in remain)
        lines.append(f"剩余未分配: {parts}（共 {total} 个地址）")
    else:
        lines.append("网段已全部分配完")
    return "\n".join(lines)

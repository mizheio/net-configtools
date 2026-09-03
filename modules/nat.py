"""Easy IP（NAT Outbound）配置生成（对应文档 4.3）。

Easy IP 复用出接口的公网 IP 做地址转换：基本 ACL 匹配允许上网的私网网段，
出接口下 nat outbound 引用该 ACL，可选追加指向运营商的默认静态路由。
规则编号从 5 起、步长 5（与华为默认编号规则一致）。
"""


def generate(params):
    rules = [row for row in params["rules"] if row.get("source")]
    if not (rules and params.get("out_interface")):
        return ""
    lines = [f"acl number {params['acl_number']}"]
    for i, row in enumerate(rules):
        lines.append(f" rule {5 + i * 5} permit source {row['source']} {row['wildcard']}")
    lines += [
        "#",
        f"interface {params['out_interface']}",
        f" nat outbound {params['acl_number']}",
    ]
    next_hop = params.get("next_hop", "")
    if next_hop:
        lines += ["#", f"ip route-static 0.0.0.0 0.0.0.0 {next_hop}"]
    return "\n".join(lines)

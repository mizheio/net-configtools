"""普通 / 高级 ACL 配置生成（对应文档 2.7）。"""


def generate(params):
    rules = [row for row in params["rules"] if row.get("source")]
    if not rules:
        return ""
    lines = [f"acl number {params['acl_number']}"]
    advanced = params["acl_type"] == "advanced"
    for row in rules:
        prefix = f" rule {row['action']}"
        if advanced:
            prefix += f" ip source {row['source']} {row['source_wildcard']}"
            if row.get("destination"):
                prefix += f" destination {row['destination']} {row['destination_wildcard']}"
        else:
            prefix += f" source {row['source']} {row['source_wildcard']}"
        lines.append(prefix)
    if params.get("bind_interface"):
        lines += [
            f"interface {params['bind_interface']}",
            f" traffic-filter {params['direction']} acl {params['acl_number']}",
        ]
    return "\n".join(lines)

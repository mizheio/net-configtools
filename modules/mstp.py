"""MSTP 配置生成（对应文档 2.3）。"""
from .base import render_vlan_batch


def collect_vlans(params):
    return sorted({int(row["vlan"]) for row in params["instances"] if str(row.get("vlan", "")).isdigit()})


def generate(params):
    instances = [row for row in params["instances"] if row.get("instance") and row.get("vlan")]
    if not instances:
        return ""
    lines = ["stp region-configuration", f" region-name {params['region_name']}"]
    for row in instances:
        lines.append(f" instance {row['instance']} vlan {row['vlan']}")
    lines.append(" active region-configuration")
    for row in instances:
        if row.get("root") in ("primary", "secondary"):
            lines.append(f"stp instance {row['instance']} root {row['root']}")
    return "\n".join(lines)


def generate_full(params):
    body = generate(params)
    if not body:
        return ""
    header = render_vlan_batch(collect_vlans(params))
    return f"{header}\n{body}" if header else body

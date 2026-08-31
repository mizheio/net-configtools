"""OSPF 配置生成（对应文档 2.5）。"""


def generate(params):
    networks = [row for row in params["networks"] if row.get("network")]
    if not networks:
        return ""
    lines = [f"ospf {params['process_id']} router-id {params['router_id']}", f" area {params['area']}"]
    for row in networks:
        lines.append(f"  network {row['network']} {row['wildcard']}")
    return "\n".join(lines)

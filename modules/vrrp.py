"""VRRP 配置生成（对应文档 2.2）。"""
from .base import render_vlan_batch


def collect_vlans(params):
    return sorted({int(row["vlan"]) for row in params["ifaces"] if str(row.get("vlan", "")).isdigit()})


def generate(params):
    """生成多 VLAN 的 VRRP 配置。

    role 为 primary 时追加优先级、抢占延时和接口跟踪；secondary 只生成
    基础 VRRP 与认证命令，正好对应主 10 备 20 / 主 20 备 10 两种场景。
    """
    blocks = []
    for row in params["ifaces"]:
        if not row.get("vlan"):
            continue
        vlan = row["vlan"]
        lines = [
            f"interface Vlanif{vlan}",
            f" ip address {row['ip']} {row['mask']}",
            f" vrrp vrid {vlan} virtual-ip {row['virtual_ip']}",
        ]
        if row.get("role") == "primary":
            lines.append(f" vrrp vrid {vlan} priority {params['priority']}")
            lines.append(f" vrrp vrid {vlan} preempt-mode timer delay {params['preempt_delay']}")
            if params.get("track_interface"):
                lines.append(
                    f" vrrp vrid {vlan} track interface {params['track_interface']} "
                    f"reduced {params['track_reduced']}"
                )
        if params.get("auth"):
            lines.append(f" vrrp vrid {vlan} authentication-mode md5 {params['auth']}")
        blocks.append("\n".join(lines))
    return "\n#\n".join(blocks)


def generate_full(params):
    body = generate(params)
    if not body:
        return ""
    header = render_vlan_batch(collect_vlans(params))
    return f"{header}\n{body}" if header else body

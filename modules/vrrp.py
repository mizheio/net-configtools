"""VRRP 双机热备配置生成（对应文档 2.2）。"""
from .base import render_vlan_batch


def collect_vlans(params):
    return sorted({int(row["vlan"]) for row in params["plans"] if str(row.get("vlan", "")).isdigit()})


def generate_device(params, device):
    """生成设备 1 或设备 2 的 VRRP 正文；每个 VLAN 可独立选择主/备角色。"""
    blocks = []
    ip_key = "device1_ip" if device == "device1" else "device2_ip"
    role_key = "device1_role" if device == "device1" else "device2_role"
    for row in params["plans"]:
        if not row.get("vlan"):
            continue
        vlan = row["vlan"]
        lines = [
            f"interface Vlanif{vlan}",
            f" ip address {row[ip_key]} {row['mask']}",
            f" vrrp vrid {vlan} virtual-ip {row['virtual_ip']}",
        ]
        if row.get(role_key) == "primary":
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


def generate_device_full(params, device):
    body = generate_device(params, device)
    if not body:
        return ""
    header = render_vlan_batch(collect_vlans(params))
    return f"{header}\n{body}" if header else body


def generate_pair(params):
    """生成便于预览的设备 1、设备 2 两段独立配置。不可把整份内容粘贴到同一设备。"""
    device1 = generate_device_full(params, "device1")
    device2 = generate_device_full(params, "device2")
    if not device1 and not device2:
        return ""
    return "\n\n".join([
        "===== 设备 1 配置 =====",
        device1,
        "===== 设备 2 配置 =====",
        device2,
    ])

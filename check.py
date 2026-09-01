"""对拍验收脚本：生成结果与《华为ensp基础配置命令.md》标准块逐行比对

运行: python check.py
比较时忽略 "#" 分隔行和行尾空格（文档里 DHCP 块本身带 #，接口块不带，均为粘贴无影响的分隔符）
"""
from modules import if_vlan, vlanif, dhcp, vrrp, mstp, eth_trunk, ospf, acl


def _strip(text):
    return [l.rstrip() for l in text.splitlines() if l.strip() != "#"]


def run(name, actual, expected):
    a, e = _strip(actual), _strip(expected)
    if a == e:
        print(f"[PASS] {name}")
        return True
    print(f"[FAIL] {name}")
    for i in range(max(len(a), len(e))):
        ai = a[i] if i < len(a) else "<缺失>"
        ei = e[i] if i < len(e) else "<缺失>"
        if ai != ei:
            print(f"    第{i + 1}行  实际: {ai!r}  期望: {ei!r}")
    return False


ok = True

# ---- 文档 1.1 接入交换机接终端（access，千兆）----
ok &= run("1.1 access口", if_vlan.generate_full({"ports": [
    {"type": "GE", "num": 1, "mode": "access", "vlan": "10"},
]}), """\
vlan 10
interface GigabitEthernet0/0/1
 port link-type access
 port default vlan 10""")

# ---- 文档 1.2 接入交换机连 AP（trunk + pvid，百兆）----
ok &= run("1.2 AP口trunk", if_vlan.generate_full({"ports": [
    {"type": "ETH", "num": 1, "mode": "trunk", "pvid": "100", "allow": "110 100"},
]}), """\
vlan batch 100 110
interface Ethernet0/0/1
 port link-type trunk
 port trunk pvid vlan 100
 port trunk allow-pass vlan 110 100""")

# ---- 文档 1.3 接上游汇聚/核心（trunk，千兆）----
ok &= run("1.3 上联trunk", if_vlan.generate_full({"ports": [
    {"type": "GE", "num": 1, "mode": "trunk", "allow": "10 20"},
]}), """\
vlan batch 10 20
interface GigabitEthernet0/0/1
 port link-type trunk
 port trunk allow-pass vlan 10 20""")

# ---- 自定义槽位：千兆板卡号 1/0/x + 百兆口混排（编号含 / 时原样使用）----
ok &= run("1.4 自定义槽位混合", if_vlan.generate_full({"ports": [
    {"type": "GE", "num": "1/0/1", "mode": "access", "vlan": "10"},
    {"type": "ETH", "num": "0/0/2", "mode": "trunk", "allow": "10 20"},
]}), """\
vlan batch 10 20
interface GigabitEthernet1/0/1
 port link-type access
 port default vlan 10
interface Ethernet0/0/2
 port link-type trunk
 port trunk allow-pass vlan 10 20""")

# ---- 旧格式兼容：num 为纯数字时自动补默认槽位 0/0/ ----
ok &= run("1.5 纯数字编号兼容", if_vlan.generate_full({"ports": [
    {"type": "ETH", "num": 3, "mode": "access", "vlan": "20"},
]}), """\
vlan 20
interface Ethernet0/0/3
 port link-type access
 port default vlan 20""")

# ---- 多接口混合（1个access + 2个trunk，vlan汇总去重）----
ok &= run("多接口混合", if_vlan.generate_full({"ports": [
    {"type": "GE", "num": 1, "mode": "access", "vlan": "10"},
    {"type": "GE", "num": 2, "mode": "trunk", "allow": "10 20"},
    {"type": "ETH", "num": 5, "mode": "trunk", "pvid": "100", "allow": "100 110"},
]}), """\
vlan batch 10 20 100 110
interface GigabitEthernet0/0/1
 port link-type access
 port default vlan 10
interface GigabitEthernet0/0/2
 port link-type trunk
 port trunk allow-pass vlan 10 20
interface Ethernet0/0/5
 port link-type trunk
 port trunk pvid vlan 100
 port trunk allow-pass vlan 100 110""")

# ---- 文档 2.1 Vlanif 配 IP ----
ok &= run("2.1 Vlanif", vlanif.generate({"ifaces": [
    {"vlan": "10", "ip": "192.168.10.1", "mask": "255.255.255.0"},
    {"vlan": "20", "ip": "192.168.20.1", "mask": "255.255.255.0"},
]}), """\
interface Vlanif10
 ip address 192.168.10.1 255.255.255.0
interface Vlanif20
 ip address 192.168.20.1 255.255.255.0""")

# ---- 文档 2.6 DHCP 全局地址池 ----
ok &= run("2.6 DHCP全局", dhcp.generate({
    "mode": "global", "if_vlan": "10", "gateway": "192.168.10.1",
    "network": "192.168.10.0", "mask": "255.255.255.0",
    "dns": "192.168.200.88", "lease": "7",
}), """\
dhcp enable
#
ip pool pool-vlan10
 gateway-list 192.168.10.1
 network 192.168.10.0 mask 255.255.255.0
 dns-list 192.168.200.88
 lease day 7
#
interface Vlanif10
 dhcp select global""")

# ---- 文档 2.6 DHCP 中继（网关设备侧）----
ok &= run("2.6b DHCP中继", dhcp.generate({
    "mode": "relay", "if_vlan": "10", "relay_ip": "192.168.200.254",
}), """\
dhcp enable
#
interface Vlanif10
 dhcp select relay
 dhcp relay server-ip 192.168.200.254""")

# ---- 文档 2.6 DHCP 主备（excluded-ip-address 由网段自动切半）----
dhcp_common = {"mode": "backup", "if_vlan": "10", "gateway": "192.168.10.254",
               "network": "192.168.10.0", "mask": "255.255.255.0", "dns": "192.168.200.88"}
ok &= run("2.6c DHCP主池", dhcp.generate({**dhcp_common, "role": "primary"}), """\
ip pool pool-vlan10
 gateway-list 192.168.10.254
 network 192.168.10.0 mask 255.255.255.0
 excluded-ip-address 192.168.10.125 192.168.10.254
 dns-list 192.168.200.88""")

ok &= run("2.6d DHCP备池", dhcp.generate({**dhcp_common, "role": "secondary"}), """\
ip pool pool-vlan10
 gateway-list 192.168.10.254
 network 192.168.10.0 mask 255.255.255.0
 excluded-ip-address 192.168.10.1 192.168.10.124
 excluded-ip-address 192.168.10.252 192.168.10.254
 dns-list 192.168.200.88""")

# ---- 文档 4.11 路由器 DHCP：全局地址池绑物理口（4.11 原文接口误写 dhcp select
#      interface，按语义修正为 dhcp select global，与 2.6 服务器侧一致）----
ok &= run("4.11 DHCP物理口", dhcp.generate({
    "mode": "global", "if_kind": "port", "if_port": "GigabitEthernet0/0/1",
    "gateway": "192.168.10.1", "network": "192.168.10.0",
    "mask": "255.255.255.0", "dns": "192.168.200.88", "lease": "7",
}), """\
dhcp enable
#
ip pool pool-vlan10
 gateway-list 192.168.10.1
 network 192.168.10.0 mask 255.255.255.0
 dns-list 192.168.200.88
 lease day 7
#
interface GigabitEthernet0/0/1
 dhcp select global""")

# ---- 文档 2.2 VRRP：主10备20 / 主20备10 双机互备 ----
vrrp_params = {
    "priority": "120", "preempt_delay": "10", "track_interface": "GigabitEthernet0/0/6",
    "track_reduced": "50", "auth": "admin123", "plans": [
        {"vlan": "10", "mask": "255.255.255.0", "virtual_ip": "192.168.10.254",
         "device1_ip": "192.168.10.252", "device1_role": "primary",
         "device2_ip": "192.168.10.253", "device2_role": "secondary"},
        {"vlan": "20", "mask": "255.255.255.0", "virtual_ip": "192.168.20.254",
         "device1_ip": "192.168.20.252", "device1_role": "secondary",
         "device2_ip": "192.168.20.253", "device2_role": "primary"},
    ],
}
ok &= run("2.2 VRRP设备1(主10备20)", vrrp.generate_device_full(vrrp_params, "device1"), """\
vlan batch 10 20
interface Vlanif10
 ip address 192.168.10.252 255.255.255.0
 vrrp vrid 10 virtual-ip 192.168.10.254
 vrrp vrid 10 priority 120
 vrrp vrid 10 preempt-mode timer delay 10
 vrrp vrid 10 track interface GigabitEthernet0/0/6 reduced 50
 vrrp vrid 10 authentication-mode md5 admin123
interface Vlanif20
 ip address 192.168.20.252 255.255.255.0
 vrrp vrid 20 virtual-ip 192.168.20.254
 vrrp vrid 20 authentication-mode md5 admin123""")

ok &= run("2.2 VRRP设备2(主20备10)", vrrp.generate_device_full(vrrp_params, "device2"), """\
vlan batch 10 20
interface Vlanif10
 ip address 192.168.10.253 255.255.255.0
 vrrp vrid 10 virtual-ip 192.168.10.254
 vrrp vrid 10 authentication-mode md5 admin123
interface Vlanif20
 ip address 192.168.20.253 255.255.255.0
 vrrp vrid 20 virtual-ip 192.168.20.254
 vrrp vrid 20 priority 120
 vrrp vrid 20 preempt-mode timer delay 10
 vrrp vrid 20 track interface GigabitEthernet0/0/6 reduced 50
 vrrp vrid 20 authentication-mode md5 admin123""")

# ---- 文档 2.3 MSTP：主 10 备 20 ----
ok &= run("2.3 MSTP", mstp.generate_full({
    "region_name": "HUAWEI", "instances": [
        {"instance": "1", "vlan": "10", "root": "primary"},
        {"instance": "2", "vlan": "20", "root": "secondary"},
    ],
}), """\
vlan batch 10 20
stp region-configuration
 region-name HUAWEI
 instance 1 vlan 10
 instance 2 vlan 20
 active region-configuration
stp instance 1 root primary
stp instance 2 root secondary""")

# ---- 文档 2.4 基础链路聚合（文档基础块本身带 mode lacp-static，v0.3 起输出该行）----
ok &= run("2.4 链路聚合", eth_trunk.generate_full({
    "trunk_id": "1",
    "vlans": [{"vlan": "10"}, {"vlan": "20"}],
    "members": [{"type": "GE", "num": "22"}, {"type": "GE", "num": "23"},
                {"type": "ETH", "num": "24"}],
}), """\
vlan batch 10 20
interface Eth-Trunk1
 port link-type trunk
 port trunk allow-pass vlan 10 20
 mode lacp-static
interface GigabitEthernet0/0/22
 eth-trunk 1
interface GigabitEthernet0/0/23
 eth-trunk 1
interface Ethernet0/0/24
 eth-trunk 1""")

# ---- 成员接口用完整接口名（界面 PortField 输出格式）----
ok &= run("2.4b 成员口完整名", eth_trunk.generate_full({
    "trunk_id": "1",
    "vlans": [{"vlan": "10"}],
    "members": [{"port": "Ethernet0/0/24"}],
}), """\
vlan 10
interface Eth-Trunk1
 port link-type trunk
 port trunk allow-pass vlan 10
 mode lacp-static
interface Ethernet0/0/24
 eth-trunk 1""")

# ---- 文档 2.4 LACP 主2备1：主设备 ----
lacp_params = {
    "mode": "lacp", "trunk_id": "1",
    "vlans": [{"vlan": "10"}, {"vlan": "20"}],
    "members": [{"port": "GigabitEthernet0/0/22"},
                {"port": "GigabitEthernet0/0/23"},
                {"port": "GigabitEthernet0/0/24"}],
    "system_priority": "100", "max_active": "2", "preempt_delay": "10",
    "member_priority": "100",
    "priority_ports": ["GigabitEthernet0/0/23", "GigabitEthernet0/0/24"],
}
ok &= run("2.4c LACP主设备", eth_trunk.generate_device(lacp_params, "master"), """\
lacp system-priority 100
interface Eth-Trunk1
 port link-type trunk
 port trunk allow-pass vlan 10 20
 mode lacp-static
 max active-linknumber 2
 lacp preempt enable
 lacp preempt delay 10
interface GigabitEthernet0/0/22
 eth-trunk 1
interface GigabitEthernet0/0/23
 eth-trunk 1
 lacp priority 100
interface GigabitEthernet0/0/24
 eth-trunk 1
 lacp priority 100""")

ok &= run("2.4d LACP从设备", eth_trunk.generate_device(lacp_params, "slave"), """\
interface Eth-Trunk1
 port link-type trunk
 port trunk allow-pass vlan 10 20
 mode lacp-static
 max active-linknumber 2
interface GigabitEthernet0/0/22
 eth-trunk 1
interface GigabitEthernet0/0/23
 eth-trunk 1
interface GigabitEthernet0/0/24
 eth-trunk 1""")

# ---- 文档 2.5 OSPF ----
ok &= run("2.5 OSPF", ospf.generate({
    "process_id": "1", "router_id": "10.1.1.1", "area": "0.0.0.0",
    "networks": [{"network": "192.168.50.0", "wildcard": "0.0.0.255"},
                 {"network": "192.168.60.0", "wildcard": "0.0.0.255"}],
}), """\
ospf 1 router-id 10.1.1.1
 area 0.0.0.0
  network 192.168.50.0 0.0.0.255
  network 192.168.60.0 0.0.0.255""")

# ---- 文档 2.7 高级 ACL ----
ok &= run("2.7 ACL", acl.generate({
    "acl_type": "advanced", "acl_number": "3000", "bind_interface": "GigabitEthernet0/0/1",
    "direction": "inbound", "rules": [
        {"action": "permit", "source": "192.168.10.0", "source_wildcard": "0.0.0.255", "destination": "192.168.10.0", "destination_wildcard": "0.0.0.255"},
        {"action": "deny", "source": "192.168.10.0", "source_wildcard": "0.0.0.255", "destination": "192.168.200.0", "destination_wildcard": "0.0.0.255"},
    ],
}), """\
acl number 3000
 rule permit ip source 192.168.10.0 0.0.0.255 destination 192.168.10.0 0.0.0.255
 rule deny ip source 192.168.10.0 0.0.0.255 destination 192.168.200.0 0.0.0.255
interface GigabitEthernet0/0/1
 traffic-filter inbound acl 3000""")

print()
print("全部通过" if ok else "存在失败项")
raise SystemExit(0 if ok else 1)

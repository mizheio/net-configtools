"""页面包：界面页按设备类别分文件存放，App 通过本注册表装配页签

加新页面三步：
1. 在对应类别文件里写 XxxPage 类（契约见 gui.py：TITLE / collect / validate /
   render / render_summary / summary_vlans / set_lib_values）
2. 在下方 CATEGORY_PAGES 对应类别加一项（双栖页面同时挂两个类别）
3. modules/ 里确认有对应 generate 函数
"""
from .switch import IfVlanPage, VlanifPage, VrrpPage, MstpPage, EthTrunkPage
from .common import OspfPage, AclPage
from .dhcp_switch import DhcpSwitchPage
from .dhcp_router import DhcpRouterPage
from .interface import InterfacePage
from .nat import NatPage

# 类别 -> 页签顺序；交换机和路由器分别使用各自的DHCP页面
CATEGORY_PAGES = {
    "交换机": [IfVlanPage, VlanifPage, VrrpPage, MstpPage, EthTrunkPage,
              DhcpSwitchPage, OspfPage, AclPage],
    "路由器": [InterfacePage, DhcpRouterPage, OspfPage, AclPage, NatPage],
}

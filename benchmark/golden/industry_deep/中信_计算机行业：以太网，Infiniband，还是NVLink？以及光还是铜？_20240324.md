# 证券研究报告·行业动态

# 以太网,Infiniband,还是NVLink？以及光还是铜？

分析师：刘永旭liuyongxu@csc.com.cnSAC 编号:S1440520070014

分析师：阎贵成
yanguicheng@csc.com.cnSAC 编号：S1440518040002SFC 编号：BNS315
分析师：武超则
wuchaoze@csc.com.cn
SAC 编号：S1440513090003
SFC 编号：BEM208

分析师：杨伟松yangweisong@csc.com.cnSAC 编号:S1440522120003

发布日期：2024年3月24日

本报告由中信建投证券股份有限公司在中华人民共和国（仅为本报告目的，不包括香港、澳门、台湾）提供。在遵守适用的法律法规情况下，本报告亦可能由中信建投（国际）证券有限公司在香港提供。同时请务必阅读正文之后的免责条款和声明。

## 核心观点

以太网 or Infiniband？在传统云计算数据中心领域，以太网技术的产品市占率保持绝对领先的地位；但是在HPC领域，对于网络的性能要求越高，IB的渗透率越高。我们认为，IB网络短期内在AI领域仍然具备较强的优势，但是以太网ROCE的发展也有可能会使得其渗透率有一定的提升。

 NVLink-Network或成最终赢家。我们认为NVLink依靠其数倍于PCIe的带宽优势，单位算力成本有望具备很强的性价比，或成最终赢家。英伟达采用NVLink-Network进行超多节点互连的尝试始于GH200，在B系列GPU的产品上全NVLink连接的节点数提升超一倍，有望成为未来主力产品。

GB200 NVL72是机架级产品，可认为是GH200 NVL32的升级版。GB200 NVL72若通过IB/以太网搭集群，GPU : 1.6T= 1:2.5；若通过NVLink-Network搭576集群，GPU : 1.6T = 1:9。网络带宽作用凸显，计算效率大幅提升。

<sup></sup> Copper or Optics？IEEE P802.3df发布的目标中单通道100Gbps速率的电信号传输的距离为2m。对于单通道200Gbps电信号的传输距离，谷歌的在报告中论证过达到1m的可行性，Intel认为在优良材料上可达到1m。在GB200NVL72中，单个差分对预计为200Gbps，Rack内可传输1m，铜线可以受益。但是到下一代更大带宽的GPU产品中，我们预计铜线传输距离大大缩短，光学方案将逐步替代。

投资建议：英伟达Blackwell架构的GPU需求有望持续高速增长，随之带来1.6T光模块广阔的市场空间，将打消市场对<sup>2025年光模块市场需求的担忧。海外云厂商及算力巨头供应链的进入壁垒较高，光模块更新迭代的节奏大幅加快，光</sup>模块的行业格局预计将更加集中，建议重点关注头部光模块及光器件公司，新易盛、中际旭创和天孚通信等。云厂商在<sub>提升光模块性能以及降低成本、功耗方面的动力较强。建议关注薄膜铌酸锂、硅光、OCS、LPO和CPO等行业新技术</sub>

## 目录

以太网还是Infiniband？
二、NVLink-Network或成最终赢家
三、光还是铜？
四、投资建议
五、风险提示

## 1.1 以太网 VS Infiniband？

 在传统云计算数据中心领域，以太网技术的产品市占率保持绝对领先的地位。以太网领域的头部厂商，充分享受云计算快速发展带来的强劲需求，包括博通、Marvell、Arista和思科等厂商。

 在HPC领域，对于网络的性能要求越高，IB的渗透率越高，全球前10大超算中心，IB市占率70%。IB市场上，主要是Nvidia（收购的Mellanox公司）和Intel（收购的Qlogic公司）两大玩家。IB虽然性能更好，但价格较贵。

 随着ChatGPT的横空出世，AIGC的大模型引爆了算力的需求，大模型的训练对于网络性能要求较高，因此Mellanox的IB产品受到了绝大部分客户的青睐。2024财年四季度，英伟达的网络部分收入增长了两倍，需求保持强劲。虽然IB的时延具有很大的优势，尤其在训练场景下，但是基于RDMA的以太网技术ROCE也保持较低的时延，且成本优势较大，性价比更高。我们认为，IB短期内在AI领域仍然具备较强的优势，但是以太网联盟的发展也会使得其渗透率有一定的提升。

图表1：全球TOP10和TOP100超算中心采用不同网络技术统计图
![](images/e1329ce2b25963785d613ec10a1cd9a23c57f9ac50547d8ec88811da3823c892.jpg)

![](images/792414e3403819ad82baacc1d0c27232a86a8fef8b9560c5d128668a4a4a6908.jpg)

图表2：超级以太网联盟主要成员
![](images/62ec6f1f8572c3f8171a43eb5b78a19d611868fb525716b1706447a4d6c3b628.jpg)

![](images/41275619cf935c48c49c2f2692851caa7600a1da2fad1bba5b7af3a989a0bc14.jpg)

## 1.2.1 以太网：全球局域网最通用的网络协议标准

 以太网是目前全球应用最广泛的局域网技术，由IEEE的802.3标准制定相关的技术标准。标准中包括了物理层的连接、电信号以及介质访问控制等内容。除了IEEE标准组织，还有以太网技术联盟（ETC）和超级以太网联盟（UEC）等组织也会发布相关标准。凭借着高可靠性、低成本、易于管理以及高速等优势，以太网技术广泛应用于自动化、自动驾驶、企业网和云计算等领域。

 以太网起源于Xerox PARC公司。1976年，Bob Metcalfe及其助手发表了《以太网：区域计算机网络的分布式数据包交换技术》，1977年他们取得了CSMA/CD（Carrier Sense Multiple Access with Collision Detection），即带有冲突检测的载波侦听多址访问的专利，以太网正式诞生。后来Metcalfe离开施乐公司创立3Com公司，与英特尔、DEC和施乐等公司共同将以太网实现了标准化。1980年，首个通用以太网标准DIX1.0诞生，随着从总线拓扑走向星型结构化布线以及光缆传输技术的快速发展，以太网迎来了快速发展的时代。

图表3：以太网下游应用领域广泛
![](images/e92e00398a5829e13ac61c7613fc921bb064dc9b3cede82965a1ccdd51c71ae5.jpg)
图表4：以太网拓扑结构从总线型走向星型
Ethernet Alliance

 通过以太网，用户终端可以与多台终端进行通信。每台终端设备（电脑、手机等）都拥有全球唯一的 48 位 MAC 地址，从而保证以太网上所有节点能互相区分，并且每台终端必须通过物理层介质传输信息，包括无线电磁波或有线电缆等，这些传输通道也被称之为以太（Ether）。物理层硬件也从同轴电缆到双绞线、光纤光缆，NIC网卡和交换机的出现也加速了以太网的发展。

 随着下游应用领域的快速发展，带宽的需求也在爆发式增长。IEEE发布的第一个以太网标准10 BASE5带宽为10M。1995年，100M带宽的快速以太网时代开启，1998年千兆带宽的以太网标准发布，2002年10G以太网标准发布。到2020年，ETC发布了800G以太网的标准，预计1.6T以太网标准也将发布。带宽的不断升级，也带来了调制方式的变化，从NRZ到PAM4，以及相干QPSK等调制方式。

图表5：以太网带宽升级路径图
![](images/10c39764e1163a965af9415da0d4cf6643a886183750de682f3d0547d6ba2e2b.jpg)

图表6：以太网各种调制方式
![](images/a9d8bb75484ad06401914de49c3a2752332cc1511db9de070236ed85c6293480.jpg)

![](images/dfb2c4e9700d2fe2ab0ac96cf9b8271877997802d4e2d88f2b960c854e49cbfa.jpg)

## 1.3.1 InfiniBand快速发展，Mellanox市占率全球第一

 20世纪90年代，PCI升级缓慢导致I/O遇到瓶颈限制HPC发展愈发成为重要的问题。HP、IBM、Intel、Mellanox、Microsoft、Oracle和QLogic等公司于1999年联合成立Infiniband贸易联盟（InfiniBand Trade Association），旨在用IB取代PCI的I/O、以太网的算力集群互连等。2000年，InfiniBand架构规范的1.0版本正式发布。

 2002年，Intel开始着眼于开发PCI Express，微软终止IB研发，至2008年仅剩Mellanox、Cisco、QLogic和Voltaire等主要参与者，IB的发展受到一定的影响。2009年，思科开始重点研发以太网交换机。2010年左右，Mellanox和Voltaire公司合并，市场上只剩下一个竞争者QLogic。2012年，Intel收购QLogic的IB技术，至此，Mellanox在InfiniBand领域占据绝对优势地位。

 2012年开始，随着HPC的快速发展，IB产品需求大增，其市场份额持续扩张。2015年，IB在TOP500榜单中占比51.4%，首次超越以太网。在收购硅光技术公司Kotura和并行光互连芯片厂商IPtronics后，Mellanox在全球IB市场的市占率达80%，成为全球网络领域的领先提供商。2019年，英伟达以69亿美元收购Mellanox。

图表7: InfiniBand发展历程
![](images/11493f5ce68c716e5ea1fea12c1e854bf39f7941297498f86ac5d9d6e890cd44.jpg)

## 1.3.2 RDMA协议降低数据传输时延，SHARP技术提升计算效率

 InfiniBand最重要的一个特点是采用RDMA协议（远程直接内存访问），从而实现低时延。相较于传统TCP/IP网络协议，RDMA可以让应用与网卡之间直接进行数据读写，无需操作系统内核的介入，从而使得数据传输时延显著降低。在大规模并行计算机集群中，低时延能够有效提升算力设施的利用效率。

 InfiniBand技术以端到端流量控制为网络数据包收发的基础，能够确保无拥塞发出报文，从而大幅降低规避丢包所导致的网络性能下降的风险。SHARP技术（可扩展分层聚合和归约协议）的引入使得InfiniBand系统能够在转发数据的同时在交换机内进行计算，以降低计算节点间进行数据传输的次数，从而大幅提升计算效率。

图表8：InfiniBand采用RDMA协议
![](images/b9d3e80aaa84b176502d7dceea951fe7178c66ed2db2c68bb38eb0a2c0d722fc.jpg)

图表9：SHARP技术原理示意图
![](images/c68af841acd025d87655a47df1e7bdb213cb04625da5e833f58c360bda143c47.jpg)

 随着AI的快速发展，IB在算力集群发挥着关键的作用。InfiniBand作为一个用于高性能计算的网络通信标准，其优势在于高吞吐和低延迟，可以用于计算机和计算机、计算机和存储以及存储之间的高速交换互连。

 HPC领域对带宽有更高的要求，InfiniBand目前传输速度达到400Gb/s。根据技术发展路线图，2024年IBTA计划推出XDR产品，四通道对应速率800Gb/s，八通道对应速率是1600Gb/s，并将于2年后发布GDR产品，四通道速率达1600Gb/s。

 InfiniBand系统的硬件由网卡适配器、交换机、电缆和光模块组成。

图表10：InfiniBand发展路线图
![](images/c9345124a4c01a002710bb22bb296283f876cbe9998e354a934cfeda6205e3ee.jpg)
© InfiniBand Trade Association - CONFIDENTIAL
IBTA Nvidia

图表11：InfiniBand技术产品示意图
![](images/30568a18ad4bbd63c1e941cfa9e16d826f05130a01a93f2dcc761d1eff7fd6bd.jpg)

## 目录

一、以太网还是Infiniband？
二、NVLink-Network或成最终赢家
三、光还是铜？
四、投资建议
五、风险提示

## 2.1 以太网 VS Infiniband？NVLink-Network或成最终赢家

 由于以太网和Infiniband在数据中心和超算中心有着较长的应用历史以及良好的客户基础，因此在AI时代，我们通常会谈论这两者之间的竞争。目前Infiniband得益于更优秀的性能以及英伟达的一体化销售战略，在AI市场处于绝对领先的地位，但是昂贵的价格以及以太网众多玩家在技术和产品上的持续突破，似乎竞争愈演愈烈。

 然而，我们认为NVLink依靠其数倍于以太网和IB的带宽优势，单位算力成本有望具备很强的性价比，或成最终赢家。目前NVLink4.0的双向带宽为900GB/s，单向带宽3.6Tbps（450GB/s），是以太网和IB网络800Gbps带宽的4倍多。

 英伟达采用NVLink-Network进行超多节点互连的尝试始于GH200，在B系列GPU的产品上全NVLink连接的节点数进一步提升。超高的互连带宽意味着更短的传输时间以及更高的算力利用效率。而在需求侧，对光模块和交换机等产业链将产生重大的影响。

图表12：NVLink技术发展路线图
![](images/61e7a7ca11db29413c16c02f884c966902dd6e816da37a765ab83c90158a3e91.jpg)

 在NVLink面世前，PCIe是最常见的高速互连标准之一，广泛用于CPU、GPU间的高速互连，但是带宽提升的节奏远远低于需求。2003年，PCIe 1.0规范发布，支持每通道2.5GT/s（250MB/s）的传输速率，最大总传输速率为4GB/s。经过20年的发展，PCIE由1.0版本迭代至6.0，每通道传输速率提高至64GT/s。然而，PCIe带宽的提升远远落后于算力的增加，成为算力系统明显的瓶颈。

 和Infiniband技术一样，为了应对PCIe迭代速度缓慢导致GPU I/O带宽成为整个算力系统的瓶颈，Nvidia专门研发了NVLink技术。NVLink用于连接GPU之间以及GPU与CPU之间，其允许GPU芯片间以点对点的方式通信，可以突破传统PCIe互联带宽限制，实现更高带宽、更低延迟的数据互连。随着GPU的不断升级，NVLink也在快速迭代，以确保GPU之间的高速互连。目前H100的GPU对应NVLink 4.0技术，而NVLink 5.0也有望很快发布。

图表13：PCIe不同代际技术参数示意图
<table><tr><td rowspan=2 colspan=1>Version</td><td rowspan=2 colspan=1>Introduced</td><td rowspan=2 colspan=2>LineCode</td><td rowspan=2 colspan=1>Transferrate/lane(GT/s)</td><td rowspan=1 colspan=5>Throughput</td></tr><tr><td rowspan=1 colspan=1>x1(GB/s)</td><td rowspan=1 colspan=1>x2(GB/s)</td><td rowspan=1 colspan=1>x4(GB/s)</td><td rowspan=1 colspan=1>x8(GB/s)</td><td rowspan=1 colspan=1>x16(GB/s)</td></tr><tr><td rowspan=1 colspan=1>1.0</td><td rowspan=1 colspan=1>2003</td><td rowspan=5 colspan=1>NRZ</td><td rowspan=3 colspan=1>8b/19b</td><td rowspan=1 colspan=1>2.5</td><td rowspan=1 colspan=1>0.250</td><td rowspan=1 colspan=1>0.500</td><td rowspan=1 colspan=1>1.000</td><td rowspan=1 colspan=1>2.000</td><td rowspan=1 colspan=1>4.000</td></tr><tr><td rowspan=1 colspan=1>2.0</td><td rowspan=1 colspan=1>2007</td><td rowspan=1 colspan=1>5.0</td><td rowspan=1 colspan=1>0.500</td><td rowspan=1 colspan=1>1.000</td><td rowspan=1 colspan=1>2.000</td><td rowspan=1 colspan=1>4.000</td><td rowspan=1 colspan=1>8.000</td></tr><tr><td rowspan=1 colspan=1>3.0</td><td rowspan=1 colspan=1>2010</td><td rowspan=1 colspan=1>8.0</td><td rowspan=1 colspan=1>0.985</td><td rowspan=1 colspan=1>1.969</td><td rowspan=1 colspan=1>3.938</td><td rowspan=1 colspan=1>7.877</td><td rowspan=1 colspan=1>15.754</td></tr><tr><td rowspan=1 colspan=1>4.0</td><td rowspan=1 colspan=1>2017</td><td rowspan=2 colspan=1>128b/130b</td><td rowspan=1 colspan=1>16.0</td><td rowspan=1 colspan=1>1.969</td><td rowspan=1 colspan=1>3.938</td><td rowspan=1 colspan=1>7.877</td><td rowspan=1 colspan=1>15.854</td><td rowspan=1 colspan=1>31.508</td></tr><tr><td rowspan=1 colspan=1>5.0</td><td rowspan=1 colspan=1>2019</td><td rowspan=1 colspan=1>32.0</td><td rowspan=1 colspan=1>3.938</td><td rowspan=1 colspan=1>7.877</td><td rowspan=1 colspan=1>15.754</td><td rowspan=1 colspan=1>31.508</td><td rowspan=1 colspan=1>63.015</td></tr><tr><td rowspan=1 colspan=1>6.0</td><td rowspan=1 colspan=1>2022</td><td rowspan=2 colspan=1>PAM-4FEC</td><td rowspan=2 colspan=1>1b/1b242B/256BFLIT</td><td rowspan=1 colspan=1>64.0,32.0 GBd</td><td rowspan=1 colspan=1>7.563</td><td rowspan=1 colspan=1>15.125</td><td rowspan=1 colspan=1>30.250</td><td rowspan=1 colspan=1>60.500</td><td rowspan=1 colspan=1>121.000</td></tr><tr><td rowspan=1 colspan=1>7.0</td><td rowspan=1 colspan=1>2025(planned)</td><td rowspan=1 colspan=1>128.0,64.0GBd</td><td rowspan=1 colspan=1>15.125</td><td rowspan=1 colspan=1>30.250</td><td rowspan=1 colspan=1>60.500</td><td rowspan=1 colspan=1>121.000</td><td rowspan=1 colspan=1>242.000</td></tr></table>

图表14：GPU与NVLink同步升级
![](images/52a2587a96026cd3222b586f498947c3b61bed4a723c878930bd37d7aecf87fe.jpg)

 2014年，NVLink 1.0发布，并应用于P100芯片。NVLink 1.0一条差分对单向速率为20 Gb/s，每个通道有8条差分对，拥有4条通道的P100的NVLink 1.0单向传输带宽可达80 GB/s，整个系统的双向带宽则为160GB/s。

 2017年，NVLink 2.0推出，其带宽接近NVLink 1.0的2倍。两个GPU V100间通过6条NVLink通道互连, 每条link通道包括8条差分对，每条差分对的速率提升至25Gb/s，则每条NVLink单向带宽为25 GB/s，故V100的NVLink双向带宽从160GB/s几乎翻倍至300 GB/s。

 2018年，为了实现8颗GPU之间的all-to-all互连，英伟达发布了NVSwitch 1.0产品。NVSwitch 1.0类似交换机的ASIC芯片，含有18个端口，每个端口的带宽是50GB/s，双向总带宽900GB/s，用6个NVSWitch可以实现8颗V100的all-to-all连接。

图表15：NVLink 1.0技术应用于P100上
![](images/87d1d2e21f67fbaff8627fcf9dfd0d6cbf97748cd6fe5f61728e6e4d417158db.jpg)

图表16：NVSwitch 1.0实现V100 all-to-all连接
![](images/9ab767fb25cbcdb51b49345bc4fca78518da270c1922dbb958433a95c200e36c.jpg)

## 2.4 NVLink3.0带宽600GB/s，NVLink 4.0达到900GB/s

 英伟达于2020年推出NVLink 3.0版本，双向总带宽提升至600GB/s，同期发布NVSWitch 2.0产品。两颗A100 GPU之间的NVLink数量增加至12条, 每条NVLink中的差分对为4条, 单条差分对的单向带宽为50Gb/s。8颗A100芯片与4个NVSwitch 2.0芯片组合而成DGXA100服务器。

 2022年，NVLink升级到4.0版本，NVSwitch升级至3.0版本。单条差分对单向带宽再次翻倍至100Gb/s，两个H100芯片从A100的12条通道提升至18条，双向总带宽提升到900GB/s。同时，Nvidia发布第三代NVSwitch，包含64个端口。DGX H100服务器由8个H100芯片与4个NVSwitch 3.0芯片组成。

图表17：NVLink发展路线图
<table><tr><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1>2016</td><td rowspan=1 colspan=1>2017</td><td rowspan=1 colspan=1>2020</td><td rowspan=1 colspan=1>2022</td><td rowspan=1 colspan=1>2024</td></tr><tr><td rowspan=1 colspan=1>NVLink代际</td><td rowspan=1 colspan=1>NVLink 1.0</td><td rowspan=1 colspan=1>NVLink 2.0</td><td rowspan=1 colspan=1>NVLink 3.0</td><td rowspan=1 colspan=1>NVLink 4.0</td><td rowspan=1 colspan=1>NVLink 5.0</td></tr><tr><td rowspan=1 colspan=1>NVLink数量</td><td rowspan=1 colspan=1>4</td><td rowspan=1 colspan=1>6</td><td rowspan=1 colspan=1>12</td><td rowspan=1 colspan=1>18</td><td rowspan=1 colspan=1>18</td></tr><tr><td rowspan=1 colspan=1>通道数</td><td rowspan=1 colspan=1>32</td><td rowspan=1 colspan=1>48</td><td rowspan=1 colspan=1>48</td><td rowspan=1 colspan=1>36</td><td rowspan=1 colspan=1>36</td></tr><tr><td rowspan=1 colspan=1>单通道带宽</td><td rowspan=1 colspan=1>5GB/s</td><td rowspan=1 colspan=1>6.25GB/s</td><td rowspan=1 colspan=1>12.5GB/s</td><td rowspan=1 colspan=1>25GB/s</td><td rowspan=1 colspan=1>50GB/s</td></tr><tr><td rowspan=1 colspan=1>调制方式</td><td rowspan=1 colspan=1>NRZ</td><td rowspan=1 colspan=1>NRZ</td><td rowspan=1 colspan=1>NRZ</td><td rowspan=1 colspan=1>PAM4</td><td rowspan=1 colspan=1>PAM4</td></tr><tr><td rowspan=1 colspan=1>总双向带宽</td><td rowspan=1 colspan=1>160GB/s</td><td rowspan=1 colspan=1>300GB/s</td><td rowspan=1 colspan=1>600GB/s</td><td rowspan=1 colspan=1>900GB/s</td><td rowspan=1 colspan=1>1800GB/s</td></tr></table>

图表18：NVSwitch发展路线图
<table><tr><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1>2017</td><td rowspan=1 colspan=1>2020</td><td rowspan=1 colspan=1>2022</td><td rowspan=1 colspan=1>2024</td></tr><tr><td rowspan=1 colspan=1>NVSwitch代际</td><td rowspan=1 colspan=1>NVSwitch 1.0</td><td rowspan=1 colspan=1>NVSwitch 2.0</td><td rowspan=1 colspan=1>NVSwitch 3.0</td><td rowspan=1 colspan=1>NVSwitch 4.0</td></tr><tr><td rowspan=1 colspan=1>配套NVLink</td><td rowspan=1 colspan=1>NVLink 2.0</td><td rowspan=1 colspan=1>NVLink 3.0</td><td rowspan=1 colspan=1>NVLink 4.0</td><td rowspan=1 colspan=1>NVLink 5.0</td></tr><tr><td rowspan=1 colspan=1>配套GPU架构</td><td rowspan=1 colspan=1>Volta</td><td rowspan=1 colspan=1>Ampere</td><td rowspan=1 colspan=1>Hopper</td><td rowspan=1 colspan=1>Blackwell</td></tr><tr><td rowspan=1 colspan=1>端口数</td><td rowspan=1 colspan=1>18</td><td rowspan=1 colspan=1>36</td><td rowspan=1 colspan=1>64</td><td rowspan=1 colspan=1>72</td></tr><tr><td rowspan=1 colspan=1>单端口带宽</td><td rowspan=1 colspan=1>50GB/s</td><td rowspan=1 colspan=1>50GB/s</td><td rowspan=1 colspan=1>50GB/s</td><td rowspan=1 colspan=1>100GB/s</td></tr><tr><td rowspan=1 colspan=1>总双向带宽</td><td rowspan=1 colspan=1>900GB/s</td><td rowspan=1 colspan=1>1800GB/s</td><td rowspan=1 colspan=1>3200GB/s</td><td rowspan=1 colspan=1>7200GB/s</td></tr></table>

 2023年，英伟达宣布生成式AI引擎NVIDIA DGX GH200现已投入量产。GH200通过NVLink 4.0的900GB/s超大网络带宽能力来提升算力，服务器内部可能采用铜线方案，但服务器之间可能采用光纤连接。对于单个256 GH200芯片的集群，计算侧1个GH200对应9个800G光模块；对于多个256 GH200集群，计算侧1个GH200对应12个800G光模块。

 相比较传统的IB/Ethernet的网络，GH200采用的NVLink-Network网络部分的成本占比大幅增长，但是因为网络在数据中心中的成本占比较低，因此通过提升网络性能来提升算力性价比很高。

图表19：DGX GH200在大模型方面的性能表现
![](images/1477fa19fed113b3fc913b60610b61b0a7ba50b29f78f80716341a2cef923ac0.jpg)

图表20：256颗GH200的网络连接示意图
![](images/b3e147d89270ff678a07c69d03d7a053d08451e47c53a909e0a9a2799aace714.jpg)

 2023年11月，在AWS的Re:Invent大会上，AWS和NVIDIA宣布AWS将成为第一个提供NVIDIA GH200 Grace Hopper超级芯片的云服务提供商，在Amazon EC2上运行。NVIDIA GH200 NVL32 是针对 NVIDIA GH200 Grace Hopper 超级芯片的机架级参考设计，通过 NVLink 连接，面向超大规模数据中心。

 NVL32不但在训练上性能更加优异，而且在推理上也具备显著的优势。NVL32相比较传统的H100以太网连接系统方案，在LLM训练上快1.7倍，在LLM推理上快两倍，在训练算法训练上快8倍，在图形训练上快6倍。

图表21：GH200 NVL32在LLM推理上比传统H100快两倍
![](images/3c30d9e8aa782b6051ac7cc44064bacb0a1f4d250af93764b4d85ed8af4743d8.jpg)
AJLUUIIIILO
资料来源：Nvidia，中信建投

图表22：GH200 NVL32机架级方案
![](images/9ba8964030a673c79e2b23a3c4f692bf459d926fd1f3b2dec0a795bb8a426176.jpg)

## 2.7 GH200 NVL32的技术参数介绍

GH200：32颗芯片16个GH200 Tray盘每个Tray盘2颗GH200

内存：19.5TBCPU：LPDDR5X 480GB x 32GPU：HBM3e 144GB x 32

算力：127PFlops @FP8
单颗GH200: 3.96PF @FP8

图表23：GH200 NVL32机架示意图
![](images/69d8fe8d766a2fad537ba9e141b1c09e050878b8f4a2a64566c604bb63539004.jpg)

![](images/bee75fa9bf36f7052d27c065dc32bf52213bb0c9536963f59fcf12ee2fb3b2a3.jpg)

总带宽：28.8TB/s双向采用NVLink 4.0：900GB/s

NVLink 4.0: 900GB/s双向18个NVLink，36个112Gb通道

NVSwitch 3.0：18颗芯片9个NVSwitch Tray盘每个Tray盘2颗NVSwitch芯片单颗芯片：64x50G=3.2TB/s

物理连接： Cable Cartridge预计单个差分对速率为100Gbps

 2024年3月，英伟达在2024年GTC大会上推出Blackwell新一代计算平台。Blackwell构架B200 GPU的AI运算性能在FP8及新的FP6上都可达20 petaflops，是前一代Hopper构架的H100运算性能8 petaflops的2.5倍，同时支持全新FP4/FP6格式。英伟达还推出了GB200超级芯片，它基于两个B200 GPU，外加一个Grace CPU。

 英伟达发布NVLink 5.0和NVSwitch 4.0。NVLink 5.0具有1.8 TB/s的双向带宽，单条差分对单向带宽达到200Gbps，通道数为18个。NVSwitch 4.0有72个端口，每个端口有2个单向带宽200G Serdes的通道，总双向带宽为7.2TB/s，可以支持4个NVLink。

图表24：GH200 NVL32在LLM推理上比传统H100快两倍
![](images/49a2c745900427bfadf25783389b8d3f40324e9c0bed0f2068298df2e0c5dbe6.jpg)
Nvidia

图表25：GH200 NVL32机架级方案
![](images/1d62b79456d9017a7a153e3d046b0e6f37d1683128f1462cc4ce47efd0c34226.jpg)

## 2.9 GB200 NVL72也是机架级产品，可认为是GH200 NVL32的升级版

图表26：GB200 NVL72机架示意图

GB200：36颗GB20018个GB200 Tray盘每个Tray盘2颗GB200

内存：30.38TBCPU：LPDDR5X 480GB x 72GPU：HBM3e 192GB x 2 x72

算力：720PFlops @FP8
GB200: 20PF @FP8

总带宽：129.6TB/s采用NVLink 5.0：1800GB/s

NVLink 5.0: 1800GB/s双向18个NVLink，36个224Gb通道

NVSwitch 4.0：18颗芯片9个NVSwitch Tray盘每个Tray盘2颗NVSwitch芯片单颗芯片双向：72x100G=7.2TB/s

物理连接：Cable Cartridge 预计单个差分对速率为200Gbps

Nvidia

## 2.10 GB200 NVL72若通过IB/以太网搭集群，GPU : 1.6T = 1:2.5

 GB200 NVL72为机架级产品，内部72颗Blackwell的GPU通过NVLink实现互连。由于机架级产品的Tray盘之间的距离较短，因此可以通过高速电连接器进行连接。

 若需要搭建千卡甚至万卡级别的集群，GPU和光模块的比例平均可以认为是1:2.5。如果以GB200 NVL72为单元，用IB或以太网实现超大规模的集群搭建，若采用Fat-tree网络架构，那么GPU和光模块的比例将达到1:2（两层），1:3（三层）。

图表27：英伟达以太网和IB的800Gbps交换机
![](images/313001538fa7c387b7ca401b594e375e67173811585257c7cd89477129eadf9a.jpg)
Nvidia

图表28：Fat-tree网络架构示意图（ 为200G光模块）
![](images/5fdb3ceab7198c5d0802ed3bf83f2744f3776ab6cba077692adb554e146fe483.jpg)

## 2.11 GB200 NVL72若通过NVLink-Network搭576集群，GPU : 1.6T = 1:9

 GB200 NVL72通过NVLink-Network搭建成576只GPU的SuperPod，可以认为是GH200 256的升级版。在英伟达的官方技术文档中，为客户提供了576只GPU全NVLink连接的集群方案，能够以1.8TB/s的超大带宽实现超大内存的高速共享。

 若需要搭建576只GPU的全NVLink连接的集群，假设采用fat-tree的架构，那么GPU：1.6T的比例可以达到1:9以上。NVLink5.0的单向带宽为7.2Tbps，若只有一层用光，那么单只GPU对应的光模块的数量为7.2T/1.6T \* 2 = 9。

图表29：Fully connected NVLink 576 GPU的结构示意图（预测）
![](images/37c5876fb58ce441e65d2cf9117a05afe1bb54dea39118257e1069f53c0f1f56.jpg)

## 目录

一、以太网还是Infiniband？
二、NVLink-Network或成最终赢家
三、光还是铜？
四、投资建议
五、风险提示

## 3.1 电信号带宽提升，趋肤效应导致传输损耗增加

##  电信号在铜线中传输存在以下几种损耗：

 导体损耗，随着交流频率升高，电流由于趋肤效应集中在导体表面而不是在导体内部，因此受到的阻抗增大，同时，铜箔表面的粗糙度也会加剧导体损耗；

 介质损耗，主要是由于介质的极化，介质中的电偶极子极化方向由于交流电场不断变化，能量被不断消耗；

 耦合到邻近走线，指串扰，造成信号自身衰减的同时对邻近铜线中信号产生干扰；

 阻抗不连续，反射会导致传输的信号损失部分能量；

 辐射损耗，虽然辐射引起的信号衰减相对较小，但是会带来EMI问题。

图表30：电信号传输损耗分解图
![](images/a8ac547500dc10caf5b81e4be35943fd09b26aa5f112d3feb2482afa77a12514.jpg)

图31：信号频率变化的趋肤效应示意图
![](images/a2d16621e28920a3ad287d530793f8968996ba4d666f7936d2e10431bd9b1235.jpg)
\*黄色为电传输线，蓝色为电信号

 我们认为通信带宽每升级一代，损耗增加，传输距离都要显著缩短。通信带宽提升，趋肤效应导致在铜线和PCB Trace中传输损耗增加，连接器头子损耗增加，封装Trace损耗增加，因此有效传输距离将明显缩短。

 从2022年11月IEEE P802.3df发布的目标来看，单通道100Gbps速率的电信号传输的距离为2m，而谷歌在2021年的报告中，论证单通道200Gbps传输距离达到1m的可行性，仍然需要BGA/via的优化、Serdes性能提升等。2021年的Photonics Summit大会上，Intel认为单通道200Gbps的电信号若在优良材料上传输，有效传输距离可达到1m。

 到单通道400Gbps时代，我们预计铜线传输距离将缩短到0.5m，铜线的应用场景将大大受限。

图表32：Intel关于电信号和光信号传输距离的观点
图33：谷歌论证200G单通道采用copper传输的可行性
![](images/50aeaea0d463651f65b55e2bea994f055abfd33fd2e37f1ea3e6a9c5ecf5a53b.jpg)

## 3.2 100Gbps电信号在铜线中传输2m，200G速率预计传输1m（续）

## 图表34：IEEE P802.3df目标参数示意图

## Adopted IEEE P802.3df Objectives

## . Non-Rate Specific

• Support full-duplex operation only

• Preserve the Ethernet frame format utilizing the Ethernet MAC

• Preserve minimum and maximum FrameSize of current IEEE 802.3 standard

• Support a BER of better than or equal to 10 -13 at the MAC/PLS service interface (or the frame loss ratio equivalent)

• Provide support to enable mapping over OTN

## . 400 Gb/s Related

• Support a MAC data rate of 400 Gb/s

• Define a physical layer specification that supports 400 Gb/s operation:

• over 4 pairs of SMF with lengths up to at least 2 km

## • 800 Gb/s Related

• Support a MAC data rate of 800 Gb/s

• Support optional eight-lane 800 Gb/s attachment unit interfaces for chip-to-module and chip-to-chip applications

•Define a physical laver specification that supports 8o0 Gb/s operation:

• over eight lanes of twin axial copper cables with a reach up to at least 2 meters

• over eight lanes over eiectricai backpianes supporting an insertion loss ≤ 28dB at26.56GHz

• over 8 pairs of MMF with lengths up to at least 50 m

• over 8 pairs of MMF with lengths up to at least 100 m

• over 8 pairs of SMF with lengths up to at least 500 m

• over 8 pairs of SMF with lengths up to at least 2 km

Approved by IEEE 802.3 WG 17 Nov 2022

## 3.3 GB200 NVL72虽然铜线短期受益，但光进铜退是大势所趋

 在GB200 NVL72中，高速背板连接器中单个差分对预计为200Gbps，Rack内可传输1m，铜线可以受益。但是到下一代GPU产品中，我们预计铜线传输距离大大缩短，光学方案将逐步替代。英伟达One Giant GPU的概念，在物理层面上将所有GPU通过NVLink连接起来，但铜线可覆盖的物理范围将越来越小，将逐步转为光学方案。

 由于芯片之间连接的铜线trace直径太小，因此带宽升级后损耗较大，因此在CPO领域硅光I/O的必要性也在大幅增强。

 因此，我们认为，无论是Tray盘之间的连接，还是芯片之间的互连，未来光学方案的渗透率都将大幅提升。而短期内光学方案的功耗和成本问题，将会有新技术或新产品来解决，但是底层仍然会是光学方案。

图表35：英伟达GPU中硅光I/O结构示意图
![](images/a1fb433e7250ff4ad3f8a5b20333c0ddaeaca7b6446e44f3e5f2559fd292ce1e.jpg)
Nvidia Intel

图36：光进铜退逐步渗透到芯片和芯片之间
![](images/85212516f96527a6f26ee2cc14e2a955444121870e310f0f91600cf36c25a4b8.jpg)

## 目录

以太网还是Infiniband？
二、NVLink-Network或成最终赢家
三、光还是铜？
四、投资建议
五、风险提示

## 投资建议

 AIGC的快速发展带来了算力的爆发性需求，网络在整个AI数据中心的作用愈发重要，可以显著提升算力的效率。800G光模块的需求大幅提升，1.6T光模块的量产进程大幅加速，预计将成为2025年的需求主力。英伟达Blackwell架构的GPU需求有望持续高速增长，随之带来1.6T光模块广阔的市场空间，将打消市场对2025年光模块市场需求的担忧。海外云厂商及算力巨头供应链的进入壁垒较高，光模块更新迭代的节奏大幅加快，光模块的行业格局预计将更加集中，建议重点关注头部光模块及光器件公司，新易盛、中际旭创和天孚通信等。

 随着AI算力基础设施中的网络架构愈发重要，光模块的需求量显著增加，且速率迭代周期加快，云厂商在提升光模块性能以及降低成本、功耗方面的动力较强。建议关注薄膜铌酸锂、硅光、OCS、LPO和CPO等行业新技术的发展，包括源杰科技、光库科技、德科立和腾景科技等公司。

## 目录

以太网还是Infiniband？
二、NVLink-Network或成最终赢家
三、光还是铜？
四、投资建议
五、风险提示

## 风险提示

 AIGC的快速发展，无论训练侧还是推理侧对光模块需求都有较大拉动，若AIGC发展不及预期，GPU需求下滑，则光模块需求也将受到影响，假设用于训练的H100 GPU销售量减少10万只，那么按照英伟达DGX H100 SuperPOD的胖树三层架构来计算，则800G光模块的需求将减少约30万只；

 NVLink全连接的网络架构若发展不及预期，则光模块需求提升的幅度预计会比较一般；

 1.6T光模块中需要核心的芯片，包括EML光芯片和DSP芯片等，若芯片量产进度不及预期，则1.6T光模块预计存在一定交付压力；

 光模块和光器件公司给海外客户提供光有源和无源器件，同时光模块公司也从海外供应商采购芯片等原材料，若国际环境变化将对商务关系产生影响，同时若海外宏观经济衰退，存在对行业的需求产生影响的风险。

## 分析师介绍

## 刘永旭

中信建投证券通信行业联席首席分析师，南开大学学士、硕士，曾从事军工行业研究工作，2020年加入中信建投通信团队，主要研究云计算IDC、工业互联网、通信新能源、卫星应用、专网通信等方向。2020-2021年《新财富》、《水晶球》通信行业最佳分析师第一名团队成员。

## 阎贵成

中信建投证券通信行业首席分析师，北京大学学士、硕士，专注于云计算、物联网、信息安全、信创与5G等领域研究。近8年中国移动工作经验，7年多证券研究经验。系2019-2021年《新财富》、《水晶球》通信行业最佳分析师第一名。

## 武超则

中信建投证券研究所所长兼国际业务部负责人，董事总经理，TMT行业首席分析师。新财富白金分析师，2013-2020年连续八届新财富最佳分析师通信行业第一名；2014-2020年连续七届水晶球最佳分析师通信行业第一名。专注于5G、云计算、物联网等领域研究。中国证券业协会证券分析师、投资顾问与首席经济学家委员会委员。

## 杨伟松

通信行业分析师，南京大学理学学士，浙江大学工学硕士。6年光通信行业研发及管理经验，曾就职于光通信头部企业Coherent。2022年2月加入中信建投通信团队，主要研究光通信、ICT设备和激光雷达等方向。

## 评级说明

<table><tr><td rowspan=1 colspan=1>投资评级标准</td><td rowspan=1 colspan=1></td><td rowspan=1 colspan=1>评级</td><td rowspan=1 colspan=1>说明</td></tr><tr><td rowspan=8 colspan=1>报告中投资建议涉及的评级标准为报告发布日后6个月内的相对市场表现，也即报告发布日后的6个月内公司股价（或行业指数）相对同期相关证券市场代表性指数的涨跌幅作为基准。A股市场以沪深300指数作为基准；新三板市场以三板成指为基准；香港市场以恒生指数作为基准；美国市场以标普500指数为基准。</td><td rowspan=5 colspan=1>股票评级</td><td rowspan=1 colspan=1>买入</td><td rowspan=1 colspan=1>相对涨幅15%以上</td></tr><tr><td rowspan=1 colspan=1>增持</td><td rowspan=1 colspan=1>相对涨幅5%—15%</td></tr><tr><td rowspan=1 colspan=1>中性</td><td rowspan=1 colspan=1>相对涨幅-5%—5%之间</td></tr><tr><td rowspan=1 colspan=1>减持</td><td rowspan=1 colspan=1>相对跌幅5%—15%</td></tr><tr><td rowspan=1 colspan=1>卖出</td><td rowspan=1 colspan=1>相对跌幅15%以上</td></tr><tr><td rowspan=3 colspan=1>行业评级</td><td rowspan=1 colspan=1>强于大市</td><td rowspan=1 colspan=1>相对涨幅10%以上</td></tr><tr><td rowspan=1 colspan=1>中性</td><td rowspan=1 colspan=1>相对涨幅-10-10%之间</td></tr><tr><td rowspan=1 colspan=1>弱于大市</td><td rowspan=1 colspan=1>相对跌幅10%以上</td></tr></table>

## 分析师声明

本报告署名分析师在此声明：（i）以勤勉的职业态度、专业审慎的研究方法，使用合法合规的信息，独立、客观地出具本报告, 结论不受任何第三方的授意或影响。（ii）本人不曾因，不因，也将不会因本报告中的具体推荐意见或观点而直接或间接收到任何形式的补偿。

## 法律主体说明

本报告由中信建投证券股份有限公司及/或其附属机构（以下合称“中信建投”）制作，由中信建投证券股份有限公司在中华人民共和国（仅为本报告目的，不包括香港、澳门、台湾）提供。中信建投证券股份有限公司具有中国证监会许可的投资咨询业务资格，本报告署名分析师所持中国证券业协会授予的证券投资咨询执业资格证书编号已披露在报告首页。

在遵守适用的法律法规情况下，本报告亦可能由中信建投（国际）证券有限公司在香港提供。本报告作者所持香港证监会牌照的中央编号已披露在报告首页。

## 一般性声明

本报告由中信建投制作。发送本报告不构成任何合同或承诺的基础，不因接收者收到本报告而视其为中信建投客户。

本报告的信息均来源于中信建投认为可靠的公开资料，但中信建投对这些信息的准确性及完整性不作任何保证。本报告所载观点、评估和预测仅反映本报告出具日该分析师的判断，该等观点、评估和预测可能在不发出通知的情况下有所变更，亦有可能因使用不同假设和标准或者采用不同分析方法而与中信建投其他部门、人员口头或书面表达的意见不同或相反。本报告所引证券或其他金融工具的过往业绩不代表其未来表现。报告中所含任何具有预测性质的内容皆基于相应的假设条件，而任何假设条件都可能随时发生变化并影响实际投资收益。中信建投不承诺、不保证本报告所含具有预测性质的内容必然得以实现。

本报告内容的全部或部分均不构成投资建议。本报告所包含的观点、建议并未考虑报告接收人在财务状况、投资目的、风险偏好等方面的具体情况，报告接收者应当独立评估本报告所含信息，基于自身投资目标、需求、市场机会、风险及其他因素自主做出决策并自行承担投资风险。中信建投建议所有投资者应就任何潜在投资向其税务、会计或法律顾问咨询。不论报告接收者是否根据本报告做出投资决策，中信建投都不对该等投资决策提供任何形式的担保，亦不以任何形式分享投资收益或者分担投资损失。中信建投不对使用本报告所产生的任何直接或间接损失承担责任。

在法律法规及监管规定允许的范围内，中信建投可能持有并交易本报告中所提公司的股份或其他财产权益，也可能在过去12个月、目前或者将来为本报告中所提公司提供或者争取为其提供投资银行、做市交易、财务顾问或其他金融服务。本报告内容真实、准确、完整地反映了署名分析师的观点，分析师的薪酬无论过去、现在或未来都不会直接或间接与其所撰写报告中的具体观点相联系，分析师亦不会因撰写本报告而获取不当利益。

本报告为中信建投所有。未经中信建投事先书面许可，任何机构和/或个人不得以任何形式转发、翻版、复制、发布或引用本报告全部或部分内容，亦不得从未经中信建投书面授权的任何机构、个人或其运营的媒体平台接收、翻版、复制或引用本报告全部或部分内容。版权所有，违者必究。

中信建投证券研究发展部

北京
东城区朝内大街2号凯恒中心B
座12层
电话：(8610) 8513-0588
联系人：李祉瑶
邮箱：lizhiyao@csc.com.cn
上海
浦东新区浦东南路528号南塔2103室
电话：(8621) 6882-1612
联系人：翁起帆
邮箱：wengqifan@csc.com.cn
深圳
福田区福中三路与鹏程一路交汇处广电金融中心35楼
电话：（86755）8252-1369
联系人：曹莹
邮箱：caoying@csc.com.cn

中信建投（国际）

香港中环交易广场2期18楼

电话：（852）3465-5600联系人：刘泓麟邮箱：charleneliu@csci.hk
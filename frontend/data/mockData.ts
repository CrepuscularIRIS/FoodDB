/**
 * 供应链异构图模拟数据 - 全国版本
 * 768节点，1078边，分布在全国各省份
 */

import { GraphNode, GraphEdge, AlertItem, RiskStats, NodeType, EdgeType } from './types';

// 中国各省份及主要城市坐标
const provinceData: Record<string, { cities: string[]; center: [number, number]; range: [[number, number], [number, number]] }> = {
  '北京市': { cities: ['朝阳区', '海淀区', '丰台区', '通州区'], center: [116.4, 39.9], range: [[116.1, 39.7], [116.7, 40.1]] },
  '上海市': { cities: ['浦东新区', '黄浦区', '徐汇区', '闵行区'], center: [121.47, 31.23], range: [[121.0, 30.8], [122.0, 31.9]] },
  '广东省': { cities: ['广州市', '深圳市', '佛山市', '东莞市'], center: [113.3, 23.1], range: [[109.5, 20.2], [117.3, 25.5]] },
  '江苏省': { cities: ['南京市', '苏州市', '无锡市', '常州市'], center: [118.78, 32.07], range: [[116.2, 30.7], [121.5, 35.2]] },
  '浙江省': { cities: ['杭州市', '宁波市', '温州市', '嘉兴市'], center: [120.15, 30.28], range: [[117.8, 27.2], [122.2, 31.5]] },
  '山东省': { cities: ['济南市', '青岛市', '烟台市', '潍坊市'], center: [117.0, 36.6], range: [[114.3, 34.4], [122.7, 38.4]] },
  '河南省': { cities: ['郑州市', '洛阳市', '新乡市', '安阳市'], center: [113.65, 34.76], range: [[110.3, 31.2], [116.6, 36.3]] },
  '四川省': { cities: ['成都市', '绵阳市', '德阳市', '南充市'], center: [104.06, 30.67], range: [[97.3, 26.0], [108.5, 34.5]] },
  '湖北省': { cities: ['武汉市', '宜昌市', '襄阳市', '荆州市'], center: [114.3, 30.6], range: [[108.3, 29.0], [116.1, 33.3]] },
  '湖南省': { cities: ['长沙市', '株洲市', '湘潭市', '衡阳市'], center: [112.98, 28.21], range: [[108.8, 24.6], [114.3, 30.2]] },
  '河北省': { cities: ['石家庄市', '唐山市', '保定市', '廊坊市'], center: [114.5, 38.0], range: [[113.4, 36.0], [119.8, 42.6]] },
  '福建省': { cities: ['福州市', '厦门市', '泉州市', '漳州市'], center: [119.3, 26.08], range: [[115.8, 23.5], [120.7, 28.3]] },
  '安徽省': { cities: ['合肥市', '芜湖市', '蚌埠市', '淮南市'], center: [117.25, 31.87], range: [[114.8, 29.6], [119.6, 34.7]] },
  '陕西省': { cities: ['西安市', '宝鸡市', '咸阳市', '渭南市'], center: [108.93, 34.27], range: [[105.4, 31.7], [111.2, 39.6]] },
  '辽宁省': { cities: ['沈阳市', '大连市', '鞍山市', '抚顺市'], center: [123.43, 41.8], range: [[118.8, 38.7], [125.8, 43.5]] },
  '黑龙江省': { cities: ['哈尔滨市', '齐齐哈尔市', '大庆市', '牡丹江市'], center: [126.53, 45.8], range: [[120.7, 43.3], [135.1, 53.6]] },
  '吉林省': { cities: ['长春市', '吉林市', '四平市', '通化市'], center: [125.32, 43.9], range: [[121.6, 40.8], [131.4, 46.3]] },
  '江西省': { cities: ['南昌市', '九江市', '赣州市', '上饶市'], center: [115.88, 28.68], range: [[113.5, 24.5], [118.5, 30.2]] },
  '山西省': { cities: ['太原市', '大同市', '阳泉市', '长治市'], center: [112.55, 37.87], range: [[110.2, 34.6], [114.4, 40.7]] },
  '广西壮族自治区': { cities: ['南宁市', '柳州市', '桂林市', '北海市'], center: [108.37, 22.82], range: [[104.5, 20.9], [112.1, 26.4]] },
  '云南省': { cities: ['昆明市', '曲靖市', '玉溪市', '大理市'], center: [102.73, 25.05], range: [[97.5, 21.1], [106.2, 29.3]] },
  '贵州省': { cities: ['贵阳市', '遵义市', '六盘水市', '安顺市'], center: [106.63, 26.65], range: [[103.6, 24.6], [109.6, 29.2]] },
  '新疆维吾尔自治区': { cities: ['乌鲁木齐市', '克拉玛依市', '吐鲁番市', '哈密市'], center: [87.62, 43.83], range: [[73.4, 34.2], [96.4, 49.2]] },
  '内蒙古自治区': { cities: ['呼和浩特市', '包头市', '赤峰市', '通辽市'], center: [111.73, 40.83], range: [[97.2, 37.3], [126.1, 53.4]] },
  '海南省': { cities: ['海口市', '三亚市', '三沙市', '儋州市'], center: [110.35, 20.02], range: [[108.6, 18.1], [117.1, 20.2]] },
  '宁夏回族自治区': { cities: ['银川市', '石嘴山市', '吴忠市', '固原市'], center: [106.27, 38.47], range: [[104.2, 35.2], [107.6, 39.6]] },
  '青海省': { cities: ['西宁市', '海东市', '德令哈市', '格尔木市'], center: [101.78, 36.62], range: [[89.4, 31.3], [103.1, 39.2]] },
  '甘肃省': { cities: ['兰州市', '嘉峪关市', '金昌市', '白银市'], center: [103.83, 36.07], range: [[92.2, 32.6], [108.9, 43.0]] },
  '西藏自治区': { cities: ['拉萨市', '日喀则市', '昌都市', '林芝市'], center: [91.12, 29.65], range: [[78.4, 26.8], [99.1, 36.5]] },
  '天津市': { cities: ['和平区', '河东区', '河西区', '南开区'], center: [117.2, 39.08], range: [[116.7, 38.5], [117.9, 40.2]] },
  '重庆市': { cities: ['渝中区', '江北区', '沙坪坝区', '九龙坡区'], center: [106.55, 29.57], range: [[105.2, 28.0], [110.2, 32.2]] },
};

// 获取省份列表
const provinces = Object.keys(provinceData);

// 节点类型
const nodeTypes: NodeType[] = ['RAW_MILK', 'PROCESSOR', 'LOGISTICS', 'WAREHOUSE', 'DISTRIBUTOR', 'RETAILER'];

// 边类型
const edgeTypes: EdgeType[] = ['SUPPLY', 'TRANSPORT', 'STORE', 'SELL', 'PROCESS', 'PARTNERSHIP', 'CONTRACT', 'LOGISTICS', 'QUALITY', 'OTHER'];

// 企业名称前缀
const companyPrefixes = ['光明', '蒙牛', '伊利', '三元', '君乐宝', '新希望', '雀巢', '达能', '贝因美', '飞鹤', '完达山', '雅士利', '合生元', '澳优', '圣元'];
const companySuffixes = ['乳业', '食品', '供应链', '物流', '商贸', '超市', '便利店', '仓储', '牧业', '奶业'];

// 生成随机数
const random = (min: number, max: number) => Math.random() * (max - min) + min;
const randomInt = (min: number, max: number) => Math.floor(random(min, max));
const randomChoice = <T>(arr: T[]): T => arr[Math.floor(Math.random() * arr.length)];

// 省份节点分布权重（基于乳制品产业分布）
const provinceWeights: Record<string, number> = {
  '内蒙古': 12,    // 奶源主产区
  '黑龙江': 8,     // 奶源主产区
  '河北省': 7,     // 奶源主产区
  '山东省': 6,     // 奶业大省
  '河南省': 5,
  '新疆维吾尔自治区': 5,  // 奶源主产区
  '江苏省': 4,
  '四川省': 4,
  '辽宁省': 4,
  '陕西省': 4,
  '湖北省': 3,
  '云南省': 3,
  '广东省': 5,     // 消费市场
  '上海市': 4,     // 消费市场
  '北京市': 4,     // 消费市场
  '浙江省': 3,
  '安徽省': 3,
  '湖南省': 3,
  '山西省': 2,
  '吉林省': 2,
  '甘肃省': 2,
  '宁夏回族自治区': 2,
  '福建省': 2,
  '江西省': 2,
  '广西壮族自治区': 2,
  '贵州省': 2,
  '重庆市': 2,
  '天津市': 2,
  '海南省': 1,
  '青海省': 1,
  '西藏自治区': 1,
};

// 根据权重选择省份
const selectProvinceByWeight = (): string => {
  const totalWeight = Object.values(provinceWeights).reduce((a, b) => a + b, 0);
  let random = Math.random() * totalWeight;
  
  for (const [province, weight] of Object.entries(provinceWeights)) {
    random -= weight;
    if (random <= 0) {
      // 匹配完整省份名称
      return provinces.find(p => p.includes(province)) || provinces[0];
    }
  }
  return provinces[0];
};

// 生成企业名称
const generateCompanyName = (nodeType: string, index: number, province: string): string => {
  const prefix = randomChoice(companyPrefixes);
  const suffix = randomChoice(companySuffixes);
  const city = provinceData[province]?.cities[0] || '市辖区';
  const typeAbbr = {
    RAW_MILK: 'MILK',
    PROCESSOR: 'PROC',
    LOGISTICS: 'LOG',
    WAREHOUSE: 'WHS',
    DISTRIBUTOR: 'DIS',
    RETAILER: 'RTL',
  }[nodeType] || 'ENT';
  return `${province}-${typeAbbr}-${String(index).padStart(3, '0')}`;
};

// 生成节点位置（基于省份范围）
const generatePosition = (province: string): { lat: number; lng: number } => {
  const pData = provinceData[province];
  if (!pData) {
    // 默认中国中心区域
    return { lat: random(20, 45), lng: random(100, 120) };
  }
  
  const [[minLng, minLat], [maxLng, maxLat]] = pData.range;
  return {
    lat: random(minLat, maxLat),
    lng: random(minLng, maxLng),
  };
};

// 生成单个节点
const generateNode = (id: number, type?: NodeType): GraphNode => {
  const nodeType: NodeType = type || randomChoice(nodeTypes);
  const province = selectProvinceByWeight();
  const pos = generatePosition(province);
  const riskScore = random(0, 1);
  let riskLevel: 'high' | 'medium' | 'low';
  if (riskScore > 0.7) riskLevel = 'high';
  else if (riskScore > 0.4) riskLevel = 'medium';
  else riskLevel = 'low';
  
  const scale = random(10, 1000); // 企业规模
  const cities = provinceData[province]?.cities || ['市辖区'];
  
  return {
    id: `node_${id}`,
    name: generateCompanyName(nodeType, id, province),
    type: nodeType,
    x: pos.lng,
    y: pos.lat,
    riskScore,
    riskLevel,
    scale,
    district: province, // 使用省份作为district
    address: `${randomChoice(cities)}某路${randomInt(1, 9999)}号`,
    creditRating: randomChoice(['AAA', 'AA', 'A', 'BBB', 'BB']),
    violationCount: randomInt(0, 10),
    lastInspection: new Date(Date.now() - randomInt(0, 365 * 24 * 60 * 60 * 1000)).toISOString(),
  };
};

// 生成边
const generateEdge = (source: string, target: string, id: number): GraphEdge => {
  const edgeType = randomChoice(edgeTypes);
  return {
    id: `edge_${id}`,
    source,
    target,
    type: edgeType,
    weight: random(0.1, 1),
  };
};

// 生成完整的图数据
export const generateGraphData = () => {
  const nodes: GraphNode[] = [];
  const edges: GraphEdge[] = [];
  
  // 生成768个节点，按类型分布
  const typeDistribution = {
    RAW_MILK: 120,
    PROCESSOR: 80,
    LOGISTICS: 150,
    WAREHOUSE: 100,
    DISTRIBUTOR: 180,
    RETAILER: 138,
  };
  
  let nodeId = 0;
  Object.entries(typeDistribution).forEach(([type, count]) => {
    for (let i = 0; i < count; i++) {
      nodes.push(generateNode(nodeId++, type as NodeType));
    }
  });
  
  // 生成1078条边
  let edgeId = 0;
  
  // 供应链上下游连接
  const connectByType = (sourceTypes: string[], targetTypes: string[], count: number) => {
    const sources = nodes.filter(n => sourceTypes.includes(n.type));
    const targets = nodes.filter(n => targetTypes.includes(n.type));
    for (let i = 0; i < count && edgeId < 1078; i++) {
      const source = randomChoice(sources);
      const target = randomChoice(targets);
      if (source.id !== target.id) {
        edges.push(generateEdge(source.id, target.id, edgeId++));
      }
    }
  };
  
  // 原奶 -> 加工厂
  connectByType(['RAW_MILK'], ['PROCESSOR'], 150);
  // 加工厂 -> 仓储
  connectByType(['PROCESSOR'], ['WAREHOUSE'], 120);
  // 仓储 -> 物流
  connectByType(['WAREHOUSE'], ['LOGISTICS'], 180);
  // 物流 -> 经销商
  connectByType(['LOGISTICS'], ['DISTRIBUTOR'], 200);
  // 经销商 -> 零售
  connectByType(['DISTRIBUTOR'], ['RETAILER'], 250);
  // 加工厂 -> 经销商（直接）
  connectByType(['PROCESSOR'], ['DISTRIBUTOR'], 100);
  // 物流 -> 零售（直接配送）
  connectByType(['LOGISTICS'], ['RETAILER'], 78);
  
  // 添加一些随机连接增加网络复杂度
  while (edgeId < 1078) {
    const source = randomChoice(nodes);
    const target = randomChoice(nodes);
    if (source.id !== target.id) {
      // 避免重复边
      const exists = edges.some(e => 
        (e.source === source.id && e.target === target.id) ||
        (e.source === target.id && e.target === source.id)
      );
      if (!exists) {
        edges.push(generateEdge(source.id, target.id, edgeId++));
      }
    }
  }
  
  return { nodes, edges };
};

// 生成预警数据
export const generateAlerts = (): AlertItem[] => {
  const alerts: AlertItem[] = [];
  const riskTypes = ['微生物污染', '食品添加剂过量', '物理性损伤', '化学残留', '标签不合格', '冷链断裂', '运输延误', '仓储异常'];
  const provinces = Object.keys(provinceData);
  
  // 生成实时预警
  for (let i = 0; i < 20; i++) {
    const province = randomChoice(provinces);
    const nodeType = randomChoice(nodeTypes);
    const riskType = randomChoice(riskTypes);
    const intensity = random(0.7, 0.99);
    const typeAbbr = {
      RAW_MILK: '原奶供应商',
      PROCESSOR: '乳制品加工厂',
      LOGISTICS: '物流公司',
      WAREHOUSE: '仓储中心',
      DISTRIBUTOR: '经销商',
      RETAILER: '零售终端',
    }[nodeType];
    
    alerts.push({
      id: `alert_${i}`,
      level: intensity > 0.85 ? 'high' : 'medium',
      title: `${province}：${typeAbbr}`,
      message: `${province}-${nodeType.substring(0, 3)}-${String(randomInt(1, 999)).padStart(3, '0')} | ${riskType} | 强度 ${intensity.toFixed(3)}`,
      timestamp: new Date(Date.now() - randomInt(0, 24 * 60 * 60 * 1000)).toISOString(),
      intensity,
      nodeId: `node_${randomInt(0, 768)}`,
    });
  }
  
  // 按时间倒序排序
  return alerts.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
};

// 生成风险统计数据
export const generateRiskStats = (): RiskStats => {
  const highRiskNodes = randomInt(30, 80);
  const mediumRiskNodes = randomInt(100, 200);
  const lowRiskNodes = 768 - highRiskNodes - mediumRiskNodes;
  
  return {
    totalNodes: 768,
    totalEdges: 1078,
    highRiskNodes,
    mediumRiskNodes,
    lowRiskNodes,
    activeAlerts: randomInt(10, 30),
    riskTrend: [
      { date: '2024-01', value: random(0.3, 0.5) },
      { date: '2024-02', value: random(0.3, 0.5) },
      { date: '2024-03', value: random(0.35, 0.55) },
      { date: '2024-04', value: random(0.35, 0.55) },
      { date: '2024-05', value: random(0.4, 0.6) },
      { date: '2024-06', value: random(0.4, 0.6) },
    ],
    nodeTypeDistribution: {
      RAW_MILK: 120,
      PROCESSOR: 80,
      LOGISTICS: 150,
      WAREHOUSE: 100,
      DISTRIBUTOR: 180,
      RETAILER: 138,
    },
    topRiskyNodes: Array.from({ length: 10 }, (_, i) => ({
      id: `node_${i}`,
      name: generateCompanyName('PROCESSOR', i, '河北省'),
      riskScore: random(0.8, 0.99),
      type: randomChoice(nodeTypes),
    })),
  };
};

// 预生成的数据
export const mockGraphData = generateGraphData();
export const mockAlerts = generateAlerts();
export const mockRiskStats = generateRiskStats();

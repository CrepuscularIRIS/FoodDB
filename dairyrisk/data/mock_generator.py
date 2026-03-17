#!/usr/bin/env python3
"""
乳制品供应链风险研判系统 - 模拟数据生成器
生成6张核心表的模拟数据
"""

import csv
import random
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# 设置随机种子以保证可重复性
random.seed(42)

# 基础配置
NUM_ENTERPRISES = 20
NUM_BATCHES = 100
NUM_INSPECTIONS = 150
NUM_EVENTS = 30
NUM_EDGES = 80

# 上海各区地址池
SHANGHAI_DISTRICTS = [
    "浦东新区", "黄浦区", "静安区", "徐汇区", "长宁区",
    "普陀区", "虹口区", "杨浦区", "闵行区", "宝山区",
    "嘉定区", "金山区", "松江区", "青浦区", "奉贤区", "崇明区"
]

# 企业名称池
ENTERPRISE_NAMES = [
    # 牧场
    ("光明牧业金山牧场", "牧场"), ("现代牧业崇明牧场", "牧场"),
    ("蒙牛乳业奉贤牧场", "牧场"), ("伊利松江牧场", "牧场"),
    # 乳企
    ("光明乳业股份有限公司", "乳企"), ("上海妙可蓝多食品", "乳企"),
    ("上海延中饮料有限公司", "乳企"), ("上海味全食品", "乳企"),
    ("上海晨冠乳业有限公司", "乳企"), ("上海纽贝滋营养乳品", "乳企"),
    # 物流
    ("上海冷鲜物流有限公司", "物流"), ("光明冷链物流", "物流"),
    ("京东物流上海分公司", "物流"), ("顺丰冷运上海", "物流"),
    # 仓储
    ("上海冷链仓储中心", "仓储"), ("光明乳业仓储部", "仓储"),
    ("盒马鲜生上海仓", "仓储"), ("京东上海生鲜仓", "仓储"),
    # 零售
    ("盒马鲜生", "零售"), ("永辉超市", "零售"),
    ("大润发", "零售"), ("联华超市", "零售"),
    ("全家便利店", "零售"), ("罗森便利店", "零售"),
]

# 产品名称池
PRODUCT_NAMES = {
    "pasteurized": ["光明鲜牛奶", "优倍鲜牛奶", "致优鲜牛奶", "新鲜牧场"],
    "UHT": ["光明纯牛奶", "莫斯利安", "优加纯牛奶", "有机纯牛奶"],
    "yogurt": ["光明原味酸奶", "健能酸奶", "畅优酸奶", "如实酸奶"],
    "powder": ["光明婴幼儿奶粉", "中老年奶粉", "学生奶粉"],
    "raw_milk": ["生牛乳", "原料乳"]
}

# GB标准规则库
GB_RULES = [
    # GB 19301-2010 生乳
    {"rule_id": "RULE-0001", "gb_no": "GB 19301-2010", "gb_name": "食品安全国家标准 生乳",
     "product_type": "raw_milk", "check_item": "蛋白质", "threshold": 2.8, "operator": ">=",
     "unit": "g/100g", "risk_type": "营养", "severity": "medium",
     "action_suggestion": "建议加强饲料管理，提高乳蛋白含量", "test_method": "GB 5009.5"},
    {"rule_id": "RULE-0002", "gb_no": "GB 19301-2010", "gb_name": "食品安全国家标准 生乳",
     "product_type": "raw_milk", "check_item": "脂肪", "threshold": 3.1, "operator": ">=",
     "unit": "g/100g", "risk_type": "营养", "severity": "low",
     "action_suggestion": "建议调整泌乳期管理", "test_method": "GB 5413.3"},
    {"rule_id": "RULE-0003", "gb_no": "GB 19301-2010", "gb_name": "食品安全国家标准 生乳",
     "product_type": "raw_milk", "check_item": "菌落总数", "threshold": 2000000, "operator": "<=",
     "unit": "CFU/mL", "risk_type": "微生物", "severity": "high",
     "action_suggestion": "建议立即排查挤奶设备和储奶罐卫生状况", "test_method": "GB 4789.2"},
    {"rule_id": "RULE-0004", "gb_no": "GB 19301-2010", "gb_name": "食品安全国家标准 生乳",
     "product_type": "raw_milk", "check_item": "体细胞数", "threshold": 600000, "operator": "<=",
     "unit": "个/mL", "risk_type": "微生物", "severity": "medium",
     "action_suggestion": "建议检查奶牛健康状况", "test_method": "GB 5413.30"},

    # GB 19645-2010 巴氏杀菌乳
    {"rule_id": "RULE-0010", "gb_no": "GB 19645-2010", "gb_name": "食品安全国家标准 巴氏杀菌乳",
     "product_type": "pasteurized", "check_item": "蛋白质", "threshold": 2.9, "operator": ">=",
     "unit": "g/100g", "risk_type": "营养", "severity": "medium",
     "action_suggestion": "建议检查原料乳质量", "test_method": "GB 5009.5"},
    {"rule_id": "RULE-0011", "gb_no": "GB 19645-2010", "gb_name": "食品安全国家标准 巴氏杀菌乳",
     "product_type": "pasteurized", "check_item": "菌落总数", "threshold": 100000, "operator": "<=",
     "unit": "CFU/mL", "risk_type": "微生物", "severity": "high",
     "action_suggestion": "建议立即排查冷链和杀菌工艺", "test_method": "GB 4789.2"},
    {"rule_id": "RULE-0012", "gb_no": "GB 19645-2010", "gb_name": "食品安全国家标准 巴氏杀菌乳",
     "product_type": "pasteurized", "check_item": "大肠菌群", "threshold": 10, "operator": "<=",
     "unit": "CFU/mL", "risk_type": "微生物", "severity": "high",
     "action_suggestion": "建议立即停产排查卫生状况", "test_method": "GB 4789.3"},
    {"rule_id": "RULE-0013", "gb_no": "GB 19645-2010", "gb_name": "食品安全国家标准 巴氏杀菌乳",
     "product_type": "pasteurized", "check_item": "金黄色葡萄球菌", "threshold": 0, "operator": "=",
     "unit": "CFU/mL", "risk_type": "微生物", "severity": "high",
     "action_suggestion": "建议召回同批次产品", "test_method": "GB 4789.10"},

    # GB 25190-2010 灭菌乳
    {"rule_id": "RULE-0020", "gb_no": "GB 25190-2010", "gb_name": "食品安全国家标准 灭菌乳",
     "product_type": "UHT", "check_item": "蛋白质", "threshold": 2.9, "operator": ">=",
     "unit": "g/100g", "risk_type": "营养", "severity": "medium",
     "action_suggestion": "建议检查原料乳质量", "test_method": "GB 5009.5"},
    {"rule_id": "RULE-0021", "gb_no": "GB 25190-2010", "gb_name": "食品安全国家标准 灭菌乳",
     "product_type": "UHT", "check_item": "脂肪", "threshold": 3.1, "operator": ">=",
     "unit": "g/100g", "risk_type": "营养", "severity": "low",
     "action_suggestion": "建议调整配方", "test_method": "GB 5413.3"},
    {"rule_id": "RULE-0022", "gb_no": "GB 25190-2010", "gb_name": "食品安全国家标准 灭菌乳",
     "product_type": "UHT", "check_item": "黄曲霉毒素M1", "threshold": 0.5, "operator": "<=",
     "unit": "μg/kg", "risk_type": "安全", "severity": "high",
     "action_suggestion": "建议排查饲料来源", "test_method": "GB 5009.24"},
    {"rule_id": "RULE-0023", "gb_no": "GB 25190-2010", "gb_name": "食品安全国家标准 灭菌乳",
     "product_type": "UHT", "check_item": "铅", "threshold": 0.05, "operator": "<=",
     "unit": "mg/kg", "risk_type": "安全", "severity": "high",
     "action_suggestion": "建议检查生产设备和包装材料", "test_method": "GB 5009.12"},

    # GB 19302-2010 发酵乳
    {"rule_id": "RULE-0030", "gb_no": "GB 19302-2010", "gb_name": "食品安全国家标准 发酵乳",
     "product_type": "yogurt", "check_item": "蛋白质", "threshold": 2.3, "operator": ">=",
     "unit": "g/100g", "risk_type": "营养", "severity": "medium",
     "action_suggestion": "建议检查原料乳和发酵工艺", "test_method": "GB 5009.5"},
    {"rule_id": "RULE-0031", "gb_no": "GB 19302-2010", "gb_name": "食品安全国家标准 发酵乳",
     "product_type": "yogurt", "check_item": "大肠菌群", "threshold": 10, "operator": "<=",
     "unit": "CFU/mL", "risk_type": "微生物", "severity": "high",
     "action_suggestion": "建议排查发酵环境和包装卫生", "test_method": "GB 4789.3"},
    {"rule_id": "RULE-0032", "gb_no": "GB 19302-2010", "gb_name": "食品安全国家标准 发酵乳",
     "product_type": "yogurt", "check_item": "酵母", "threshold": 100, "operator": "<=",
     "unit": "CFU/mL", "risk_type": "微生物", "severity": "medium",
     "action_suggestion": "建议检查冷链储存条件", "test_method": "GB 4789.15"},
    {"rule_id": "RULE-0033", "gb_no": "GB 19302-2010", "gb_name": "食品安全国家标准 发酵乳",
     "product_type": "yogurt", "check_item": "霉菌", "threshold": 30, "operator": "<=",
     "unit": "CFU/mL", "risk_type": "微生物", "severity": "medium",
     "action_suggestion": "建议检查生产环境卫生", "test_method": "GB 4789.15"},

    # GB 2760 食品添加剂
    {"rule_id": "RULE-0040", "gb_no": "GB 2760-2014", "gb_name": "食品安全国家标准 食品添加剂使用标准",
     "product_type": "all", "check_item": "防腐剂", "threshold": 0, "operator": "=",
     "unit": "mg/kg", "risk_type": "添加剂", "severity": "high",
     "action_suggestion": "纯牛奶中不得添加防腐剂，建议严查", "test_method": "GB 5009.28"},
    {"rule_id": "RULE-0041", "gb_no": "GB 2760-2014", "gb_name": "食品安全国家标准 食品添加剂使用标准",
     "product_type": "all", "check_item": "三聚氰胺", "threshold": 2.5, "operator": "<=",
     "unit": "mg/kg", "risk_type": "安全", "severity": "high",
     "action_suggestion": "建议追溯原料来源", "test_method": "GB/T 22388"},
]


def generate_enterprise_id(index: int) -> str:
    """生成企业ID"""
    return f"ENT-{index:04d}"


def generate_batch_id(index: int) -> str:
    """生成批次ID"""
    return f"BATCH-{index:06d}"


def generate_inspection_id(index: int) -> str:
    """生成检验ID"""
    return f"INS-{index:06d}"


def generate_event_id(index: int) -> str:
    """生成事件ID"""
    return f"EVT-{index:06d}"


def generate_edge_id(index: int) -> str:
    """生成边ID"""
    return f"EDGE-{index:06d}"


def random_date(start_date: datetime, end_date: datetime) -> str:
    """生成随机日期"""
    time_between = end_date - start_date
    days_between = time_between.days
    random_days = random.randrange(days_between)
    random_date = start_date + timedelta(days=random_days)
    return random_date.strftime("%Y-%m-%d")


def generate_enterprise_data() -> list[dict]:
    """生成企业主数据"""
    enterprises = []
    node_type_counts = {"牧场": 0, "乳企": 0, "物流": 0, "仓储": 0, "零售": 0}

    for i, (name, node_type) in enumerate(ENTERPRISE_NAMES[:NUM_ENTERPRISES]):
        enterprise_id = generate_enterprise_id(i + 1)
        node_type_counts[node_type] += 1

        district = random.choice(SHANGHAI_DISTRICTS)
        address = f"上海市{district}{random.randint(1, 999)}号"

        # 经纬度模拟（上海大致范围）
        lat = random.uniform(30.7, 31.5)
        lng = random.uniform(121.0, 122.0)

        # 许可证号
        sc_code = f"SC{random.randint(100, 999)}31{random.randint(10000000, 99999999)}"

        # 根据节点类型设置不同的特征
        if node_type == "牧场":
            credit_rating = random.choice(["A", "B", "B"])
            violation_count = random.randint(0, 2)
            supervision_freq = random.randint(2, 4)
            haccp = random.choice([True, False])
            iso = random.choice([True, False])
        elif node_type == "乳企":
            credit_rating = random.choice(["A", "A", "B", "B", "C"])
            violation_count = random.randint(0, 3)
            supervision_freq = random.randint(4, 12)
            haccp = random.choice([True, True, False])
            iso = random.choice([True, True, False])
        else:
            credit_rating = random.choice(["A", "B", "B", "C"])
            violation_count = random.randint(0, 2)
            supervision_freq = random.randint(1, 6)
            haccp = random.choice([True, False])
            iso = random.choice([True, False])

        enterprise = {
            "enterprise_id": enterprise_id,
            "enterprise_name": name,
            "enterprise_type": random.choice(["large", "medium", "small", "micro"]),
            "node_type": node_type,
            "address": address,
            "latitude": round(lat, 6),
            "longitude": round(lng, 6),
            "license_no": sc_code,
            "credit_rating": credit_rating,
            "historical_violation_count": violation_count,
            "supervision_freq": supervision_freq,
            "haccp_certified": haccp,
            "iso22000_certified": iso,
            "production_capacity_daily": round(random.uniform(10, 500), 2) if node_type == "乳企" else None,
            "main_products": random.choice(PRODUCT_NAMES["pasteurized"]) if node_type == "乳企" else None,
            "establishment_date": random_date(datetime(2000, 1, 1), datetime(2020, 12, 31)),
        }
        enterprises.append(enterprise)

    return enterprises


def generate_batch_data(enterprises: list[dict]) -> list[dict]:
    """生成批次数据"""
    batches = []
    # 获取乳企列表
    dairy_enterprises = [e for e in enterprises if e["node_type"] == "乳企"]
    # 获取牧场列表（作为原料供应商）
    farm_enterprises = [e for e in enterprises if e["node_type"] == "牧场"]

    start_date = datetime(2024, 1, 1)
    end_date = datetime(2025, 3, 1)

    for i in range(NUM_BATCHES):
        batch_id = generate_batch_id(i + 1)
        enterprise = random.choice(dairy_enterprises)
        product_type = random.choice(list(PRODUCT_NAMES.keys()))
        product_name = random.choice(PRODUCT_NAMES[product_type])

        production_date = datetime.strptime(random_date(start_date, end_date), "%Y-%m-%d")

        # 根据产品类型设置保质期
        if product_type == "pasteurized":
            shelf_life = random.choice([7, 15, 21])
            storage_temp = random.uniform(2, 8)
        elif product_type == "UHT":
            shelf_life = random.choice([180, 270, 365])
            storage_temp = random.uniform(15, 25)
        elif product_type == "yogurt":
            shelf_life = random.choice([14, 21, 28])
            storage_temp = random.uniform(2, 8)
        elif product_type == "powder":
            shelf_life = 730
            storage_temp = random.uniform(15, 25)
        else:  # raw_milk
            shelf_life = 2
            storage_temp = random.uniform(0, 4)

        # 原料批次
        raw_batch = f"RAW-{production_date.strftime('%Y%m%d')}-{random.randint(100, 999)}"
        raw_supplier = random.choice(farm_enterprises)["enterprise_id"] if farm_enterprises else None

        batch = {
            "batch_id": batch_id,
            "enterprise_id": enterprise["enterprise_id"],
            "product_name": product_name,
            "product_type": product_type,
            "batch_no": f"{production_date.strftime('%Y%m%d')}-{random.randint(1000, 9999)}",
            "production_date": production_date.strftime("%Y-%m-%d"),
            "shelf_life": shelf_life,
            "raw_material_batch": raw_batch,
            "raw_material_supplier_id": raw_supplier,
            "production_line": f"Line-{random.randint(1, 5)}",
            "storage_temp_avg": round(storage_temp, 1),
            "transport_temp_avg": round(storage_temp + random.uniform(-2, 3), 1),
            "transport_duration_hours": round(random.uniform(2, 48), 1),
            "storage_location": random.choice(["上海冷链中心", "企业自有仓库", "第三方仓储"]),
            "target_market": random.choice(["上海本地", "华东地区", "全国"]),
            "production_volume_tons": round(random.uniform(1, 50), 2),
        }
        batches.append(batch)

    return batches


def generate_inspection_data(enterprises: list[dict], batches: list[dict]) -> list[dict]:
    """生成检验数据"""
    inspections = []
    start_date = datetime(2024, 1, 1)
    end_date = datetime(2025, 3, 1)

    # 为每个批次生成检验记录
    for i, batch in enumerate(batches[:100]):  # 为前100个批次生成检验
        inspection_id = generate_inspection_id(i + 1)

        # 决定是原料检验还是成品检验
        inspection_type = random.choice(["raw", "product", "routine", "risk"])

        # 基础检验值
        product_type = batch["product_type"]

        # 根据产品类型设置检验指标
        if product_type == "pasteurized":
            protein = round(random.uniform(2.9, 3.4), 2)
            fat = round(random.uniform(3.1, 4.0), 2)
            aerobic = random.randint(10000, 500000)  # 可能超标
            coliforms = random.randint(1, 50)  # 可能超标
            aflatoxin = round(random.uniform(0.05, 0.5), 3)
            lead = round(random.uniform(0.01, 0.05), 3)
        elif product_type == "UHT":
            protein = round(random.uniform(2.9, 3.5), 2)
            fat = round(random.uniform(3.1, 4.0), 2)
            aerobic = random.randint(1000, 100000)
            coliforms = random.randint(1, 20)
            aflatoxin = round(random.uniform(0.05, 0.5), 3)
            lead = round(random.uniform(0.01, 0.05), 3)
        elif product_type == "yogurt":
            protein = round(random.uniform(2.3, 3.0), 2)
            fat = round(random.uniform(2.5, 3.5), 2)
            aerobic = random.randint(10000, 200000)
            coliforms = random.randint(1, 30)
            aflatoxin = round(random.uniform(0.05, 0.5), 3)
            lead = round(random.uniform(0.01, 0.05), 3)
        else:
            protein = round(random.uniform(2.8, 3.2), 2)
            fat = round(random.uniform(3.1, 3.8), 2)
            aerobic = random.randint(50000, 2000000)
            coliforms = random.randint(1, 100)
            aflatoxin = round(random.uniform(0.1, 0.8), 3)
            lead = round(random.uniform(0.01, 0.08), 3)

        # 判定结果（随机让一些不合格）
        unqualified_items = []
        if aerobic > 100000 and product_type == "pasteurized":
            unqualified_items.append("菌落总数")
        if coliforms > 10:
            unqualified_items.append("大肠菌群")
        if protein < 2.9 and product_type in ["pasteurized", "UHT"]:
            unqualified_items.append("蛋白质")
        if aflatoxin > 0.5:
            unqualified_items.append("黄曲霉毒素M1")

        test_result = "unqualified" if unqualified_items else "qualified"

        inspection = {
            "inspection_id": inspection_id,
            "batch_id": batch["batch_id"],
            "enterprise_id": batch["enterprise_id"],
            "inspection_type": inspection_type,
            "inspection_date": random_date(start_date, end_date),
            "protein_g_100g": protein,
            "fat_g_100g": fat,
            "aerobic_count_cfu_ml": aerobic,
            "coliforms_mpn_100ml": coliforms,
            "aflatoxin_m1_ug_kg": aflatoxin,
            "lead_mg_kg": lead,
            "total_bacteria_count": aerobic * 10 if random.random() > 0.5 else None,
            "acid_degree": round(random.uniform(12, 18), 1) if product_type == "raw_milk" else None,
            "melamine_mg_kg": round(random.uniform(0.1, 2.0), 2),
            "preservative_presence": random.choice([False, False, False, True]),
            "test_result": test_result,
            "unqualified_items": ",".join(unqualified_items) if unqualified_items else None,
            "inspection_agency": random.choice(["上海市食品药品检验所", "国家食品质量安全监督检验中心"]),
            "standard_ref": f"GB 19645-2010" if product_type == "pasteurized" else f"GB 25190-2010" if product_type == "UHT" else "GB 19302-2010",
            "risk_level": "high" if unqualified_items else random.choice(["low", "medium", "low"]),
        }
        inspections.append(inspection)

    # 为企业生成额外的监管抽检记录
    for i in range(50):
        enterprise = random.choice(enterprises)
        inspection_id = generate_inspection_id(100 + i + 1)

        inspection = {
            "inspection_id": inspection_id,
            "batch_id": None,
            "enterprise_id": enterprise["enterprise_id"],
            "inspection_type": "supervision",
            "inspection_date": random_date(start_date, end_date),
            "protein_g_100g": None,
            "fat_g_100g": None,
            "aerobic_count_cfu_ml": None,
            "coliforms_mpn_100ml": None,
            "aflatoxin_m1_ug_kg": None,
            "lead_mg_kg": None,
            "total_bacteria_count": None,
            "acid_degree": None,
            "melamine_mg_kg": None,
            "preservative_presence": None,
            "test_result": random.choice(["qualified", "qualified", "qualified", "unqualified"]),
            "unqualified_items": random.choice(["标签不规范", "储存条件不符", None, None]),
            "inspection_agency": random.choice(["上海市市场监管局", "区市场监管局"]),
            "standard_ref": "GB 7718-2011",
            "risk_level": random.choice(["low", "medium"]),
        }
        inspections.append(inspection)

    return inspections


def generate_regulatory_events(enterprises: list[dict], batches: list[dict]) -> list[dict]:
    """生成监管事件数据"""
    events = []
    start_date = datetime(2023, 1, 1)
    end_date = datetime(2025, 3, 1)

    event_templates = [
        ("处罚", "high", "因菌落总数超标被处以罚款{amount}元", "微生物超标"),
        ("处罚", "high", "因大肠菌群不合格被处以罚款{amount}元", "微生物超标"),
        ("处罚", "medium", "因标签标识不规范被处以罚款{amount}元", "标签违规"),
        ("整改", "medium", "被要求限期整改冷链储存条件", "质量指标"),
        ("整改", "low", "被要求完善进货查验记录", "其他"),
        ("投诉", "medium", "收到消费者关于产品异味的投诉", "微生物超标"),
        ("投诉", "low", "收到消费者关于包装破损的投诉", "其他"),
        ("抽检异常", "high", "监督抽检发现蛋白质含量不达标", "质量指标"),
        ("抽检异常", "medium", "风险监测发现防腐剂可疑阳性", "添加剂违规"),
        ("召回", "high", "主动召回某批次产品", "微生物超标"),
    ]

    for i in range(NUM_EVENTS):
        event_id = generate_event_id(i + 1)
        enterprise = random.choice(enterprises)

        event_type, severity, template, violation_type = random.choice(event_templates)

        description = template.format(amount=random.randint(5000, 50000))

        event = {
            "event_id": event_id,
            "enterprise_id": enterprise["enterprise_id"],
            "event_type": event_type,
            "event_date": random_date(start_date, end_date),
            "severity": severity,
            "description": description,
            "related_batch_id": random.choice(batches)["batch_id"] if random.random() > 0.5 else None,
            "violation_type": violation_type,
            "penalty_amount": random.randint(5000, 100000) if event_type == "处罚" else None,
            "rectification_deadline": random_date(end_date, datetime(2025, 12, 31)) if event_type == "整改" else None,
            "rectification_status": random.choice(["未整改", "整改中", "已整改"]) if event_type == "整改" else None,
            "source_url": None,
            "region": random.choice(SHANGHAI_DISTRICTS),
        }
        events.append(event)

    return events


def generate_supply_edges(enterprises: list[dict], batches: list[dict]) -> list[dict]:
    """生成供应链边数据"""
    edges = []

    # 分类企业
    farms = [e for e in enterprises if e["node_type"] == "牧场"]
    dairies = [e for e in enterprises if e["node_type"] == "乳企"]
    logistics = [e for e in enterprises if e["node_type"] == "物流"]
    storages = [e for e in enterprises if e["node_type"] == "仓储"]
    retails = [e for e in enterprises if e["node_type"] == "零售"]

    edge_index = 0

    # 1. 原料供应边: 牧场 -> 乳企
    for dairy in dairies:
        # 每个乳企连接1-3个牧场
        for farm in random.sample(farms, min(random.randint(1, 3), len(farms))):
            edge_index += 1
            edges.append({
                "edge_id": generate_edge_id(edge_index),
                "edge_type": "raw_material",
                "source_id": farm["enterprise_id"],
                "target_id": dairy["enterprise_id"],
                "source_type": "牧场",
                "target_type": "乳企",
                "weight": round(random.uniform(0.5, 1.0), 2),
                "evidence_type": random.choice(["public_record", "simulated"]),
                "start_date": "2020-01-01",
                "end_date": None,
                "transport_distance_km": round(random.uniform(50, 200), 1),
                "transport_duration_hours": round(random.uniform(2, 8), 1),
                "cold_chain_maintained": True,
                "transaction_volume": round(random.uniform(10, 100), 2),
                "frequency_monthly": random.randint(10, 30),
            })

    # 2. 加工边: 乳企 -> 批次（隐式）
    # 这个关系通过batch表中的enterprise_id体现

    # 3. 运输边: 乳企 -> 物流
    for dairy in dairies:
        for logistic in random.sample(logistics, min(random.randint(1, 2), len(logistics))):
            edge_index += 1
            edges.append({
                "edge_id": generate_edge_id(edge_index),
                "edge_type": "transport",
                "source_id": dairy["enterprise_id"],
                "target_id": logistic["enterprise_id"],
                "source_type": "乳企",
                "target_type": "物流",
                "weight": round(random.uniform(0.6, 1.0), 2),
                "evidence_type": "simulated",
                "start_date": random_date(datetime(2020, 1, 1), datetime(2024, 1, 1)),
                "end_date": None,
                "transport_distance_km": round(random.uniform(10, 100), 1),
                "transport_duration_hours": round(random.uniform(1, 4), 1),
                "cold_chain_maintained": True,
                "transaction_volume": None,
                "frequency_monthly": random.randint(20, 60),
            })

    # 4. 仓储边: 物流 -> 仓储
    for logistic in logistics:
        for storage in random.sample(storages, min(random.randint(1, 2), len(storages))):
            edge_index += 1
            edges.append({
                "edge_id": generate_edge_id(edge_index),
                "edge_type": "storage",
                "source_id": logistic["enterprise_id"],
                "target_id": storage["enterprise_id"],
                "source_type": "物流",
                "target_type": "仓储",
                "weight": round(random.uniform(0.5, 0.9), 2),
                "evidence_type": "simulated",
                "start_date": random_date(datetime(2020, 1, 1), datetime(2024, 1, 1)),
                "end_date": None,
                "transport_distance_km": round(random.uniform(5, 50), 1),
                "transport_duration_hours": round(random.uniform(0.5, 2), 1),
                "cold_chain_maintained": True,
                "transaction_volume": None,
                "frequency_monthly": random.randint(30, 90),
            })

    # 5. 销售边: 仓储 -> 零售
    for storage in storages:
        for retail in random.sample(retails, min(random.randint(2, 4), len(retails))):
            edge_index += 1
            edges.append({
                "edge_id": generate_edge_id(edge_index),
                "edge_type": "sale",
                "source_id": storage["enterprise_id"],
                "target_id": retail["enterprise_id"],
                "source_type": "仓储",
                "target_type": "零售",
                "weight": round(random.uniform(0.4, 0.8), 2),
                "evidence_type": "simulated",
                "start_date": random_date(datetime(2021, 1, 1), datetime(2024, 1, 1)),
                "end_date": None,
                "transport_distance_km": round(random.uniform(3, 30), 1),
                "transport_duration_hours": round(random.uniform(0.5, 2), 1),
                "cold_chain_maintained": random.choice([True, True, False]),
                "transaction_volume": None,
                "frequency_monthly": random.randint(10, 40),
            })

    # 6. 供货边: 乳企之间（代工/贴牌）
    for _ in range(5):
        if len(dairies) >= 2:
            source, target = random.sample(dairies, 2)
            edge_index += 1
            edges.append({
                "edge_id": generate_edge_id(edge_index),
                "edge_type": "supply",
                "source_id": source["enterprise_id"],
                "target_id": target["enterprise_id"],
                "source_type": "乳企",
                "target_type": "乳企",
                "weight": round(random.uniform(0.3, 0.7), 2),
                "evidence_type": "public_record",
                "start_date": random_date(datetime(2020, 1, 1), datetime(2024, 1, 1)),
                "end_date": None,
                "transport_distance_km": None,
                "transport_duration_hours": None,
                "cold_chain_maintained": None,
                "transaction_volume": round(random.uniform(5, 30), 2),
                "frequency_monthly": random.randint(5, 15),
            })

    return edges


def write_csv(data: list[dict], filepath: Path):
    """将数据写入CSV文件"""
    if not data:
        print(f"Warning: No data to write to {filepath}")
        return

    filepath.parent.mkdir(parents=True, exist_ok=True)

    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)

    print(f"✓ 写入 {filepath}: {len(data)} 条记录")


def generate_all():
    """生成所有模拟数据"""
    print("=" * 60)
    print("乳制品供应链风险研判系统 - 模拟数据生成器")
    print("=" * 60)

    base_path = Path(__file__).parent
    mock_path = base_path / "mock"

    # 1. 生成企业数据
    print("\n[1/6] 生成企业主数据...")
    enterprises = generate_enterprise_data()
    write_csv(enterprises, mock_path / "enterprise_master.csv")

    # 2. 生成批次数据
    print("\n[2/6] 生成批次记录...")
    batches = generate_batch_data(enterprises)
    write_csv(batches, mock_path / "batch_records.csv")

    # 3. 生成检验数据
    print("\n[3/6] 生成检验记录...")
    inspections = generate_inspection_data(enterprises, batches)
    write_csv(inspections, mock_path / "inspection_records.csv")

    # 4. 生成监管事件
    print("\n[4/6] 生成监管事件...")
    events = generate_regulatory_events(enterprises, batches)
    write_csv(events, mock_path / "regulatory_events.csv")

    # 5. 生成供应链边
    print("\n[5/6] 生成供应链边...")
    edges = generate_supply_edges(enterprises, batches)
    write_csv(edges, mock_path / "supply_edges.csv")

    # 6. 写入GB规则库
    print("\n[6/6] 写入GB标准规则库...")
    write_csv(GB_RULES, mock_path / "gb_rules.csv")

    # 生成统计信息
    print("\n" + "=" * 60)
    print("数据生成完成!")
    print("=" * 60)
    print(f"企业主数据: {len(enterprises)} 条")
    print(f"批次记录: {len(batches)} 条")
    print(f"检验记录: {len(inspections)} 条")
    print(f"监管事件: {len(events)} 条")
    print(f"供应链边: {len(edges)} 条")
    print(f"GB规则: {len(GB_RULES)} 条")
    print(f"\n数据目录: {mock_path}")

    return {
        "enterprises": enterprises,
        "batches": batches,
        "inspections": inspections,
        "events": events,
        "edges": edges,
        "gb_rules": GB_RULES,
    }


if __name__ == "__main__":
    generate_all()

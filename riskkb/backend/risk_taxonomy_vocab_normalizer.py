#!/usr/bin/env python3
"""Normalize product, symptom, and vulnerable-group vocab in risk_taxonomy.yaml."""

from __future__ import annotations

import argparse
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "knowledge" / "configs" / "risk_taxonomy.yaml"
MANIFEST_PATH = ROOT / "knowledge" / "derived" / "risk_taxonomy_vnext" / "risk_taxonomy_vocab_manifest.json"

PRODUCT_MAP = [
    (re.compile(r"infant formula|baby formula", re.I), "婴儿配方奶粉"),
    (re.compile(r"powdered infant food|powdered infant formula", re.I), "婴儿配方奶粉"),
    (re.compile(r"unpasteurized milk|raw milk", re.I), "未经巴氏杀菌乳"),
    (re.compile(r"unpasteurized cheese|raw cheese|queso fresco", re.I), "生奶酪"),
    (re.compile(r"\bmilk\b", re.I), "乳制品"),
    (re.compile(r"生牛奶|牛奶", re.I), "生鲜乳"),
    (re.compile(r"\bcheese\b|奶酪", re.I), "奶酪"),
    (re.compile(r"\bdairy\b|dairy products|乳制品|奶制品", re.I), "乳制品"),
    (re.compile(r"protein powder|protein shake|protein powders and supplements|蛋白粉|蛋白质粉", re.I), "蛋白粉"),
    (re.compile(r"special medical purpose|特医食品|特殊医学用途配方食品", re.I), "特医食品"),
    (re.compile(r"nutritional supplement|营养补充剂|营养补充饮品", re.I), "营养补充剂"),
    (re.compile(r"shellfish|clam|shrimp|crab|oyster|生蚝|蛤蜊|虾|蟹", re.I), "贝类"),
    (re.compile(r"mollusks", re.I), "软体贝类"),
    (re.compile(r"fish|tuna|salmon|水产品|鱼类", re.I), "水产品"),
    (re.compile(r"raw fish", re.I), "生食水产品"),
    (re.compile(r"lettuce|leafy|vegetable|vegetables|蔬菜", re.I), "蔬菜"),
    (re.compile(r"spinach|sprout", re.I), "生鲜农产品"),
    (re.compile(r"fruit|fruits|水果", re.I), "水果"),
    (re.compile(r"salad|凉拌|冷盘", re.I), "沙拉"),
    (re.compile(r"sandwich|三明治", re.I), "三明治"),
    (re.compile(r"juice|苹果汁", re.I), "果汁"),
    (re.compile(r"grain|corn|cereal|meal|谷物|玉米", re.I), "谷物"),
    (re.compile(r"maize|processed maize products", re.I), "玉米制品"),
    (re.compile(r"wheat", re.I), "小麦"),
    (re.compile(r"barley", re.I), "大麦"),
    (re.compile(r"sorghum", re.I), "高粱"),
    (re.compile(r"rice|米饭", re.I), "米饭制品"),
    (re.compile(r"meat|beef|pork|肉类|肉制品", re.I), "肉类"),
    (re.compile(r"poultry|chicken|家禽|鸡肉", re.I), "家禽肉类"),
    (re.compile(r"nut|peanut|坚果|花生酱", re.I), "坚果制品"),
    (re.compile(r"seed|sesame|种子类|芝麻", re.I), "种子类制品"),
    (re.compile(r"flour", re.I), "面粉"),
    (re.compile(r"coffee", re.I), "咖啡"),
    (re.compile(r"wine", re.I), "葡萄酒"),
    (re.compile(r"grape products", re.I), "葡萄制品"),
    (re.compile(r"fatty foods", re.I), "高脂动物源性食品"),
    (re.compile(r"pekmez", re.I), "果浆制品"),
    (re.compile(r"ducal apple nectar", re.I), "果汁饮料"),
    (re.compile(r"spices", re.I), "香辛料"),
    (re.compile(r"drinking[_ ]water|饮用水", re.I), "饮用水"),
    (re.compile(r"beverage|饮料", re.I), "饮料"),
    (re.compile(r"condiment|sauce|调味品", re.I), "调味品"),
    (re.compile(r"candy|confectionery|糖果", re.I), "糖果"),
    (re.compile(r"snack|零食", re.I), "零食"),
    (re.compile(r"processed foods?|加工食品", re.I), "加工食品"),
    (re.compile(r"processed_foods", re.I), "加工食品"),
    (re.compile(r"ready-to-eat|即食", re.I), "即食食品"),
    (re.compile(r"cold chain|冷链", re.I), "冷链食品"),
    (re.compile(r"animal-derived foods|animal origin foods|animal_origin_foods", re.I), "动物源性食品"),
    (re.compile(r"feed|animal feed", re.I), "饲料"),
]

SYMPTOM_MAP = {
    "acute enterocolitis": "急性肠炎",
    "bacterial gastroenteritis": "细菌性胃肠炎",
    "dysenteric stools": "痢疾样腹泻",
    "c. jejuni infection": "空肠弯曲菌感染",
    "food poisoning": "食物中毒",
    "death": "死亡",
    "vomiting": "呕吐",
    "nausea": "恶心",
    "diarrhea": "腹泻",
    "diarrhoea": "腹泻",
    "abdominal cramps": "腹痛",
    "gastroenteritis": "胃肠炎",
    "campylobacteriosis": "弯曲菌肠炎",
    "acute renal failure": "急性肾衰竭",
    "progressive neuromuscular blockade": "进行性神经肌肉阻断",
    "muscle weakness": "肌无力",
    "flaccid paralysis": "弛缓性麻痹",
    "diarrheal syndrome": "腹泻综合征",
    "emetic syndrome": "呕吐综合征",
    "neonatal meningitis": "新生儿脑膜炎",
    "e. sakazakii infections": "阪崎肠杆菌感染",
    "staphylococcal foodborne intoxication": "葡萄球菌性食物中毒",
    "developmental toxicity": "发育毒性",
    "reproductive effects": "生殖毒性",
    "immunosuppression": "免疫抑制",
    "endocrine disruption": "内分泌干扰",
    "chloracne": "氯痤疮",
    "impaired animal health": "动物健康受损",
    "fungal contamination": "真菌污染",
    "animal diseases": "动物疾病",
    "hepatocarcinogenesis": "肝癌",
    "leukoencephalomalacia": "脑白质软化症",
    "pulmonary edema syndrome": "肺水肿综合征",
    "liver cancer": "肝癌",
    "lem": "脑白质软化症",
    "pes": "肺水肿综合征",
    "methemoglobinemia": "高铁血红蛋白血症",
    "methaemoglobinaemia": "高铁血红蛋白血症",
    "cyanosis": "发绀",
    "hypoxia": "缺氧",
    "infant_blue_baby_syndrome": "婴儿蓝婴综合征",
    "brucellosis": "布鲁氏菌病",
    "zoonotic infection": "人畜共患感染",
    "carcinogenic compounds": "致癌化合物",
    "carcinogenicity": "致癌性",
    "estrogenic effects": "雌激素样效应",
    "reproductive disorders": "生殖障碍",
    "immunotoxicity": "免疫毒性",
    "genotoxicity": "遗传毒性",
    "cytotoxicity": "细胞毒性",
    "teratogenicity": "致畸性",
    "teratogenic": "致畸",
    "immunotoxic": "免疫毒性",
    "nephrotoxic": "肾毒性",
    "nephrotoxic impairment": "肾功能损害",
    "visual deficits": "视觉损害",
    "neuronal degeneration": "神经元退行性损伤",
    "smoking": "毒性",
    "mycotoxins": "真菌毒素中毒",
    "fungal": "真菌毒素中毒",
    "norovirus": "诺如病毒感染",
    "neurotoxic and": "神经毒性",
    "nephrotoxicity (肾毒性)": "肾毒性",
    "nephrotoxicity": "肾毒性",
    "cancer": "癌症",
    "carcinogenic": "致癌",
    "toxicity": "毒性",
    "choking": "窒息",
    "dental injury": "牙齿损伤",
    "foodborne infection": "食源性感染",
}
DROP_SYMPTOMS = {"coagulase", "cns", "zoonotic", "foodborne", "listerial", "brick"}

GROUP_MAP = {
    "elderly": "老年人",
    "children": "儿童",
    "child": "儿童",
    "infants": "婴儿",
    "infant": "婴儿",
    "young children": "幼儿",
    "newborns": "新生儿",
    "pregnant women": "孕妇",
    "pregnant_women": "孕妇",
    "immunocompromised individuals": "免疫功能低下者",
    "immunocompromised": "免疫功能低下者",
    "immunocompromised patients": "免疫功能低下者",
    "consumers with dental issues": "牙齿脆弱者",
    "lactating mothers": "哺乳期妇女",
    "fetuses": "胎儿",
    "agricultural workers": "农业工人",
    "children and elderly": "儿童和老年人",
    "infants (infant botulism)": "婴儿",
}

PRODUCT_SYNONYMS = {
    "生牛奶": "生鲜乳",
    "未巴氏消毒牛奶": "未经巴氏杀菌乳",
    "未巴氏消毒羊奶": "未经巴氏杀菌乳",
    "粉末婴儿食品": "婴儿配方奶粉",
    "粉末状婴儿食品": "婴儿配方奶粉",
    "一次性塑料餐具": "一次性餐具",
    "塑料容器": "塑料包装食品",
    "饮用水": "饮用水",
    "dairy_products": "乳制品",
}

GROUP_SYNONYMS = {
    "婴幼儿": "婴儿",
    "幼儿": "儿童",
    "免疫力低下者": "免疫功能低下者",
    "牙齿有问题者": "牙齿脆弱者",
    "畜牧业从业者": "农业工人",
    "G6PD缺乏症患者": "葡萄糖-6-磷酸脱氢酶缺乏者",
}


def _clean_list(items: list[str], limit: int) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        text = " ".join(str(item or "").split()).strip(" ,;")
        if not text:
            continue
        lowered = text.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        out.append(text)
        if len(out) >= limit:
            break
    return out


def _normalize_product(text: str) -> str:
    raw = " ".join(text.split()).strip()
    if not raw:
        return ""
    if len(raw) > 60 or re.search(r"\bUPC\b|\bNET WT\b|\d{4,}", raw, re.I):
        for pattern, replacement in PRODUCT_MAP:
            if pattern.search(raw):
                return replacement
        return ""
    for pattern, replacement in PRODUCT_MAP:
        if pattern.search(raw):
            return replacement
    if raw in PRODUCT_SYNONYMS:
        return PRODUCT_SYNONYMS[raw]
    return raw


def _normalize_symptom(text: str) -> str:
    raw = " ".join(text.split()).strip()
    if not raw:
        return ""
    lowered = raw.lower()
    if lowered in DROP_SYMPTOMS:
        return ""
    if raw in SYMPTOM_MAP:
        return SYMPTOM_MAP[raw]
    if lowered in SYMPTOM_MAP:
        return SYMPTOM_MAP[lowered]
    if raw == "溶血性尿毒综合征（HUS）":
        return "溶血性尿毒综合征"
    if "（hus）" in raw:
        return "溶血性尿毒综合征"
    if "iq" in lowered:
        return "智力损伤"
    return raw


def _normalize_group(text: str) -> str:
    raw = " ".join(text.split()).strip()
    if not raw:
        return ""
    lowered = raw.lower()
    if raw in GROUP_MAP:
        return GROUP_MAP[raw]
    if lowered in GROUP_MAP:
        return GROUP_MAP[lowered]
    if raw in GROUP_SYNONYMS:
        return GROUP_SYNONYMS[raw]
    return raw


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Normalize vocabulary in risk_taxonomy.yaml")
    parser.add_argument("--config-path", default=str(CONFIG_PATH), help="Path to risk_taxonomy.yaml")
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    path = Path(args.config_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))

    product_changes = 0
    symptom_changes = 0
    group_changes = 0
    for item in data.get("risk_factors", []):
        new_products = _clean_list([_normalize_product(x) for x in item.get("applicable_products", [])], 8)
        new_symptoms = _clean_list([_normalize_symptom(x) for x in item.get("typical_symptoms", [])], 8)
        new_groups = _clean_list([_normalize_group(x) for x in item.get("vulnerable_groups", [])], 6)
        if new_products != item.get("applicable_products", []):
            product_changes += 1
            item["applicable_products"] = new_products
        if new_symptoms != item.get("typical_symptoms", []):
            symptom_changes += 1
            item["typical_symptoms"] = new_symptoms
        if new_groups != item.get("vulnerable_groups", []):
            group_changes += 1
            item["vulnerable_groups"] = new_groups

    data["generated_at"] = datetime.now(UTC).isoformat()
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    manifest = {
        "generated_at": datetime.now(UTC).isoformat(),
        "config_path": str(path),
        "product_changes": product_changes,
        "symptom_changes": symptom_changes,
        "group_changes": group_changes,
    }
    MANIFEST_PATH.write_text(yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

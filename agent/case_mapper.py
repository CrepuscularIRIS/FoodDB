"""
Case Mapper Module - Real-world Case Integration

Maps real-world dairy safety incidents from case.md to:
- Risk factors
- GB standards
- Demonstration scenarios
- LLM context
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class RiskCase:
    """Structured risk case from real-world incidents"""
    case_id: str
    case_name: str
    year: int
    company: str
    product: str
    batch_info: str

    # Risk classification
    risk_type: str  # microbial, additive, cross_contamination, cold_chain, veterinary_drug, etc.
    risk_level: str  # high, medium, low

    # Detailed information
    background: str = ""
    direct_cause: str = ""
    root_cause: str = ""
    investigation_path: str = ""

    # Regulatory aspects
    primary_risk_link: str = ""  # Main risk环节
    secondary_risk_links: list[str] = field(default_factory=list)
    gb_standards: list[str] = field(default_factory=list)

    # Sampling and testing
    key_testing_items: list[str] = field(default_factory=list)
    testing_methods: list[str] = field(default_factory=list)

    # Regulatory recommendations
    immediate_actions: list[str] = field(default_factory=list)
    short_term_actions: list[str] = field(default_factory=list)
    long_term_actions: list[str] = field(default_factory=list)

    # Impact
    affected_scope: str = ""
    population_impact: str = ""
    economic_loss: str = ""

    def to_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "case_name": self.case_name,
            "year": self.year,
            "company": self.company,
            "product": self.product,
            "batch_info": self.batch_info,
            "risk_type": self.risk_type,
            "risk_level": self.risk_level,
            "background": self.background,
            "direct_cause": self.direct_cause,
            "root_cause": self.root_cause,
            "investigation_path": self.investigation_path,
            "primary_risk_link": self.primary_risk_link,
            "secondary_risk_links": self.secondary_risk_links,
            "gb_standards": self.gb_standards,
            "key_testing_items": self.key_testing_items,
            "testing_methods": self.testing_methods,
            "immediate_actions": self.immediate_actions,
            "short_term_actions": self.short_term_actions,
            "long_term_actions": self.long_term_actions,
            "affected_scope": self.affected_scope,
            "population_impact": self.population_impact,
            "economic_loss": self.economic_loss
        }

    def to_llm_context(self) -> str:
        """Convert case to LLM context string"""
        return f"""
案例: {self.case_name} ({self.year})
企业: {self.company}
产品: {self.product}
风险类型: {self.risk_type}
风险等级: {self.risk_level}

直接原因: {self.direct_cause[:200]}...

根因分析: {self.root_cause[:200]}...

相关GB标准: {', '.join(self.gb_standards)}

关键检测项: {', '.join(self.key_testing_items)}
"""


class CaseRepository:
    """Repository of real-world risk cases"""

    def __init__(self):
        self.cases: dict[str, RiskCase] = {}
        self._initialize_cases()

    def _initialize_cases(self):
        """Initialize the case database with selected cases"""

        # Case 1: Nestle ARA contamination (2026)
        self.cases["CASE-001"] = RiskCase(
            case_id="CASE-001",
            case_name="雀巢能恩/力多精奶粉ARA原料蜡样芽孢杆菌毒素召回事件",
            year=2026,
            company="雀巢集团",
            product="雀巢力多精/铂初能恩/舒宜能恩系列婴幼儿配方奶粉",
            batch_info="2025年10月-2026年1月生产批次，涉及71个大陆批次+21个香港批次",
            risk_type="microbial",
            risk_level="high",
            background="ARA原料供应商发酵环节被蜡样芽孢杆菌污染，产生Cereulide毒素。该毒素耐热性强，126℃加热90分钟仍保持活性。",
            direct_cause="ARA原料储存运输温度控制不当（超过25℃），芽孢萌发并产生Cereulide毒素；入厂检测未针对Cereulide建立专项检测程序。",
            root_cause="供应商管控缺失：未实施严格现场审核和全项目检测；原料验收标准不完善：未将Cereulide毒素纳入必检项目；风险评估体系缺陷：对微生物毒素风险认识不足。",
            investigation_path="ARA供应商发酵环节污染→储存运输温度超标→原料入厂未检出→奶粉成品污染→全球流通→荷兰工厂自检发现→全球召回",
            primary_risk_link="原料供应与验收环节",
            secondary_risk_links=["生产加工环节", "物流储存环节"],
            gb_standards=["GB 10765-2021 婴儿配方食品", "GB 4789.14-2014 蜡样芽孢杆菌检验"],
            key_testing_items=["蜡样芽孢杆菌计数", "Cereulide毒素(LC-MS/MS)", "蛋白质", "脂肪"],
            testing_methods=["平板计数法(MYP琼脂)", "液质联用(LC-MS/MS)", "ELISA快速筛查"],
            immediate_actions=["立即召回涉事批次产品", "对ARA供应商全面排查", "进口口岸100%抽样送检"],
            short_term_actions=["建立Cereulide毒素专项检测", "强化供应商审核机制", "优化原料储存温控"],
            long_term_actions=["推动GB标准修订纳入Cereulide限量", "建立供应商黑名单制度", "行业培训推广三重验证机制"],
            affected_scope="全球31个国家和地区，中国71个批次",
            population_impact="0-3岁婴幼儿为主要风险人群",
            economic_loss="巨额召回成本、库存清理、品牌声誉受损"
        )

        # Case 2: Bright Dairy Moslian cold chain failure (2022)
        self.cases["CASE-002"] = RiskCase(
            case_id="CASE-002",
            case_name="光明乳业莫斯利安常温奶冷链受热导致包装膨胀异味事件",
            year=2022,
            company="光明乳业股份有限公司",
            product="莫斯利安常温酸牛奶（原味、香草味、草莓味）",
            batch_info="2022年4-5月生产批次，批号MSL20220415、MSL20220428等",
            risk_type="cold_chain",
            risk_level="medium",
            background="2022年夏季高温期间，莫斯利安常温奶在华东、华南地区出现包装鼓胀、异味问题。产品虽标注'常温保存'，但长期高温仍会导致品质劣变。",
            direct_cause="第三方物流商冷链中断：冷藏车未开启制冷、温度监测失效；区域仓储中心未配备温控仓库，产品堆放于露天货场。",
            root_cause="物流管控体系不完善：未建立全链路温控监测；产品储存标准缺陷：未明确'常温'温度范围（应≤25℃）；供应链应急机制缺失：未针对高温天气调整运输方案。",
            investigation_path="生产基地出厂→第三方物流冷链中断→区域仓储高温存放→配送至终端→消费者投诉→抽检确认问题",
            primary_risk_link="运输储存环节",
            secondary_risk_links=["物流服务商管理环节", "销售终端管理环节"],
            gb_standards=["GB 19301-2010 生乳", "GB 25190-2010 灭菌乳"],
            key_testing_items=["菌落总数", "大肠菌群", "乳酸菌活菌数", "酸度", "pH值", "二氧化碳含量"],
            testing_methods=["平板计数法", "酸度滴定", "便携式微生物快检"],
            immediate_actions=["启动紧急召回", "排查温控记录", "下架问题产品"],
            short_term_actions=["完善物流商监管", "明确储存温度标识", "建立温控监测平台"],
            long_term_actions=["修订常温乳制品储运标准", "出台冷链物流管理办法", "建立夏季风险预警机制"],
            affected_scope="华东、华南地区超5000家销售终端",
            population_impact="超200名消费者投诉，3名儿童轻微腹泻",
            economic_loss="召回超10万箱，直接损失超500万元，销售额环比下降12%"
        )

        # Case 3: Abbott vanillin violation (2021)
        self.cases["CASE-003"] = RiskCase(
            case_id="CASE-003",
            case_name="雅培喜康优1段婴儿奶粉违规添加香兰素被罚909万事件",
            year=2021,
            company="雅培贸易（上海）有限公司",
            product="雅培铂优恩美力婴儿配方奶粉（0-6月龄，1段）",
            batch_info="批号18042NT，生产日期2020年6月3日，进口45078罐，销售44306罐",
            risk_type="additive",
            risk_level="high",
            background="国家市场监管总局抽检发现，雅培1段奶粉香兰素实测值171.6μg/kg。GB 2760-2014规定0-6月龄婴幼儿配方食品不得添加任何食品用香料。",
            direct_cause="爱尔兰工厂生产线切换时管道清洁不彻底，前序含香兰素产品残留导致交叉污染；出厂检验未将香兰素纳入检测项目。",
            root_cause="生产过程管控缺失：未建立含香料与无香料产品切换的清洁验证标准；跨国生产标准衔接不足：对中国法规理解不到位；检验标准不完善：未将香兰素纳入1段奶粉必检项目。",
            investigation_path="爱尔兰工厂生产线残留→管道清洁不彻底→生产1段奶粉时混入→出厂检验未检出→进口流通→宁波抽检发现→立案调查处罚",
            primary_risk_link="生产加工环节",
            secondary_risk_links=["检验检测环节", "标准合规管理环节"],
            gb_standards=["GB 2760-2014 食品添加剂使用标准", "GB 10765-2021 婴儿配方食品"],
            key_testing_items=["香兰素", "乙基香兰素", "蛋白质", "脂肪", "菌落总数"],
            testing_methods=["气相色谱法", "液相色谱法", "ELISA快速检测"],
            immediate_actions=["下架召回涉事产品", "暂停相关生产线", "全面排查进口批次"],
            short_term_actions=["优化生产线清洁验证流程", "将香兰素纳入必检项目", "强化跨国标准合规培训"],
            long_term_actions=["建立交叉污染风险预警体系", "完善婴幼儿奶粉添加剂监管", "建立信用黑名单制度"],
            affected_scope="全国多地母婴店、商超及电商平台",
            population_impact="0-6月龄婴幼儿群体，无健康损害案例但引发家长担忧",
            economic_loss="没收违法所得343.74万元，罚款909.31万元，合计罚没超1253万元"
        )

        # Case 4: Maiquer propylene glycol incident (2022)
        self.cases["CASE-004"] = RiskCase(
            case_id="CASE-004",
            case_name="麦趣尔纯牛奶检出非法添加丙二醇上海全渠道下架事件",
            year=2022,
            company="麦趣尔集团股份有限公司",
            product="麦趣尔纯牛奶（灭菌乳，200ml/盒）",
            batch_info="2批次检出丙二醇，货值金额522万元，销售金额492万元",
            risk_type="cross_contamination",
            risk_level="high",
            background="浙江省丽水市庆元县抽检发现麦趣尔纯牛奶检出丙二醇。GB 2760-2014规定灭菌乳不得添加丙二醇，检出即判定为不合格。",
            direct_cause="纯牛奶与调制奶生产线切换时，未对设备管道进行彻底清洗，调制奶中合法使用的含丙二醇香精残留混入纯牛奶。",
            root_cause="生产工艺管控缺失：未建立生产线切换清洁验证标准；质量管控体系不完善：出厂检验未覆盖非允许添加物质筛查；合规意识淡薄：未评估生产线共用引发的合规风险。",
            investigation_path="调制奶生产线使用含丙二醇香精→切换纯牛奶生产时管道清洁不彻底→残留香精混入→出厂检验未检测丙二醇→市场流通→抽检发现→立案调查",
            primary_risk_link="生产加工环节",
            secondary_risk_links=["质量检验环节", "供应链管理环节"],
            gb_standards=["GB 2760-2014 食品添加剂使用标准", "GB 25190-2010 灭菌乳"],
            key_testing_items=["丙二醇", "蛋白质", "脂肪", "菌落总数", "大肠菌群"],
            testing_methods=["气相色谱法", "气质联用(GC-MS)", "快速检测试剂盒"],
            immediate_actions=["全渠道下架涉事产品", "召回未销售产品", "立案调查"],
            short_term_actions=["改造生产线实现物理隔离", "建立清洁验证标准", "将丙二醇纳入出厂必检"],
            long_term_actions=["修订乳制品生产规范", "出台生产线分类管理办法", "建立风险预警机制"],
            affected_scope="全国多省市，上海全渠道下架",
            population_impact="儿童、老人等肠胃敏感群体为主要风险人群",
            economic_loss="没收违法所得36万元，罚款7315.1万元，上半年预计亏损1.3-1.95亿元"
        )

        # Case 5: Meiji veterinary drug residue (2023)
        self.cases["CASE-005"] = RiskCase(
            case_id="CASE-005",
            case_name="明治醇壹鲜牛奶因兽药磺胺甲恶唑残留风险预防性回收事件",
            year=2023,
            company="明治乳业株式会社（日本）",
            product="明治配送专用鲜牛奶（醇壹系列，180mL瓶装）",
            batch_info="关西工厂生产，保质期截至2023年11月13日，约4.5万瓶",
            risk_type="veterinary_drug",
            risk_level="medium",
            background="日本监管部门在大阪关西工厂检出磺胺甲恶唑残留。该兽药用于预防和治疗奶牛细菌性感染，用药后需间隔72小时以上才能挤奶。",
            direct_cause="合作牧场奶牛用药后未达到72小时间隔期即挤奶；原料奶入厂检验未将磺胺甲恶唑纳入必检项目。",
            root_cause="奶源管理体系不完善：未要求牧场提供用药记录及间隔期证明；检验标准存在缺陷：未覆盖全部常用兽药种类；风险预警机制滞后：对养殖环节用药风险预判不足。",
            investigation_path="合作牧场违规用药→间隔期不足即挤奶→原料奶携带残留→入厂检验未检出→加工为成品→监管部门抽检发现→预防性回收",
            primary_risk_link="原料供应与验收环节",
            secondary_risk_links=["奶源养殖管理环节", "生产过程追溯环节"],
            gb_standards=["GB 31650-2019 动物性食品中兽药最高残留限量", "GB 19301-2010 鲜乳"],
            key_testing_items=["磺胺甲恶唑", "磺胺嘧啶", "四环素类", "β-内酰胺类", "乳蛋白", "乳脂肪"],
            testing_methods=["HPLC-MS/MS高效液相色谱-质谱联用", "ELISA快速筛查", "微生物抑制法"],
            immediate_actions=["启动预防性回收", "排查合作牧场用药记录", "加强原料奶兽药检测"],
            short_term_actions=["完善奶源审核标准", "将磺胺类纳入必检项目", "建立用药间隔期核验机制"],
            long_term_actions=["推动养殖档案电子化管理", "研发兽药残留快检技术", "建立信用惩戒机制"],
            affected_scope="日本西部、中部地区宅配用户，未进入中国市场",
            population_impact="约数万宅配用户，无健康不适报告",
            economic_loss="回收退款及排查成本数千万日元，低温奶销量环比下降约8%"
        )

        # Case 6: Classy Kiss yeast超标 (2022)
        self.cases["CASE-006"] = RiskCase(
            case_id="CASE-006",
            case_name="卡士餐后一小时酸奶酵母超标60倍被官方通报事件",
            year=2022,
            company="卡士酸奶（苏州）有限公司",
            product="卡士'餐后一小时'双歧杆菌C-I风味发酵乳（250g/瓶）",
            batch_info="生产日期2021年12月23日，酵母检出值6000CFU/g",
            risk_type="microbial",
            risk_level="medium",
            background="上海市监局通报卡士酸奶酵母超标60倍（标准≤100CFU/g，实测6000CFU/g）。产品为高端低温酸奶，定位'品质标杆'。",
            direct_cause="储运环节温控失效：冷链中断、冷藏设备故障；或生产环节污染：设备清洁不彻底、原料乳携带酵母。",
            root_cause="全链条冷链管控存在盲区：对下游物流商、终端缺乏有效监管；出厂检验标准存在缺陷：未严格把控酵母指标；历史问题整改不彻底：2015年曾发生同类事件。",
            investigation_path="苏州工厂生产→出厂检验合格→物流运输/仓储温控失效→终端销售→抽检发现超标→全链条溯源",
            primary_risk_link="运输储存及销售终端环节",
            secondary_risk_links=["生产工艺管控环节", "供应链管理环节"],
            gb_standards=["GB 19302-2010 发酵乳"],
            key_testing_items=["酵母", "霉菌", "菌落总数", "大肠菌群", "酸度", "pH值"],
            testing_methods=["平板计数法（25℃培养5天）", "便携式微生物快检", "ATP荧光检测"],
            immediate_actions=["下架同批次在售产品", "启动退货退款", "排查冷链记录"],
            short_term_actions=["完善全链条冷链管控", "将酵母纳入出厂必检", "建立终端巡检机制"],
            long_term_actions=["修订低温乳制品冷链物流标准", "建立冷链追溯平台", "实施物流商资质认证"],
            affected_scope="上海地区统一超商旗下便利店及合作商超",
            population_impact="具体人数无统计，无集中健康损害投诉",
            economic_loss="品牌声誉受损，干酪类产品销售额环比下降约8%"
        )

    def get_case(self, case_id: str) -> Optional[RiskCase]:
        """Get a case by ID"""
        return self.cases.get(case_id)

    def get_all_cases(self) -> list[RiskCase]:
        """Get all cases"""
        return list(self.cases.values())

    def get_cases_by_risk_type(self, risk_type: str) -> list[RiskCase]:
        """Get cases by risk type"""
        return [c for c in self.cases.values() if c.risk_type == risk_type]

    def get_cases_by_company(self, company: str) -> list[RiskCase]:
        """Get cases by company name (partial match)"""
        return [c for c in self.cases.values() if company.lower() in c.company.lower()]

    def get_similar_cases(self, risk_type: str, risk_level: str, limit: int = 3) -> list[RiskCase]:
        """Get similar cases based on risk type and level"""
        matches = [
            c for c in self.cases.values()
            if c.risk_type == risk_type or c.risk_level == risk_level
        ]
        return matches[:limit]

    def get_gb_standards_for_risk_type(self, risk_type: str) -> list[str]:
        """Get relevant GB standards for a risk type"""
        standards = set()
        for case in self.get_cases_by_risk_type(risk_type):
            standards.update(case.gb_standards)
        return list(standards)

    def get_testing_items_for_risk_type(self, risk_type: str) -> list[str]:
        """Get recommended testing items for a risk type"""
        items = set()
        for case in self.get_cases_by_risk_type(risk_type):
            items.update(case.key_testing_items)
        return list(items)

    def to_dict(self) -> dict:
        """Convert all cases to dictionary"""
        return {
            case_id: case.to_dict()
            for case_id, case in self.cases.items()
        }

    def save_to_json(self, filepath: str):
        """Save cases to JSON file"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    def get_llm_context_for_case(self, case_id: str) -> str:
        """Get LLM context string for a specific case"""
        case = self.get_case(case_id)
        if case:
            return case.to_llm_context()
        return ""

    def get_combined_llm_context(self, risk_type: Optional[str] = None, limit: int = 3) -> str:
        """Get combined LLM context for multiple cases"""
        if risk_type:
            cases = self.get_cases_by_risk_type(risk_type)[:limit]
        else:
            cases = list(self.cases.values())[:limit]

        contexts = [case.to_llm_context() for case in cases]
        return "\n---\n".join(contexts)


# Singleton instance
case_repository = CaseRepository()


def get_repository() -> CaseRepository:
    """Get the singleton case repository"""
    return case_repository

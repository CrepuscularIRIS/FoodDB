# Research Notes: Minimax M2.5 Integration & Real-world Data

## Available Real-world Data Sources

### 1. Shanghai Dairy Processing Plants
**File**: `/home/yarizakurahime/data/agents/清洗后的上海市乳制品加工厂(1).xlsx`

**Structure**:
- 9 processing plants with detailed attributes
- Product categories: 乳粉（婴幼儿配方乳粉）, 液体乳（巴氏杀菌乳、灭菌乳）, 奶酪, etc.
- Enterprise scales: 大型企业, 中型企业, 小微企业
- Raw material sources: 进口奶源, 长三角地区牧场, 上海本地牧场为主
- Geographic coordinates (longitude/latitude)
- District information

**Key Enterprises**:
- 上海三元全佳乳业有限公司 (UHT, yogurt)
- 光明乳业股份有限公司华东中心工厂 (infant formula, pasteurized milk)
- 上海乳品七厂有限公司 (pasteurized milk)
- 上海纽贝滋营养乳品有限公司 (infant formula)
- 上海晨冠乳业有限公司 (infant formula)
- 上海花冠营养乳品有限公司 (infant formula)
- 上海爱婴室商务服务股份有限公司 (retail)
- 上海力涌商贸有限公司 (retail)
- 上海培芝生物科技有限公司 (biotech)

### 2. Shanghai Supply Chain Nodes
**File**: `/home/yarizakurahime/data/agents/上海市乳制品供应链节点_筛选后(1).csv`

**Structure**:
- 50+ supply chain nodes
- Node types: 原奶供应商, 乳制品加工厂, 冷链仓储中心
- Geographic coordinates
- Source keywords

**Key Nodes**:
- 光明牧业有限公司金山种奶牛场 (raw milk supplier)
- 纽仕兰乳业有限公司 (processor)
- Various cold chain centers

### 3. Risk Knowledge Base
**Directory**: `/home/yarizakurahime/data/standalone_food_risk_kb`

Contains structured risk factor data for food safety assessment.

## Case.md Analysis - Potential Demonstration Cases

### Selected Cases for Integration (5 cases):

1. **2026雀巢能恩/力多精奶粉ARA原料检出蜡样芽孢杆菌毒素召回事件**
   - Risk type: 微生物污染 (Microbial contamination - Cereulide toxin)
   - Key factors: Raw material contamination, supplier management failure
   - GB relevance: GB 10765-2021 (Infant formula)

2. **2022光明乳业莫斯利安常温奶冷链受热导致包装膨胀异味事件**
   - Risk type: 冷链失效 (Cold chain failure)
   - Key factors: Temperature control, logistics management
   - GB relevance: GB 19645-2010 (Pasteurized milk storage)

3. **2021雅培喜康优1段婴儿奶粉违规添加香兰素被罚909万事件**
   - Risk type: 添加剂违规 (Additive violation - Vanillin)
   - Key factors: Cross-contamination, production line management
   - GB relevance: GB 2760-2014 (Food additives)

4. **2022麦趣尔纯牛奶检出非法添加丙二醇上海全渠道下架事件**
   - Risk type: 非法添加 (Illegal additive - Propylene glycol)
   - Key factors: Production line switching, cleaning validation
   - GB relevance: GB 2760-2014 (Food additives in pure milk)

5. **2023明治醇壹鲜牛奶因兽药磺胺甲恶唑残留风险预防性回收事件**
   - Risk type: 兽药残留 (Veterinary drug residue)
   - Key factors: Raw milk quality, supplier management
   - GB relevance: GB 31650-2019 (Veterinary drug residues)

## Heterogeneous Graph Model Design

### Node Types (5 types):
1. **牧场 (Dairy Farm)** - Raw milk production
2. **乳企 (Dairy Processor)** - Processing/manufacturing
3. **物流 (Logistics)** - Transportation
4. **仓储 (Storage)** - Cold chain warehouses
5. **零售 (Retail)** - End sales points

### Edge Types (Multiple relationships):
1. **supply** - 牧场→乳企 (raw milk supply)
2. **transport** - 乳企→物流→仓储 (product distribution)
3. **sale** - 仓储→零售 (wholesale/retail)
4. **contract** - 乳企→牧场 (long-term contracts)
5. **group** - Intra-enterprise relationships

### Node Features:
- Risk score (computed)
- Historical violations
- Certifications (HACCP, ISO22000)
- Geographic location
- Enterprise scale
- Product types

### Edge Features:
- Transport frequency
- Temperature compliance rate
- Historical quality issues
- Distance/time

## Minimax M2.5 API Integration Strategy

### API Endpoint:
```
https://api.minimax.chat/v1/text/chatcompletion_v2
```

### Authentication:
- API Key required
- Group ID required

### Model Configuration:
- Model: `abab6.5s-chat` or `abab6.5-chat`
- Temperature: 0.3 (low for consistent outputs)
- Max tokens: 4096

### Prompt Design Strategy:

**System Prompt**:
```
You are an expert dairy supply chain risk assessment analyst.
Your task is to generate professional risk assessment reports based on structured data.
You must use formal Chinese regulatory language and cite GB standards where applicable.
```

**Report Sections to Generate**:
1. Executive Summary (结论) - Risk level and key findings
2. Evidence Analysis (证据分析) - Data-driven insights
3. Root Cause Analysis (根因分析) - Deep dive into causes
4. Regulatory Basis (法规依据) - GB standards reference
5. Recommendations (监管建议) - Actionable steps

### Hybrid Architecture:
```
Rule Engine → Risk Scores → LLM Enhancement → Final Report
     ↓              ↓              ↓
  Scoring      Structured    Narrative
  (Numeric)    Evidence      Analysis
```

## Implementation Modules Required:

1. **llm_client.py** - Minimax API client with retry logic
2. **prompt_templates.py** - Structured prompt templates
3. **heterogeneous_graph.py** - Graph data structure and queries
4. **real_data_loader.py** - Parse CSV/Excel files
5. **case_mapper.py** - Map cases to risk factors
6. **enhanced_reporter.py** - LLM-enhanced report generation

## Integration Flow:

```
User Query
    ↓
Object Identification
    ↓
Data Retrieval (Retriever)
    ↓
Risk Scoring (Engine)
    ↓
Heterogeneous Graph Query
    ↓
LLM Prompt Construction
    ↓
Minimax M2.5 API Call
    ↓
Report Assembly
    ↓
Final Output
```

# 供应链异构图数据生成器

根据方案文档5.1-5.5章节实现，生成包含6种节点类型和10种边类型的乳制品供应链异构图数据。

## 功能特性

### 1. 节点类型 (6种)

| 节点类型 | 说明 | 主要特征 |
|---------|------|----------|
| EnterpriseNode | 企业节点 | 规模、类型、员工数、年产量等 |
| RawMaterialNode | 原料节点 | 菌落数、体细胞数、抗生素残留等 |
| ProductionLineNode | 生产线节点 | 洁净度等级、杀菌温度、环境监控等 |
| BatchNode | 批次节点 | 质检结果（作为风险标签） |
| LogisticsNode | 物流节点 | 运输温度、冷链监控、运输时长等 |
| RetailNode | 零售节点 | 货架温度、库存天数、投诉数等 |

### 2. 边类型 (10种)

```
enterprise --purchases--> raw_material
enterprise --owns--> production_line
production_line --produces--> batch
raw_material --used_in--> batch
enterprise --manufactures--> batch
batch --transported_by--> logistics
logistics --delivers_to--> retail
batch --sold_at--> retail
enterprise --supplies--> enterprise
batch --temporal_next--> batch
```

### 3. 数据完整性策略

| 企业规模 | 数据完整度 | 特点 |
|---------|-----------|------|
| 大企业 | 95% | 全面的质量监控 |
| 中企业 | 80% | 部分监控缺失 |
| 小企业 | 50% | 重点监管对象 |

## 快速开始

### 基本使用

```python
from dairyrisk.data.supply_chain_generator import SupplyChainDataGenerator

# 创建生成器
generator = SupplyChainDataGenerator(random_seed=42)

# 生成数据
data = generator.generate_supply_chain(
    num_enterprises={"large": 10, "medium": 50, "small": 100},
    num_batches_per_enterprise=5,
    time_span_days=30
)

# 保存数据
generator.save_to_file(data, "supply_chain_graph.pt")
```

### 访问生成的数据

```python
# 节点特征
enterprise_features = data["enterprise"].x
batch_features = data["batch"].x

# 风险标签
risk_labels = data["batch"].y_risk      # 连续风险分数 (0-1)
binary_labels = data["batch"].y_binary  # 二分类标签 (0=合格, 1=不合格)

# 边索引
edge_index = data[("batch", "transported_by", "logistics")].edge_index
```

## 文件结构

```
dairyrisk/
├── graph/
│   ├── __init__.py          # 图模块导出
│   ├── nodes.py              # 6种节点类型定义
│   └── edges.py              # 10种边类型定义
└── data/
    ├── supply_chain_generator.py  # 数据生成器主类
    └── generator_examples.py      # 使用示例
```

## 验收标准验证

运行测试脚本验证所有验收标准:

```bash
cd /home/yarizakurahime/data/dairy_supply_chain_risk
python3 dairyrisk/tests/test_supply_chain_generator.py
```

### 验证结果

1. ✓ **节点数量**: 生成的异构图包含 500-1000 个节点
2. ✓ **数据保存**: 可保存为 `.pt` 文件
3. ✓ **数据完整性**: 包含大/中/小企业的数据完整性差异
4. ✓ **风险标签**: 批次节点有合理的风险标签（基于qc_colony_count）
5. ✓ **边类型**: 包含全部10种必需边类型

## 配置参数

### 企业数量配置

```python
num_enterprises = {
    "large": 10,   # 大企业数量
    "medium": 50,  # 中企业数量
    "small": 100   # 小企业数量
}
```

### 生成参数

```python
data = generator.generate_supply_chain(
    num_enterprises={"large": 10, "medium": 50, "small": 100},
    num_batches_per_enterprise=5,  # 每个企业生成的批次数量
    time_span_days=30              # 生产时间跨度（天）
)
```

## 风险标签说明

批次节点的风险标签基于质检菌落数生成:

- **连续风险分数** (`y_risk`): 0-1之间的浮点数，越高表示风险越大
  - 计算公式: `min(1.0, qc_colony_count / 100000)`
  - 国家标准: 菌落总数 ≤ 100000 CFU/mL 为合格

- **二分类标签** (`y_binary`):
  - 0: 合格 (`qc_result == "pass"`)
  - 1: 不合格 (`qc_result == "fail"` 或 `"pending"`)

## 示例输出

```
============================================================
供应链数据统计
============================================================

节点统计 (总计: 768 个):
  企业节点: 98 个
    - large: 8 个
    - medium: 30 个
    - small: 60 个
  原料节点: 288 个
  生产线节点: 114 个
  批次节点: 84 个
  物流节点: 84 个
  零售节点: 100 个

边统计:
  总边数: 1078 条

风险批次统计:
  不合格批次: 7 (8.33%)
  待检批次: 17 (20.24%)
  合格批次: 60 (71.43%)
```

## 依赖项

- Python 3.8+
- PyTorch 2.0+
- NumPy 1.20+

## 注意事项

1. 随机种子可重复: 设置相同的 `random_seed` 可生成相同的数据
2. 节点ID格式: 使用统一格式便于追踪 (`ENT_`, `RAW_`, `BATCH_` 等前缀)
3. 特征填充: 缺失值使用行业平均值或默认值填充
4. 内存使用: 大规模数据生成时请注意内存限制

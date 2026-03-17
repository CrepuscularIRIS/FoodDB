"""基础功能调试测试 - 不加载大模型，不训练"""
import sys
sys.path.insert(0, '.')

print("=" * 50)
print("基础模块导入测试")
print("=" * 50)

# 测试1: 基础模块（不加载PyTorch大文件）
try:
    print("\n[1/5] 导入基础节点/边定义...")
    from dairyrisk.graph.nodes import EnterpriseScale, NodeType
    from dairyrisk.graph.edges import EdgeType
    print(f"  ✅ 企业规模枚举: {[s.value for s in EnterpriseScale]}")
    print(f"  ✅ 边类型数: {len(EdgeType)}")
except Exception as e:
    print(f"  ❌ 失败: {e}")

# 测试2: 时序模块（不加载数据）
try:
    print("\n[2/5] 导入时序模块（仅类定义）...")
    from dairyrisk.graph.temporal import TemporalGraphBuilder
    print("  ✅ TemporalGraphBuilder 类可导入")
except Exception as e:
    print(f"  ❌ 失败: {e}")

# 测试3: 风险模块（不加载数据）
try:
    print("\n[3/5] 导入风险模块（仅类定义）...")
    from dairyrisk.risk.transmission import RiskTransmissionModel
    from dairyrisk.risk.alerts import AlertManager
    print("  ✅ RiskTransmissionModel 类可导入")
    print("  ✅ AlertManager 类可导入")
except Exception as e:
    print(f"  ❌ 失败: {e}")

# 测试4: 数据生成器（轻量级测试）
try:
    print("\n[4/5] 测试数据生成器（小规模）...")
    from dairyrisk.data.supply_chain_generator import SupplyChainDataGenerator
    # 只创建生成器实例，不生成数据
    generator = SupplyChainDataGenerator(random_seed=42)
    print("  ✅ 生成器实例创建成功")
    # 只检查上海区域列表
    print(f"  ✅ 上海区域数: {len(generator.SHANGHAI_DISTRICTS)}")
except Exception as e:
    print(f"  ❌ 失败: {e}")

# 测试5: API路由（不启动服务器）
try:
    print("\n[5/5] 导入API路由...")
    from fastapi import APIRouter
    from dairyrisk.api.temporal_routes import router as temporal_router
    print(f"  ✅ 时序API路由导入成功，路由数: {len(temporal_router.routes)}")
except Exception as e:
    print(f"  ❌ 失败: {e}")

print("\n" + "=" * 50)
print("基础测试完成")
print("=" * 50)

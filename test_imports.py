import sys
sys.path.insert(0, '/home/yarizakurahime/data/dairy_supply_chain_risk')

errors = []

# 测试所有模块导入
tests = [
    ("dairyrisk.graph.nodes", "EnterpriseScale"),
    ("dairyrisk.graph.edges", "EdgeType"),
    ("dairyrisk.data.labels", "fuse_labels"),
    ("dairyrisk.data.dataset", "SupplyChainDataset"),
    ("dairyrisk.evaluation.metrics", "calculate_auc_pr"),
    ("dairyrisk.evaluation.validator", "StratifiedValidator"),
    ("dairyrisk.training.losses", "SupplyChainRiskLoss"),
    ("dairyrisk.training.callbacks", "ModelCheckpoint"),
    ("dairyrisk.risk.transmission", "RiskTransmissionModel"),
    ("dairyrisk.risk.simulation", "RiskPropagationSimulator"),
    ("dairyrisk.utils.config", "Config"),
    ("dairyrisk.utils.logging", "setup_logger"),
]

print("=== 后端模块导入测试 ===")
for module_name, attr in tests:
    try:
        module = __import__(module_name, fromlist=[attr])
        getattr(module, attr)
        print(f"✅ {module_name}.{attr}")
    except Exception as e:
        print(f"❌ {module_name}.{attr}: {e}")
        errors.append((module_name, str(e)))

print(f"\n总计: {len(tests)} 个模块, {len(errors)} 个错误")
if errors:
    print("\n错误列表:")
    for mod, err in errors:
        print(f"  - {mod}: {err}")

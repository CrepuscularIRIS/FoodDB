#!/usr/bin/env python3
"""验证所有模块可导入"""

import sys
from pathlib import Path

def test_imports():
    """测试所有模块导入"""
    results = []
    
    tests = [
        ("dairyrisk.data.labels", "fuse_labels"),
        ("dairyrisk.evaluation.metrics", "calculate_auc_pr"),
        ("dairyrisk.evaluation.validator", "StratifiedValidator"),
        ("dairyrisk.training.losses", "SupplyChainRiskLoss"),
        ("dairyrisk.training.callbacks", "ModelCheckpoint"),
        ("dairyrisk.data.dataset", "SupplyChainDataset"),
        ("dairyrisk.utils.config", "load_config"),
        ("dairyrisk.utils.logging", "setup_logger"),
    ]
    
    for module_name, attr in tests:
        try:
            module = __import__(module_name, fromlist=[attr])
            getattr(module, attr)
            results.append((module_name, attr, "OK"))
            print(f"✓ {module_name}.{attr}")
        except Exception as e:
            results.append((module_name, attr, f"FAILED: {e}"))
            print(f"✗ {module_name}.{attr}: {e}")
    
    return results

def test_config():
    """测试配置加载"""
    try:
        import yaml
        config = yaml.safe_load(open('configs/supply_chain.yaml'))
        print("✓ configs/supply_chain.yaml")
        return True
    except Exception as e:
        print(f"✗ configs/supply_chain.yaml: {e}")
        return False

def main():
    print("=" * 60)
    print("模块验证")
    print("=" * 60)
    
    print("\n1. 测试模块导入...")
    results = test_imports()
    
    print("\n2. 测试配置文件...")
    config_ok = test_config()
    
    print("\n" + "=" * 60)
    passed = sum(1 for _, _, r in results if r == "OK")
    total = len(results)
    print(f"结果: {passed}/{total} 模块通过")
    
    if passed == total and config_ok:
        print("✅ 所有验证通过！")
        return 0
    else:
        print("⚠️ 部分验证失败")
        return 1

if __name__ == '__main__':
    sys.exit(main())

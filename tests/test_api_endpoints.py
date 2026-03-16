#!/usr/bin/env python3
"""
API端点最小自动化测试
测试关键接口是否正常工作
"""

import sys
import time
import requests
from pathlib import Path

# 配置
BASE_URL = "http://localhost:8000"
TIMEOUT = 30


def test_health_endpoint():
    """测试健康检查接口"""
    print("\n[测试1/4] 健康检查接口 (/health)")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"  ✓ 状态: {data.get('status', 'unknown')}")
            print(f"  ✓ 版本: {data.get('version', 'unknown')}")
            return True
        else:
            print(f"  ✗ 状态码异常: {response.status_code}")
            return False
    except Exception as e:
        print(f"  ✗ 请求失败: {e}")
        return False


def test_data_source_endpoint():
    """测试数据源信息接口"""
    print("\n[测试2/4] 数据源信息接口 (/data_source)")
    try:
        response = requests.get(f"{BASE_URL}/data_source", timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                source_data = data.get("data", {})
                print(f"  ✓ 数据源: {source_data.get('data_source', 'unknown')}")
                print(f"  ✓ 企业数: {source_data.get('enterprise_count', 0)}")
                print(f"  ✓ 批次数: {source_data.get('batch_count', 0)}")
                return True
            else:
                print(f"  ✗ 返回数据异常")
                return False
        else:
            print(f"  ✗ 状态码异常: {response.status_code}")
            return False
    except Exception as e:
        print(f"  ✗ 请求失败: {e}")
        return False


def get_valid_enterprise_id():
    """从/enterprises获取一个有效的企业ID"""
    try:
        response = requests.get(f"{BASE_URL}/enterprises", timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get("success") and data.get("data"):
                enterprises = data.get("data", [])
                if enterprises:
                    return enterprises[0].get("enterprise_id")
        return None
    except:
        return None


def test_assess_endpoint():
    """测试风险研判接口"""
    print("\n[测试3/4] 风险研判接口 (/assess)")
    try:
        # 先获取一个有效的企业ID
        enterprise_id = get_valid_enterprise_id()
        if not enterprise_id:
            print(f"  ⚠ 无法获取有效企业ID，跳过此测试")
            return False

        print(f"  使用企业ID: {enterprise_id}")

        response = requests.post(
            f"{BASE_URL}/assess",
            json={"query": enterprise_id, "with_propagation": False},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                report_data = data.get("data", {})
                print(f"  ✓ 报告ID: {report_data.get('report_id', 'unknown')[:20]}...")
                print(f"  ✓ 风险等级: {report_data.get('risk_level', 'unknown')}")
                print(f"  ✓ 风险评分: {report_data.get('risk_score', 0)}")
                return True
            else:
                print(f"  ✗ 返回数据异常")
                return False
        else:
            print(f"  ✗ 状态码异常: {response.status_code}")
            try:
                error_data = response.json()
                print(f"  ✗ 错误: {error_data.get('detail', 'unknown')}")
            except:
                pass
            return False
    except Exception as e:
        print(f"  ✗ 请求失败: {e}")
        return False


def test_symptom_assess_endpoint():
    """测试症状驱动评估接口"""
    print("\n[测试4/4] 症状驱动评估接口 (/symptom/assess)")
    try:
        response = requests.post(
            f"{BASE_URL}/symptom/assess",
            json={"query": "腹泻、发热、腹痛", "product_type": None},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                result_data = data.get("data", {})
                print(f"  ✓ 症状识别: {len(result_data.get('symptoms_detected', []))} 个")
                print(f"  ✓ 风险因子: {len(result_data.get('risk_factors', []))} 个")
                print(f"  ✓ 风险等级: {result_data.get('risk_level', 'unknown')}")
                return True
            else:
                print(f"  ✗ 返回数据异常")
                return False
        else:
            print(f"  ✗ 状态码异常: {response.status_code}")
            return False
    except Exception as e:
        print(f"  ✗ 请求失败: {e}")
        return False


def wait_for_server():
    """等待服务器启动"""
    print("等待服务器启动...")
    for i in range(TIMEOUT):
        try:
            response = requests.get(f"{BASE_URL}/health", timeout=2)
            if response.status_code == 200:
                print(f"  ✓ 服务器已就绪\n")
                return True
        except:
            pass
        time.sleep(1)
        if i % 5 == 0:
            print(f"  ... 等待中 ({i}/{TIMEOUT})")
    print(f"  ✗ 服务器启动超时\n")
    return False


def main():
    """主函数"""
    print("="*60)
    print("API端点最小自动化测试")
    print("="*60)

    # 等待服务器
    if not wait_for_server():
        print("\n请先启动后端服务: python backend/api.py")
        sys.exit(1)

    # 运行测试
    results = []
    results.append(("健康检查", test_health_endpoint()))
    results.append(("数据源信息", test_data_source_endpoint()))
    results.append(("风险研判", test_assess_endpoint()))
    results.append(("症状驱动评估", test_symptom_assess_endpoint()))

    # 测试结果汇总
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"  {status} - {name}")

    print("="*60)
    print(f"总计: {passed}/{total} 通过")
    print("="*60)

    if passed == total:
        print("\n✓ 所有测试通过")
        sys.exit(0)
    else:
        print(f"\n✗ {total - passed} 个测试失败")
        sys.exit(1)


if __name__ == "__main__":
    main()

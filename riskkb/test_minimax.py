#!/usr/bin/env python3
"""测试 Minimax API Key 和 M2.5 模型是否可用"""

import os
import requests
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

API_KEY = os.environ.get("minimaxi-api-key")
BASE_URL = os.environ.get("url", "https://api.minimax.chat/v1")

def test_api():
    """测试 Minimax API"""

    if not API_KEY:
        print("❌ 错误: 未找到 minimaxi-api-key")
        return False

    print(f"✓ API Key 已加载: {API_KEY[:20]}...")
    print(f"✓ API URL: {BASE_URL}")

    # 构建请求
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    # 测试用的请求体 (使用 M2.5 模型)
    payload = {
        "model": "MiniMax-M2.5",
        "messages": [
            {"role": "system", "content": "你是一个有帮助的助手。"},
            {"role": "user", "content": "你好，请用一句话介绍自己。"}
        ],
        "temperature": 0.7,
        "max_tokens": 100
    }

    print("\n🔄 正在发送请求到 Minimax API...")
    print(f"   模型: MiniMax-M2.5")

    try:
        response = requests.post(
            f"{BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )

        print(f"\n📡 响应状态码: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print("\n✅ API 请求成功!")
            print("\n📝 模型响应:")
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            print(f"   {content}")

            # 显示用量信息
            usage = data.get("usage", {})
            if usage:
                print(f"\n📊 Token 用量:")
                print(f"   Prompt: {usage.get('prompt_tokens', 'N/A')}")
                print(f"   Completion: {usage.get('completion_tokens', 'N/A')}")
                print(f"   Total: {usage.get('total_tokens', 'N/A')}")

            return True
        else:
            print(f"\n❌ 请求失败!")
            print(f"   错误信息: {response.text}")
            return False

    except requests.exceptions.Timeout:
        print("\n❌ 请求超时!")
        return False
    except requests.exceptions.ConnectionError:
        print("\n❌ 连接错误! 请检查网络或 API URL")
        return False
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("Minimax API 测试工具")
    print("=" * 50)

    success = test_api()

    print("\n" + "=" * 50)
    if success:
        print("✅ 测试结果: API Key 有效，模型可用!")
    else:
        print("❌ 测试结果: API 测试失败")
    print("=" * 50)

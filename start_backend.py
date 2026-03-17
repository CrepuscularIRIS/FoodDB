#!/usr/bin/env python3
"""
后端服务启动脚本

启动FastAPI服务，提供图数据API和其他后端服务。

用法:
    python start_backend.py          # 启动服务
    python start_backend.py --help   # 显示帮助
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path

def check_dependencies():
    """检查必要的依赖"""
    try:
        import fastapi
        import uvicorn
        print("✓ FastAPI和Uvicorn已安装")
    except ImportError as e:
        print(f"✗ 缺少依赖: {e}")
        print("请运行: pip install fastapi uvicorn")
        return False
    
    try:
        import dotenv
        print("✓ python-dotenv已安装")
    except ImportError:
        print("⚠ python-dotenv未安装（可选）")
    
    return True

def setup_environment():
    """设置环境变量"""
    # 获取项目根目录
    project_root = Path(__file__).parent.resolve()
    
    # 添加到Python路径
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    
    # 设置默认环境变量
    os.environ.setdefault('DATA_DIR', str(project_root / 'data' / 'merged'))
    os.environ.setdefault('PORT', '8000')
    os.environ.setdefault('HOST', '0.0.0.0')
    
    # 加载.env文件
    env_file = project_root / '.env'
    if env_file.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(env_file)
            print(f"✓ 已加载环境变量: {env_file}")
        except ImportError:
            print("⚠ 无法加载.env文件（python-dotenv未安装）")

def start_backend(host='0.0.0.0', port=8000, reload=False, workers=1):
    """
    启动FastAPI后端服务
    
    Args:
        host: 绑定的主机地址
        port: 绑定的端口
        reload: 是否启用自动重载（开发模式）
        workers: 工作进程数（生产模式）
    """
    print("=" * 60)
    print("启动乳制品供应链风险研判后端服务")
    print("=" * 60)
    
    # 检查依赖
    if not check_dependencies():
        return 1
    
    # 设置环境
    setup_environment()
    
    # 检查数据文件
    data_dir = Path('data/merged')
    if data_dir.exists():
        enterprise_file = data_dir / 'enterprise_master.csv'
        edges_file = data_dir / 'supply_edges.csv'
        
        if enterprise_file.exists():
            print(f"✓ 企业数据文件存在: {enterprise_file}")
        else:
            print(f"✗ 企业数据文件不存在: {enterprise_file}")
        
        if edges_file.exists():
            print(f"✓ 供应链边数据文件存在: {edges_file}")
        else:
            print(f"✗ 供应链边数据文件不存在: {edges_file}")
    else:
        print(f"✗ 数据目录不存在: {data_dir}")
    
    print("-" * 60)
    print(f"服务地址: http://{host}:{port}")
    print(f"API文档: http://{host}:{port}/docs")
    print(f"图数据API: http://{host}:{port}/api/graph/data")
    print("-" * 60)
    
    try:
        import uvicorn
        
        # 启动服务
        uvicorn.run(
            'backend.api:app',
            host=host,
            port=port,
            reload=reload,
            workers=workers if not reload else 1,
            log_level='info',
        )
    except KeyboardInterrupt:
        print("\n✓ 服务已停止")
        return 0
    except Exception as e:
        print(f"\n✗ 启动失败: {e}")
        return 1

def main():
    parser = argparse.ArgumentParser(
        description='启动乳制品供应链风险研判后端服务',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python start_backend.py                    # 默认启动
  python start_backend.py --port 8080        # 指定端口
  python start_backend.py --reload           # 开发模式（自动重载）
  python start_backend.py --workers 4        # 生产模式（多进程）
        """
    )
    
    parser.add_argument(
        '--host',
        type=str,
        default='0.0.0.0',
        help='绑定的主机地址 (默认: 0.0.0.0)'
    )
    
    parser.add_argument(
        '--port',
        type=int,
        default=8000,
        help='绑定的端口 (默认: 8000)'
    )
    
    parser.add_argument(
        '--reload',
        action='store_true',
        help='启用自动重载（开发模式）'
    )
    
    parser.add_argument(
        '--workers',
        type=int,
        default=1,
        help='工作进程数（生产模式，默认: 1）'
    )
    
    args = parser.parse_args()
    
    # 启动服务
    sys.exit(start_backend(
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers
    ))

if __name__ == '__main__':
    main()

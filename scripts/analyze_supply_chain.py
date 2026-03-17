#!/usr/bin/env python3
"""
供应链异构图数据分析主脚本

功能：
1. 加载并分析异构图数据
2. 生成统计报告
3. 输出可视化图表
4. 生成数据质量报告

用法：
    python scripts/analyze_supply_chain.py [--data-path PATH] [--output-dir DIR]

示例：
    python scripts/analyze_supply_chain.py
    python scripts/analyze_supply_chain.py --data-path data/supply_chain_graph.pt --output-dir reports
"""

import os
import sys
import argparse
import warnings
from pathlib import Path

# 添加上级目录到路径
script_dir = Path(__file__).parent.absolute()
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

warnings.filterwarnings('ignore')


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='供应链异构图数据分析工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  %(prog)s                                    # 使用默认路径运行
  %(prog)s --data-path data/custom_graph.pt   # 指定数据文件
  %(prog)s --output-dir my_reports            # 指定输出目录
  %(prog)s --skip-viz                         # 跳过可视化生成
  %(prog)s --skip-report                      # 跳过报告生成
        '''
    )
    
    parser.add_argument(
        '--data-path',
        type=str,
        default='data/supply_chain_graph.pt',
        help='图数据文件路径 (默认: data/supply_chain_graph.pt)'
    )
    
    parser.add_argument(
        '--output-dir',
        type=str,
        default='reports',
        help='报告输出目录 (默认: reports)'
    )
    
    parser.add_argument(
        '--skip-viz',
        action='store_true',
        help='跳过可视化图表生成'
    )
    
    parser.add_argument(
        '--skip-report',
        action='store_true',
        help='跳过报告生成'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='显示详细输出'
    )
    
    return parser.parse_args()


def check_environment():
    """检查运行环境"""
    print("=" * 60)
    print("环境检查")
    print("=" * 60)
    
    # 检查Python版本
    import platform
    print(f"Python版本: {platform.python_version()}")
    
    # 检查必要的库
    required_packages = [
        ('torch', 'PyTorch'),
        ('numpy', 'NumPy'),
        ('matplotlib', 'Matplotlib'),
    ]
    
    optional_packages = [
        ('torch_geometric', 'PyTorch Geometric'),
        ('networkx', 'NetworkX'),
    ]
    
    print("\n必需依赖:")
    for module, name in required_packages:
        try:
            __import__(module)
            print(f"  ✓ {name}")
        except ImportError:
            print(f"  ✗ {name} - 请安装: pip install {module}")
            return False
    
    print("\n可选依赖:")
    for module, name in optional_packages:
        try:
            __import__(module)
            print(f"  ✓ {name}")
        except ImportError:
            print(f"  ⚠ {name} - 部分功能可能受限")
    
    print("=" * 60)
    return True


def main():
    """主函数"""
    # 解析参数
    args = parse_arguments()
    
    # 检查环境
    if not check_environment():
        print("\n❌ 环境检查失败，请安装缺失的依赖")
        sys.exit(1)
    
    # 切换到项目根目录
    os.chdir(project_root)
    
    # 检查数据文件
    if not os.path.exists(args.data_path):
        print(f"\n❌ 数据文件不存在: {args.data_path}")
        print(f"   请确保数据文件在正确位置，或使用 --data-path 指定路径")
        sys.exit(1)
    
    print(f"\n📊 数据文件: {args.data_path}")
    print(f"📁 输出目录: {args.output_dir}")
    print()
    
    try:
        # 导入分析模块
        print("加载分析模块...")
        from dairyrisk.analysis.graph_analyzer import GraphAnalyzer
        from dairyrisk.visualization.graph_viz import GraphVisualizer
        from dairyrisk.analysis.data_report import DataReportGenerator
        
        # 步骤1: 图数据分析
        print("\n" + "=" * 60)
        print("步骤 1/3: 图数据分析")
        print("=" * 60)
        
        analyzer = GraphAnalyzer(data_path=args.data_path)
        stats = analyzer.run_full_analysis()
        
        # 打印摘要
        print("\n" + analyzer.get_summary())
        
        # 步骤2: 可视化
        figure_paths = []
        if not args.skip_viz:
            print("\n" + "=" * 60)
            print("步骤 2/3: 生成可视化图表")
            print("=" * 60)
            
            # 加载PyG数据用于可视化
            import torch
            data = torch.load(args.data_path, weights_only=False)
            
            visualizer = GraphVisualizer(output_dir=os.path.join(args.output_dir, 'figures'))
            figure_paths = visualizer.generate_all_visualizations(data, stats)
            
            print(f"\n✓ 已生成 {len(figure_paths)} 个可视化图表")
        else:
            print("\n⏭ 跳过可视化生成")
        
        # 步骤3: 生成报告
        if not args.skip_report:
            print("\n" + "=" * 60)
            print("步骤 3/3: 生成数据质量报告")
            print("=" * 60)
            
            # 转换图表路径为相对路径
            rel_figure_paths = [os.path.relpath(p, args.output_dir) for p in figure_paths]
            
            generator = DataReportGenerator(output_dir=args.output_dir)
            report_path = generator.generate_full_report(stats, rel_figure_paths)
            
            print(f"\n✓ 报告已生成: {report_path}")
        else:
            print("\n⏭ 跳过报告生成")
        
        # 完成
        print("\n" + "=" * 60)
        print("✅ 分析完成!")
        print("=" * 60)
        print(f"\n输出文件:")
        print(f"  📊 可视化图表: {os.path.join(args.output_dir, 'figures')}")
        if not args.skip_report:
            print(f"  📝 数据报告: {args.output_dir}/data_quality_report_latest.md")
        print()
        
    except Exception as e:
        print(f"\n❌ 分析过程中出现错误:")
        print(f"   {type(e).__name__}: {e}")
        
        if args.verbose:
            import traceback
            print("\n详细错误信息:")
            traceback.print_exc()
        
        sys.exit(1)


if __name__ == '__main__':
    main()

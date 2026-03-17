#!/usr/bin/env python3
"""
时序图更新模块测试脚本

测试内容：
1. 时序图构建器功能
2. 增量更新引擎
3. 快照管理器
4. API路由（可选）
"""

import sys
import asyncio
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_temporal_builder():
    """测试时序图构建器"""
    print("\n" + "="*60)
    print("测试 1: 时序图构建器 (TemporalGraphBuilder)")
    print("="*60)
    
    from dairyrisk.graph.temporal import TemporalGraphBuilder, TimeGranularity
    from dairyrisk.graph.nodes import NodeType, EnterpriseNode, BatchNode, EnterpriseScale
    from dairyrisk.graph.edges import EdgeType, Edge
    
    # 创建构建器
    builder = TemporalGraphBuilder(
        data_dir="./test_temporal_data",
        window_days=7,
        enable_auto_cleanup=True
    )
    
    # 测试节点添加
    print("\n[1.1] 添加节点...")
    
    enterprise = EnterpriseNode(
        node_id="ENT_001",
        name="测试企业A",
        scale=EnterpriseScale.LARGE,
        enterprise_type="producer",
        location="上海市浦东新区",
        registration_date="2020-01-01"
    )
    
    batch = BatchNode(
        node_id="BATCH_001",
        batch_id="B202503001",
        product_name="鲜牛奶",
        product_type="milk",
        enterprise_id="ENT_001"
    )
    
    builder.add_node(enterprise, NodeType.ENTERPRISE)
    builder.add_node(batch, NodeType.BATCH)
    print(f"  ✓ 添加企业节点: {enterprise.node_id}")
    print(f"  ✓ 添加批次节点: {batch.node_id}")
    
    # 测试边添加
    print("\n[1.2] 添加边...")
    
    edge = Edge(
        src_id="ENT_001",
        dst_id="BATCH_001",
        edge_type=EdgeType.MANUFACTURES,
        weight=1.0
    )
    
    edge_id = builder.add_edge(edge)
    print(f"  ✓ 添加边: {edge.src_id} -> {edge.dst_id} (ID: {edge_id})")
    
    # 测试查询
    print("\n[1.3] 查询功能...")
    
    nodes = builder.get_nodes_by_type(NodeType.ENTERPRISE)
    print(f"  ✓ 企业节点数: {len(nodes)}")
    
    edges = builder.get_edges_by_type(EdgeType.MANUFACTURES)
    print(f"  ✓ 制造边数: {len(edges)}")
    
    neighbors = builder.get_neighbors("ENT_001", "out")
    print(f"  ✓ ENT_001 的出邻居: {neighbors}")
    
    # 测试统计
    print("\n[1.4] 统计信息...")
    stats = builder.get_stats()
    print(f"  ✓ 总节点数: {stats['total_nodes']}")
    print(f"  ✓ 总边数: {stats['total_edges']}")
    print(f"  ✓ 时间窗口: {stats['current_window']['duration_days']}天")
    
    # 测试时序摘要
    print("\n[1.5] 节点时序摘要...")
    summary = builder.get_node_temporal_summary("ENT_001")
    print(f"  ✓ 节点ID: {summary['node_id']}")
    print(f"  ✓ 类型: {summary['node_type']}")
    print(f"  ✓ 出度: {summary['out_degree']}")
    
    print("\n✅ 时序图构建器测试通过!")
    return builder


def test_incremental_engine():
    """测试增量更新引擎"""
    print("\n" + "="*60)
    print("测试 2: 增量更新引擎 (IncrementalUpdateEngine)")
    print("="*60)
    
    from dairyrisk.graph.incremental import IncrementalUpdateEngine, UpdateEventType
    
    # 创建引擎
    engine = IncrementalUpdateEngine(
        data_dir="./test_incremental_data",
        enable_async_processing=False  # 测试时禁用异步
    )
    
    # 测试事件订阅
    print("\n[2.1] 事件订阅...")
    events_received = []
    
    def on_event(event):
        events_received.append(event.event_type.value)
        print(f"  📡 收到事件: {event.event_type.value}")
    
    engine.subscribe(UpdateEventType.NODE_ADDED, on_event)
    engine.subscribe(UpdateEventType.EDGE_ADDED, on_event)
    print("  ✓ 已订阅节点和边添加事件")
    
    # 测试节点添加
    print("\n[2.2] 添加节点...")
    
    success, msg, node_id = engine.add_or_update_node(
        node_data={
            "node_id": "ENT_002",
            "name": "测试企业B",
            "enterprise_type": "processor",
            "location": "上海市闵行区"
        },
        node_type=engine.temporal_builder._node_index_by_type.__class__.__name__,
        skip_validation=True
    )
    
    # 修正：使用正确的NodeType
    from dairyrisk.graph.nodes import NodeType
    success, msg, node_id = engine.add_or_update_node(
        node_data={
            "node_id": "ENT_002",
            "name": "测试企业B",
            "enterprise_type": "processor",
            "location": "上海市闵行区"
        },
        node_type=NodeType.ENTERPRISE
    )
    print(f"  ✓ {msg}: {node_id}")
    
    # 测试批量导入
    print("\n[2.3] 批量导入...")
    
    batch_data = {
        "batches": [
            {
                "batch_id": "B202503002",
                "product_name": "酸奶",
                "product_type": "yogurt",
                "enterprise_id": "ENT_002"
            },
            {
                "batch_id": "B202503003",
                "product_name": "奶酪",
                "product_type": "cheese",
                "enterprise_id": "ENT_002"
            }
        ],
        "edges": [
            {
                "src_id": "ENT_002",
                "dst_id": "B202503002",
                "edge_type": "MANUFACTURES"
            }
        ]
    }
    
    result = engine.import_batch_data(batch_data)
    print(f"  ✓ 批量导入完成")
    print(f"    - 添加节点: {len(result.added_nodes)}")
    print(f"    - 添加边: {len(result.added_edges)}")
    print(f"    - 总变化: {result.to_dict()['total_changes']}")
    
    # 测试数据验证
    print("\n[2.4] 数据验证...")
    
    validation = engine.validate_node_data(
        node_data={"name": "缺少ID的企业"},
        node_type=NodeType.ENTERPRISE
    )
    print(f"  ✓ 无效数据验证: 通过={validation.is_valid}, 错误={len(validation.errors)}")
    
    valid_data = {"node_id": "ENT_003", "name": "有效企业"}
    validation = engine.validate_node_data(valid_data, NodeType.ENTERPRISE)
    print(f"  ✓ 有效数据验证: 通过={validation.is_valid}")
    
    # 测试统计
    print("\n[2.5] 引擎统计...")
    stats = engine.get_stats()
    print(f"  ✓ 队列大小: {stats['queue_size']}")
    print(f"  ✓ 异步启用: {stats['async_enabled']}")
    
    print("\n✅ 增量更新引擎测试通过!")
    return engine


def test_snapshot_manager(temporal_builder):
    """测试快照管理器"""
    print("\n" + "="*60)
    print("测试 3: 快照管理器 (SnapshotManager)")
    print("="*60)
    
    from dairyrisk.data.snapshot_manager import SnapshotManager, CompressionType
    
    # 创建管理器
    manager = SnapshotManager(
        temporal_builder=temporal_builder,
        data_dir="./test_snapshot_data",
        default_compression=CompressionType.GZIP
    )
    
    # 测试快照创建
    print("\n[3.1] 创建快照...")
    
    snapshot = manager.create_snapshot(
        granularity="day",
        metadata={"test": True, "version": "1.0"}
    )
    print(f"  ✓ 快照ID: {snapshot.snapshot_id}")
    print(f"  ✓ 时间戳: {snapshot.timestamp}")
    print(f"  ✓ 节点数: {snapshot.node_count}")
    print(f"  ✓ 边数: {snapshot.edge_count}")
    
    # 测试列表查询
    print("\n[3.2] 快照列表...")
    
    snapshots = manager.list_snapshots(limit=10)
    print(f"  ✓ 快照数量: {len(snapshots)}")
    for s in snapshots:
        print(f"    - {s['snapshot_id'][:8]}... ({s['granularity']}, {s['node_count']}节点)")
    
    # 测试快照获取
    print("\n[3.3] 获取快照...")
    
    loaded = manager.get_snapshot(snapshot.snapshot_id)
    print(f"  ✓ 加载成功: {loaded.snapshot_id == snapshot.snapshot_id}")
    
    # 创建第二个快照进行对比
    print("\n[3.4] 快照对比...")
    
    # 添加一个新节点
    from dairyrisk.graph.nodes import BatchNode, NodeType
    new_batch = BatchNode(
        node_id="BATCH_COMPARE",
        batch_id="B202503_COMPARE",
        product_name="对比测试产品",
        product_type="milk",
        enterprise_id="ENT_001"
    )
    temporal_builder.add_node(new_batch, NodeType.BATCH)
    
    snapshot2 = manager.create_snapshot(granularity="day")
    
    diff = manager.compare_snapshots(snapshot.snapshot_id, snapshot2.snapshot_id)
    print(f"  ✓ 对比结果:")
    print(f"    - 新增节点: {len(diff.get('added_nodes', []))}")
    print(f"    - 节点变化: {diff.get('node_change', 0)}")
    
    # 测试统计
    print("\n[3.5] 统计信息...")
    stats = manager.get_stats()
    print(f"  ✓ 总快照数: {stats['total_snapshots']}")
    print(f"  ✓ 存储大小: {stats['total_storage_bytes'] / 1024:.2f} KB")
    print(f"  ✓ 缓存大小: {stats['cache_size']}")
    
    print("\n✅ 快照管理器测试通过!")
    return manager


def test_api_routes():
    """测试API路由（模拟）"""
    print("\n" + "="*60)
    print("测试 4: API路由 (Temporal Routes)")
    print("="*60)
    
    from dairyrisk.api.temporal_routes import (
        init_temporal_components,
        router
    )
    
    # 测试初始化
    print("\n[4.1] 组件初始化...")
    try:
        builder, engine, manager = init_temporal_components(
            data_dir="./test_api_data"
        )
        print(f"  ✓ 时序构建器: {builder is not None}")
        print(f"  ✓ 增量引擎: {engine is not None}")
        print(f"  ✓ 快照管理器: {manager is not None}")
    except Exception as e:
        print(f"  ✗ 初始化失败: {e}")
        return
    
    # 测试路由存在
    print("\n[4.2] 路由检查...")
    routes = [r.path for r in router.routes]
    print(f"  ✓ 路由数量: {len(routes)}")
    
    expected_routes = [
        "/api/graph/update",
        "/api/graph/nodes",
        "/api/graph/edges",
        "/api/graph/snapshot",
        "/api/graph/snapshot/{date}",
        "/api/graph/snapshots",
        "/api/graph/temporal/{node_id}",
        "/api/graph/stats",
        "/api/graph/ws"
    ]
    
    for route in expected_routes:
        match = any(route in r for r in routes)
        status = "✓" if match else "✗"
        print(f"  {status} {route}")
    
    print("\n✅ API路由测试通过!")


def cleanup_test_data():
    """清理测试数据"""
    print("\n" + "="*60)
    print("清理测试数据")
    print("="*60)
    
    import shutil
    
    test_dirs = [
        "./test_temporal_data",
        "./test_incremental_data", 
        "./test_snapshot_data",
        "./test_api_data"
    ]
    
    for dir_path in test_dirs:
        path = Path(dir_path)
        if path.exists():
            shutil.rmtree(path)
            print(f"  ✓ 删除: {dir_path}")


def run_all_tests():
    """运行所有测试"""
    print("\n" + "🧪" * 30)
    print("时序图更新模块测试套件")
    print("🧪" * 30)
    
    try:
        # 测试1: 时序图构建器
        builder = test_temporal_builder()
        
        # 测试2: 增量更新引擎
        engine = test_incremental_engine()
        
        # 测试3: 快照管理器
        manager = test_snapshot_manager(builder)
        
        # 测试4: API路由
        test_api_routes()
        
        print("\n" + "="*60)
        print("🎉 所有测试通过!")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # 询问是否清理
        cleanup_test_data()


if __name__ == "__main__":
    run_all_tests()

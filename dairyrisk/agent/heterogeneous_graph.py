"""
Heterogeneous Graph Module for Dairy Supply Chain

This module implements a heterogeneous graph data structure for modeling
dairy supply chains with multiple node types (牧场/乳企/物流/仓储/零售)
and relationship types.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
import pandas as pd

logger = logging.getLogger(__name__)


class NodeType(Enum):
    """Node types in the supply chain graph"""
    FARM = "牧场"              # Raw milk supplier
    PROCESSOR = "乳企"         # Dairy processor
    LOGISTICS = "物流"         # Logistics provider
    WAREHOUSE = "仓储"         # Cold chain storage
    RETAIL = "零售"            # Retail endpoint


class EdgeType(Enum):
    """Edge types representing supply chain relationships"""
    SUPPLY = "supply"          # 牧场→乳企 (raw milk supply)
    TRANSPORT = "transport"    # 乳企→物流→仓储 (product transport)
    SALE = "sale"              # 仓储→零售 (wholesale/retail)
    CONTRACT = "contract"      # Long-term supply contract
    GROUP = "group"            # Intra-enterprise relationship


@dataclass
class HeteroNode:
    """Heterogeneous graph node"""
    node_id: str
    node_type: NodeType
    name: str
    attributes: dict = field(default_factory=dict)
    risk_score: float = 0.0
    features: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type.value,
            "name": self.name,
            "attributes": self.attributes,
            "risk_score": self.risk_score,
            "features": self.features
        }


@dataclass
class HeteroEdge:
    """Heterogeneous graph edge"""
    edge_id: str
    source_id: str
    target_id: str
    edge_type: EdgeType
    weight: float = 1.0
    attributes: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "edge_id": self.edge_id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "edge_type": self.edge_type.value,
            "weight": self.weight,
            "attributes": self.attributes
        }


class HeterogeneousSupplyChainGraph:
    """
    Heterogeneous Graph for Dairy Supply Chain

    Models the supply chain as a graph with:
    - 5 node types: 牧场, 乳企, 物流, 仓储, 零售
    - Multiple edge types representing different relationships
    - Risk propagation capabilities
    """

    def __init__(self):
        self.nodes: dict[str, HeteroNode] = {}
        self.edges: dict[str, HeteroEdge] = {}
        self.adjacency: dict[str, list[str]] = {}  # node_id -> list of edge_ids
        self.node_index_by_type: dict[NodeType, list[str]] = {
            nt: [] for nt in NodeType
        }

    def add_node(
        self,
        node_id: str,
        node_type: NodeType,
        name: str,
        attributes: Optional[dict] = None,
        features: Optional[dict] = None
    ) -> HeteroNode:
        """Add a node to the graph"""
        if node_id in self.nodes:
            logger.warning(f"Node {node_id} already exists, updating")

        node = HeteroNode(
            node_id=node_id,
            node_type=node_type,
            name=name,
            attributes=attributes or {},
            features=features or {}
        )

        self.nodes[node_id] = node
        self.adjacency[node_id] = []

        if node_id not in self.node_index_by_type[node_type]:
            self.node_index_by_type[node_type].append(node_id)

        return node

    def add_edge(
        self,
        edge_id: str,
        source_id: str,
        target_id: str,
        edge_type: EdgeType,
        weight: float = 1.0,
        attributes: Optional[dict] = None
    ) -> Optional[HeteroEdge]:
        """Add an edge to the graph"""
        if source_id not in self.nodes:
            logger.error(f"Source node {source_id} not found")
            return None

        if target_id not in self.nodes:
            logger.error(f"Target node {target_id} not found")
            return None

        edge = HeteroEdge(
            edge_id=edge_id,
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type,
            weight=weight,
            attributes=attributes or {}
        )

        self.edges[edge_id] = edge
        self.adjacency[source_id].append(edge_id)

        return edge

    def get_neighbors(
        self,
        node_id: str,
        edge_type: Optional[EdgeType] = None
    ) -> list[HeteroNode]:
        """Get neighbor nodes"""
        if node_id not in self.nodes:
            return []

        neighbors = []
        for edge_id in self.adjacency.get(node_id, []):
            edge = self.edges.get(edge_id)
            if edge:
                if edge_type is None or edge.edge_type == edge_type:
                    neighbor_id = edge.target_id
                    if neighbor_id in self.nodes:
                        neighbors.append(self.nodes[neighbor_id])

        return neighbors

    def get_nodes_by_type(self, node_type: NodeType) -> list[HeteroNode]:
        """Get all nodes of a specific type"""
        return [
            self.nodes[node_id]
            for node_id in self.node_index_by_type.get(node_type, [])
            if node_id in self.nodes
        ]

    def calculate_network_metrics(self) -> dict:
        """Calculate network-level metrics"""
        total_nodes = len(self.nodes)
        total_edges = len(self.edges)

        # Node type distribution
        type_distribution = {
            nt.value: len(node_ids)
            for nt, node_ids in self.node_index_by_type.items()
        }

        # Average degree
        total_degree = sum(len(edges) for edges in self.adjacency.values())
        avg_degree = total_degree / total_nodes if total_nodes > 0 else 0

        # Edge type distribution
        edge_type_distribution = {}
        for edge in self.edges.values():
            et = edge.edge_type.value
            edge_type_distribution[et] = edge_type_distribution.get(et, 0) + 1

        return {
            "total_nodes": total_nodes,
            "total_edges": total_edges,
            "node_type_distribution": type_distribution,
            "edge_type_distribution": edge_type_distribution,
            "average_degree": round(avg_degree, 2),
            "network_density": total_edges / (total_nodes * (total_nodes - 1)) if total_nodes > 1 else 0
        }

    def find_paths(
        self,
        source_id: str,
        target_id: str,
        max_depth: int = 5
    ) -> list[list[str]]:
        """Find all paths between two nodes up to max_depth"""
        if source_id not in self.nodes or target_id not in self.nodes:
            return []

        paths = []
        visited = set()

        def dfs(current: str, target: str, path: list[str], depth: int):
            if depth > max_depth:
                return

            if current == target:
                paths.append(path.copy())
                return

            visited.add(current)

            for edge_id in self.adjacency.get(current, []):
                edge = self.edges.get(edge_id)
                if edge and edge.target_id not in visited:
                    path.append(edge.target_id)
                    dfs(edge.target_id, target, path, depth + 1)
                    path.pop()

            visited.remove(current)

        dfs(source_id, target_id, [source_id], 0)
        return paths

    def get_upstream_network(self, node_id: str, depth: int = 2) -> dict:
        """Get upstream supply chain network (suppliers)"""
        if node_id not in self.nodes:
            return {}

        upstream_nodes = []
        upstream_edges = []
        visited = set()

        def traverse(current_id: str, current_depth: int):
            if current_depth > depth or current_id in visited:
                return

            visited.add(current_id)

            # Find incoming edges (suppliers)
            for edge in self.edges.values():
                if edge.target_id == current_id:
                    source = self.nodes.get(edge.source_id)
                    if source:
                        upstream_nodes.append(source)
                        upstream_edges.append(edge)
                        traverse(edge.source_id, current_depth + 1)

        traverse(node_id, 0)

        return {
            "nodes": [n.to_dict() for n in upstream_nodes],
            "edges": [e.to_dict() for e in upstream_edges]
        }

    def get_downstream_network(self, node_id: str, depth: int = 2) -> dict:
        """Get downstream supply chain network (customers)"""
        if node_id not in self.nodes:
            return {}

        downstream_nodes = []
        downstream_edges = []
        visited = set()

        def traverse(current_id: str, current_depth: int):
            if current_depth > depth or current_id in visited:
                return

            visited.add(current_id)

            # Find outgoing edges (customers)
            for edge_id in self.adjacency.get(current_id, []):
                edge = self.edges.get(edge_id)
                if edge:
                    target = self.nodes.get(edge.target_id)
                    if target:
                        downstream_nodes.append(target)
                        downstream_edges.append(edge)
                        traverse(edge.target_id, current_depth + 1)

        traverse(node_id, 0)

        return {
            "nodes": [n.to_dict() for n in downstream_nodes],
            "edges": [e.to_dict() for e in downstream_edges]
        }

    def to_dict(self) -> dict:
        """Convert graph to dictionary"""
        return {
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [e.to_dict() for e in self.edges.values()],
            "metrics": self.calculate_network_metrics()
        }

    def save_to_json(self, filepath: str):
        """Save graph to JSON file"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load_from_json(cls, filepath: str) -> 'HeterogeneousSupplyChainGraph':
        """Load graph from JSON file"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        graph = cls()

        for node_data in data.get("nodes", []):
            graph.add_node(
                node_id=node_data["node_id"],
                node_type=NodeType(node_data["node_type"]),
                name=node_data["name"],
                attributes=node_data.get("attributes", {}),
                features=node_data.get("features", {})
            )
            # Restore risk score
            if node_data["node_id"] in graph.nodes:
                graph.nodes[node_data["node_id"]].risk_score = node_data.get("risk_score", 0.0)

        for edge_data in data.get("edges", []):
            graph.add_edge(
                edge_id=edge_data["edge_id"],
                source_id=edge_data["source_id"],
                target_id=edge_data["target_id"],
                edge_type=EdgeType(edge_data["edge_type"]),
                weight=edge_data.get("weight", 1.0),
                attributes=edge_data.get("attributes", {})
            )

        return graph


class RealDataGraphBuilder:
    """
    Builder for creating heterogeneous graph from real-world data
    """

    def __init__(self):
        self.graph = HeterogeneousSupplyChainGraph()
        self._node_counter = 0
        self._edge_counter = 0

    def _generate_node_id(self, prefix: str) -> str:
        """Generate unique node ID"""
        self._node_counter += 1
        return f"{prefix}-{self._node_counter:04d}"

    def _generate_edge_id(self) -> str:
        """Generate unique edge ID"""
        self._edge_counter += 1
        return f"EDGE-{self._edge_counter:04d}"

    def load_processing_plants(self, filepath: str) -> list[str]:
        """Load dairy processing plants from Excel file"""
        try:
            df = pd.read_excel(filepath)
        except Exception as e:
            logger.error(f"Failed to load processing plants: {e}")
            return []

        node_ids = []

        for _, row in df.iterrows():
            name = row.get('名称', '')
            if not name:
                continue

            node_id = self._generate_node_id("PROC")

            # Determine node type based on product types
            product_types = row.get('生产的乳制品品类', '')
            if '零售' in str(product_types) or '商务服务' in str(name):
                node_type = NodeType.RETAIL
            elif '生物' in str(name) or '科技' in str(name):
                node_type = NodeType.PROCESSOR
            else:
                node_type = NodeType.PROCESSOR

            features = {
                "address": str(row.get('地址', '')),
                "district": str(row.get('区', '')),
                "product_types": str(product_types),
                "enterprise_scale": str(row.get('企业规模类型', '')),
                "raw_material_source": str(row.get('原料来源', '')),
                "specific_farms": str(row.get('具体奶源牧场', '')),
                "longitude": row.get('经度'),
                "latitude": row.get('纬度')
            }

            self.graph.add_node(
                node_id=node_id,
                node_type=node_type,
                name=name,
                features=features
            )

            node_ids.append(node_id)

        logger.info(f"Loaded {len(node_ids)} processing plants")
        return node_ids

    def load_supply_chain_nodes(self, filepath: str) -> list[str]:
        """Load supply chain nodes from CSV file"""
        try:
            df = pd.read_csv(filepath)
        except Exception as e:
            logger.error(f"Failed to load supply chain nodes: {e}")
            return []

        node_ids = []

        for _, row in df.iterrows():
            # CSV uses Chinese column headers
            name = row.get('名称', '')
            if not name or pd.isna(name):
                continue

            # Determine node type from 节点类型 field
            node_type_str = str(row.get('节点类型', ''))
            name_str = str(name)

            if '原奶供应商' in node_type_str or '牧场' in name_str or '奶牛' in name_str or '养殖' in name_str:
                node_type = NodeType.FARM
                prefix = "FARM"
            elif '乳制品加工厂' in node_type_str or '乳品' in name_str or '乳业' in name_str:
                node_type = NodeType.PROCESSOR
                prefix = "PROC"
            elif '仓储' in node_type_str or '冷链' in name_str:
                node_type = NodeType.WAREHOUSE
                prefix = "WARE"
            elif '物流' in node_type_str:
                node_type = NodeType.LOGISTICS
                prefix = "LOGI"
            elif '零售' in node_type_str or '超市' in name_str or '店' in name_str:
                node_type = NodeType.RETAIL
                prefix = "RETAIL"
            else:
                # Default based on name patterns
                if '牧场' in name_str or '奶牛' in name_str:
                    node_type = NodeType.FARM
                    prefix = "FARM"
                elif '乳业' in name_str or '乳品' in name_str or '加工' in name_str:
                    node_type = NodeType.PROCESSOR
                    prefix = "PROC"
                else:
                    node_type = NodeType.WAREHOUSE
                    prefix = "NODE"

            node_id = self._generate_node_id(prefix)

            features = {
                "source_keyword": str(row.get('来源关键词', '')),
                "longitude": row.get('经度'),
                "latitude": row.get('纬度'),
                "original_node_type": node_type_str
            }

            self.graph.add_node(
                node_id=node_id,
                node_type=node_type,
                name=name,
                features=features
            )

            node_ids.append(node_id)

        logger.info(f"Loaded {len(node_ids)} supply chain nodes")
        return node_ids

    def build_graph_from_real_data(
        self,
        processing_plants_file: str,
        supply_chain_nodes_file: str
    ) -> HeterogeneousSupplyChainGraph:
        """
        Build complete graph from real-world data files
        """
        # Load processing plants
        processor_ids = self.load_processing_plants(processing_plants_file)

        # Load supply chain nodes
        node_ids = self.load_supply_chain_nodes(supply_chain_nodes_file)

        # Create relationships based on naming and data
        self._infer_relationships()

        logger.info(
            f"Graph built: {len(self.graph.nodes)} nodes, "
            f"{len(self.graph.edges)} edges"
        )

        return self.graph

    def _infer_relationships(self):
        """Infer relationships between nodes based on data"""
        processors = self.graph.get_nodes_by_type(NodeType.PROCESSOR)
        farms = self.graph.get_nodes_by_type(NodeType.FARM)
        warehouses = self.graph.get_nodes_by_type(NodeType.WAREHOUSE)
        logistics = self.graph.get_nodes_by_type(NodeType.LOGISTICS)
        retail = self.graph.get_nodes_by_type(NodeType.RETAIL)

        logger.info(
            f"Building relationships: {len(processors)} processors, "
            f"{len(farms)} farms, {len(warehouses)} warehouses, "
            f"{len(logistics)} logistics, {len(retail)} retail"
        )

        # Connect farms to processors based on name matching or proximity
        for processor in processors:
            # Check for specific farm mentions in processor features
            specific_farms = processor.features.get('specific_farms', '')
            raw_material = processor.features.get('raw_material_source', '')

            connected_farms = 0
            for farm in farms:
                farm_name = farm.name

                # Create supply relationship if farm is mentioned in processor data
                farm_mentioned = (
                    farm_name in specific_farms or
                    farm_name.split('有限公司')[0] in specific_farms or
                    farm_name.split('牧场')[0] in specific_farms
                )

                # Or if both are from same company (e.g., 光明)
                same_company = False
                if '光明' in processor.name and '光明' in farm_name:
                    same_company = True
                if '蒙牛' in processor.name and '蒙牛' in farm_name:
                    same_company = True

                if farm_mentioned or same_company:
                    self.graph.add_edge(
                        edge_id=self._generate_edge_id(),
                        source_id=farm.node_id,
                        target_id=processor.node_id,
                        edge_type=EdgeType.SUPPLY,
                        weight=1.0,
                        attributes={"evidence": "explicit_mention" if farm_mentioned else "same_company"}
                    )
                    connected_farms += 1

            # If no explicit farm connection, connect to nearest farms (up to 3)
            if connected_farms == 0 and farms:
                for farm in farms[:3]:
                    self.graph.add_edge(
                        edge_id=self._generate_edge_id(),
                        source_id=farm.node_id,
                        target_id=processor.node_id,
                        edge_type=EdgeType.SUPPLY,
                        weight=0.6,
                        attributes={"evidence": "inferred_proximity"}
                    )

        # Connect processors to logistics/warehouses
        for i, processor in enumerate(processors):
            # Connect to warehouses (create transport edges)
            target_warehouses = warehouses[:3] if warehouses else []
            for j, warehouse in enumerate(target_warehouses):
                self.graph.add_edge(
                    edge_id=self._generate_edge_id(),
                    source_id=processor.node_id,
                    target_id=warehouse.node_id,
                    edge_type=EdgeType.TRANSPORT,
                    weight=0.7,
                    attributes={"evidence": "inferred", "route_index": j}
                )

            # Connect to logistics if available
            if logistics:
                logi = logistics[i % len(logistics)]
                self.graph.add_edge(
                    edge_id=self._generate_edge_id(),
                    source_id=processor.node_id,
                    target_id=logi.node_id,
                    edge_type=EdgeType.TRANSPORT,
                    weight=0.8,
                    attributes={"evidence": "inferred", "service_type": "cold_chain"}
                )

        # Connect warehouses to retail
        for warehouse in warehouses:
            target_retail = retail[:5] if retail else []
            for r in target_retail:
                self.graph.add_edge(
                    edge_id=self._generate_edge_id(),
                    source_id=warehouse.node_id,
                    target_id=r.node_id,
                    edge_type=EdgeType.SALE,
                    weight=0.8,
                    attributes={"evidence": "inferred"}
                )

        logger.info(f"Created {len(self.graph.edges)} edges")


def create_sample_heterogeneous_graph() -> HeterogeneousSupplyChainGraph:
    """Create a sample heterogeneous graph for demonstration"""
    graph = HeterogeneousSupplyChainGraph()

    # Add nodes
    nodes = [
        ("FARM-001", NodeType.FARM, "光明牧业金山种奶牛场", {"scale": "large"}),
        ("FARM-002", NodeType.FARM, "上海本地牧场", {"scale": "medium"}),
        ("PROC-001", NodeType.PROCESSOR, "光明乳业华东中心工厂", {"scale": "large"}),
        ("PROC-002", NodeType.PROCESSOR, "上海乳品七厂", {"scale": "medium"}),
        ("LOGI-001", NodeType.LOGISTICS, "顺丰冷链上海分公司", {"scale": "large"}),
        ("WARE-001", NodeType.WAREHOUSE, "上海冷链仓储中心", {"scale": "large"}),
        ("RETAIL-001", NodeType.RETAIL, "联华超市", {"scale": "large"}),
        ("RETAIL-002", NodeType.RETAIL, "社区奶站", {"scale": "small"}),
    ]

    for node_id, node_type, name, attrs in nodes:
        graph.add_node(node_id, node_type, name, attrs)

    # Add edges
    edges = [
        ("FARM-001", "PROC-001", EdgeType.SUPPLY, 1.0),
        ("FARM-002", "PROC-001", EdgeType.SUPPLY, 0.8),
        ("PROC-001", "LOGI-001", EdgeType.TRANSPORT, 1.0),
        ("LOGI-001", "WARE-001", EdgeType.TRANSPORT, 1.0),
        ("WARE-001", "RETAIL-001", EdgeType.SALE, 0.9),
        ("WARE-001", "RETAIL-002", EdgeType.SALE, 0.7),
    ]

    edge_counter = 1
    for source, target, edge_type, weight in edges:
        graph.add_edge(
            edge_id=f"EDGE-{edge_counter:04d}",
            source_id=source,
            target_id=target,
            edge_type=edge_type,
            weight=weight
        )
        edge_counter += 1

    return graph

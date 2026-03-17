import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

export async function GET() {
  try {
    const dataPath = path.join(process.cwd(), '..', 'data', 'v2', 'heterogeneous_graph.json');
    
    if (!fs.existsSync(dataPath)) {
      return NextResponse.json({
        success: false,
        error: 'Graph data not found'
      }, { status: 404 });
    }

    const data = JSON.parse(fs.readFileSync(dataPath, 'utf-8'));
    
    // 转换格式适配 Reagraph
    const graphData = {
      nodes: data.nodes.map((n: any) => ({
        id: n.id,
        label: n.name,
        nodeType: n.type,
        riskProbability: n.risk_probability,
        riskLevel: n.risk_level,
        metadata: n,
      })),
      edges: data.links.map((e: any, i: number) => ({
        id: `edge-${i}`,
        source: e.source,
        target: e.target,
        label: e.type,
      })),
    };

    return NextResponse.json({
      success: true,
      data: graphData,
      metadata: data.metadata,
    });
  } catch (error) {
    console.error('Error loading graph data:', error);
    return NextResponse.json({
      success: false,
      error: 'Failed to load graph data'
    }, { status: 500 });
  }
}

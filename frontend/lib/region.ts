const REGION_ALIASES: Record<string, string> = {
  '上海': '上海市',
  '浦东': '上海市',
  '浦东新区': '上海市',
  '北京': '北京市',
  '天津': '天津市',
  '重庆': '重庆市',
  '内蒙古': '内蒙古自治区',
  '广西': '广西壮族自治区',
  '西藏': '西藏自治区',
  '宁夏': '宁夏回族自治区',
  '新疆': '新疆维吾尔自治区',
};

const KNOWN_REGIONS = [
  '上海市', '北京市', '天津市', '重庆市', '河北省', '山西省', '辽宁省', '吉林省', '黑龙江省',
  '江苏省', '浙江省', '安徽省', '福建省', '江西省', '山东省', '河南省', '湖北省', '湖南省',
  '广东省', '海南省', '四川省', '贵州省', '云南省', '陕西省', '甘肃省', '青海省',
  '内蒙古自治区', '广西壮族自治区', '西藏自治区', '宁夏回族自治区', '新疆维吾尔自治区',
];

export function normalizeRegion(raw?: string | null): string | null {
  if (!raw) return null;
  const text = raw.trim();
  if (!text) return null;

  for (const [alias, region] of Object.entries(REGION_ALIASES)) {
    if (text.includes(alias)) return region;
  }

  for (const region of KNOWN_REGIONS) {
    if (text.includes(region)) return region;
    const short = region.replace('省', '').replace('市', '').replace('自治区', '');
    if (short && text.includes(short)) return region;
  }

  if (text.endsWith('省') || text.endsWith('市') || text.endsWith('自治区')) {
    return text;
  }
  return null;
}

export function detectRegionFromText(text: string): string | null {
  return normalizeRegion(text);
}

export function saveDashboardAutoFilter(region: string, keywords?: string) {
  if (typeof window === 'undefined') return;
  try {
    const normalized = normalizeRegion(region);
    if (!normalized) return;
    localStorage.setItem('dashboard_auto_districts', JSON.stringify([normalized]));
    localStorage.setItem('dashboard_auto_districts_ts', String(Date.now()));
    if (keywords && keywords.trim()) {
      localStorage.setItem('dashboard_auto_keywords', keywords.trim());
    }
  } catch (e) {
    console.warn('保存大屏联动筛选失败:', e);
  }
}

export function buildDashboardUrl(keywords?: string, region?: string | null): string {
  const params = new URLSearchParams();
  if (keywords && keywords.trim()) params.set('q', keywords.trim());
  const normalized = normalizeRegion(region || undefined);
  if (normalized) params.set('district', normalized);
  const query = params.toString();
  return query ? `/dashboard?${query}` : '/dashboard';
}

'use client';

import { useEffect, useMemo, useState } from 'react';
import { modebOpinionApi } from '@/lib/api';
import type {
  ModeBMultimodalAssessData,
  ModeBMultimodalItemPayload,
  ModeBOpinionCrawlStatus,
  ModeBQingmingBriefData,
  ModeBOpinionSummary,
  ModeBOpinionTopItem,
  ModeBSymptomAssessData,
} from '@/types';

const DEFAULT_MEDIA_ROOT = '/home/yarizakurahime/Agents/winteragent/MediaCrawler/data';
const DEFAULT_CRAWLER_ROOT = '/home/yarizakurahime/Agents/winteragent/MediaCrawler';
const DEFAULT_ENTERPRISE_CSV = '/home/yarizakurahime/data/dairy_supply_chain_risk/data/merged/enterprise_master.csv';
const MAX_MM_FILE_SIZE_MB = 4;

const PLATFORM_OPTIONS = [
  { value: 'all', label: '全部平台' },
  { value: 'weibo', label: '微博' },
  { value: 'douyin', label: '抖音' },
  { value: 'xhs', label: '小红书' },
  { value: 'zhihu', label: '知乎' },
  { value: 'bili', label: 'B站' },
  { value: 'kuaishou', label: '快手' },
];

function toPct(v: string | number | undefined): string {
  const n = Number(v || 0);
  return `${(n * 100).toFixed(1)}%`;
}

function readAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ''));
    reader.onerror = () => reject(new Error(`读取文件失败: ${file.name}`));
    reader.readAsDataURL(file);
  });
}

export default function ModeBOpinionPage() {
  const [crawlerRoot, setCrawlerRoot] = useState(DEFAULT_CRAWLER_ROOT);
  const [crawlKeywords, setCrawlKeywords] = useState('乳制品安全,奶粉腹泻,牛奶变质投诉');
  const [crawlStatus, setCrawlStatus] = useState<ModeBOpinionCrawlStatus | null>(null);
  const [startingCrawl, setStartingCrawl] = useState(false);
  const [stoppingCrawl, setStoppingCrawl] = useState(false);
  const [loadingCrawlStatus, setLoadingCrawlStatus] = useState(false);

  const [mediaRoot, setMediaRoot] = useState(DEFAULT_MEDIA_ROOT);
  const [enterpriseCsv, setEnterpriseCsv] = useState(DEFAULT_ENTERPRISE_CSV);
  const [importPlatform, setImportPlatform] = useState('all');
  const [crawlPlatform, setCrawlPlatform] = useState('weibo');
  const [days, setDays] = useState(365);
  const [topN, setTopN] = useState(20);

  const [loadingSummary, setLoadingSummary] = useState(false);
  const [loadingTop, setLoadingTop] = useState(false);
  const [importing, setImporting] = useState(false);
  const [loadingAssess, setLoadingAssess] = useState(false);
  const [loadingMultimodalAssess, setLoadingMultimodalAssess] = useState(false);
  const [loadingQingmingBrief, setLoadingQingmingBrief] = useState(false);
  const [startingQingmingCrawl, setStartingQingmingCrawl] = useState(false);

  const [summary, setSummary] = useState<ModeBOpinionSummary | null>(null);
  const [qingmingBrief, setQingmingBrief] = useState<ModeBQingmingBriefData | null>(null);
  const [topItems, setTopItems] = useState<ModeBOpinionTopItem[]>([]);
  const [assessQuery, setAssessQuery] = useState('腹泻 发热 呕吐');
  const [assessResult, setAssessResult] = useState<ModeBSymptomAssessData | null>(null);
  const [multimodalResult, setMultimodalResult] = useState<ModeBMultimodalAssessData | null>(null);
  const [mmText, setMmText] = useState('清明期间有消费者反馈牛奶异味并伴随腹泻');
  const [mmProductType, setMmProductType] = useState('');
  const [mmUseQingming, setMmUseQingming] = useState(true);
  const [qingmingDays, setQingmingDays] = useState(15);
  const [qingmingPlatform, setQingmingPlatform] = useState('all');
  const [imageItems, setImageItems] = useState<ModeBMultimodalItemPayload[]>([]);
  const [videoItems, setVideoItems] = useState<ModeBMultimodalItemPayload[]>([]);
  const [audioItems, setAudioItems] = useState<ModeBMultimodalItemPayload[]>([]);
  const [imageNote, setImageNote] = useState('图片包含包装外观、色泽、结块等线索');
  const [videoNote, setVideoNote] = useState('视频包含开箱、储运、现场环境线索');
  const [audioNote, setAudioNote] = useState('语音包含消费者主诉、时间地点与症状');
  const [error, setError] = useState('');

  const refreshSummary = async () => {
    setLoadingSummary(true);
    const res = await modebOpinionApi.getSummary();
    setLoadingSummary(false);
    if (res.success && res.data) {
      setSummary(res.data);
    } else if (res.error) {
      setError(res.error);
    }
  };

  const refreshTop = async (n: number = topN) => {
    setLoadingTop(true);
    const res = await modebOpinionApi.getTop(n);
    setLoadingTop(false);
    if (res.success && res.data) {
      setTopItems(res.data);
    } else if (res.error) {
      setError(res.error);
    }
  };

  const refreshQingmingBrief = async () => {
    setLoadingQingmingBrief(true);
    const res = await modebOpinionApi.getQingmingBrief({
      platform: qingmingPlatform,
      days: qingmingDays,
      top_n: 12,
      media_root: mediaRoot.trim() || undefined,
    });
    setLoadingQingmingBrief(false);
    if (res.success && res.data) {
      setQingmingBrief(res.data);
      return;
    }
    if (res.error) {
      setError(res.error);
    }
  };

  const refreshCrawlStatus = async (silent: boolean = false) => {
    if (!silent) setLoadingCrawlStatus(true);
    const res = await modebOpinionApi.getCrawlStatus(100);
    if (!silent) setLoadingCrawlStatus(false);
    if (res.success && res.data) {
      setCrawlStatus(res.data);
    } else if (res.error) {
      setError(res.error);
    }
  };

  const startCrawler = async () => {
    if (!crawlKeywords.trim()) {
      setError('请输入抓取关键词');
      return;
    }
    setStartingCrawl(true);
    setError('');
    const res = await modebOpinionApi.startCrawl({
      mediacrawler_root: crawlerRoot.trim() || undefined,
      platform: crawlPlatform,
      crawler_type: 'search',
      login_type: 'qrcode',
      keywords: crawlKeywords.trim(),
      headless: false,
      get_comment: true,
      get_sub_comment: false,
      start_page: 1,
      max_comments_count_singlenotes: 20,
      save_data_option: 'json',
    });
    setStartingCrawl(false);
    if (res.success && res.data) {
      setCrawlStatus(res.data);
      return;
    }
    setError(res.error || '启动抓取失败');
  };

  const stopCrawler = async () => {
    setStoppingCrawl(true);
    setError('');
    const res = await modebOpinionApi.stopCrawl();
    setStoppingCrawl(false);
    if (res.success && res.data) {
      setCrawlStatus(res.data);
      return;
    }
    setError(res.error || '停止抓取失败');
  };

  const startQingmingQuickCrawler = async () => {
    setStartingQingmingCrawl(true);
    setError('');
    const res = await modebOpinionApi.qingmingQuickStart({
      mediacrawler_root: crawlerRoot.trim() || undefined,
      platform: qingmingPlatform === 'all' ? 'weibo' : qingmingPlatform,
      headless: false,
      get_comment: true,
      get_sub_comment: false,
      save_data_option: 'json',
      login_type: 'qrcode',
    });
    setStartingQingmingCrawl(false);
    if (res.success && res.data) {
      setCrawlStatus(res.data);
      return;
    }
    setError(res.error || '清明一键抓取启动失败');
  };

  const importOpinion = async () => {
    setImporting(true);
    setError('');
    const res = await modebOpinionApi.importOpinion({
      media_root: mediaRoot.trim() || undefined,
      enterprise_csv: enterpriseCsv.trim() || undefined,
      platform: importPlatform,
      days,
    });
    setImporting(false);

    if (res.success && res.data) {
      setSummary(res.data);
      await Promise.all([refreshTop(topN), refreshQingmingBrief()]);
      return;
    }
    setError(res.error || '导入失败');
  };

  const runSymptomAssess = async () => {
    if (!assessQuery.trim()) {
      setError('请输入症状/舆情描述');
      return;
    }
    setLoadingAssess(true);
    setError('');
    const res = await modebOpinionApi.symptomAssess(assessQuery.trim());
    setLoadingAssess(false);
    if (res.success && res.data) {
      setAssessResult(res.data);
    } else {
      setError(res.error || 'ModeB评估失败');
    }
  };

  const loadModalityFiles = async (
    files: FileList | null,
    modality: 'image' | 'video' | 'audio'
  ) => {
    if (!files || files.length === 0) return;
    const picked = Array.from(files).slice(0, 4);
    const maxBytes = MAX_MM_FILE_SIZE_MB * 1024 * 1024;
    const items: ModeBMultimodalItemPayload[] = [];
    for (const file of picked) {
      const item: ModeBMultimodalItemPayload = {
        name: file.name,
        mime_type: file.type || 'application/octet-stream',
      };
      if (file.size <= maxBytes) {
        try {
          item.data_url = await readAsDataUrl(file);
        } catch (e: any) {
          item.note = `文件读取失败: ${e?.message || ''}`;
        }
      } else {
        item.note = `文件超过 ${MAX_MM_FILE_SIZE_MB}MB，未内联，仅使用文件名与备注`;
      }
      items.push(item);
    }
    if (modality === 'image') setImageItems(items);
    if (modality === 'video') setVideoItems(items);
    if (modality === 'audio') setAudioItems(items);
  };

  const runMultimodalAssess = async () => {
    if (!mmText.trim() && imageItems.length === 0 && videoItems.length === 0 && audioItems.length === 0) {
      setError('请至少输入文本或上传一种模态文件');
      return;
    }
    setLoadingMultimodalAssess(true);
    setError('');
    const attachNote = (arr: ModeBMultimodalItemPayload[], note: string) =>
      arr.map((x) => ({
        ...x,
        note: [x.note, note].filter(Boolean).join(' | '),
      }));
    const res = await modebOpinionApi.multimodalAssess({
      text: mmText.trim() || undefined,
      image_items: attachNote(imageItems, imageNote),
      video_items: attachNote(videoItems, videoNote),
      audio_items: attachNote(audioItems, audioNote),
      product_type: mmProductType.trim() || undefined,
      use_qingming_context: mmUseQingming,
      qingming_days: qingmingDays,
      qingming_platform: qingmingPlatform,
    });
    setLoadingMultimodalAssess(false);
    if (res.success && res.data) {
      setMultimodalResult(res.data);
      return;
    }
    setError(res.error || '四模态评估失败');
  };

  useEffect(() => {
    const boot = async () => {
      setError('');
      await Promise.all([refreshSummary(), refreshTop(20), refreshCrawlStatus(true), refreshQingmingBrief()]);
    };
    boot();
  }, []);

  useEffect(() => {
    if (!crawlStatus || crawlStatus.status !== 'running') return;
    const timer = setInterval(() => {
      refreshCrawlStatus(true);
    }, 2500);
    return () => clearInterval(timer);
  }, [crawlStatus?.status]);

  const topRows = useMemo(() => {
    return [...topItems].sort((a, b) => Number(b.opinion_risk_index || 0) - Number(a.opinion_risk_index || 0));
  }, [topItems]);

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-sky-200 bg-gradient-to-r from-sky-50 via-cyan-50 to-blue-50 p-4">
        <h2 className="text-xl font-bold text-slate-900">MediaCrawler 舆情中心 (Mode B)</h2>
        <p className="text-sm text-slate-600 mt-1">
          专门用于接入 MediaCrawler 舆情语料，生成企业舆情风险特征，并直接作为 Mode B 输入增强。
        </p>
        <p className="text-xs text-slate-500 mt-2">
          说明：该页面负责“导入与分析”本机已抓取结果，不直接处理平台登录动作。
        </p>
      </div>

      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {error}
        </div>
      )}

      <div className="rounded-xl border border-indigo-200 bg-indigo-50/40 p-4">
        <div className="text-base font-semibold text-slate-900 mb-3">MediaCrawler 抓取任务</div>
        <div className="grid grid-cols-12 gap-3">
          <div className="col-span-12 lg:col-span-5">
            <label className="block text-slate-600 mb-1 text-sm">MediaCrawler 根目录</label>
            <input
              value={crawlerRoot}
              onChange={(e) => setCrawlerRoot(e.target.value)}
              className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
            />
          </div>
          <div className="col-span-12 lg:col-span-3">
            <label className="block text-slate-600 mb-1 text-sm">平台</label>
            <select
              value={crawlPlatform}
              onChange={(e) => setCrawlPlatform(e.target.value)}
              className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
            >
              {PLATFORM_OPTIONS.filter((x) => x.value !== 'all').map((x) => (
                <option key={x.value} value={x.value}>
                  {x.label}
                </option>
              ))}
            </select>
          </div>
          <div className="col-span-12 lg:col-span-4">
            <label className="block text-slate-600 mb-1 text-sm">关键词（逗号分隔）</label>
            <input
              value={crawlKeywords}
              onChange={(e) => setCrawlKeywords(e.target.value)}
              className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
            />
          </div>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            onClick={startCrawler}
            disabled={startingCrawl || crawlStatus?.status === 'running'}
            className="rounded bg-indigo-600 px-3 py-1.5 text-sm text-white hover:bg-indigo-500 disabled:opacity-60"
          >
            {startingCrawl ? '启动中...' : '启动抓取'}
          </button>
          <button
            onClick={stopCrawler}
            disabled={stoppingCrawl || crawlStatus?.status !== 'running'}
            className="rounded bg-rose-600 px-3 py-1.5 text-sm text-white hover:bg-rose-500 disabled:opacity-60"
          >
            {stoppingCrawl ? '停止中...' : '停止抓取'}
          </button>
          <button
            onClick={() => refreshCrawlStatus()}
            disabled={loadingCrawlStatus}
            className="rounded border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50"
          >
            {loadingCrawlStatus ? '刷新中...' : '刷新状态'}
          </button>
        </div>

        {crawlStatus && (
          <div className="mt-3 grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
            <Metric label="任务状态" value={crawlStatus.status || '-'} />
            <Metric label="PID" value={String(crawlStatus.pid || '-')} />
            <Metric label="开始时间" value={crawlStatus.started_at || '-'} />
            <Metric label="结束时间" value={crawlStatus.ended_at || '-'} />
            <Metric label="返回码" value={String(crawlStatus.return_code ?? '-')} />
            <Metric label="平台(CLI)" value={crawlStatus.platform_cli || '-'} />
            <Metric label="日志文件" value={crawlStatus.log_path || '-'} mono />
            <Metric label="命令" value={(crawlStatus.command || []).join(' ') || '-'} mono />
          </div>
        )}

        {crawlStatus?.log_tail && crawlStatus.log_tail.length > 0 && (
          <div className="mt-3">
            <div className="text-xs text-slate-600 mb-1">日志尾部（最近100行）</div>
            <pre className="max-h-56 overflow-auto rounded border border-slate-200 bg-slate-900 p-3 text-xs text-slate-100 whitespace-pre-wrap">
              {crawlStatus.log_tail.join('\n')}
            </pre>
          </div>
        )}
      </div>

      <div className="rounded-xl border border-emerald-200 bg-emerald-50/40 p-4">
        <div className="flex flex-wrap items-center gap-2 mb-3">
          <div className="text-base font-semibold text-slate-900">清明节舆情专题</div>
          <select
            value={qingmingPlatform}
            onChange={(e) => setQingmingPlatform(e.target.value)}
            className="rounded border border-slate-300 px-2 py-1.5 text-sm"
          >
            {PLATFORM_OPTIONS.map((x) => (
              <option key={x.value} value={x.value}>
                {x.label}
              </option>
            ))}
          </select>
          <input
            type="number"
            min={1}
            max={120}
            value={qingmingDays}
            onChange={(e) => setQingmingDays(Number(e.target.value) || 15)}
            className="w-24 rounded border border-slate-300 px-2 py-1.5 text-sm"
          />
          <button
            onClick={startQingmingQuickCrawler}
            disabled={startingQingmingCrawl}
            className="rounded bg-emerald-600 px-3 py-1.5 text-sm text-white hover:bg-emerald-500 disabled:opacity-60"
          >
            {startingQingmingCrawl ? '启动中...' : '一键启动清明抓取'}
          </button>
          <button
            onClick={refreshQingmingBrief}
            disabled={loadingQingmingBrief}
            className="rounded border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50"
          >
            {loadingQingmingBrief ? '刷新中...' : '刷新清明简报'}
          </button>
        </div>

        {qingmingBrief && (
          <div className="space-y-3">
            <div className="grid grid-cols-2 md:grid-cols-5 gap-2 text-sm">
              <Metric label="扫描记录" value={String(qingmingBrief.scanned_records)} />
              <Metric label="清明命中" value={String(qingmingBrief.qingming_hits)} />
              <Metric label="乳制品相关" value={String(qingmingBrief.qingming_dairy_hits)} />
              <Metric label="平台" value={qingmingBrief.platform} />
              <Metric label="窗口天数" value={String(qingmingBrief.days_window)} />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="rounded border border-slate-200 bg-white p-3">
                <div className="text-xs text-slate-500 mb-2">清明关键词热度</div>
                <div className="flex flex-wrap gap-2">
                  {(qingmingBrief.top_qingming_keywords || []).map(([k, v]) => (
                    <span key={k} className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs text-emerald-700">
                      {k} {v}
                    </span>
                  ))}
                </div>
              </div>
              <div className="rounded border border-slate-200 bg-white p-3">
                <div className="text-xs text-slate-500 mb-2">风险关键词热度</div>
                <div className="flex flex-wrap gap-2">
                  {(qingmingBrief.top_risk_keywords || []).map(([k, v]) => (
                    <span key={k} className="rounded-full bg-rose-100 px-2 py-0.5 text-xs text-rose-700">
                      {k} {v}
                    </span>
                  ))}
                </div>
              </div>
            </div>
            <div className="overflow-auto rounded border border-slate-200 bg-white">
              <table className="min-w-full text-sm">
                <thead className="bg-slate-50 text-slate-600">
                  <tr>
                    <th className="text-left px-2 py-2">平台</th>
                    <th className="text-left px-2 py-2">时间</th>
                    <th className="text-left px-2 py-2">文本片段</th>
                    <th className="text-left px-2 py-2">互动量</th>
                  </tr>
                </thead>
                <tbody>
                  {(qingmingBrief.samples || []).map((x, idx) => (
                    <tr key={`${x.platform}-${idx}`} className="border-t border-slate-100">
                      <td className="px-2 py-2">{x.platform}</td>
                      <td className="px-2 py-2">{x.create_time || '-'}</td>
                      <td className="px-2 py-2">{x.text}</td>
                      <td className="px-2 py-2">{x.engagement}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-12 lg:col-span-5 rounded-xl border border-slate-200 bg-white p-4">
          <div className="text-base font-semibold text-slate-900 mb-3">导入配置</div>
          <div className="space-y-3 text-sm">
            <div>
              <label className="block text-slate-600 mb-1">MediaCrawler data 根目录</label>
              <input
                value={mediaRoot}
                onChange={(e) => setMediaRoot(e.target.value)}
                className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
              />
            </div>
            <div>
              <label className="block text-slate-600 mb-1">企业主档 CSV</label>
              <input
                value={enterpriseCsv}
                onChange={(e) => setEnterpriseCsv(e.target.value)}
                className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-slate-600 mb-1">平台</label>
                <select
                  value={importPlatform}
                  onChange={(e) => setImportPlatform(e.target.value)}
                  className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
                >
                  {PLATFORM_OPTIONS.map((x) => (
                    <option key={x.value} value={x.value}>
                      {x.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-slate-600 mb-1">统计窗口(天)</label>
                <input
                  type="number"
                  min={1}
                  max={3650}
                  value={days}
                  onChange={(e) => setDays(Number(e.target.value) || 30)}
                  className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
                />
              </div>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            <button
              onClick={importOpinion}
              disabled={importing}
              className="rounded bg-cyan-600 px-3 py-1.5 text-sm text-white hover:bg-cyan-500 disabled:opacity-60"
            >
              {importing ? '导入中...' : '抓取结果导入 ModeB'}
            </button>
            <button
              onClick={refreshSummary}
              disabled={loadingSummary}
              className="rounded border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50"
            >
              刷新摘要
            </button>
          </div>
        </div>

        <div className="col-span-12 lg:col-span-7 rounded-xl border border-slate-200 bg-white p-4">
          <div className="text-base font-semibold text-slate-900 mb-3">导入摘要</div>
          {!summary && loadingSummary && <div className="text-sm text-slate-500">加载中...</div>}
          {!summary && !loadingSummary && <div className="text-sm text-slate-500">暂无摘要，请先导入。</div>}
          {summary && (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
              <Metric label="扫描记录" value={String(summary.scanned_records)} />
              <Metric label="匹配记录" value={String(summary.matched_records)} />
              <Metric label="匹配企业" value={String(summary.matched_enterprises)} />
              <Metric label="特征企业数" value={String(summary.opinion_feature_loaded_count || 0)} />
              <Metric label="平台" value={(summary.platforms_scanned || [summary.platform]).join(', ')} />
              <Metric label="窗口天数" value={String(summary.days_window)} />
              <Metric label="特征文件" value={summary.outputs?.feature_csv || '-'} mono />
              <Metric label="摘要文件" value={summary.outputs?.summary_json || '-'} mono />
              <Metric label="原始匹配文件" value={summary.outputs?.raw_jsonl || '-'} mono />
            </div>
          )}
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <div className="flex flex-wrap items-center gap-2 mb-3">
          <div className="text-base font-semibold text-slate-900">舆情风险 Top 企业</div>
          <input
            type="number"
            min={1}
            max={200}
            value={topN}
            onChange={(e) => setTopN(Number(e.target.value) || 20)}
            className="w-20 rounded border border-slate-300 px-2 py-1 text-sm"
          />
          <button
            onClick={() => refreshTop(topN)}
            disabled={loadingTop}
            className="rounded border border-slate-300 bg-white px-3 py-1 text-sm text-slate-700 hover:bg-slate-50"
          >
            {loadingTop ? '加载中...' : '刷新Top'}
          </button>
        </div>

        <div className="overflow-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                <th className="text-left px-2 py-2">#</th>
                <th className="text-left px-2 py-2">企业</th>
                <th className="text-left px-2 py-2">舆情风险指数</th>
                <th className="text-left px-2 py-2">提及数</th>
                <th className="text-left px-2 py-2">负向比例</th>
                <th className="text-left px-2 py-2">风险关键词</th>
              </tr>
            </thead>
            <tbody>
              {topRows.map((x, idx) => {
                const score = Number(x.opinion_risk_index || 0);
                return (
                  <tr key={`${x.enterprise_id}-${idx}`} className="border-t border-slate-100">
                    <td className="px-2 py-2 text-slate-500">{idx + 1}</td>
                    <td className="px-2 py-2">{x.enterprise_name}</td>
                    <td className="px-2 py-2 min-w-[180px]">
                      <div className="flex items-center gap-2">
                        <div className="h-2 w-28 rounded bg-slate-100 overflow-hidden">
                          <div className="h-full bg-gradient-to-r from-amber-400 to-rose-500" style={{ width: `${Math.min(100, score * 100)}%` }} />
                        </div>
                        <span className="text-xs text-slate-700">{toPct(score)}</span>
                      </div>
                    </td>
                    <td className="px-2 py-2">{x.mention_count_30d}</td>
                    <td className="px-2 py-2">{toPct(x.negative_ratio_30d)}</td>
                    <td className="px-2 py-2">{x.risk_keyword_hits_30d}</td>
                  </tr>
                );
              })}
              {topRows.length === 0 && (
                <tr>
                  <td className="px-2 py-6 text-slate-500" colSpan={6}>
                    暂无数据，请先执行“抓取结果导入 ModeB”。
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="rounded-xl border border-violet-200 bg-violet-50/30 p-4">
        <div className="text-base font-semibold text-slate-900 mb-3">Mode B 四模态融合评估（文本/图片/视频/语音）</div>
        <div className="grid grid-cols-12 gap-3 text-sm">
          <div className="col-span-12">
            <label className="block text-slate-600 mb-1">文本描述</label>
            <textarea
              value={mmText}
              onChange={(e) => setMmText(e.target.value)}
              rows={3}
              className="w-full rounded border border-slate-300 px-2 py-1.5"
              placeholder="输入事件描述、症状与场景线索"
            />
          </div>
          <div className="col-span-12 md:col-span-3">
            <label className="block text-slate-600 mb-1">产品类型（可选）</label>
            <input
              value={mmProductType}
              onChange={(e) => setMmProductType(e.target.value)}
              className="w-full rounded border border-slate-300 px-2 py-1.5"
              placeholder="如：巴氏杀菌乳"
            />
          </div>
          <div className="col-span-6 md:col-span-2">
            <label className="block text-slate-600 mb-1">清明窗口(天)</label>
            <input
              type="number"
              min={1}
              max={120}
              value={qingmingDays}
              onChange={(e) => setQingmingDays(Number(e.target.value) || 15)}
              className="w-full rounded border border-slate-300 px-2 py-1.5"
            />
          </div>
          <div className="col-span-6 md:col-span-2">
            <label className="block text-slate-600 mb-1">清明平台</label>
            <select
              value={qingmingPlatform}
              onChange={(e) => setQingmingPlatform(e.target.value)}
              className="w-full rounded border border-slate-300 px-2 py-1.5"
            >
              {PLATFORM_OPTIONS.map((x) => (
                <option key={x.value} value={x.value}>
                  {x.label}
                </option>
              ))}
            </select>
          </div>
          <div className="col-span-12 md:col-span-5 flex items-end">
            <label className="inline-flex items-center gap-2 text-slate-700">
              <input
                type="checkbox"
                checked={mmUseQingming}
                onChange={(e) => setMmUseQingming(e.target.checked)}
              />
              融合清明舆情上下文
            </label>
          </div>

          <div className="col-span-12 md:col-span-4">
            <label className="block text-slate-600 mb-1">图片文件（最多4个，单个≤{MAX_MM_FILE_SIZE_MB}MB）</label>
            <input
              type="file"
              accept="image/*"
              multiple
              onChange={(e) => loadModalityFiles(e.target.files, 'image')}
              className="w-full rounded border border-slate-300 px-2 py-1.5 bg-white"
            />
            <input
              value={imageNote}
              onChange={(e) => setImageNote(e.target.value)}
              className="mt-2 w-full rounded border border-slate-300 px-2 py-1.5"
              placeholder="图片备注"
            />
            <div className="mt-1 text-xs text-slate-500">已选 {imageItems.length} 个</div>
          </div>

          <div className="col-span-12 md:col-span-4">
            <label className="block text-slate-600 mb-1">视频文件（最多4个，单个≤{MAX_MM_FILE_SIZE_MB}MB）</label>
            <input
              type="file"
              accept="video/*"
              multiple
              onChange={(e) => loadModalityFiles(e.target.files, 'video')}
              className="w-full rounded border border-slate-300 px-2 py-1.5 bg-white"
            />
            <input
              value={videoNote}
              onChange={(e) => setVideoNote(e.target.value)}
              className="mt-2 w-full rounded border border-slate-300 px-2 py-1.5"
              placeholder="视频备注"
            />
            <div className="mt-1 text-xs text-slate-500">已选 {videoItems.length} 个</div>
          </div>

          <div className="col-span-12 md:col-span-4">
            <label className="block text-slate-600 mb-1">语音文件（最多4个，单个≤{MAX_MM_FILE_SIZE_MB}MB）</label>
            <input
              type="file"
              accept="audio/*"
              multiple
              onChange={(e) => loadModalityFiles(e.target.files, 'audio')}
              className="w-full rounded border border-slate-300 px-2 py-1.5 bg-white"
            />
            <input
              value={audioNote}
              onChange={(e) => setAudioNote(e.target.value)}
              className="mt-2 w-full rounded border border-slate-300 px-2 py-1.5"
              placeholder="语音备注"
            />
            <div className="mt-1 text-xs text-slate-500">已选 {audioItems.length} 个</div>
          </div>
        </div>

        <div className="mt-3">
          <button
            onClick={runMultimodalAssess}
            disabled={loadingMultimodalAssess}
            className="rounded bg-violet-600 px-3 py-1.5 text-sm text-white hover:bg-violet-500 disabled:opacity-60"
          >
            {loadingMultimodalAssess ? '融合评估中...' : '执行四模态融合评估'}
          </button>
        </div>

        {multimodalResult && (
          <div className="mt-4 space-y-3">
            <div className="rounded border border-slate-200 bg-white p-3 text-sm text-slate-700">
              <div>融合Query: {multimodalResult.fused_query}</div>
              <div className="mt-1">
                风险等级: <b>{multimodalResult.risk_level}</b>，置信度: <b>{(Number(multimodalResult.confidence || 0) * 100).toFixed(1)}%</b>
              </div>
              <div className="mt-1 text-xs text-slate-500">
                模态计数: 文本 {multimodalResult.modalities?.text_length || 0} 字符，
                图片 {multimodalResult.modalities?.image_count || 0}，
                视频 {multimodalResult.modalities?.video_count || 0}，
                语音 {multimodalResult.modalities?.audio_count || 0}
              </div>
            </div>
            <div className="overflow-auto rounded border border-slate-200 bg-white">
              <table className="min-w-full text-sm">
                <thead className="bg-slate-50 text-slate-600">
                  <tr>
                    <th className="text-left px-2 py-2">企业</th>
                    <th className="text-left px-2 py-2">基础风险分</th>
                    <th className="text-left px-2 py-2">舆情指数</th>
                    <th className="text-left px-2 py-2">综合分</th>
                    <th className="text-left px-2 py-2">提及数</th>
                  </tr>
                </thead>
                <tbody>
                  {(multimodalResult.linked_enterprises || []).map((x) => (
                    <tr key={x.enterprise_id} className="border-t border-slate-100">
                      <td className="px-2 py-2">{x.enterprise_name}</td>
                      <td className="px-2 py-2">{Number(x.risk_score || 0).toFixed(2)}</td>
                      <td className="px-2 py-2">{toPct(x.opinion_risk_index || 0)}</td>
                      <td className="px-2 py-2 font-semibold text-violet-700">{Number(x.combined_risk_score || x.risk_score || 0).toFixed(2)}</td>
                      <td className="px-2 py-2">{x.opinion_mentions_30d || 0}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <div className="text-base font-semibold text-slate-900 mb-3">Mode B 联动测试（含舆情增强）</div>
        <div className="flex flex-wrap gap-2 items-center">
          <input
            value={assessQuery}
            onChange={(e) => setAssessQuery(e.target.value)}
            className="flex-1 min-w-[280px] rounded border border-slate-300 px-2 py-1.5 text-sm"
            placeholder="输入症状或舆情描述，例如：奶粉 腹泻 投诉"
          />
          <button
            onClick={runSymptomAssess}
            disabled={loadingAssess}
            className="rounded bg-indigo-600 px-3 py-1.5 text-sm text-white hover:bg-indigo-500 disabled:opacity-60"
          >
            {loadingAssess ? '评估中...' : '执行 ModeB 评估'}
          </button>
        </div>

        {assessResult && (
          <div className="mt-4 space-y-3">
            <div className="text-sm text-slate-600">
              风险等级: <b>{assessResult.risk_level}</b>，置信度: <b>{(Number(assessResult.confidence || 0) * 100).toFixed(1)}%</b>，
              舆情增强: <b>{assessResult.opinion_enabled ? '已启用' : '未启用'}</b>，
              已加载企业特征: <b>{assessResult.opinion_feature_loaded_count || 0}</b>
            </div>
            <div className="overflow-auto">
              <table className="min-w-full text-sm">
                <thead className="bg-slate-50 text-slate-600">
                  <tr>
                    <th className="text-left px-2 py-2">企业</th>
                    <th className="text-left px-2 py-2">基础风险分</th>
                    <th className="text-left px-2 py-2">舆情指数</th>
                    <th className="text-left px-2 py-2">综合分</th>
                    <th className="text-left px-2 py-2">提及数</th>
                  </tr>
                </thead>
                <tbody>
                  {(assessResult.linked_enterprises || []).map((x) => (
                    <tr key={x.enterprise_id} className="border-t border-slate-100">
                      <td className="px-2 py-2">{x.enterprise_name}</td>
                      <td className="px-2 py-2">{Number(x.risk_score || 0).toFixed(2)}</td>
                      <td className="px-2 py-2">{toPct(x.opinion_risk_index || 0)}</td>
                      <td className="px-2 py-2 font-semibold text-indigo-700">{Number(x.combined_risk_score || x.risk_score || 0).toFixed(2)}</td>
                      <td className="px-2 py-2">{x.opinion_mentions_30d || 0}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Metric({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="rounded border border-slate-200 bg-slate-50 p-2">
      <div className="text-xs text-slate-500 mb-1">{label}</div>
      <div className={`text-sm text-slate-900 break-all ${mono ? 'font-mono' : 'font-semibold'}`}>{value || '-'}</div>
    </div>
  );
}

import { test } from '@playwright/test';

test('capture modela v2 views', async ({ page }) => {
  await page.goto('http://127.0.0.1:3001/modela-v2', { waitUntil: 'networkidle' });
  await page.getByRole('button', { name: '刷新图谱' }).click();
  await page.waitForTimeout(12000);
  await page.screenshot({ path: '/home/yarizakurahime/data/dairy_supply_chain_risk/reports/visualization_20260331/screenshots/modela_v2_default.png', fullPage: true });

  await page.getByText('仅看Top5%节点及其关联风险边').click();
  await page.waitForTimeout(6000);
  await page.screenshot({ path: '/home/yarizakurahime/data/dairy_supply_chain_risk/reports/visualization_20260331/screenshots/modela_v2_top5_with_incident_edges.png', fullPage: true });
});

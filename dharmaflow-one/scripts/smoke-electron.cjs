const { _electron: electron } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');

(async () => {
  const root = path.resolve(__dirname, '..');
  const scratch = fs.mkdtempSync(path.join(root, 'backend', 'temp', 'electron-smoke-'));
  const app = await electron.launch({
    args: [root],
    env: { ...process.env, NODE_ENV: 'production', DHARMAFLOW_MOCK_AI: '1',
      DHARMAFLOW_DATABASE_URL: `sqlite+aiosqlite:///${path.join(scratch, 'test.db').replaceAll('\\', '/')}`,
      MEDIA_DIR: path.join(scratch, 'media') },
  });
  try {
    const page = await app.firstWindow();
    await page.getByTestId('topic-input').waitFor({ timeout: 60000 });
    await page.getByText('Turbo Mode', { exact: true }).click();
    await page.getByTestId('topic-input').fill('A fox leaps across a woodland stream');
    await page.getByTestId('start-btn').click();
    await page.getByText('Final Video & YouTube Metadata', { exact: true }).waitFor({ timeout: 120000 });
    await page.getByTestId('quality-report').waitFor({ timeout: 15000 });
    await page.waitForFunction(() => document.querySelector('video')?.readyState >= 1);
    await page.locator('video').evaluate(async video => { video.muted = true; await video.play(); });
    await page.waitForFunction(() => {
      const video = document.querySelector('video');
      return video?.readyState >= 2 && video.currentTime > 0.3;
    }, { timeout: 30000 });
    await page.locator('video').evaluate(video => video.pause());
    const src = await page.locator('video').getAttribute('src');
    const id = new URL(src).pathname.split('/')[2];
    const quality = await (await fetch(`http://127.0.0.1:8000/api/projects/${id}/quality`)).json();
    if (!quality.passed || !quality.synthetic_test) throw new Error('Expected verified synthetic export');
    fs.mkdirSync(path.join(root, 'test-results'), { recursive: true });
    fs.writeFileSync(path.join(root, 'test-results', 'electron-quality.json'), JSON.stringify(quality, null, 2));
    await page.screenshot({ path: path.join(root, 'test-results', 'electron-workflow.png'), fullPage: true });
    console.log(`Desktop workflow passed: ${quality.max_offset_ms} ms timing offset; ${quality.scenes.length} scenes; playable video.`);
  } finally {
    await app.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });

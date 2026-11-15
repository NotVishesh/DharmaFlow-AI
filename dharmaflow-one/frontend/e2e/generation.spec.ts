import { test, expect } from '@playwright/test';

test('setup honestly shows missing video weights', async ({ page }) => {
  await page.route('**/api/system/status', route => route.fulfill({ json: {
    hardware_tier:'TIER_MID', vram_gb:6, ram_gb:16, models_ready:false, models:[],
    generation:{ready:false,mock:false,provider:'local',issues:['Download and verify the local Wan video model.'],
      download:{status:'idle',message:''}}
  }}));
  await page.route('**/api/auth/youtube/channels', route => route.fulfill({json:[]}));
  await page.goto('/');
  await expect(page.getByText('Video engine: local')).toBeVisible();
  await expect(page.getByRole('button',{name:'Download Local Video Model'})).toBeVisible();
  await expect(page.getByTestId('start-btn')).not.toBeVisible();
  await page.screenshot({path:'test-results/setup.png',fullPage:true});
});

test('test mode is visibly labeled', async ({page}) => {
  await page.route('**/api/system/status', route => route.fulfill({json:{
    hardware_tier:'TIER_MID',vram_gb:6,ram_gb:16,models_ready:true,models:[],
    generation:{ready:true,mock:true,provider:'test',issues:[]}
  }}));
  await page.route('**/api/auth/youtube/channels', route=>route.fulfill({json:[]}));
  await page.goto('/');
  await expect(page.getByText(/Test mode — synthetic test footage/)).toBeVisible();
});

test('one-minute default and duration choice reach project request', async ({page}) => {
  await page.route('**/api/system/status', route => route.fulfill({json:{
    hardware_tier:'TIER_MID',vram_gb:6,ram_gb:16,models_ready:true,models:[],
    generation:{ready:true,mock:false,provider:'local',issues:[]}
  }}));
  await page.route('**/api/auth/youtube/channels', route => route.fulfill({json:[]}));
  let submitted: any;
  await page.route('**/api/projects', async route => {
    submitted = route.request().postDataJSON();
    await route.fulfill({status:503,json:{detail:'Stop before generation in UI test'}});
  });
  await page.goto('/');
  await expect(page.getByLabel('Video length')).toHaveValue('60');
  await page.getByTestId('topic-input').fill('A fox follows a butterfly home.');
  await page.getByLabel('Video length').selectOption('30');
  await page.getByLabel('Character speaks (lip-sync)').check();
  await page.getByTestId('start-btn').click();
  await expect.poll(() => submitted?.target_duration_seconds).toBe(30);
  expect(submitted.lip_sync).toBe(true);
});

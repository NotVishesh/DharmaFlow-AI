import { test, expect } from '@playwright/test';

test.describe('DharmaFlow One E2E Workflows', () => {
  test('switching between multi-channel options in channel-select', async ({ page }) => {
    let currentSelected = 'channel_A';

    await page.route('**/api/system/status', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          hardware_tier: 'TIER_MID',
          vram_gb: 8.0,
          ram_gb: 16.0,
          models_ready: true,
          models: [],
        }),
      });
    });

    await page.route('**/api/auth/youtube/channels', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            channel_id: 'channel_A',
            account_email: 'user@gmail.com',
            title: 'Primary Spiritual Channel',
            thumbnail_url: '',
            subscriber_count: 12500,
            is_selected: currentSelected === 'channel_A',
          },
          {
            channel_id: 'channel_B',
            account_email: 'user@gmail.com',
            title: 'Secondary Philosophy Channel',
            thumbnail_url: '',
            subscriber_count: 3400,
            is_selected: currentSelected === 'channel_B',
          },
        ]),
      });
    });

    await page.route('**/api/auth/youtube/select-channel', async (route) => {
      const data = JSON.parse(route.request().postData() || '{}');
      currentSelected = data.channel_id;
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'selected' }) });
    });

    await page.goto('/');

    const select = page.locator('[data-testid="channel-select"]');
    await expect(select).toBeVisible();
    await expect(select).toHaveValue('channel_A');

    await select.selectOption('channel_B');
    await expect(select).toHaveValue('channel_B');
  });

  test('complete Review Mode user journey', async ({ page }) => {
    let projectState: any = null;

    await page.route('**/api/system/status', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          hardware_tier: 'TIER_MID',
          vram_gb: 8.0,
          ram_gb: 16.0,
          models_ready: true,
          models: [],
        }),
      });
    });

    await page.route('**/api/auth/youtube/channels', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            channel_id: 'channel_main',
            account_email: 'creator@gmail.com',
            title: 'Dharma Channel',
            thumbnail_url: '',
            subscriber_count: 50000,
            is_selected: true,
          },
        ]),
      });
    });

    await page.route('**/api/projects', async (route) => {
      const req = JSON.parse(route.request().postData() || '{}');
      projectState = {
        id: 'proj_review_001',
        topic: req.topic,
        style: req.style,
        mode: 'REVIEW',
        status: 'WAIT_SCRIPT_REVIEW',
        raw_script: 'Initial draft script: The essence of mindful living.',
        yt_title: 'Draft Title',
        yt_description: 'Draft Description',
        yt_tags: ['dharma', 'mindfulness'],
        yt_privacy: 'private',
        target_channel_id: 'channel_main',
        final_video_path: null,
        youtube_video_id: null,
        error_message: null,
        created_at: new Date().toISOString(),
        scenes: [],
      };
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(projectState) });
    });

    await page.route('**/api/projects/proj_review_001', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(projectState) });
    });

    await page.route('**/api/projects/proj_review_001/approve-script', async (route) => {
      const req = JSON.parse(route.request().postData() || '{}');
      projectState.raw_script = req.raw_script;
      projectState.status = 'WAIT_SCENE_REVIEW';
      projectState.scenes = [
        {
          id: 'sc_0',
          project_id: 'proj_review_001',
          scene_index: 0,
          dialogue_or_lyrics: 'Scene 1: Introduction to awareness.',
          visual_prompt: 'A serene Himalayan sunrise.',
          audio_path: null,
          duration_ms: null,
          visual_path: null,
          muxed_scene_path: null,
        },
        {
          id: 'sc_1',
          project_id: 'proj_review_001',
          scene_index: 1,
          dialogue_or_lyrics: 'Scene 2: Overcoming daily turbulence.',
          visual_prompt: 'Flowing mountain river in clear focus.',
          audio_path: null,
          duration_ms: null,
          visual_path: null,
          muxed_scene_path: null,
        },
      ];
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(projectState) });
    });

    await page.route('**/api/projects/proj_review_001/approve-scenes', async (route) => {
      projectState.status = 'WAIT_VIDEO_REVIEW';
      projectState.final_video_path = '/media/proj_review_001/final_video.mp4';
      projectState.yt_title = 'Generated YouTube Title';
      projectState.yt_description = 'Generated YouTube Description';
      projectState.yt_tags = ['mindfulness', 'focus'];
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(projectState) });
    });

    await page.route('**/api/projects/proj_review_001/metadata', async (route) => {
      const patch = JSON.parse(route.request().postData() || '{}');
      if (patch.yt_title) projectState.yt_title = patch.yt_title;
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(projectState) });
    });

    await page.route('**/api/projects/proj_review_001/upload', async (route) => {
      projectState.status = 'COMPLETED';
      projectState.youtube_video_id = 'yt_vid_success_777';
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'upload_started' }) });
    });

    await page.goto('/');

    // 1. Enter topic and start
    const topicInput = page.locator('[data-testid="topic-input"]');
    await expect(topicInput).toBeVisible();
    await topicInput.fill('The Art of Mindful Action');

    const startBtn = page.locator('[data-testid="start-btn"]');
    await startBtn.click();

    // 2. Edit script
    const scriptEditor = page.locator('[data-testid="script-editor"]');
    await expect(scriptEditor).toBeVisible();
    await scriptEditor.fill('Polished script with thoughtful insights.');

    const approveScriptBtn = page.locator('[data-testid="approve-script-btn"]');
    await approveScriptBtn.click();

    // 3. Edit scene 0 dialogue and visual prompt
    const scene0Dialogue = page.locator('[data-testid="scene-dialogue-0"]');
    await expect(scene0Dialogue).toBeVisible();
    await scene0Dialogue.fill('Scene 1: Spoken wisdom for mindful clarity.');

    const scene0Visual = page.locator('[data-testid="scene-visual-0"]');
    await scene0Visual.fill('Cinematic golden hour over still waters.');

    const approveScenesBtn = page.locator('[data-testid="approve-scenes-btn"]');
    await approveScenesBtn.click();

    // 4. Video preview and edit title
    const ytTitleInput = page.locator('[data-testid="yt-title-input"]');
    await expect(ytTitleInput).toBeVisible();
    await ytTitleInput.fill('Custom Edited Masterpiece Title');

    // 5. Click Upload and verify Completed state
    const uploadBtn = page.locator('[data-testid="upload-btn"]');
    await uploadBtn.click();

    await expect(page.locator('text=Successfully Published!')).toBeVisible();
    await expect(page.locator('text=yt_vid_success_777')).toBeVisible();
  });

  test('Turbo Mode user journey', async ({ page }) => {
    let turboProject: any = null;

    await page.route('**/api/system/status', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          hardware_tier: 'TIER_MID',
          vram_gb: 8.0,
          ram_gb: 16.0,
          models_ready: true,
          models: [],
        }),
      });
    });

    await page.route('**/api/auth/youtube/channels', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            channel_id: 'channel_turbo',
            account_email: 'turbo@gmail.com',
            title: 'Turbo Channel',
            thumbnail_url: '',
            subscriber_count: 100000,
            is_selected: true,
          },
        ]),
      });
    });

    await page.route('**/api/projects', async (route) => {
      const req = JSON.parse(route.request().postData() || '{}');
      turboProject = {
        id: 'proj_turbo_999',
        topic: req.topic,
        style: req.style,
        mode: 'TURBO',
        status: 'WAIT_VIDEO_REVIEW',
        raw_script: 'Auto generated script',
        yt_title: 'Autonomous Turbo Video Title',
        yt_description: 'Autonomous description',
        yt_tags: ['turbo', 'ai'],
        yt_privacy: 'private',
        target_channel_id: 'channel_turbo',
        final_video_path: '/media/proj_turbo_999/final_video.mp4',
        youtube_video_id: null,
        error_message: null,
        created_at: new Date().toISOString(),
        scenes: [],
      };
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(turboProject) });
    });

    await page.route('**/api/projects/proj_turbo_999', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(turboProject) });
    });

    await page.goto('/');

    // 1. Toggle Turbo Mode
    const modeToggle = page.locator('[data-testid="mode-toggle"]');
    await expect(modeToggle).toBeVisible();
    await modeToggle.locator('button:has-text("Turbo Mode")').click();

    // 2. Enter topic
    const topicInput = page.locator('[data-testid="topic-input"]');
    await topicInput.fill('The Infinite Future of AI');

    // 3. Start generation
    const startBtn = page.locator('[data-testid="start-btn"]');
    await startBtn.click();

    // 4. Assert direct progression to Step 4 publish screen without stopping for script or scene review
    const ytTitleInput = page.locator('[data-testid="yt-title-input"]');
    await expect(ytTitleInput).toBeVisible();
    await expect(ytTitleInput).toHaveValue('Autonomous Turbo Video Title');
    await expect(page.locator('[data-testid="upload-btn"]')).toBeVisible();
  });
});

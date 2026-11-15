export type HardwareTier = 'TIER_LOW' | 'TIER_MID' | 'TIER_HIGH';
export type ExecutionMode = 'REVIEW' | 'TURBO';
export type ProjectStatus =
  | 'IDLE'
  | 'GENERATING_SCRIPT'
  | 'WAIT_SCRIPT_REVIEW'
  | 'GENERATING_SCENES'
  | 'WAIT_SCENE_REVIEW'
  | 'GENERATING_AUDIO'
  | 'GENERATING_VISUALS'
  | 'MUXING_VIDEO'
  | 'WAIT_VIDEO_REVIEW'
  | 'UPLOADING'
  | 'COMPLETED'
  | 'FAILED';

export interface ModelArtifact {
  id: string;
  role: string;
  tier: HardwareTier;
  url: string;
  filename: string;
  sha256: string;
  size_bytes: number;
  downloaded_bytes: number;
  is_ready: boolean;
}

export interface GenerationStatus {
  ready: boolean;
  mock: boolean;
  provider: string;
  issues: string[];
  local_weights_ready?: boolean;
  api_key_configured?: boolean;
  native_resolution?: string;
  export_resolution?: string;
  download?: { status: string; message: string };
}

export interface HardwareProfileResponse {
  generation?: GenerationStatus;
  hardware_tier: HardwareTier;
  vram_gb: number;
  ram_gb: number;
  models_ready: boolean;
  models: ModelArtifact[];
}

export interface YouTubeChannel {
  channel_id: string;
  account_email: string;
  title: string;
  thumbnail_url: string;
  subscriber_count: number;
  is_selected: boolean;
}

export interface Scene {
  id: string;
  project_id: string;
  scene_index: number;
  dialogue_or_lyrics: string;
  visual_prompt: string;
  audio_path: string | null;
  duration_ms: number | null;
  visual_path: string | null;
  muxed_scene_path: string | null;
}

export interface Project {
  id: string;
  topic: string;
  target_duration_seconds?: number;
  lip_sync?: boolean;
  style: string;
  mode: ExecutionMode;
  status: ProjectStatus;
  raw_script: string | null;
  yt_title: string | null;
  yt_description: string | null;
  yt_tags: string[] | null;
  yt_privacy: string;
  target_channel_id: string | null;
  final_video_path: string | null;
  youtube_video_id: string | null;
  error_message: string | null;
  created_at: string;
  scenes: Scene[];
}

export interface CreateProjectRequest {
  topic: string;
  target_duration_seconds?: number;
  lip_sync?: boolean;
  style: string;
  mode: ExecutionMode;
}

export interface SceneUpdateRequest {
  id: string;
  dialogue_or_lyrics: string;
  visual_prompt: string;
}

import { create } from 'zustand';
import {
  HardwareProfileResponse,
  YouTubeChannel,
  Project,
  ExecutionMode,
  SceneUpdateRequest,
} from '../api/types';
import { api, wsManager } from '../api/client';

interface AppState {
  systemStatus: HardwareProfileResponse | null;
  channels: YouTubeChannel[];
  selectedChannelId: string | null;
  activeProject: Project | null;
  selectedMode: ExecutionMode;
  uploadProgress: number;
  modelDownloadProgress: Record<string, number>;
  isLoading: boolean;
  error: string | null;
  generationMessage: string;

  // Actions
  fetchSystemStatus: () => Promise<void>;
  triggerModelDownload: () => Promise<void>;
  loginYouTube: () => Promise<void>;
  fetchChannels: () => Promise<void>;
  selectChannel: (channelId: string) => Promise<void>;
  setMode: (mode: ExecutionMode) => void;
  createProject: (topic: string, style: string, targetDuration?: number, lipSync?: boolean) => Promise<void>;
  fetchActiveProject: (id: string) => Promise<void>;
  approveScript: (raw_script: string) => Promise<void>;
  approveScenes: (scenes: SceneUpdateRequest[]) => Promise<void>;
  updateMetadata: (meta: {
    yt_title?: string;
    yt_description?: string;
    yt_tags?: string[];
    yt_privacy?: string;
    target_channel_id?: string;
  }) => Promise<void>;
  uploadToYouTube: () => Promise<void>;
  initWebSocket: () => void;
}

export const useAppStore = create<AppState>((set, get) => ({
  systemStatus: null,
  channels: [],
  selectedChannelId: null,
  activeProject: null,
  selectedMode: 'REVIEW',
  uploadProgress: 0,
  modelDownloadProgress: {},
  isLoading: false,
  error: null,
  generationMessage: '',

  fetchSystemStatus: async () => {
    try {
      const status = await api.getSystemStatus();
      set({ systemStatus: status });
    } catch (err: any) {
      console.error('Failed to fetch system status:', err);
    }
  },

  triggerModelDownload: async () => {
    try {
      set({ isLoading: true });
      await api.downloadModels();
    } catch (err: any) {
      set({ error: err.message || 'Download failed' });
    } finally {
      set({ isLoading: false });
    }
  },

  loginYouTube: async () => {
    try {
      set({ isLoading: true });
      const channels = await api.loginYouTube();
      const selected = channels.find((c) => c.is_selected)?.channel_id || channels[0]?.channel_id || null;
      set({ channels, selectedChannelId: selected });
    } catch (err: any) {
      set({ error: err.message || 'YouTube login failed' });
    } finally {
      set({ isLoading: false });
    }
  },

  fetchChannels: async () => {
    try {
      const channels = await api.getChannels();
      const selected = channels.find((c) => c.is_selected)?.channel_id || channels[0]?.channel_id || null;
      set({ channels, selectedChannelId: selected });
    } catch (err: any) {
      console.error('Failed to fetch channels:', err);
    }
  },

  selectChannel: async (channelId: string) => {
    try {
      await api.selectChannel(channelId);
      set((state) => ({
        selectedChannelId: channelId,
        channels: state.channels.map((c) => ({
          ...c,
          is_selected: c.channel_id === channelId,
        })),
      }));
    } catch (err: any) {
      console.error('Failed to select channel:', err);
    }
  },

  setMode: (mode: ExecutionMode) => {
    set({ selectedMode: mode });
  },

  createProject: async (topic: string, style: string, targetDuration = 60, lipSync = false) => {
    try {
      set({ isLoading: true, error: null, uploadProgress: 0, generationMessage: '' });
      const mode = get().selectedMode;
      const project = await api.createProject({ topic, style, mode, target_duration_seconds: targetDuration, lip_sync: lipSync });
      set({ activeProject: project });
    } catch (err: any) {
      set({ error: err.response?.data?.detail || err.message || 'Failed to create project' });
    } finally {
      set({ isLoading: false });
    }
  },

  fetchActiveProject: async (id: string) => {
    try {
      const project = await api.getProject(id);
      set({ activeProject: project });
    } catch (err: any) {
      console.error('Failed to fetch project:', err);
    }
  },

  approveScript: async (raw_script: string) => {
    const { activeProject } = get();
    if (!activeProject) return;
    try {
      set({ isLoading: true });
      const updated = await api.approveScript(activeProject.id, raw_script);
      set({ activeProject: updated });
    } catch (err: any) {
      set({ error: err.message || 'Failed to approve script' });
    } finally {
      set({ isLoading: false });
    }
  },

  approveScenes: async (scenes: SceneUpdateRequest[]) => {
    const { activeProject } = get();
    if (!activeProject) return;
    try {
      set({ isLoading: true });
      const updated = await api.approveScenes(activeProject.id, scenes);
      set({ activeProject: updated });
    } catch (err: any) {
      set({ error: err.message || 'Failed to approve scenes' });
    } finally {
      set({ isLoading: false });
    }
  },

  updateMetadata: async (metadata) => {
    const { activeProject } = get();
    if (!activeProject) return;
    try {
      const updated = await api.updateMetadata(activeProject.id, metadata);
      set({ activeProject: updated });
    } catch (err: any) {
      set({ error: err.response?.data?.detail || 'Failed to save metadata' });
      throw err;
    }
  },

  uploadToYouTube: async () => {
    const { activeProject } = get();
    if (!activeProject) return;
    try {
      set({ isLoading: true });
      await api.uploadVideo(activeProject.id);
      await get().fetchActiveProject(activeProject.id);
    } catch (err: any) {
      set({ error: err.message || 'Failed to start upload' });
    } finally {
      set({ isLoading: false });
    }
  },

  initWebSocket: () => {
    wsManager.connect();
    wsManager.subscribe((event) => {
      if (event.event === 'STATE_CHANGED' && event.project_id) {
        const { activeProject } = get();
        if (activeProject && activeProject.id === event.project_id) {
          get().fetchActiveProject(event.project_id);
        }
      } else if (event.event === 'GENERATION_PROGRESS' && event.project_id === get().activeProject?.id) {
        set({ generationMessage: event.message });
      } else if (event.event === 'ERROR') {
        set({ error: event.message || 'Generation failed' });
      } else if (event.event === 'UPLOAD_PROGRESS') {
        set({ uploadProgress: event.percent || 0 });
      } else if (event.event === 'MODEL_DOWNLOAD_PROGRESS') {
        set((state) => ({
          modelDownloadProgress: {
            ...state.modelDownloadProgress,
            [event.model_id]: event.percent,
          },
        }));
        if (event.is_ready) {
          get().fetchSystemStatus();
        }
      }
    });
  },
}));

import axios from 'axios';
import {
  HardwareProfileResponse,
  YouTubeChannel,
  Project,
  CreateProjectRequest,
  SceneUpdateRequest,
} from './types';

const API_BASE = 'http://127.0.0.1:8000';

export const apiClient = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const api = {
  getSystemStatus: async (): Promise<HardwareProfileResponse> => {
    const res = await apiClient.get('/api/system/status');
    return res.data;
  },

  downloadModels: async (): Promise<{ status: string; artifact_count: number }> => {
    const res = await apiClient.post('/api/system/models/download');
    return res.data;
  },

  loginYouTube: async (): Promise<YouTubeChannel[]> => {
    const res = await apiClient.post('/api/auth/youtube/login');
    return res.data;
  },

  getChannels: async (): Promise<YouTubeChannel[]> => {
    const res = await apiClient.get('/api/auth/youtube/channels');
    return res.data;
  },

  selectChannel: async (channelId: string): Promise<void> => {
    await apiClient.post('/api/auth/youtube/select-channel', { channel_id: channelId });
  },

  createProject: async (req: CreateProjectRequest): Promise<Project> => {
    const res = await apiClient.post('/api/projects', req);
    return res.data;
  },

  getProject: async (id: string): Promise<Project> => {
    const res = await apiClient.get(`/api/projects/${id}`);
    return res.data;
  },

  approveScript: async (id: string, raw_script: string): Promise<Project> => {
    const res = await apiClient.post(`/api/projects/${id}/approve-script`, { raw_script });
    return res.data;
  },

  approveScenes: async (id: string, scenes: SceneUpdateRequest[]): Promise<Project> => {
    const res = await apiClient.post(`/api/projects/${id}/approve-scenes`, { scenes });
    return res.data;
  },

  updateMetadata: async (
    id: string,
    metadata: {
      yt_title?: string;
      yt_description?: string;
      yt_tags?: string[];
      yt_privacy?: string;
      target_channel_id?: string;
    }
  ): Promise<Project> => {
    const res = await apiClient.patch(`/api/projects/${id}/metadata`, metadata);
    return res.data;
  },

  uploadVideo: async (id: string): Promise<void> => {
    await apiClient.post(`/api/projects/${id}/upload`);
  },
};

export class WSManager {
  private ws: WebSocket | null = null;
  private listeners: Array<(event: any) => void> = [];
  private reconnectTimer: any = null;

  connect() {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    try {
      this.ws = new WebSocket('ws://127.0.0.1:8000/ws');

      this.ws.onmessage = (event) => {
        try {
          const parsed = JSON.parse(event.data);
          this.listeners.forEach((listener) => listener(parsed));
        } catch (err) {
          console.error('WS parse error:', err);
        }
      };

      this.ws.onclose = () => {
        this.reconnectTimer = setTimeout(() => this.connect(), 2000);
      };

      this.ws.onerror = (err) => {
        console.error('WS error:', err);
        this.ws?.close();
      };
    } catch (err) {
      console.error('Failed to create WebSocket:', err);
    }
  }

  subscribe(listener: (event: any) => void) {
    this.listeners.push(listener);
    return () => {
      this.listeners = this.listeners.filter((l) => l !== listener);
    };
  }

  disconnect() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.ws?.close();
  }
}

export const wsManager = new WSManager();

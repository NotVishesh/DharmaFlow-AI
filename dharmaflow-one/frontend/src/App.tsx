import React, { useEffect } from 'react';
import { apiClient } from './api/client';
import { useAppStore } from './store/useAppStore';
import { TopNav } from './components/TopNav';
import { SetupWizard } from './components/SetupWizard';
import { Step1TopicInput } from './components/Step1TopicInput';
import { Step2ScriptReview } from './components/Step2ScriptReview';
import { Step3SceneStoryboard } from './components/Step3SceneStoryboard';
import { Step4VideoPublish } from './components/Step4VideoPublish';
import { Loader2, AlertCircle } from 'lucide-react';

export const App: React.FC = () => {
  const {
    systemStatus,
    fetchSystemStatus,
    fetchChannels,
    initWebSocket,
    activeProject,
    error,
    generationMessage,
  } = useAppStore();

  useEffect(() => {
    fetchSystemStatus();
    fetchChannels();
    initWebSocket();
    const setupPoll = window.setInterval(fetchSystemStatus, 10000);
    return () => window.clearInterval(setupPoll);
  }, []);

  useEffect(() => {
    if (!activeProject) return;
    const id = activeProject.id;
    const timer = window.setInterval(() => useAppStore.getState().fetchActiveProject(id), 3000);
    return () => window.clearInterval(timer);
  }, [activeProject?.id]);

  const renderContent = () => {
    if (systemStatus && !systemStatus.models_ready) {
      return <SetupWizard />;
    }

    if (!activeProject || activeProject.status === 'IDLE') {
      return <Step1TopicInput />;
    }

    if (activeProject.status === 'GENERATING_SCRIPT') {
      return (
        <div className="max-w-lg mx-auto text-center py-24 bg-slate-900 border border-slate-800 rounded-2xl shadow-xl mt-12 p-8">
          <Loader2 className="animate-spin text-amber-500 mx-auto mb-4" size={40} />
          <h3 className="text-lg font-bold text-slate-100">Generating Script & Storyboard</h3>
          <p className="text-sm text-slate-400 mt-1">Our AI is outlining scenes and draft dialogue...</p>
        </div>
      );
    }

    if (activeProject.status === 'WAIT_SCRIPT_REVIEW') {
      return <Step2ScriptReview />;
    }

    if (activeProject.status === 'GENERATING_SCENES') {
      return (
        <div className="max-w-lg mx-auto text-center py-24 bg-slate-900 border border-slate-800 rounded-2xl shadow-xl mt-12 p-8">
          <Loader2 className="animate-spin text-amber-500 mx-auto mb-4" size={40} />
          <h3 className="text-lg font-bold text-slate-100">Breaking Down Storyboard Scenes</h3>
          <p className="text-sm text-slate-400 mt-1">Structuring ordered dialogue and visual prompts...</p>
        </div>
      );
    }

    if (activeProject.status === 'WAIT_SCENE_REVIEW') {
      return <Step3SceneStoryboard />;
    }

    if (
      activeProject.status === 'GENERATING_AUDIO' ||
      activeProject.status === 'GENERATING_VISUALS' ||
      activeProject.status === 'MUXING_VIDEO'
    ) {
      const stepMap: Record<string, string> = {
        GENERATING_AUDIO: 'Synthesizing Audio via TTS Engine...',
        GENERATING_VISUALS: 'Generating Motion Video Shots...',
        MUXING_VIDEO: 'Audio-First FFmpeg Synchronization & Muxing...',
      };
      return (
        <div className="max-w-lg mx-auto text-center py-24 bg-slate-900 border border-slate-800 rounded-2xl shadow-xl mt-12 p-8">
          <Loader2 className="animate-spin text-amber-500 mx-auto mb-4" size={40} />
          <h3 className="text-lg font-bold text-slate-100">Rendering Video in Progress</h3>
          <p className="text-sm text-amber-400 font-semibold mt-2">{stepMap[activeProject.status]}</p>
          {activeProject.status === 'GENERATING_VISUALS' && <p className="text-sm text-slate-400 mt-2">{generationMessage || 'Preparing the video model. Local rendering may take several minutes per shot.'}</p>}
          <p className="text-xs text-slate-500 mt-1">Narration sets scene length. Export timing is checked within 50 ms; lip-sync is not generated.</p>
        </div>
      );
    }

    if (
      activeProject.status === 'WAIT_VIDEO_REVIEW' ||
      activeProject.status === 'UPLOADING' ||
      activeProject.status === 'COMPLETED'
    ) {
      return <Step4VideoPublish />;
    }

    if (activeProject.status === 'FAILED') {
      return (
        <div className="max-w-lg mx-auto text-center py-16 bg-rose-950/20 border border-rose-500/30 rounded-2xl shadow-xl mt-12 p-8 text-rose-300">
          <AlertCircle size={40} className="mx-auto mb-3 text-rose-500" />
          <h3 className="text-lg font-bold">Pipeline Error</h3>
          <p className="text-xs text-rose-400 mt-2 font-mono bg-rose-950/60 p-3 rounded-lg border border-rose-900/50">
            {activeProject.error_message || 'An unknown error occurred during video rendering.'}
          </p>
          <button className="mt-5 rounded-lg bg-amber-500 px-5 py-3 text-slate-950 font-semibold" onClick={async () => {
            try {
              await apiClient.post(`/api/projects/${activeProject.id}/retry`);
              await useAppStore.getState().fetchActiveProject(activeProject.id);
            } catch (err: any) {
              useAppStore.setState({ error: err.response?.data?.detail || 'Retry failed' });
            }
          }}>Retry after fixing setup</button>
        </div>
      );
    }

    return null;
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-amber-500 selection:text-slate-950">
      <TopNav />
      {systemStatus?.generation?.mock && <div className="bg-amber-950 text-amber-200 text-center p-2 text-sm">Test mode — synthetic test footage and tones, not AI-generated content.</div>}
      {error && (
        <div className="bg-rose-950/80 border-b border-rose-500/50 px-6 py-2.5 text-xs text-rose-200 flex items-center justify-between">
          <span>{error}</span>
        </div>
      )}
      <main className="flex-1 px-6 py-6 overflow-y-auto">{renderContent()}</main>
    </div>
  );
};
export default App;

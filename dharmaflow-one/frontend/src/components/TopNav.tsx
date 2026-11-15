import React from 'react';
import { useAppStore } from '../store/useAppStore';
import { Youtube, Sparkles, SlidersHorizontal, Zap } from 'lucide-react';

export const TopNav: React.FC = () => {
  const {
    channels,
    selectedChannelId,
    selectChannel,
    loginYouTube,
    selectedMode,
    setMode,
    isLoading,
    activeProject,
  } = useAppStore();

  return (
    <header className="border-b border-slate-800 bg-slate-900/90 backdrop-blur sticky top-0 z-50 px-6 py-3.5 flex items-center justify-between">
      {/* Brand */}
      <div className="flex items-center gap-3">
        {activeProject && ['WAIT_VIDEO_REVIEW', 'FAILED', 'COMPLETED'].includes(activeProject.status) &&
          <button className="text-xs text-amber-300 border border-amber-500/30 rounded-lg px-3 py-2" onClick={() => {
            useAppStore.setState({ activeProject: null, error: null, generationMessage: '' });
          }}>New video</button>}
        <div className="w-9 h-9 rounded-lg bg-gradient-to-tr from-amber-600 to-rose-600 flex items-center justify-center font-black text-slate-950 text-xl shadow-lg shadow-rose-950/40">
          ॐ
        </div>
        <div>
          <h1 className="font-extrabold text-base tracking-wide text-slate-100 flex items-center gap-2">
            DHARMAFLOW <span className="text-amber-500 font-mono text-xs px-1.5 py-0.5 rounded bg-amber-500/10 border border-amber-500/20">ONE</span>
          </h1>
          <p className="text-[11px] text-slate-400">Motion Video Studio</p>
        </div>
      </div>

      {/* Center Mode Toggle */}
      <div
        data-testid="mode-toggle"
        className="bg-slate-950 p-1 rounded-xl border border-slate-800 flex items-center gap-1"
      >
        <button
          onClick={() => setMode('REVIEW')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
            selectedMode === 'REVIEW'
              ? 'bg-amber-500 text-slate-950 shadow'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <SlidersHorizontal size={14} />
          Review Mode
        </button>
        <button
          onClick={() => setMode('TURBO')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
            selectedMode === 'TURBO'
              ? 'bg-amber-500 text-slate-950 shadow'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Zap size={14} />
          Turbo Mode
        </button>
      </div>

      {/* Right: YouTube Multi-channel / Auth */}
      <div className="flex items-center gap-3">
        {channels.length > 0 ? (
          <div className="flex items-center gap-2 bg-slate-950 border border-slate-800 px-3 py-1.5 rounded-lg">
            <Youtube size={18} className="text-red-500" />
            <select
              data-testid="channel-select"
              value={selectedChannelId || ''}
              onChange={(e) => selectChannel(e.target.value)}
              className="bg-transparent text-xs text-slate-200 font-medium focus:outline-none cursor-pointer"
            >
              {channels.map((ch) => (
                <option key={ch.channel_id} value={ch.channel_id} className="bg-slate-900 text-slate-100">
                  {ch.title} ({ch.subscriber_count.toLocaleString()} subs)
                </option>
              ))}
            </select>
          </div>
        ) : (
          <button
            onClick={loginYouTube}
            disabled={isLoading}
            className="flex items-center gap-2 bg-red-600/10 hover:bg-red-600/20 text-red-400 border border-red-500/30 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition"
          >
            <Youtube size={16} />
            Connect YouTube
          </button>
        )}
      </div>
    </header>
  );
};

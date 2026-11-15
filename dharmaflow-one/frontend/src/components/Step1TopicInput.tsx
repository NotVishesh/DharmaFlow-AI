import React, { useState } from 'react';
import { useAppStore } from '../store/useAppStore';
import { Sparkles, ArrowRight } from 'lucide-react';

export const Step1TopicInput: React.FC = () => {
  const { createProject, isLoading, selectedMode } = useAppStore();
  const [topic, setTopic] = useState('');
  const [style, setStyle] = useState('cinematic');
  const [targetDuration, setTargetDuration] = useState(60);
  const [lipSync, setLipSync] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!topic.trim()) return;
    createProject(topic.trim(), style, targetDuration, lipSync);
  };

  return (
    <div className="max-w-3xl mx-auto p-8 bg-slate-900 border border-slate-800 rounded-2xl shadow-xl mt-6">
      <div className="mb-6">
        <span className="text-xs font-bold uppercase tracking-wider text-amber-500 bg-amber-500/10 px-2.5 py-1 rounded-md border border-amber-500/20">
          Step 1: Ideation & Direction
        </span>
        <h2 className="text-2xl font-bold text-slate-100 mt-3">What topic shall we bring to life?</h2>
        <p className="text-sm text-slate-400 mt-1">
          Describe a subject, what it does, and the world around it. We turn your idea into narrated motion video.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        <div>
          <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
            Topic Prompt
          </label>
          <textarea
            data-testid="topic-input"
            rows={4}
            maxLength={500}
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="e.g. A small fox trots through a sunlit forest, leaps over a mossy log, and shakes leaves from its fur."
            className="w-full bg-slate-950 border border-slate-800 rounded-xl p-4 text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-amber-500 transition resize-none"
            required
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
              Visual & Narrative Style
            </label>
            <select
              value={style}
              onChange={(e) => setStyle(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-sm text-slate-200 focus:outline-none focus:border-amber-500 cursor-pointer"
            >
              <option value="cinematic">Cinematic Volumetric</option>
              <option value="mythological">Classical Sacred Art</option>
              <option value="minimalist">Minimalist Modern</option>
              <option value="cyberpunk">Futuristic Tech</option>
              <option value="historical">Archival Historical</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
              Pipeline Mode
            </label>
            <div className="bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-sm text-amber-400 font-semibold flex items-center justify-between">
              <span>{selectedMode === 'REVIEW' ? 'Review (Human-in-the-loop)' : 'Turbo (Autonomous)'}</span>
            </div>
          </div>
        </div>

        <div>
          <label htmlFor="film-duration" className="block text-sm text-slate-300 mb-2">Video length</label>
          <select id="film-duration" value={targetDuration} onChange={e => setTargetDuration(Number(e.target.value))}
            className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-slate-200">
            <option value={15}>15 seconds · 3 scenes</option>
            <option value={30}>30 seconds · 6 scenes</option>
            <option value={60}>1 minute · 12 scenes</option>
            <option value={120}>2 minutes · 24 scenes</option>
          </select>
          <p className="text-xs text-slate-400 mt-2">Connected scenes with shared character and setting descriptions. Each scene has its own action. Longer narration can extend the runtime.</p>
          <p className="text-xs text-amber-400 mt-2">Local rendering can take several hours for a one-minute film on a 6 GB GPU. Review the storyboard before rendering. Character appearance may vary between generated shots.</p>
        </div>

        <label className="block text-sm text-slate-200">
          <input type="checkbox" checked={lipSync} onChange={e => setLipSync(e.target.checked)} className="mr-2" />
          Character speaks (lip-sync)
          <span className="block text-xs text-slate-400 mt-1">One frontal face per shot. Generates mouth movement from dialogue; review alignment before publishing. Requires the local MuseTalk model.</span>
        </label>
        <button
          data-testid="start-btn"
          type="submit"
          disabled={isLoading || !topic.trim()}
          className="w-full py-3.5 bg-gradient-to-r from-amber-600 to-rose-600 hover:from-amber-500 hover:to-rose-500 disabled:opacity-50 text-slate-950 font-bold rounded-xl flex items-center justify-center gap-2 shadow-lg shadow-rose-950/30 transition text-sm cursor-pointer"
        >
          <Sparkles size={18} />
          {isLoading ? 'Starting Pipeline...' : 'Start Generation'}
          <ArrowRight size={16} />
        </button>
      </form>
    </div>
  );
};

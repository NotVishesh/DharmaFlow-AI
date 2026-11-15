import React, { useState, useEffect } from 'react';
import { useAppStore } from '../store/useAppStore';
import { Film, Clapperboard, Sparkles } from 'lucide-react';

interface LocalScene {
  id: string;
  scene_index: number;
  dialogue_or_lyrics: string;
  visual_prompt: string;
}

export const Step3SceneStoryboard: React.FC = () => {
  const { activeProject, approveScenes, isLoading } = useAppStore();
  const [scenes, setScenes] = useState<LocalScene[]>([]);

  useEffect(() => {
    if (activeProject?.scenes) {
      setScenes(
        activeProject.scenes.map((s) => ({
          id: s.id,
          scene_index: s.scene_index,
          dialogue_or_lyrics: s.dialogue_or_lyrics,
          visual_prompt: s.visual_prompt,
        }))
      );
    }
  }, [activeProject?.id]);

  const handleUpdate = (index: number, field: 'dialogue_or_lyrics' | 'visual_prompt', value: string) => {
    setScenes((prev) =>
      prev.map((s, i) => (i === index ? { ...s, [field]: value } : s))
    );
  };

  const handleApprove = () => {
    approveScenes(
      scenes.map((s) => ({
        id: s.id,
        dialogue_or_lyrics: s.dialogue_or_lyrics,
        visual_prompt: s.visual_prompt,
      }))
    );
  };

  return (
    <div className="max-w-4xl mx-auto p-8 bg-slate-900 border border-slate-800 rounded-2xl shadow-xl mt-6">
      <div className="mb-6 flex justify-between items-start">
        <div>
          <span className="text-xs font-bold uppercase tracking-wider text-amber-500 bg-amber-500/10 px-2.5 py-1 rounded-md border border-amber-500/20">
            Step 3: Scene Storyboard Review
          </span>
          <h2 className="text-2xl font-bold text-slate-100 mt-3">Scene Breakdown & Prompts</h2>
          <p className="text-sm text-slate-400 mt-1">
            {scenes.length} connected scenes · target {activeProject?.target_duration_seconds ?? 60} seconds. Keep shared character details consistent when editing.
          </p>
        </div>
      </div>

      <div className="space-y-6 mb-8">
        {scenes.map((sc, index) => (
          <div
            key={sc.id}
            className="p-5 bg-slate-950 border border-slate-800 rounded-xl space-y-4 hover:border-slate-700 transition"
          >
            <div className="flex items-center gap-2 text-xs font-bold text-amber-500 uppercase tracking-wider">
              <Clapperboard size={15} />
              Scene {index + 1}
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                Spoken Dialogue / Narration
              </label>
              <textarea
                data-testid={`scene-dialogue-${index}`}
                rows={2}
                value={sc.dialogue_or_lyrics}
                onChange={(e) => handleUpdate(index, 'dialogue_or_lyrics', e.target.value)}
                className="w-full bg-slate-900 border border-slate-800 rounded-lg p-3 text-sm text-slate-200 focus:outline-none focus:border-amber-500 transition resize-none"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                Visual Prompt
              </label>
              <textarea
                data-testid={`scene-visual-${index}`}
                rows={2}
                value={sc.visual_prompt}
                onChange={(e) => handleUpdate(index, 'visual_prompt', e.target.value)}
                className="w-full bg-slate-900 border border-slate-800 rounded-lg p-3 text-sm text-slate-300 focus:outline-none focus:border-amber-500 transition resize-none"
              />
            </div>
          </div>
        ))}
      </div>

      <button
        data-testid="approve-scenes-btn"
        onClick={handleApprove}
        disabled={isLoading || scenes.length === 0}
        className="w-full py-3.5 bg-gradient-to-r from-amber-600 to-rose-600 hover:from-amber-500 hover:to-rose-500 disabled:opacity-50 text-slate-950 font-bold rounded-xl flex items-center justify-center gap-2 shadow-lg transition text-sm cursor-pointer"
      >
        <Sparkles size={18} />
        {isLoading ? 'Synthesizing Audio & Rendering Scenes...' : 'Generate Audio & Video'}
      </button>
    </div>
  );
};

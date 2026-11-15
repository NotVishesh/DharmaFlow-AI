import React, { useState, useEffect } from 'react';
import { useAppStore } from '../store/useAppStore';
import { FileEdit, CheckCircle2 } from 'lucide-react';

export const Step2ScriptReview: React.FC = () => {
  const { activeProject, approveScript, isLoading } = useAppStore();
  const [script, setScript] = useState('');

  useEffect(() => {
    if (activeProject?.raw_script) {
      setScript(activeProject.raw_script);
    }
  }, [activeProject?.raw_script]);

  const handleApprove = () => {
    if (!script.trim()) return;
    approveScript(script);
  };

  return (
    <div className="max-w-4xl mx-auto p-8 bg-slate-900 border border-slate-800 rounded-2xl shadow-xl mt-6">
      <div className="mb-6 flex justify-between items-start">
        <div>
          <span className="text-xs font-bold uppercase tracking-wider text-amber-500 bg-amber-500/10 px-2.5 py-1 rounded-md border border-amber-500/20">
            Step 2: Script Review & Editing
          </span>
          <h2 className="text-2xl font-bold text-slate-100 mt-3">Review & Refine Script</h2>
          <p className="text-sm text-slate-400 mt-1">
            Topic: <span className="text-amber-400 font-medium">"{activeProject?.topic}"</span>
          </p>
        </div>
      </div>

      <div className="space-y-6">
        <div>
          <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
            Generated Script · one line per scene
          </label>
          <textarea
            data-testid="script-editor"
            rows={10}
            value={script}
            onChange={(e) => setScript(e.target.value)}
            className="w-full bg-slate-950 border border-slate-800 rounded-xl p-4 font-mono text-sm text-slate-200 focus:outline-none focus:border-amber-500 transition resize-y leading-relaxed"
          />
        </div>

        <button
          data-testid="approve-script-btn"
          onClick={handleApprove}
          disabled={isLoading || !script.trim()}
          className="w-full py-3.5 bg-amber-500 hover:bg-amber-400 disabled:opacity-50 text-slate-950 font-bold rounded-xl flex items-center justify-center gap-2 shadow-lg transition text-sm cursor-pointer"
        >
          <CheckCircle2 size={18} />
          {isLoading ? 'Processing...' : 'Approve Script & Generate Scenes'}
        </button>
      </div>
    </div>
  );
};

import React from 'react';
import { useAppStore } from '../store/useAppStore';
import { Cpu, HardDrive, Download, CheckCircle2 } from 'lucide-react';

export const SetupWizard: React.FC = () => {
  const { systemStatus, triggerModelDownload, modelDownloadProgress, isLoading } = useAppStore();

  if (!systemStatus) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-10 w-10 border-t-2 border-b-2 border-amber-500"></div>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto p-6 bg-slate-900 border border-slate-800 rounded-xl shadow-2xl mt-8">
      <div className="text-center mb-8">
        <h2 className="text-2xl font-bold text-amber-500 mb-2">Hardware Setup & Model Verification</h2>
        <p className="text-slate-400 text-sm">
          Set up real motion video generation. Local rendering uses your GPU; the optional API requires a paid account.
        </p>
      </div>

      <div className="grid grid-cols-3 gap-4 mb-8">
        <div className="bg-slate-950 p-4 rounded-lg border border-slate-800 text-center">
          <Cpu className="mx-auto text-amber-400 mb-2" size={24} />
          <div className="text-xs text-slate-400 uppercase tracking-wider">Detected Tier</div>
          <div className="text-lg font-bold text-slate-100">{systemStatus.hardware_tier}</div>
        </div>

        <div className="bg-slate-950 p-4 rounded-lg border border-slate-800 text-center">
          <HardDrive className="mx-auto text-cyan-400 mb-2" size={24} />
          <div className="text-xs text-slate-400 uppercase tracking-wider">GPU VRAM</div>
          <div className="text-lg font-bold text-slate-100">{systemStatus.vram_gb} GB</div>
        </div>

        <div className="bg-slate-950 p-4 rounded-lg border border-slate-800 text-center">
          <HardDrive className="mx-auto text-emerald-400 mb-2" size={24} />
          <div className="text-xs text-slate-400 uppercase tracking-wider">System RAM</div>
          <div className="text-lg font-bold text-slate-100">{systemStatus.ram_gb} GB</div>
        </div>
      </div>

      {systemStatus.generation && <div className="p-5 mb-6 rounded-xl bg-slate-950 border border-slate-700 space-y-3">
        <h3 className="font-semibold">Video engine: {systemStatus.generation.provider}</h3>
        <p className="text-sm text-slate-400">Local Wan: 480 × 832 native video. Export: 1080 × 1920 upscaled. A 6 GB GPU uses CPU offloading and can render slowly.</p>
        <ul className="text-sm text-amber-200 space-y-2">{systemStatus.generation.issues.map(issue => <li key={issue}>{issue}</li>)}</ul>
        <p className="text-sm" role="status">{systemStatus.generation.download?.message}</p>
        <p className="text-xs text-slate-400">API fallback: set VIDEO_PROVIDER=local_then_fal and FAL_KEY in backend/.env, then restart. Prompts go to fal only when fallback is enabled; usage is billed by fal.</p>
      </div>}
      <div className="space-y-4 mb-8">
        <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">Local video setup</h3>
        {systemStatus.models.filter(art => !art.url.includes("mock.local")).map((art) => {
          const progress = modelDownloadProgress[art.id] ?? (art.is_ready ? 100 : 0);
          return (
            <div key={art.id} className="bg-slate-950 p-4 rounded-lg border border-slate-800 flex flex-col gap-2">
              <div className="flex justify-between items-center">
                <div>
                  <span className="font-medium text-slate-200">{art.filename}</span>
                  <span className="text-xs text-slate-500 ml-2">({art.role} â€¢ {(art.size_bytes / (1024 * 1024)).toFixed(1)} MB)</span>
                </div>
                {art.is_ready ? (
                  <span className="flex items-center text-emerald-400 text-xs font-semibold gap-1">
                    <CheckCircle2 size={16} /> Ready
                  </span>
                ) : (
                  <span className="text-amber-400 text-xs font-semibold">{progress.toFixed(0)}%</span>
                )}
              </div>
              <div className="w-full bg-slate-800 rounded-full h-2">
                <div
                  className="bg-amber-500 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${progress}%` }}
                ></div>
              </div>
            </div>
          );
        })}
      </div>

      <button
        onClick={triggerModelDownload}
        disabled={isLoading || ['downloading', 'verifying'].includes(systemStatus.generation?.download?.status || '')}
        className="w-full py-3 bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-slate-950 font-bold rounded-lg flex items-center justify-center gap-2 shadow-lg transition"
      >
        <Download size={20} />
        {['downloading', 'verifying'].includes(systemStatus.generation?.download?.status || '') ? 'Downloading / verifying model…' : 'Download Local Video Model'}
      </button>
    </div>
  );
};

import React, { useState, useEffect } from 'react';
import { apiClient } from '../api/client';
import { useAppStore } from '../store/useAppStore';
import { Youtube, CheckCircle2, UploadCloud, Film } from 'lucide-react';

export const Step4VideoPublish: React.FC = () => {
  const { activeProject, updateMetadata, uploadToYouTube, uploadProgress, isLoading } = useAppStore();

  const [quality, setQuality] = useState<any>(null);
  useEffect(() => {
    setQuality(null);
    if (activeProject?.id) apiClient.get(`/api/projects/${activeProject.id}/quality`).then(r => setQuality(r.data)).catch(() => {});
  }, [activeProject?.id]);

  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [tags, setTags] = useState('');
  const [privacy, setPrivacy] = useState('private');

  useEffect(() => {
    if (activeProject) {
      setTitle(activeProject.yt_title || '');
      setDescription(activeProject.yt_description || '');
      setTags((activeProject.yt_tags || []).join(', '));
      setPrivacy(activeProject.yt_privacy || 'private');
    }
  }, [activeProject?.id]);

  const handleSaveMetadata = () => {
    return updateMetadata({
      yt_title: title,
      yt_description: description,
      yt_tags: tags.split(',').map((t) => t.trim()).filter(Boolean),
      yt_privacy: privacy,
    });
  };

  const handleUpload = async () => {
    await handleSaveMetadata();
    await uploadToYouTube();
  };

  const mediaUrl = activeProject?.id
    ? `http://127.0.0.1:8000/media/${activeProject.id}/final_video.mp4`
    : '';

  return (
    <div className="max-w-5xl mx-auto p-8 bg-slate-900 border border-slate-800 rounded-2xl shadow-xl mt-6">
      <div className="mb-6 flex justify-between items-start">
        <div>
          <span className="text-xs font-bold uppercase tracking-wider text-emerald-400 bg-emerald-500/10 px-2.5 py-1 rounded-md border border-emerald-500/20">
            Step 4: Preview & One-Click Publish
          </span>
          <h2 className="text-2xl font-bold text-slate-100 mt-3">Final Video & YouTube Metadata</h2>
          <p className="text-sm text-slate-400 mt-1">
            Review the final rendered vertical video and customize metadata before uploading.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {/* Left Column: Video Player */}
        <div className="space-y-4">
          {quality ? <div className="text-sm p-4 border border-emerald-800 rounded-xl bg-emerald-950/30" data-testid="quality-report">
            <p className="font-semibold text-emerald-300">Audio/video timing verified: {quality.max_offset_ms} ms</p>
            <p className="text-slate-400 mt-1">1080 × 1920 export · 30 fps · narration over motion footage</p>
            <p className="text-slate-400">{quality.synthetic_test ? 'Synthetic test content' : 'Generated video'} · {quality.lip_sync === 'generated_not_independently_scored' ? 'Mouth animation generated; review lip alignment' : 'Lip-sync not evaluated'}</p>
            {quality.scenes?.map((scene: any) => <p key={scene.scene_index} className="text-xs text-slate-400 mt-1">Shot {scene.scene_index + 1}: {scene.generation?.provider} · native {scene.generation?.native_resolution || 'test resolution'}</p>)}
          </div> : <p className="text-sm text-amber-300">No timing verification report available for this export.</p>}
          <a className="text-amber-300 text-sm underline" href={mediaUrl} download="dharmaflow-video.mp4">Download video</a>
          <div className="aspect-[9/16] bg-slate-950 rounded-2xl overflow-hidden border border-slate-800 relative flex items-center justify-center max-h-[580px] mx-auto shadow-2xl">
            {mediaUrl ? (
              <video
                controls
                src={mediaUrl}
                className="w-full h-full object-contain"
                playsInline
              />
            ) : (
              <div className="text-center text-slate-500 p-4">
                <Film size={36} className="mx-auto mb-2 opacity-50" />
                <p className="text-xs">Video is finalizing...</p>
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Editable Metadata & Publish */}
        <div className="space-y-5">
          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
              YouTube Title (max 100 chars)
            </label>
            <input
              type="text"
              data-testid="yt-title-input"
              value={title}
              maxLength={100}
              onChange={(e) => setTitle(e.target.value)}
              onBlur={handleSaveMetadata}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-sm text-slate-100 focus:outline-none focus:border-amber-500 transition"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
              Description
            </label>
            <textarea
              data-testid="yt-desc-input"
              rows={5}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              onBlur={handleSaveMetadata}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl p-4 text-sm text-slate-200 focus:outline-none focus:border-amber-500 transition resize-none leading-relaxed"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
              Tags (comma separated)
            </label>
            <input
              type="text"
              data-testid="yt-tags-input"
              value={tags}
              onChange={(e) => setTags(e.target.value)}
              onBlur={handleSaveMetadata}
              placeholder="e.g. shorts, philosophy, mindfulness"
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-sm text-slate-200 focus:outline-none focus:border-amber-500 transition"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
              Privacy Status
            </label>
            <select
              value={privacy}
              onChange={(e) => {
                setPrivacy(e.target.value);
                updateMetadata({ yt_privacy: e.target.value });
              }}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-sm text-slate-200 focus:outline-none focus:border-amber-500 cursor-pointer"
            >
              <option value="private">Private (Recommended for testing)</option>
              <option value="unlisted">Unlisted</option>
              <option value="public">Public</option>
            </select>
          </div>

          {activeProject?.status === 'UPLOADING' ? (
            <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 space-y-2">
              <div className="flex justify-between text-xs font-semibold text-slate-300">
                <span>Uploading to YouTube...</span>
                <span className="text-amber-400">{uploadProgress}%</span>
              </div>
              <div className="w-full bg-slate-800 rounded-full h-2">
                <div
                  className="bg-red-500 h-2 rounded-full transition-all duration-200"
                  style={{ width: `${uploadProgress}%` }}
                ></div>
              </div>
            </div>
          ) : activeProject?.status === 'COMPLETED' ? (
            <div className="bg-emerald-950/40 border border-emerald-500/30 rounded-xl p-4 flex items-center gap-3 text-emerald-400">
              <CheckCircle2 size={24} />
              <div>
                <div className="font-bold text-sm">Successfully Published!</div>
                <div className="text-xs text-emerald-300">
                  YouTube Video ID: <span className="font-mono">{activeProject.youtube_video_id}</span>
                </div>
              </div>
            </div>
          ) : (
            <button
              data-testid="upload-btn"
              onClick={handleUpload}
              disabled={isLoading || !title.trim()}
              className="w-full py-3.5 bg-gradient-to-r from-red-600 to-amber-600 hover:from-red-500 hover:to-amber-500 disabled:opacity-50 text-slate-100 font-bold rounded-xl flex items-center justify-center gap-2 shadow-lg shadow-red-950/40 transition text-sm cursor-pointer"
            >
              <UploadCloud size={20} />
              {isLoading ? 'Starting Upload...' : 'One-Click Upload to YouTube'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

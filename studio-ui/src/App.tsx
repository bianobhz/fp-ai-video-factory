import { useEffect, useState } from 'react';
import { LibraryPanel } from './components/LibraryPanel';
import { PreviewStage } from './components/PreviewStage';
import { PropertiesPanel } from './components/PropertiesPanel';
import { Timeline } from './components/Timeline';
import { TopBar } from './components/TopBar';
import { useProjectStore } from './store/useProjectStore';

export function App() {
  const { project } = useProjectStore();
  const [videos, setVideos] = useState<any[]>([]);
  const [jobStatus, setJobStatus] = useState('idle');
  const [previewVideoUrl, setPreviewVideoUrl] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  async function refreshStatus() {
    try {
      const res = await fetch('/api/status');
      const data = await res.json();
      setJobStatus(data.status || 'idle');
      setVideos(data.videos || []);
    } catch {
      // Backend offline
    }
  }

  useEffect(() => {
    refreshStatus();
    const id = setInterval(refreshStatus, 4000);
    return () => clearInterval(id);
  }, []);

  async function handleEnqueue() {
    const payload = {
      title: project.title,
      workflow: project.workflow,
      width: project.format === '16:9' ? 1280 : 720,
      height: project.format === '16:9' ? 720 : project.format === '1:1' ? 720 : 1280,
      length: 65,
      scenes: project.scenes.map((s) => ({
        speaker: s.speaker,
        voice: s.voice,
        speech_ptbr: s.speechPtBr,
        visual_prompt_en: s.visualPromptEn,
        lip_sync: s.lipSyncEnabled,
      })),
    };
    const res = await fetch('/api/queue', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    setToast(data.ok ? `Projeto "${project.title}" salvo na fila!` : `Erro: ${data.error}`);
    setTimeout(() => setToast(null), 3500);
  }

  async function handleRunQueue() {
    await handleEnqueue();
    setToast('Projeto salvo! Conecte uma GPU Vast.ai para processar a fila.');
    setTimeout(() => setToast(null), 4000);
  }

  return (
    <div className="h-screen w-screen flex flex-col bg-[#090c12] text-slate-100 overflow-hidden">
      <TopBar
        onEnqueue={handleEnqueue}
        onRunQueue={handleRunQueue}
        gpuLabel="Vast.ai Pronto (Offline)"
        jobStatus={jobStatus}
      />

      <div className="flex-1 flex min-h-0 overflow-hidden">
        <LibraryPanel videos={videos} onSelectPreviewVideo={(url) => setPreviewVideoUrl(url)} />
        <PreviewStage previewVideoUrl={previewVideoUrl} onClearPreviewVideo={() => setPreviewVideoUrl(null)} />
        <PropertiesPanel />
      </div>

      <Timeline />

      {toast && (
        <div className="fixed bottom-48 right-6 px-4 py-2.5 rounded-xl bg-blue-600 text-white text-xs font-semibold shadow-2xl z-50">
          {toast}
        </div>
      )}
    </div>
  );
}

export default App;

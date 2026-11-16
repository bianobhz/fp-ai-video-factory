import { useEffect, useState } from 'react';
import { LibraryPanel } from './components/LibraryPanel';
import { PreviewStage } from './components/PreviewStage';
import { PropertiesPanel } from './components/PropertiesPanel';
import { Timeline } from './components/Timeline';
import { TopBar } from './components/TopBar';
import { useProjectStore } from './store/useProjectStore';

interface VastQuote {
  offer_id: number;
  gpu_name: string;
  vram_gb: number;
  dph_total: number;
  disk_gb: number;
}

export function App() {
  const { project } = useProjectStore();
  const [videos, setVideos] = useState<any[]>([]);
  const [uploads, setUploads] = useState<any[]>([]);
  const [jobStatus, setJobStatus] = useState('idle');
  const [previewVideoUrl, setPreviewVideoUrl] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [quote, setQuote] = useState<VastQuote | null>(null);
  const [quoting, setQuoting] = useState(false);

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

  async function refreshUploads() {
    try {
      const res = await fetch('/api/uploads');
      const data = await res.json();
      setUploads(data.items || []);
    } catch {
      // Backend offline
    }
  }

  useEffect(() => {
    refreshStatus();
    refreshUploads();
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

  async function handleLocalRender() {
    const res = await fetch('/api/local/render', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(project),
    });
    const data = await res.json();
    setToast(data.ok ? 'Renderização local (FFmpeg) iniciada!' : `Erro: ${data.error}`);
    setTimeout(() => setToast(null), 4000);
    refreshStatus();
  }

  async function handleRunQueue() {
    await handleEnqueue();
    setQuoting(true);
    try {
      const res = await fetch('/api/vast/quote');
      const data = await res.json();
      if (!data.ok) {
        setToast(`Erro Vast.ai: ${data.error}`);
        setTimeout(() => setToast(null), 4000);
        return;
      }
      setQuote(data);
    } finally {
      setQuoting(false);
    }
  }

  async function confirmVastProduce() {
    if (!quote) return;
    const offer_id = quote.offer_id;
    setQuote(null);
    const res = await fetch('/api/vast/produce', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ offer_id }),
    });
    const data = await res.json();
    setToast(data.ok ? 'Produção iniciada na Vast.ai! A máquina será destruída ao concluir.' : `Erro: ${data.error}`);
    setTimeout(() => setToast(null), 5000);
    refreshStatus();
  }

  return (
    <div className="h-screen w-screen flex flex-col bg-[#090c12] text-slate-100 overflow-hidden">
      <TopBar
        onEnqueue={handleEnqueue}
        onRunQueue={handleRunQueue}
        onLocalRender={handleLocalRender}
        gpuLabel={quoting ? 'Buscando GPU...' : 'Vast.ai (50 GB)'}
        jobStatus={jobStatus}
      />

      <div className="flex-1 flex min-h-0 overflow-hidden">
        <LibraryPanel
          videos={videos}
          uploads={uploads}
          onRefreshUploads={refreshUploads}
          onSelectPreviewVideo={(url) => setPreviewVideoUrl(url)}
          onEnqueue={handleEnqueue}
          onOpenProduceModal={handleRunQueue}
          onLocalRender={handleLocalRender}
        />
        <PreviewStage previewVideoUrl={previewVideoUrl} onClearPreviewVideo={() => setPreviewVideoUrl(null)} />
        <PropertiesPanel />
      </div>

      <Timeline />

      {quote && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-[#111723] border border-[#263248] rounded-2xl p-5 w-96 shadow-2xl">
            <h3 className="text-sm font-bold text-white mb-1">Autorizar Produção na Nuvem</h3>
            <p className="text-xs text-slate-400 mb-4">
              A instância será criada, processará sua fila e será destruída automaticamente ao terminar.
            </p>
            <div className="bg-[#090c12] border border-[#1f293d] rounded-xl p-3 text-xs space-y-1.5 mb-4">
              <div className="flex justify-between"><span className="text-slate-400">GPU:</span><strong className="text-white">{quote.gpu_name}</strong></div>
              <div className="flex justify-between"><span className="text-slate-400">VRAM:</span><span>{quote.vram_gb} GB</span></div>
              <div className="flex justify-between"><span className="text-slate-400">Disco:</span><span>{quote.disk_gb} GB</span></div>
              <div className="flex justify-between"><span className="text-slate-400">Custo/hora:</span><strong className="text-emerald-400">US$ {quote.dph_total}/h</strong></div>
            </div>
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => setQuote(null)}
                className="px-3.5 py-2 rounded-lg bg-[#182132] text-xs font-semibold text-slate-300 cursor-pointer"
              >
                Cancelar
              </button>
              <button
                onClick={confirmVastProduce}
                className="px-4 py-2 rounded-lg bg-gradient-to-r from-blue-600 to-violet-600 text-xs font-semibold text-white cursor-pointer"
              >
                Autorizar e Iniciar
              </button>
            </div>
          </div>
        </div>
      )}

      {toast && (
        <div className="fixed bottom-48 right-6 px-4 py-2.5 rounded-xl bg-blue-600 text-white text-xs font-semibold shadow-2xl z-50">
          {toast}
        </div>
      )}
    </div>
  );
}

export default App;

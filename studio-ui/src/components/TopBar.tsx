import { Cloud, Cpu, Download, Film, Layers, Plus, Sparkles } from 'lucide-react';
import { useProjectStore } from '../store/useProjectStore';
import type { AspectFormat, StudioFrontMode } from '../types/project';

interface TopBarProps {
  onEnqueue: () => void;
  onRunQueue: () => void;
  onLocalRender: () => void;
  gpuLabel: string;
  jobStatus: string;
}

export function TopBar({ onEnqueue, onRunQueue, onLocalRender, gpuLabel, jobStatus }: TopBarProps) {
  const { project, setProjectTitle, setMode, setFormat, addScene } = useProjectStore();
  const totalDur = project.scenes.reduce((acc, s) => acc + s.durationSec, 0);

  return (
    <header className="h-14 px-4 bg-[#0f141e] border-b border-[#1e2738] flex items-center justify-between gap-3 shrink-0">
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center shadow-lg shadow-blue-500/20">
          <Film className="w-4 h-4 text-white" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <span className="font-bold text-sm tracking-tight text-white">FP AI Video Factory</span>
            <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-blue-500/15 text-blue-300 border border-blue-500/30">
              STUDIO v3.1
            </span>
          </div>
          <div className="text-[11px] text-slate-400">
            {project.scenes.length} cenas • {totalDur.toFixed(1)}s totais
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <select
          value={project.mode || 'social_ia'}
          onChange={(e) => setMode(e.target.value as StudioFrontMode)}
          className="bg-[#141d2e] border border-blue-500/40 rounded-lg px-2.5 py-1.5 text-xs font-semibold text-blue-200 focus:outline-none focus:border-blue-400"
          title="Frente de Produção"
        >
          <option value="social_ia">Frente 1: Redes IA (Viral / Lip-Sync)</option>
          <option value="school_local">Frente 2: Colégio / Reels Local (Fotos &amp; Takes)</option>
          <option value="commercial_i2v">Frente 3: Comercial (Produto / Ambiente I2V)</option>
        </select>

        <input
          value={project.title}
          onChange={(e) => setProjectTitle(e.target.value)}
          className="bg-[#090c12] border border-[#243046] rounded-lg px-2.5 py-1.5 text-xs text-slate-100 w-40 focus:outline-none focus:border-blue-500"
          placeholder="Nome do projeto"
        />
        <select
          value={project.format}
          onChange={(e) => setFormat(e.target.value as AspectFormat)}
          className="bg-[#090c12] border border-[#243046] rounded-lg px-2 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-blue-500"
        >
          <option value="9:16">9:16 (1080×1920 Reels)</option>
          <option value="16:9">16:9 (1920×1080 YouTube)</option>
          <option value="1:1">1:1 (1080×1080 Feed)</option>
        </select>
        <button
          onClick={() => addScene()}
          className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-[#182132] hover:bg-[#1f2b42] border border-[#28354d] text-xs font-medium text-slate-200 cursor-pointer"
        >
          <Plus className="w-3.5 h-3.5" />
          Cena
        </button>
      </div>

      <div className="flex items-center gap-2">
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#131a27] border border-[#222d42] text-[11px] text-slate-300">
          <Cpu className="w-3.5 h-3.5 text-emerald-400" />
          <span>{gpuLabel}</span>
        </div>
        <div className="px-2.5 py-1 rounded-full bg-[#131a27] border border-[#222d42] text-[11px] text-slate-300">
          Status: <strong className="text-blue-300">{jobStatus}</strong>
        </div>
        <button
          onClick={onEnqueue}
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-[#182132] hover:bg-[#1f2b42] border border-[#2a3852] text-xs font-semibold text-slate-100 cursor-pointer"
        >
          <Layers className="w-3.5 h-3.5 text-blue-400" />
          Fila
        </button>
        <button
          onClick={onLocalRender}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-xs font-semibold text-white cursor-pointer"
          title="Renderizar localmente via FFmpeg com música e movimentos (custo zero de nuvem)"
        >
          <Download className="w-3.5 h-3.5" />
          Exportar Local
        </button>
        <button
          onClick={onRunQueue}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gradient-to-r from-blue-600 to-violet-600 hover:opacity-90 text-xs font-semibold text-white shadow-lg shadow-blue-600/20 cursor-pointer"
        >
          <Cloud className="w-3.5 h-3.5" />
          <span>Produzir Nuvem</span>
          <Sparkles className="w-3 h-3" />
        </button>
      </div>
    </header>
  );
}

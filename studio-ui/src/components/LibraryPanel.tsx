import { Bot, Film, FolderOpen, Send, Sparkles } from 'lucide-react';
import { useState } from 'react';
import { useProjectStore } from '../store/useProjectStore';
import type { SceneItem } from '../types/project';

interface FinalVideo {
  name: string;
  url: string;
  size_mb: number;
}

interface LibraryPanelProps {
  videos: FinalVideo[];
  onSelectPreviewVideo: (url: string) => void;
}

export function LibraryPanel({ videos, onSelectPreviewVideo }: LibraryPanelProps) {
  const [tab, setTab] = useState<'copilot' | 'media'>('copilot');
  const [goal, setGoal] = useState('');
  const [loading, setLoading] = useState(false);
  const [copilotMsg, setCopilotMsg] = useState<string | null>(null);
  const { project, selectedSceneId, selectScene, replaceScenes } = useProjectStore();

  async function handleCopilot() {
    if (!goal.trim()) return;
    setLoading(true);
    setCopilotMsg(null);
    try {
      const res = await fetch('/api/ai-copilot', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ goal, provider: 'openai' }),
      });
      const data = await res.json();
      if (!data.ok) {
        setCopilotMsg(`Erro: ${data.error}`);
        return;
      }
      const plan = data.plan;
      const mapped: SceneItem[] = (plan.scenes || []).map((sc: any, i: number) => ({
        id: `scene-${Date.now()}-${i}`,
        title: `${sc.speaker || 'Cena'} ${i + 1}`,
        speaker: sc.speaker || 'Personagem',
        voice: sc.voice || 'pt-BR-FranciscaNeural',
        speechPtBr: sc.speech_ptbr || '',
        visualPromptEn: sc.visual_prompt_en || '',
        durationSec: 4.5,
        transition: 'cut',
        volume: 1,
        subtitleText: sc.speech_ptbr || '',
        lipSyncEnabled: true,
        status: 'draft',
      }));
      replaceScenes(plan.title || 'novo_projeto', mapped);
      setCopilotMsg(`Roteiro "${plan.title}" aplicado com ${mapped.length} cenas!`);
      setGoal('');
    } catch (err: any) {
      setCopilotMsg(`Falha de conexão: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <aside className="w-80 bg-[#0f141e] border-r border-[#1e2738] flex flex-col shrink-0 overflow-hidden">
      <div className="flex border-b border-[#1e2738]">
        <button
          onClick={() => setTab('copilot')}
          className={`flex-1 py-2.5 text-xs font-semibold flex items-center justify-center gap-1.5 cursor-pointer ${
            tab === 'copilot' ? 'text-blue-400 border-b-2 border-blue-500 bg-[#141b29]' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Bot className="w-3.5 h-3.5" />
          Copiloto IA
        </button>
        <button
          onClick={() => setTab('media')}
          className={`flex-1 py-2.5 text-xs font-semibold flex items-center justify-center gap-1.5 cursor-pointer ${
            tab === 'media' ? 'text-blue-400 border-b-2 border-blue-500 bg-[#141b29]' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <FolderOpen className="w-3.5 h-3.5" />
          Biblioteca ({videos.length})
        </button>
      </div>

      {tab === 'copilot' ? (
        <div className="flex-1 flex flex-col p-3 gap-3 overflow-y-auto">
          <div className="p-3 rounded-xl bg-[#141b29] border border-[#222d42]">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-blue-300 mb-1.5">
              <Sparkles className="w-3.5 h-3.5" />
              Diretor de IA (OpenAI integrado)
            </div>
            <p className="text-[11px] text-slate-400 mb-2.5">
              Descreva a cena, anúncio ou diálogo em português. O Copiloto monta as falas, escolhe as vozes PT-BR e escreve os prompts cinematográficos.
            </p>
            <textarea
              rows={3}
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              placeholder="Ex: Comercial de 15s de uma cafeteria artesanal com 2 pessoas elogiando o espresso..."
              className="w-full bg-[#090c12] border border-[#243046] rounded-lg p-2 text-xs text-slate-100 focus:outline-none focus:border-blue-500 mb-2"
            />
            <button
              onClick={handleCopilot}
              disabled={loading}
              className="w-full py-2 rounded-lg bg-gradient-to-r from-blue-600 to-violet-600 text-xs font-semibold text-white flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-50"
            >
              <Send className="w-3.5 h-3.5" />
              {loading ? 'Criando roteiro...' : 'Gerar Cenas com IA'}
            </button>
            {copilotMsg && <div className="mt-2 text-[11px] text-emerald-300">{copilotMsg}</div>}
          </div>

          <div>
            <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-2">
              Cenas do Projeto ({project.scenes.length})
            </div>
            <div className="flex flex-col gap-1.5">
              {project.scenes.map((sc, i) => (
                <button
                  key={sc.id}
                  onClick={() => selectScene(sc.id)}
                  className={`text-left p-2.5 rounded-lg border transition cursor-pointer ${
                    selectedSceneId === sc.id
                      ? 'bg-blue-600/15 border-blue-500/50 text-white'
                      : 'bg-[#141b29] border-[#1f293d] text-slate-300 hover:border-[#30405e]'
                  }`}
                >
                  <div className="flex items-center justify-between text-xs font-semibold">
                    <span>{i + 1}. {sc.title}</span>
                    <span className="text-[10px] text-slate-400">{sc.durationSec}s</span>
                  </div>
                  <div className="text-[11px] text-slate-400 truncate mt-0.5">{sc.speechPtBr || 'Sem fala'}</div>
                </button>
              ))}
            </div>
          </div>
        </div>
      ) : (
        <div className="flex-1 p-3 overflow-y-auto flex flex-col gap-2">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-1">
            Vídeos Exportados (outputs/final)
          </div>
          {videos.map((v) => (
            <button
              key={v.name}
              onClick={() => onSelectPreviewVideo(v.url)}
              className="text-left p-2.5 rounded-lg bg-[#141b29] border border-[#1f293d] hover:border-blue-500/50 transition cursor-pointer"
            >
              <div className="flex items-center gap-2 text-xs font-semibold text-slate-200 truncate">
                <Film className="w-3.5 h-3.5 text-blue-400 shrink-0" />
                <span className="truncate">{v.name}</span>
              </div>
              <div className="text-[11px] text-slate-400 mt-1">{v.size_mb} MB • Clique para assistir</div>
            </button>
          ))}
        </div>
      )}
    </aside>
  );
}

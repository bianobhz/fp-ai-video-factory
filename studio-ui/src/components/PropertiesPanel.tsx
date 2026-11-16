import { Image, Music, Sliders, Trash2, Volume2 } from 'lucide-react';
import { useRef, useState } from 'react';
import { useProjectStore } from '../store/useProjectStore';
import type { TransitionType } from '../types/project';

interface PropertiesPanelProps {
  musicBank: { name: string; label: string; url: string }[];
  uploads: { name: string; url: string; kind: string }[];
}

const VOICES = [
  { id: 'pt-BR-FranciscaNeural', label: 'Francisca (Feminina Natural)' },
  { id: 'pt-BR-AntonioNeural', label: 'Antonio (Masculina Natural)' },
  { id: 'pt-BR-ThalitaNeural', label: 'Thalita (Feminina Jovem / Reels)' },
  { id: 'pt-BR-BrendaNeural', label: 'Brenda (Feminina Comercial)' },
  { id: 'pt-BR-DonatoNeural', label: 'Donato (Masculina Madura)' },
  { id: 'pt-BR-GiovannaNeural', label: 'Giovanna (Feminina Expressiva)' },
  { id: 'pt-BR-HumbertoNeural', label: 'Humberto (Masculina Narrador)' },
  { id: 'pt-BR-JulioNeural', label: 'Júlio (Masculina Dinâmica)' },
  { id: 'openai:nova', label: 'OpenAI Nova (Ultra-Realista Feminina)' },
  { id: 'openai:onyx', label: 'OpenAI Onyx (Ultra-Realista Masculina)' },
  { id: 'openai:alloy', label: 'OpenAI Alloy (Estúdio Neutro)' },
  { id: 'openai:shimmer', label: 'OpenAI Shimmer (Comercial Suave)' },
];

export function PropertiesPanel({ musicBank, uploads }: PropertiesPanelProps) {
  const { project, selectedSceneId, updateScene, removeScene, setSubtitlesEnabled, setMusicUrl, setMusicVolume } =
    useProjectStore();
  const scene = project.scenes.find((s) => s.id === selectedSceneId);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [ttsLoading, setTtsLoading] = useState(false);
  const imageUploads = uploads.filter((u) => u.kind === 'image');

  async function previewVoice() {
    if (!scene || !scene.speechPtBr.trim()) return;
    setTtsLoading(true);
    try {
      const res = await fetch('/api/tts-preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: scene.speechPtBr, voice: scene.voice }),
      });
      const data = await res.json();
      if (data.ok && audioRef.current) {
        updateScene(scene.id, { audioUrl: data.url });
        audioRef.current.src = data.url;
        audioRef.current.play();
      }
    } finally {
      setTtsLoading(false);
    }
  }

  function previewMusic() {
    if (!project.musicUrl || !audioRef.current) return;
    audioRef.current.src = project.musicUrl;
    audioRef.current.play();
  }

  return (
    <aside className="w-80 bg-[#0f141e] border-l border-[#1e2738] flex flex-col shrink-0 overflow-y-auto p-3.5 gap-3">
      <audio ref={audioRef} className="hidden" />
      <div className="flex items-center justify-between border-b border-[#1e2738] pb-2.5">
        <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-200">
          <Sliders className="w-3.5 h-3.5 text-blue-400" />
          Propriedades da Cena
        </div>
        {scene && (
          <button
            onClick={() => removeScene(scene.id)}
            className="text-red-400 hover:text-red-300 p-1 rounded cursor-pointer"
            title="Remover cena"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {scene ? (
        <>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-[11px] text-slate-400 mb-1">Título da Cena</label>
              <input
                value={scene.title}
                onChange={(e) => updateScene(scene.id, { title: e.target.value })}
                className="w-full bg-[#090c12] border border-[#243046] rounded-lg px-2.5 py-1.5 text-xs text-slate-100"
              />
            </div>
            <div>
              <label className="block text-[11px] text-slate-400 mb-1">Duração (s)</label>
              <input
                type="number"
                step="0.5"
                min="1.5"
                max="15"
                value={scene.durationSec}
                onChange={(e) => updateScene(scene.id, { durationSec: Number(e.target.value) || 2.5 })}
                className="w-full bg-[#090c12] border border-[#243046] rounded-lg px-2.5 py-1.5 text-xs text-slate-100"
              />
            </div>
          </div>

          <div>
            <label className="block text-[11px] text-slate-400 mb-1">Voz PT-BR (12 Vozes — Edge &amp; OpenAI)</label>
            <div className="flex gap-1.5">
              <select
                value={scene.voice}
                onChange={(e) => updateScene(scene.id, { voice: e.target.value })}
                className="flex-1 min-w-0 bg-[#090c12] border border-[#243046] rounded-lg px-2 py-1.5 text-xs text-slate-100"
              >
                {VOICES.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.label}
                  </option>
                ))}
              </select>
              <button
                onClick={previewVoice}
                disabled={ttsLoading}
                className="px-2.5 py-1.5 rounded-lg bg-[#182132] hover:bg-[#1f2b42] border border-[#28354d] text-xs text-blue-300 flex items-center gap-1 cursor-pointer shrink-0"
              >
                <Volume2 className="w-3.5 h-3.5" />
                {ttsLoading ? '...' : 'Ouvir'}
              </button>
            </div>
          </div>

          <div>
            <label className="block text-[11px] text-slate-400 mb-1">Fala / Locução PT-BR &amp; Legenda</label>
            <textarea
              rows={2}
              value={scene.speechPtBr}
              onChange={(e) => updateScene(scene.id, { speechPtBr: e.target.value, subtitleText: e.target.value })}
              placeholder="Deixe vazio se quiser apenas música nesta cena..."
              className="w-full bg-[#090c12] border border-[#243046] rounded-lg p-2 text-xs text-slate-100"
            />
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-[11px] text-slate-400 mb-1">Movimento / Efeito</label>
              <select
                value={scene.transition}
                onChange={(e) => updateScene(scene.id, { transition: e.target.value as TransitionType })}
                className="w-full bg-[#090c12] border border-[#243046] rounded-lg px-2 py-1.5 text-xs text-slate-100"
              >
                <option value="zoom_in">Zoom In Suave</option>
                <option value="zoom_out">Zoom Out</option>
                <option value="pan_right">Panorâmica Direita</option>
                <option value="pan_left">Panorâmica Esquerda</option>
                <option value="crossfade">Alternado Automático</option>
                <option value="cut">Corte Seco</option>
              </select>
            </div>
            <div>
              <label className="block text-[11px] text-slate-400 mb-1">Volume Voz ({Math.round(scene.volume * 100)}%)</label>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={scene.volume}
                onChange={(e) => updateScene(scene.id, { volume: Number(e.target.value) })}
                className="w-full mt-2 accent-blue-500"
              />
            </div>
          </div>

          <div>
            <label className="block text-[11px] text-slate-400 mb-1 flex items-center gap-1">
              <Image className="w-3 h-3 text-violet-400" />
              Foto Local / Referência Ambiente &amp; Produto (I2V)
            </label>
            <select
              value={scene.mediaUrl || scene.referenceImageUrl || ''}
              onChange={(e) =>
                updateScene(scene.id, {
                  mediaUrl: e.target.value || undefined,
                  referenceImageUrl: e.target.value || undefined,
                  mediaType: e.target.value ? 'image' : 'ai',
                })
              }
              className="w-full bg-[#090c12] border border-[#243046] rounded-lg px-2 py-1.5 text-xs text-slate-100"
            >
              <option value="">Sem foto fixa (Gerar 100% por IA)</option>
              {imageUploads.map((img) => (
                <option key={img.url} value={img.url}>
                  {img.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-[11px] text-slate-400 mb-1">Prompt Visual IA (Wan 2.2 / I2V)</label>
            <textarea
              rows={2}
              value={scene.visualPromptEn}
              onChange={(e) => updateScene(scene.id, { visualPromptEn: e.target.value })}
              className="w-full bg-[#090c12] border border-[#243046] rounded-lg p-2 text-xs text-slate-100"
            />
          </div>

          <label className="flex items-center gap-2 text-xs text-slate-200 pt-1 cursor-pointer">
            <input
              type="checkbox"
              checked={scene.lipSyncEnabled}
              onChange={(e) => updateScene(scene.id, { lipSyncEnabled: e.target.checked })}
              className="accent-emerald-500"
            />
            Sincronia Labial (LatentSync) na Nuvem
          </label>
        </>
      ) : (
        <div className="text-xs text-slate-500">Selecione uma cena na timeline.</div>
      )}

      <div className="mt-auto pt-3 border-t border-[#1e2738] flex flex-col gap-2.5">
        <div className="text-[11px] font-semibold uppercase tracking-wider text-emerald-400 flex items-center gap-1.5">
          <Music className="w-3.5 h-3.5" />
          Banco de Músicas &amp; Áudio Global
        </div>
        <div className="flex gap-1.5">
          <select
            value={project.musicUrl || '/music-bank/upbeat_reels.mp3'}
            onChange={(e) => setMusicUrl(e.target.value)}
            className="flex-1 min-w-0 bg-[#090c12] border border-[#243046] rounded-lg px-2 py-1.5 text-xs text-slate-100"
          >
            {musicBank.map((m) => (
              <option key={m.url} value={m.url}>
                {m.label}
              </option>
            ))}
          </select>
          <button
            onClick={previewMusic}
            className="px-2.5 py-1.5 rounded-lg bg-[#182132] hover:bg-[#1f2b42] border border-[#28354d] text-xs text-emerald-300 cursor-pointer shrink-0"
          >
            Ouvir
          </button>
        </div>
        <div>
          <label className="block text-[11px] text-slate-400 mb-1">
            Volume da Música ({Math.round(project.musicVolume * 100)}% • Auto-Ducking ativo)
          </label>
          <input
            type="range"
            min="0"
            max="1"
            step="0.05"
            value={project.musicVolume}
            onChange={(e) => setMusicVolume(Number(e.target.value))}
            className="w-full accent-emerald-500"
          />
        </div>
        <label className="flex items-center gap-2 text-xs text-slate-200 cursor-pointer">
          <input
            type="checkbox"
            checked={project.subtitlesEnabled}
            onChange={(e) => setSubtitlesEnabled(e.target.checked)}
            className="accent-blue-500"
          />
          Exibir Legendas Dinâmicas
        </label>
      </div>
    </aside>
  );
}

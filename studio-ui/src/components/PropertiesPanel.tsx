import { Sliders, Trash2, Volume2 } from 'lucide-react';
import { useRef, useState } from 'react';
import { useProjectStore } from '../store/useProjectStore';
import type { TransitionType } from '../types/project';

export function PropertiesPanel() {
  const { project, selectedSceneId, updateScene, removeScene, setSubtitlesEnabled, setMusicVolume } =
    useProjectStore();
  const scene = project.scenes.find((s) => s.id === selectedSceneId);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [ttsLoading, setTtsLoading] = useState(false);

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

  return (
    <aside className="w-80 bg-[#0f141e] border-l border-[#1e2738] flex flex-col shrink-0 overflow-y-auto p-3.5 gap-3">
      <audio ref={audioRef} className="hidden" />
      <div className="flex items-center justify-between border-b border-[#1e2738] pb-2.5">
        <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-200">
          <Sliders className="w-3.5 h-3.5 text-blue-400" />
          Propriedades
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
          <div>
            <label className="block text-[11px] text-slate-400 mb-1">Título da Cena</label>
            <input
              value={scene.title}
              onChange={(e) => updateScene(scene.id, { title: e.target.value })}
              className="w-full bg-[#090c12] border border-[#243046] rounded-lg px-2.5 py-1.5 text-xs text-slate-100"
            />
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-[11px] text-slate-400 mb-1">Personagem</label>
              <input
                value={scene.speaker}
                onChange={(e) => updateScene(scene.id, { speaker: e.target.value })}
                className="w-full bg-[#090c12] border border-[#243046] rounded-lg px-2.5 py-1.5 text-xs text-slate-100"
              />
            </div>
            <div>
              <label className="block text-[11px] text-slate-400 mb-1">Duração (s)</label>
              <input
                type="number"
                step="0.5"
                min="2"
                max="15"
                value={scene.durationSec}
                onChange={(e) => updateScene(scene.id, { durationSec: Number(e.target.value) || 4 })}
                className="w-full bg-[#090c12] border border-[#243046] rounded-lg px-2.5 py-1.5 text-xs text-slate-100"
              />
            </div>
          </div>

          <div>
            <label className="block text-[11px] text-slate-400 mb-1">Voz Neural PT-BR</label>
            <div className="flex gap-1.5">
              <select
                value={scene.voice}
                onChange={(e) => updateScene(scene.id, { voice: e.target.value })}
                className="flex-1 bg-[#090c12] border border-[#243046] rounded-lg px-2 py-1.5 text-xs text-slate-100"
              >
                <option value="pt-BR-FranciscaNeural">Francisca (Feminina)</option>
                <option value="pt-BR-AntonioNeural">Antonio (Masculina)</option>
                <option value="pt-BR-ThalitaNeural">Thalita (Jovem)</option>
              </select>
              <button
                onClick={previewVoice}
                disabled={ttsLoading}
                className="px-2.5 py-1.5 rounded-lg bg-[#182132] hover:bg-[#1f2b42] border border-[#28354d] text-xs text-blue-300 flex items-center gap-1 cursor-pointer"
              >
                <Volume2 className="w-3.5 h-3.5" />
                {ttsLoading ? '...' : 'Ouvir'}
              </button>
            </div>
          </div>

          <div>
            <label className="block text-[11px] text-slate-400 mb-1">Fala PT-BR &amp; Legenda</label>
            <textarea
              rows={2}
              value={scene.speechPtBr}
              onChange={(e) => updateScene(scene.id, { speechPtBr: e.target.value, subtitleText: e.target.value })}
              className="w-full bg-[#090c12] border border-[#243046] rounded-lg p-2 text-xs text-slate-100"
            />
          </div>

          <div>
            <label className="block text-[11px] text-slate-400 mb-1">Prompt Visual (Inglês — Wan 2.2)</label>
            <textarea
              rows={3}
              value={scene.visualPromptEn}
              onChange={(e) => updateScene(scene.id, { visualPromptEn: e.target.value })}
              className="w-full bg-[#090c12] border border-[#243046] rounded-lg p-2 text-xs text-slate-100"
            />
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-[11px] text-slate-400 mb-1">Transição</label>
              <select
                value={scene.transition}
                onChange={(e) => updateScene(scene.id, { transition: e.target.value as TransitionType })}
                className="w-full bg-[#090c12] border border-[#243046] rounded-lg px-2 py-1.5 text-xs text-slate-100"
              >
                <option value="cut">Corte Seco</option>
                <option value="crossfade">Crossfade</option>
                <option value="zoom_in">Zoom Dinâmico</option>
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
        <div className="text-xs text-slate-500">Selecione uma cena na timeline ou biblioteca.</div>
      )}

      <div className="mt-auto pt-3 border-t border-[#1e2738] flex flex-col gap-2">
        <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Global do Projeto</div>
        <label className="flex items-center gap-2 text-xs text-slate-200 cursor-pointer">
          <input
            type="checkbox"
            checked={project.subtitlesEnabled}
            onChange={(e) => setSubtitlesEnabled(e.target.checked)}
            className="accent-blue-500"
          />
          Exibir Legendas Dinâmicas
        </label>
        <div>
          <label className="block text-[11px] text-slate-400 mb-1">
            Volume Trilha Sonora ({Math.round(project.musicVolume * 100)}%)
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
      </div>
    </aside>
  );
}

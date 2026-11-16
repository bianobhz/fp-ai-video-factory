import { Pause, Play, RotateCcw, Sparkles, Video } from 'lucide-react';
import { useEffect } from 'react';
import { useProjectStore } from '../store/useProjectStore';

interface PreviewStageProps {
  previewVideoUrl: string | null;
  onClearPreviewVideo: () => void;
}

export function PreviewStage({ previewVideoUrl, onClearPreviewVideo }: PreviewStageProps) {
  const { project, selectedSceneId, currentTime, isPlaying, setCurrentTime, setIsPlaying } = useProjectStore();
  const totalDuration = Math.max(
    1,
    project.scenes.reduce((acc, s) => acc + s.durationSec, 0)
  );

  useEffect(() => {
    if (!isPlaying) return;
    const id = setInterval(() => {
      setCurrentTime(currentTime + 0.1 >= totalDuration ? 0 : +(currentTime + 0.1).toFixed(1));
    }, 100);
    return () => clearInterval(id);
  }, [isPlaying, currentTime, totalDuration, setCurrentTime]);

  let elapsed = 0;
  let activeScene = project.scenes.find((s) => s.id === selectedSceneId) || project.scenes[0];
  for (const sc of project.scenes) {
    if (currentTime >= elapsed && currentTime < elapsed + sc.durationSec) {
      activeScene = sc;
      break;
    }
    elapsed += sc.durationSec;
  }

  const aspectClass =
    project.format === '9:16'
      ? 'aspect-[9/16] h-[430px]'
      : project.format === '16:9'
      ? 'aspect-[16/9] w-[560px]'
      : 'aspect-square h-[400px]';

  return (
    <main className="flex-1 bg-[#090c12] flex flex-col items-center justify-center p-4 relative overflow-hidden">
      <div className="mb-2 flex items-center gap-2 text-[11px] text-slate-400">
        <span>Pré-visualização • {project.format}</span>
        {previewVideoUrl && (
          <button
            onClick={onClearPreviewVideo}
            className="px-2 py-0.5 rounded bg-[#182132] text-blue-300 hover:bg-[#1f2b42] cursor-pointer"
          >
            Voltar ao Modo Cenas
          </button>
        )}
      </div>

      <div
        className={`${aspectClass} rounded-2xl bg-[#111723] border border-[#243046] shadow-2xl relative overflow-hidden flex flex-col items-center justify-center`}
      >
        {previewVideoUrl ? (
          <video key={previewVideoUrl} src={previewVideoUrl} controls autoPlay className="w-full h-full object-contain bg-black" />
        ) : activeScene ? (
          <>
            <div className="absolute top-3 left-3 px-2.5 py-1 rounded-full bg-black/60 backdrop-blur text-[10px] font-semibold text-blue-300 border border-white/10 flex items-center gap-1">
              <Video className="w-3 h-3" />
              {activeScene.title}
            </div>
            {activeScene.lipSyncEnabled && (
              <div className="absolute top-3 right-3 px-2 py-1 rounded-full bg-emerald-500/20 text-[10px] font-semibold text-emerald-300 border border-emerald-500/30 flex items-center gap-1">
                <Sparkles className="w-3 h-3" />
                Lip-Sync ON
              </div>
            )}

            {activeScene.mediaUrl && activeScene.mediaType === 'image' ? (
              <img src={activeScene.mediaUrl} alt={activeScene.title} className="w-full h-full object-cover" />
            ) : activeScene.mediaUrl && activeScene.mediaType === 'video' ? (
              <video key={activeScene.mediaUrl} src={activeScene.mediaUrl} controls className="w-full h-full object-cover bg-black" />
            ) : (
              <div className="px-6 text-center">
                <div className="w-14 h-14 mx-auto mb-3 rounded-full bg-blue-500/10 border border-blue-500/30 flex items-center justify-center text-blue-400 font-bold text-lg">
                  {activeScene.speaker.slice(0, 2).toUpperCase()}
                </div>
                <div className="text-xs font-semibold text-slate-200 mb-1">{activeScene.speaker}</div>
                <p className="text-[11px] text-slate-400 line-clamp-4">{activeScene.visualPromptEn}</p>
              </div>
            )}

            {project.subtitlesEnabled && activeScene.subtitleText && (
              <div className="absolute bottom-8 left-4 right-4 text-center">
                <span className="inline-block px-3 py-1.5 rounded-lg bg-black/75 text-white text-xs font-semibold shadow-lg">
                  {activeScene.subtitleText}
                </span>
              </div>
            )}
          </>
        ) : (
          <div className="text-xs text-slate-500">Nenhuma cena selecionada</div>
        )}
      </div>

      <div className="mt-3 flex items-center gap-3 bg-[#111723] border border-[#1f293d] px-4 py-1.5 rounded-full">
        <button
          onClick={() => setCurrentTime(0)}
          className="text-slate-400 hover:text-white cursor-pointer"
          title="Voltar ao início"
        >
          <RotateCcw className="w-4 h-4" />
        </button>
        <button
          onClick={() => setIsPlaying(!isPlaying)}
          className="w-8 h-8 rounded-full bg-blue-600 hover:bg-blue-500 text-white flex items-center justify-center cursor-pointer"
        >
          {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 ml-0.5" />}
        </button>
        <span className="text-xs font-mono text-slate-300">
          {currentTime.toFixed(1)}s / {totalDuration.toFixed(1)}s
        </span>
      </div>
    </main>
  );
}

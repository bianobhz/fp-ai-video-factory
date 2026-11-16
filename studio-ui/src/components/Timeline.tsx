import { DndContext, PointerSensor, closestCenter, useSensor, useSensors, type DragEndEvent } from '@dnd-kit/core';
import { SortableContext, horizontalListSortingStrategy, useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { GripVertical, Music, Mic, Video } from 'lucide-react';
import { useEffect, useRef } from 'react';
import WaveSurfer from 'wavesurfer.js';
import { useProjectStore } from '../store/useProjectStore';
import type { SceneItem } from '../types/project';

function SortableSceneBlock({
  scene,
  isSelected,
  onSelect,
}: {
  scene: SceneItem;
  isSelected: boolean;
  onSelect: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({ id: scene.id });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    width: `${Math.max(120, scene.durationSec * 36)}px`,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      onClick={onSelect}
      className={`h-10 rounded-lg px-2.5 flex items-center justify-between gap-1.5 shrink-0 cursor-pointer border select-none ${
        isSelected
          ? 'bg-blue-600/30 border-blue-400 text-white'
          : 'bg-[#1a2942] border-[#2b4269] text-slate-200 hover:border-blue-400/60'
      }`}
    >
      <div className="flex items-center gap-1.5 truncate text-xs font-medium">
        <span {...attributes} {...listeners} className="cursor-grab text-slate-400 hover:text-white">
          <GripVertical className="w-3.5 h-3.5" />
        </span>
        <span className="truncate">{scene.title}</span>
      </div>
      <span className="text-[10px] text-blue-200/80 font-mono">{scene.durationSec}s</span>
    </div>
  );
}

export function Timeline() {
  const { project, selectedSceneId, selectScene, reorderScenes } = useProjectStore();
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }));
  const waveRef = useRef<HTMLDivElement | null>(null);
  const selectedScene = project.scenes.find((s) => s.id === selectedSceneId);

  useEffect(() => {
    if (!waveRef.current || !selectedScene?.audioUrl) return;
    const ws = WaveSurfer.create({
      container: waveRef.current,
      waveColor: '#d97706',
      progressColor: '#fbbf24',
      height: 28,
      barWidth: 2,
      barGap: 1,
      url: selectedScene.audioUrl,
    });
    return () => ws.destroy();
  }, [selectedScene?.audioUrl]);

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIdx = project.scenes.findIndex((s) => s.id === active.id);
    const newIdx = project.scenes.findIndex((s) => s.id === over.id);
    if (oldIdx !== -1 && newIdx !== -1) reorderScenes(oldIdx, newIdx);
  }

  return (
    <section className="h-44 bg-[#0f141e] border-t border-[#1e2738] p-3 flex flex-col gap-2 shrink-0">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-slate-300">Timeline Multifaixa (arraste as cenas para reordenar)</span>
        <span className="text-[11px] text-slate-500">WaveSurfer.js + dnd-kit</span>
      </div>

      <div className="flex-1 flex flex-col gap-1.5 overflow-x-auto">
        <div className="flex items-center gap-2">
          <div className="w-20 text-[11px] text-slate-400 flex items-center gap-1.5 shrink-0">
            <Video className="w-3.5 h-3.5 text-blue-400" />
            Vídeo
          </div>
          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
            <SortableContext items={project.scenes.map((s) => s.id)} strategy={horizontalListSortingStrategy}>
              <div className="flex items-center gap-1.5">
                {project.scenes.map((sc) => (
                  <SortableSceneBlock
                    key={sc.id}
                    scene={sc}
                    isSelected={sc.id === selectedSceneId}
                    onSelect={() => selectScene(sc.id)}
                  />
                ))}
              </div>
            </SortableContext>
          </DndContext>
        </div>

        <div className="flex items-center gap-2">
          <div className="w-20 text-[11px] text-slate-400 flex items-center gap-1.5 shrink-0">
            <Mic className="w-3.5 h-3.5 text-amber-400" />
            Voz PT-BR
          </div>
          <div className="flex-1 h-8 rounded-lg bg-amber-500/15 border border-amber-500/30 px-2 flex items-center overflow-hidden">
            {selectedScene?.audioUrl ? (
              <div ref={waveRef} className="w-full" />
            ) : (
              <span className="text-[11px] text-amber-300/80">
                Narração PT-BR sincronizada (clique em "Ouvir" nas Propriedades para gerar a onda sonora)
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className="w-20 text-[11px] text-slate-400 flex items-center gap-1.5 shrink-0">
            <Music className="w-3.5 h-3.5 text-emerald-400" />
            Música
          </div>
          <div className="flex-1 h-7 rounded-lg bg-emerald-500/15 border border-emerald-500/30 px-2 flex items-center justify-between text-[11px] text-emerald-300">
            <span>
              Trilha Ativa: <strong>{(project.musicUrl || '/music-bank/upbeat_reels.mp3').split('/').pop()}</strong>
            </span>
            <span>Volume: {Math.round(project.musicVolume * 100)}% (Auto-Ducking)</span>
          </div>
        </div>
      </div>
    </section>
  );
}

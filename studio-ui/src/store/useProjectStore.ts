import { create } from 'zustand';
import type { AspectFormat, SceneItem, StudioProject } from '../types/project';

interface ProjectState {
  project: StudioProject;
  selectedSceneId: string | null;
  currentTime: number;
  isPlaying: boolean;
  setProjectTitle: (title: string) => void;
  setFormat: (format: AspectFormat) => void;
  setWorkflow: (workflow: string) => void;
  setSubtitlesEnabled: (enabled: boolean) => void;
  setMusicVolume: (volume: number) => void;
  selectScene: (id: string | null) => void;
  addScene: (partial?: Partial<SceneItem>) => void;
  updateScene: (id: string, patch: Partial<SceneItem>) => void;
  removeScene: (id: string) => void;
  reorderScenes: (oldIndex: number, newIndex: number) => void;
  replaceScenes: (title: string, scenes: SceneItem[]) => void;
  setCurrentTime: (t: number) => void;
  setIsPlaying: (playing: boolean) => void;
}

const initialScenes: SceneItem[] = [
  {
    id: 'scene-1',
    title: 'Abertura — Ana',
    speaker: 'Ana',
    voice: 'pt-BR-FranciscaNeural',
    speechPtBr: 'Você não vai acreditar no que acabou de acontecer lá na reunião.',
    visualPromptEn:
      'Candid 35mm film close-up medium shot of a Brazilian woman in her late 20s in a modern coffee shop speaking excitedly with expressive hand gestures, realistic skin pores, natural window daylight, shallow depth of field',
    durationSec: 4.5,
    transition: 'cut',
    volume: 1,
    subtitleText: 'Você não vai acreditar no que acabou de acontecer lá na reunião.',
    lipSyncEnabled: true,
    status: 'draft',
  },
  {
    id: 'scene-2',
    title: 'Reação — Lucas',
    speaker: 'Lucas',
    voice: 'pt-BR-AntonioNeural',
    speechPtBr: 'Sério? Me conta logo, o que foi que eles decidiram?',
    visualPromptEn:
      'Candid 35mm film close-up medium shot of a Brazilian man in his early 30s in a modern coffee shop leaning forward curiously and asking a question, realistic skin texture, warm ambient cafe lighting, shallow depth of field',
    durationSec: 4.0,
    transition: 'cut',
    volume: 1,
    subtitleText: 'Sério? Me conta logo, o que foi que eles decidiram?',
    lipSyncEnabled: true,
    status: 'draft',
  },
  {
    id: 'scene-3',
    title: 'Fechamento — Ana',
    speaker: 'Ana',
    voice: 'pt-BR-FranciscaNeural',
    speechPtBr: 'Aprovaram tudo! A gente começa o projeto novo já na segunda-feira.',
    visualPromptEn:
      'Candid 35mm film close-up medium shot of the same Brazilian woman smiling warmly with confidence in a coffee shop, natural handheld camera movement, realistic skin pores, shallow depth of field',
    durationSec: 4.5,
    transition: 'crossfade',
    volume: 1,
    subtitleText: 'Aprovaram tudo! A gente começa o projeto novo já na segunda-feira.',
    lipSyncEnabled: true,
    status: 'draft',
  },
];

export const useProjectStore = create<ProjectState>((set) => ({
  project: {
    version: '1.0',
    id: 'proj-default',
    title: 'dialogo_cafe_comercial',
    format: '9:16',
    fps: 30,
    workflow: 'wan22_t2v_14b_vertical_api.json',
    musicVolume: 0.25,
    subtitlesEnabled: true,
    scenes: initialScenes,
  },
  selectedSceneId: initialScenes[0].id,
  currentTime: 0,
  isPlaying: false,

  setProjectTitle: (title) => set((s) => ({ project: { ...s.project, title } })),
  setFormat: (format) => set((s) => ({ project: { ...s.project, format } })),
  setWorkflow: (workflow) => set((s) => ({ project: { ...s.project, workflow } })),
  setSubtitlesEnabled: (subtitlesEnabled) => set((s) => ({ project: { ...s.project, subtitlesEnabled } })),
  setMusicVolume: (musicVolume) => set((s) => ({ project: { ...s.project, musicVolume } })),
  selectScene: (selectedSceneId) => set({ selectedSceneId }),

  addScene: (partial) =>
    set((s) => {
      const idx = s.project.scenes.length + 1;
      const newScene: SceneItem = {
        id: `scene-${Date.now()}`,
        title: partial?.title || `Cena ${idx}`,
        speaker: partial?.speaker || 'Personagem',
        voice: partial?.voice || 'pt-BR-FranciscaNeural',
        speechPtBr: partial?.speechPtBr || '',
        visualPromptEn:
          partial?.visualPromptEn ||
          'Candid 35mm film medium close-up, natural motion, realistic skin pores, shallow depth of field',
        durationSec: partial?.durationSec || 4.5,
        transition: partial?.transition || 'cut',
        volume: partial?.volume ?? 1,
        subtitleText: partial?.subtitleText || partial?.speechPtBr || '',
        lipSyncEnabled: partial?.lipSyncEnabled ?? true,
        status: 'draft',
      };
      return {
        project: { ...s.project, scenes: [...s.project.scenes, newScene] },
        selectedSceneId: newScene.id,
      };
    }),

  updateScene: (id, patch) =>
    set((s) => ({
      project: {
        ...s.project,
        scenes: s.project.scenes.map((sc) => (sc.id === id ? { ...sc, ...patch } : sc)),
      },
    })),

  removeScene: (id) =>
    set((s) => {
      const filtered = s.project.scenes.filter((sc) => sc.id !== id);
      return {
        project: { ...s.project, scenes: filtered },
        selectedSceneId: s.selectedSceneId === id ? filtered[0]?.id ?? null : s.selectedSceneId,
      };
    }),

  reorderScenes: (oldIndex, newIndex) =>
    set((s) => {
      const next = [...s.project.scenes];
      const [moved] = next.splice(oldIndex, 1);
      if (moved) next.splice(newIndex, 0, moved);
      return { project: { ...s.project, scenes: next } };
    }),

  replaceScenes: (title, scenes) =>
    set((s) => ({
      project: { ...s.project, title, scenes },
      selectedSceneId: scenes[0]?.id ?? null,
    })),

  setCurrentTime: (currentTime) => set({ currentTime }),
  setIsPlaying: (isPlaying) => set({ isPlaying }),
}));

export type TransitionType = 'cut' | 'crossfade' | 'zoom_in';
export type AspectFormat = '9:16' | '16:9' | '1:1';

export interface SceneItem {
  id: string;
  title: string;
  speaker: string;
  voice: string;
  speechPtBr: string;
  visualPromptEn: string;
  durationSec: number;
  transition: TransitionType;
  volume: number; // 0..1
  subtitleText: string;
  videoUrl?: string;
  audioUrl?: string;
  lipSyncEnabled: boolean;
  status: 'draft' | 'queued' | 'rendering' | 'ready';
}

export interface StudioProject {
  version: '1.0';
  id: string;
  title: string;
  format: AspectFormat;
  fps: number;
  workflow: string;
  musicUrl?: string;
  musicVolume: number;
  subtitlesEnabled: boolean;
  scenes: SceneItem[];
}

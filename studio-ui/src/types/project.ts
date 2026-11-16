export type TransitionType = 'cut' | 'crossfade' | 'zoom_in' | 'zoom_out' | 'pan_right' | 'pan_left';
export type AspectFormat = '9:16' | '16:9' | '1:1';
export type StudioFrontMode = 'social_ia' | 'school_local' | 'commercial_i2v';

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
  mediaType?: 'ai' | 'image' | 'video';
  mediaUrl?: string;
  referenceImageUrl?: string;
  videoUrl?: string;
  audioUrl?: string;
  lipSyncEnabled: boolean;
  status: 'draft' | 'queued' | 'rendering' | 'ready';
}

export interface StudioProject {
  version: '1.0';
  id: string;
  title: string;
  mode?: StudioFrontMode;
  format: AspectFormat;
  fps: number;
  workflow: string;
  musicUrl?: string;
  musicVolume: number;
  subtitlesEnabled: boolean;
  scenes: SceneItem[];
}

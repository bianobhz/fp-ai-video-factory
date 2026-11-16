import { Bot, Film, FolderOpen, Image, Mic, MicOff, Music, Paperclip, Scissors, Send } from 'lucide-react';
import { useRef, useState } from 'react';
import { useProjectStore } from '../store/useProjectStore';
import type { SceneItem } from '../types/project';

interface FinalVideo {
  name: string;
  url: string;
  size_mb: number;
}

interface UploadItem {
  name: string;
  url: string;
  kind: 'image' | 'video' | 'audio';
  size_mb: number;
}

interface ChatMsg {
  role: 'user' | 'assistant';
  content: string;
}

interface LibraryPanelProps {
  videos: FinalVideo[];
  uploads: UploadItem[];
  onRefreshUploads: () => void;
  onSelectPreviewVideo: (url: string) => void;
  onEnqueue: () => Promise<void>;
  onOpenProduceModal: () => Promise<void>;
  onLocalRender: () => Promise<void>;
}

export function LibraryPanel({
  videos,
  uploads,
  onRefreshUploads,
  onSelectPreviewVideo,
  onEnqueue,
  onOpenProduceModal,
  onLocalRender,
}: LibraryPanelProps) {
  const [tab, setTab] = useState<'copilot' | 'media'>('copilot');
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [listening, setListening] = useState(false);
  const recogRef = useRef<any>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [messages, setMessages] = useState<ChatMsg[]>([
    {
      role: 'assistant',
      content:
        'Olá! Sou o Agente do Studio v3. Posso criar cenas IA, montar Reels com suas fotos/vídeos anexados, cortar silêncios, adicionar música e exportar localmente via FFmpeg. O que vamos fazer?',
    },
  ]);

  const {
    project,
    selectedSceneId,
    selectScene,
    addScene,
    replaceScenes,
    updateScene,
    setProjectTitle,
    setFormat,
    setMusicUrl,
    setMusicVolume,
    setSubtitlesEnabled,
  } = useProjectStore();

  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    setLoading(true);
    try {
      const uploadedNames: string[] = [];
      for (const file of files) {
        const b64 = await new Promise<string>((resolve) => {
          const reader = new FileReader();
          reader.onload = () => resolve(String(reader.result || ''));
          reader.readAsDataURL(file);
        });
        const res = await fetch('/api/upload', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ filename: file.name, data_base64: b64 }),
        });
        const data = await res.json();
        if (data.ok) uploadedNames.push(file.name);
      }
      onRefreshUploads();
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: `Arquivos anexados ao projeto local: ${uploadedNames.join(', ')}` },
      ]);
    } finally {
      setLoading(false);
      e.target.value = '';
    }
  }

  function toggleVoiceInput() {
    const SpeechRec = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRec) {
      alert('Seu navegador não suporta ditado por voz. Use Chrome ou Edge.');
      return;
    }
    if (listening && recogRef.current) {
      recogRef.current.stop();
      setListening(false);
      return;
    }
    const rec = new SpeechRec();
    rec.lang = 'pt-BR';
    rec.interimResults = true;
    rec.continuous = true;
    rec.onresult = (ev: any) => {
      let transcript = '';
      for (let i = 0; i < ev.results.length; i++) transcript += ev.results[i][0].transcript;
      setInput(transcript);
    };
    rec.onend = () => setListening(false);
    rec.onerror = () => setListening(false);
    recogRef.current = rec;
    rec.start();
    setListening(true);
  }

  async function runAutoCut(filename: string) {
    setLoading(true);
    try {
      const res = await fetch('/api/local/auto-cut', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename }),
      });
      const data = await res.json();
      onRefreshUploads();
      return data;
    } finally {
      setLoading(false);
    }
  }

  async function sendChat() {
    const text = input.trim();
    if (!text || loading) return;
    const nextHistory: ChatMsg[] = [...messages, { role: 'user', content: text }];
    setMessages(nextHistory);
    setInput('');
    setLoading(true);

    try {
      const res = await fetch('/api/ai-agent', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: nextHistory, project }),
      });
      const data = await res.json();
      if (!data.ok) {
        setMessages([...nextHistory, { role: 'assistant', content: `Erro: ${data.error}` }]);
        return;
      }

      for (const act of data.actions || []) {
        if (act.name === 'replace_scenes') {
          const mapped: SceneItem[] = (act.args.scenes || []).map((sc: any, i: number) => ({
            id: `scene-${Date.now()}-${i}`,
            title: `${sc.speaker || 'Cena'} ${i + 1}`,
            speaker: sc.speaker || 'Personagem',
            voice: sc.voice || 'pt-BR-FranciscaNeural',
            speechPtBr: sc.speech_ptbr || '',
            visualPromptEn: sc.visual_prompt_en || '',
            durationSec: sc.durationSec || 4.5,
            transition: 'cut',
            volume: 1,
            subtitleText: sc.speech_ptbr || '',
            mediaType: 'ai',
            lipSyncEnabled: true,
            status: 'draft',
          }));
          replaceScenes(act.args.title || project.title, mapped);
        } else if (act.name === 'add_local_media_scenes') {
          const files: string[] = act.args.filenames || [];
          const dur = act.args.durationSec || 2.5;
          const mapped: SceneItem[] = files.map((fname, i) => {
            const isImg = /\.(jpg|jpeg|png|webp)$/i.test(fname);
            return {
              id: `local-${Date.now()}-${i}`,
              title: fname.slice(0, 18),
              speaker: 'Local',
              voice: 'pt-BR-FranciscaNeural',
              speechPtBr: '',
              visualPromptEn: '',
              durationSec: dur,
              transition: 'crossfade',
              volume: 1,
              subtitleText: '',
              mediaType: isImg ? 'image' : 'video',
              mediaUrl: `/uploads/${fname}`,
              lipSyncEnabled: false,
              status: 'ready',
            };
          });
          if (act.args.replace !== false) {
            replaceScenes(act.args.title || project.title, mapped);
          } else {
            mapped.forEach((m) => addScene(m));
          }
        } else if (act.name === 'set_music') {
          setMusicUrl(`/uploads/${act.args.filename}`);
          if (act.args.volume !== undefined) setMusicVolume(act.args.volume);
        } else if (act.name === 'auto_cut_video') {
          const cutRes = await runAutoCut(act.args.filename);
          if (cutRes?.ok) {
            addScene({
              title: `Cut: ${cutRes.filename.slice(0, 14)}`,
              mediaType: 'video',
              mediaUrl: cutRes.url,
              lipSyncEnabled: false,
            });
          }
        } else if (act.name === 'render_local_video') {
          await onLocalRender();
        } else if (act.name === 'update_scene') {
          const idx = (act.args.scene_index || 1) - 1;
          const target = project.scenes[idx];
          if (target) {
            const patch: Partial<SceneItem> = {};
            if (act.args.speechPtBr !== undefined) {
              patch.speechPtBr = act.args.speechPtBr;
              patch.subtitleText = act.args.speechPtBr;
            }
            if (act.args.visualPromptEn !== undefined) patch.visualPromptEn = act.args.visualPromptEn;
            if (act.args.voice !== undefined) patch.voice = act.args.voice;
            if (act.args.durationSec !== undefined) patch.durationSec = act.args.durationSec;
            if (act.args.lipSyncEnabled !== undefined) patch.lipSyncEnabled = act.args.lipSyncEnabled;
            updateScene(target.id, patch);
          }
        } else if (act.name === 'set_project_settings') {
          if (act.args.title) setProjectTitle(act.args.title);
          if (act.args.format) setFormat(act.args.format);
          if (act.args.subtitlesEnabled !== undefined) setSubtitlesEnabled(act.args.subtitlesEnabled);
        } else if (act.name === 'save_to_queue') {
          await onEnqueue();
        } else if (act.name === 'open_produce_modal') {
          await onOpenProduceModal();
        }
      }

      setMessages([...nextHistory, { role: 'assistant', content: data.reply }]);
    } catch (err: any) {
      setMessages([...nextHistory, { role: 'assistant', content: `Falha de conexão: ${err.message}` }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <aside className="w-80 bg-[#0f141e] border-r border-[#1e2738] flex flex-col shrink-0 overflow-hidden">
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept="image/*,video/*,audio/*"
        className="hidden"
        onChange={handleFileUpload}
      />

      <div className="flex border-b border-[#1e2738]">
        <button
          onClick={() => setTab('copilot')}
          className={`flex-1 py-2.5 text-xs font-semibold flex items-center justify-center gap-1.5 cursor-pointer ${
            tab === 'copilot' ? 'text-blue-400 border-b-2 border-blue-500 bg-[#141b29]' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Bot className="w-3.5 h-3.5" />
          Agente IA
        </button>
        <button
          onClick={() => setTab('media')}
          className={`flex-1 py-2.5 text-xs font-semibold flex items-center justify-center gap-1.5 cursor-pointer ${
            tab === 'media' ? 'text-blue-400 border-b-2 border-blue-500 bg-[#141b29]' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <FolderOpen className="w-3.5 h-3.5" />
          Mídias ({uploads.length + videos.length})
        </button>
      </div>

      {tab === 'copilot' ? (
        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="flex-1 overflow-y-auto p-3 space-y-2.5">
            {messages.map((m, i) => (
              <div
                key={i}
                className={`p-2.5 rounded-xl text-xs leading-relaxed ${
                  m.role === 'user'
                    ? 'bg-blue-600/20 border border-blue-500/30 text-blue-100 ml-4'
                    : 'bg-[#141b29] border border-[#222d42] text-slate-200 mr-2'
                }`}
              >
                {m.content}
              </div>
            ))}
          </div>

          <div className="p-2.5 border-t border-[#1e2738] bg-[#0c1018]">
            <div className="flex gap-1.5">
              <button
                onClick={() => fileInputRef.current?.click()}
                title="Anexar fotos, vídeos ou músicas do PC"
                className="px-2.5 py-2 rounded-lg bg-[#182132] border border-[#28354d] text-slate-300 hover:text-white cursor-pointer"
              >
                <Paperclip className="w-3.5 h-3.5" />
              </button>
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && sendChat()}
                placeholder="Peça ou anexe mídias..."
                className="flex-1 min-w-0 bg-[#090c12] border border-[#243046] rounded-lg px-2.5 py-2 text-xs text-slate-100 focus:outline-none focus:border-blue-500"
              />
              <button
                onClick={toggleVoiceInput}
                title={listening ? 'Parar ditado' : 'Falar instrução (PT-BR)'}
                className={`px-2.5 py-2 rounded-lg border cursor-pointer ${
                  listening
                    ? 'bg-red-600/30 border-red-500 text-red-300 animate-pulse'
                    : 'bg-[#182132] border-[#28354d] text-slate-300 hover:text-white'
                }`}
              >
                {listening ? <MicOff className="w-3.5 h-3.5" /> : <Mic className="w-3.5 h-3.5" />}
              </button>
              <button
                onClick={sendChat}
                disabled={loading}
                className="px-2.5 py-2 rounded-lg bg-gradient-to-r from-blue-600 to-violet-600 text-white cursor-pointer disabled:opacity-50"
              >
                <Send className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          <div className="max-h-36 overflow-y-auto border-t border-[#1e2738] p-2.5 space-y-1">
            <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 mb-1">
              Cenas ({project.scenes.length})
            </div>
            {project.scenes.map((sc, i) => (
              <button
                key={sc.id}
                onClick={() => selectScene(sc.id)}
                className={`w-full text-left px-2 py-1.5 rounded-md text-[11px] flex justify-between cursor-pointer ${
                  selectedSceneId === sc.id ? 'bg-blue-600/20 text-blue-200' : 'text-slate-400 hover:bg-[#141b29]'
                }`}
              >
                <span className="truncate">{i + 1}. {sc.title}</span>
                <span>{sc.durationSec}s</span>
              </button>
            ))}
          </div>
        </div>
      ) : (
        <div className="flex-1 p-3 overflow-y-auto flex flex-col gap-3">
          <button
            onClick={() => fileInputRef.current?.click()}
            className="w-full py-2 rounded-lg bg-[#182132] hover:bg-[#1f2b42] border border-[#2a3852] text-xs font-semibold text-blue-300 flex items-center justify-center gap-1.5 cursor-pointer"
          >
            <Paperclip className="w-3.5 h-3.5" />
            Anexar Fotos, Vídeos ou Músicas
          </button>

          {uploads.length > 0 && (
            <div className="space-y-1.5">
              <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                Arquivos Anexados ({uploads.length})
              </div>
              {uploads.map((u) => (
                <div key={u.name} className="p-2 rounded-lg bg-[#141b29] border border-[#1f293d] text-xs space-y-1.5">
                  <div className="flex items-center gap-1.5 font-medium text-slate-200 truncate">
                    {u.kind === 'image' ? (
                      <Image className="w-3.5 h-3.5 text-blue-400 shrink-0" />
                    ) : u.kind === 'audio' ? (
                      <Music className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                    ) : (
                      <Film className="w-3.5 h-3.5 text-violet-400 shrink-0" />
                    )}
                    <span className="truncate">{u.name}</span>
                  </div>
                  <div className="flex gap-1.5">
                    {u.kind === 'audio' ? (
                      <button
                        onClick={() => setMusicUrl(u.url)}
                        className="px-2 py-1 rounded bg-emerald-600/20 text-emerald-300 text-[10px] cursor-pointer"
                      >
                        + Usar como Música
                      </button>
                    ) : (
                      <button
                        onClick={() =>
                          addScene({
                            title: u.name.slice(0, 16),
                            mediaType: u.kind === 'image' ? 'image' : 'video',
                            mediaUrl: u.url,
                            durationSec: 3,
                            lipSyncEnabled: false,
                          })
                        }
                        className="px-2 py-1 rounded bg-blue-600/20 text-blue-300 text-[10px] cursor-pointer"
                      >
                        + Timeline
                      </button>
                    )}
                    {u.kind === 'video' && (
                      <button
                        onClick={() => runAutoCut(u.name)}
                        className="px-2 py-1 rounded bg-amber-600/20 text-amber-300 text-[10px] flex items-center gap-1 cursor-pointer"
                      >
                        <Scissors className="w-3 h-3" />
                        Auto-Cut
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="space-y-1.5">
            <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
              Vídeos Exportados (outputs/final)
            </div>
            {videos.map((v) => (
              <button
                key={v.name}
                onClick={() => onSelectPreviewVideo(v.url)}
                className="w-full text-left p-2.5 rounded-lg bg-[#141b29] border border-[#1f293d] hover:border-blue-500/50 transition cursor-pointer"
              >
                <div className="flex items-center gap-2 text-xs font-semibold text-slate-200 truncate">
                  <Film className="w-3.5 h-3.5 text-blue-400 shrink-0" />
                  <span className="truncate">{v.name}</span>
                </div>
                <div className="text-[11px] text-slate-400 mt-1">{v.size_mb} MB • Assistir</div>
              </button>
            ))}
          </div>
        </div>
      )}
    </aside>
  );
}

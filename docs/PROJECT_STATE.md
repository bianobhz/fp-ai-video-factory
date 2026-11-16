# FP AI Video Factory — Estado Atual do Projeto (Studio v3.1)

> **Instrução para qualquer nova sessão/modelo:** leia este arquivo antes de propor ou executar qualquer alteração.

## 1. Visão de Negócio (3 Frentes Integradas no Studio v3.1)
1. **Frente 1 — Redes Sociais 100% IA (`social_ia`):** vídeos curtos (15–30s) ultra-realistas com diálogos, 12 vozes PT-BR (Edge Neural + OpenAI TTS) e sincronia labial (`LatentSync`) gerados em lote na Vast.ai.
2. **Frente 2 — Cliente Colégio (`school_local`):** montagem rápida de Reels no PC local a partir de fotos/takes, com 4 movimentos cinematográficos alternados (`zoom_in`, `pan_right`, `zoom_out`, `pan_left`), fades suaves e Banco de Músicas integrado.
3. **Frente 3 — Produção Comercial (`commercial_i2v`):** peças publicitárias usando fotos de ambiente real e produto do cliente (`workflows/wan21_i2v_14b_vertical_api.json` + `LatentSync`).

## 2. O que foi auditado, corrigido e validado na v3.1
- **Correção Crítica de Performance e Duração no FFmpeg (`studio_api.py`):**
  - Removido `-loop 1` antes de `-i` que multiplicava `63 frames × 75 frames = 4.725 frames` (157s por foto / 615 MB) e re-decodificava JPEGs de 14 MB 75 vezes por segundo.
  - Agora cada foto de 14 MB é decodificada **uma única vez**, renderizando em **~2,4s por foto** (85× mais rápido) com duração exata (`2.5s` por foto).
- **Auto-Probing de GPU Local (`_get_video_encoder_args`):**
  - Testa `h264_nvenc` automaticamente; como o driver Nvidia atual (API 13.0 vs 13.1 exigido pelo FFmpeg) recusa NVENC, usa fallback seguro `libx264 -preset superfast -crf 20` sem quebrar, ativando `h264_nvenc` automaticamente assim que o driver/hardware for atualizado.
- **Banco Local de Músicas (`outputs/music_bank/`) + Garantia Anti-Vídeo-Mudo:**
  - 4 trilhas instrumentais integradas (`upbeat_reels.mp3`, `lofi_school.mp3`, `corporate_clean.mp3`, `cinematic_warm.mp3`) + suporte a uploads de áudio.
  - Validação estrita na tool `set_music` (impede passar `.jpg` como áudio) e fallback automático para `upbeat_reels.mp3` com *auto-ducking*.
- **Catálogo de 12 Vozes PT-BR:** 8 vozes Microsoft Edge Neural + 4 vozes OpenAI TTS (`nova`, `onyx`, `alloy`, `shimmer`).
- **Suporte a I2V 14B (Ambiente / Produto):** `workflows/wan21_i2v_14b_vertical_api.json` + seletor de Foto de Referência nas Propriedades da Cena.

## 3. Decisões Travadas
- **Hardware Local:** Ryzen 5 5600 + 64 GB RAM + GPU 4 GB VRAM para interface, Agente IA, TTS e FFmpeg (`1080×1920`).
- **Trava Financeira Vast.ai:** disco `50 GB` padrão; nenhuma instância sobe sem confirmação no Modal de Autorização mostrando GPU + US$/hora; autodestruição imediata após o término da fila.

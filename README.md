# FP AI Video Factory

Pipeline híbrida, descartável e escalável (**"liga, puxa, gera e destrói"**) para produção de vídeos curtos hiper-realistas com IA (TikTok, Reels, YouTube Shorts).

**Princípio profissional:** cada peça deve respeitar as referências reais do produto e do ambiente e só é considerada pronta depois de revisão visual, temporal, sonora e de marca. Consulte [docs/production-standard.md](docs/production-standard.md).

## Arquitetura
- **Nuvem (Vast.ai):** GPU 24 GB VRAM sob demanda apenas para inferência pesada no ComfyUI (`80–100 GB` de disco recomendados).
- **Google Drive:** Cofre de modelos pesados (`IA_Studio/models/`) e destino dos vídeos gerados (`IA_Studio/outputs/`).
- **Local:** Orquestração, scripts Python/FFmpeg, pós-produção, cortes, áudio e legendas.
- **GitHub + GHCR:** Imagem Docker pública (`ghcr.io/bianobhz/fp-ai-video-factory:latest`) construída via GitHub Actions.

---

## 1. Configurar `rclone` localmente

1. Instale o `rclone` na sua máquina local e configure o remote chamado `gdrive` apontando para o seu Google Drive:
   ```bash
   rclone config
   ```
2. Converta o arquivo `rclone.conf` para Base64 (sem quebras de linha):
   - **Linux / macOS:**
     ```bash
     base64 -w 0 ~/.config/rclone/rclone.conf
     ```
   - **Windows (PowerShell):**
     ```powershell
     [Convert]::ToBase64String([IO.File]::ReadAllBytes("$env:APPDATA\rclone\rclone.conf"))
     ```

> **Segurança:** Nunca faça commit do `rclone.conf` nem dê `echo` da variável `RCLONE_CONF_BASE64` nos logs.

---

## 2. Deploy na Vast.ai

1. Escolha uma instância com **24 GB VRAM** e **80–100 GB** de disco.
2. Use a imagem Docker pública:
   ```text
   ghcr.io/bianobhz/fp-ai-video-factory:latest
   ```
3. Exponha a porta `8188` (ComfyUI).
4. Configure as variáveis de ambiente na Vast.ai:
   - `RCLONE_CONF_BASE64`: `<seu-base64-aqui>`
   - `RCLONE_REMOTE`: `gdrive` (padrão)
   - `DRIVE_MODELS_PATH`: `IA_Studio/models` (padrão)
   - `MODELS_TO_DOWNLOAD`: lista separada por vírgulas dos modelos necessários para a sessão, por exemplo:
     ```text
     checkpoints/flux1-dev.safetensors,vae/ae.safetensors
     ```

O container irá decodificar o `rclone.conf` em memória/arquivo seguro (`chmod 600`), baixar **apenas** os modelos listados em `MODELS_TO_DOWNLOAD` e iniciar o ComfyUI na porta `8188`.

---

## 3. Gerar uma história com várias cenas

O painel gera uma tomada por solicitação. Para montar uma narrativa longa com continuidade visual, use o gerador em lote. Cada prompt do storyboard vira uma tomada; o script baixa os frames, concatena as cenas, queima as legendas e produz um MP4 vertical.

Exemplo de história de 40 segundos:

```powershell
python scripts/story_batch.py workflows/stories/cafe_cuidado_40s.json --server http://IP-DA-VAST:PORTA
```

O endpoint precisa usar a porta pública mapeada para `8188` pela Vast.ai. A história exemplo cria personagens fictícios fotorrealistas; a consistência de rosto entre tomadas independentes pode variar. Para uma trilha, passe um arquivo de áudio que você tenha direito de publicar com `--audio caminho\trilha.mp3`.

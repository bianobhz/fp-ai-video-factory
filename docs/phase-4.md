# Fase 4: pipeline de vídeo Wan 2.1

O workflow `workflows/wan21_t2v_vertical_api.json` usa nós nativos do ComfyUI; portanto, esta versão não instala custom nodes adicionais. O exemplo oficial do Wan 2.1 também usa nós nativos. Isso evita manter dependências de terceiros que o grafo não usa.

## Modelos

Coloque os arquivos nos diretórios indicados:

- `wan2.1_t2v_1.3B_fp16.safetensors` em `models/diffusion_models/`
- `umt5_xxl_fp8_e4m3fn_scaled.safetensors` em `models/text_encoders/`
- `wan_2.1_vae.safetensors` em `models/vae/`

Para baixar via Rclone no container, configure `MODELS_TO_DOWNLOAD` com:

```text
diffusion_models/wan2.1_t2v_1.3B_fp16.safetensors,text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors,vae/wan_2.1_vae.safetensors
```

O workflow gera 33 frames em 480x832 (vertical, 16 fps inicial) com Wan 2.1 T2V 1.3B. Altere os prompts e `length` no JSON para cada job. A saída final é redimensionada pelo `postprocess.py` para 1080x1920/30 fps.

## Executar

Com o endpoint ComfyUI da instância Vast.ai acessível:

```bash
python3 scripts/pipeline.py --server https://SEU-ENDPOINT:8188
```

Com música, legenda e codificação NVENC:

```bash
python3 scripts/pipeline.py --server https://SEU-ENDPOINT:8188 --audio assets/trilha.mp3 --subtitles assets/legenda.srt --nvenc
```

Arquivos brutos, frames e vídeo intermediário ficam em `outputs/raw/<id>/`; o MP4 pronto fica em `outputs/final/`. A pasta bruta é mantida para depuração. Requer FFmpeg no host local e uma GPU compatível com NVENC se `--nvenc` for usado.

## Dependências e limites

- O Dockerfile atual instala o ComfyUI-Manager, mas o workflow padrão não depende de custom nodes.
- O prompt inicial é um exemplo genérico hiper-realista; revise prompt, seed, duração e orçamento de inferência antes de uma produção.
- A resolução é 480x832 durante geração para manter o fluxo acessível. O pós-processamento amplia para 1080x1920; isso não adiciona detalhes reais como um upscaler dedicado.
- Use uma imagem de container atualizada com os nós Wan 2.1 nativos do ComfyUI e exponha a porta 8188. Modelos são baixados separadamente para não inflar a imagem.

Exemplo e requisitos de modelo: [ComfyUI Wan 2.1 examples](https://github.com/comfyanonymous/ComfyUI_examples/tree/master/wan).

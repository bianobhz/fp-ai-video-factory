# Princípio de produção profissional

## Princípio

Cada peça deve parecer uma produção publicitária intencional e representar com fidelidade o produto, a marca e o ambiente fornecidos. O vídeo só pode ser marcado como pronto depois de revisão visual, temporal, sonora e de marca. Um prompt longo, sozinho, não garante esse padrão.

## O que o cliente fornece

- Fotos do produto em boa resolução, de frente e em ângulos úteis; fotos de embalagem e detalhes quando existirem.
- Foto ou vídeo curto do ambiente real que deve aparecer na peça.
- Logo em PNG transparente ou vetor, cores, texto aprovado e restrições de uso.
- Objetivo, público, chamada para ação e proporção/duração de publicação.

Manter esses arquivos como referências aprovadas do projeto. Não pedir ao modelo que invente textos, rótulos, preços, logotipos ou detalhes funcionais do produto.

## Fluxo de produção

1. **Briefing e roteiro:** definir o gancho, a promessa visual, as ações, a chamada final e o que não pode mudar.
2. **Composição de referência:** criar uma imagem-base aprovada com o produto e o ambiente corretos. Quando a fidelidade do produto for crítica, preservar a foto real do produto por composição, máscara ou camada de pós-produção.
3. **Animação por referência:** usar image-to-video ou fluxo equivalente para animar a imagem-base. Reutilizar referências aprovadas entre cenas para reduzir mudanças de rosto, roupa, cenário e produto.
4. **Geração em tomadas curtas:** produzir tomadas de aproximadamente 4–5 segundos, com uma ação principal, enquadramento e movimento de câmera definidos. Evitar pedir várias ações ou interações complexas no mesmo clipe.
5. **Revisão por tomada:** conferir primeiro quadro, último quadro, movimento, mãos, rostos, embalagem, marca e continuidade. Regerar ou corrigir apenas as tomadas reprovadas.
6. **Montagem e som:** montar os cortes, aplicar textos e logos reais, locução, ambiência, efeitos sincronizados e música com licença adequada.
7. **Entrega:** conferir duração, 9:16, 1080×1920, 30 fps, legibilidade em tela de celular e exportação MP4 antes de marcar como pronto.

## Controle de qualidade

Uma tomada é reprovada se houver qualquer um destes problemas:

- O produto muda de forma, cor, embalagem, rótulo ou proporção.
- Rosto, roupa, cabelo ou cenário mudam sem motivo entre planos que deveriam ser contínuos.
- Mãos, contato entre pessoas ou uso do produto parecem incorretos.
- Há cintilação, deformação, objetos flutuando, movimento congelado ou câmera instável.
- Texto ou logo gerado pelo modelo aparece ilegível ou diferente do material aprovado.
- Voz, ruído ambiente, música ou efeitos brigam entre si ou não combinam com a ação.

Não esconder defeitos com upscale ou compressão. Corrigir a referência, simplificar a ação, regenerar a tomada ou ajustar a montagem.

## Limites do protótipo atual

O workflow `wan21_t2v_vertical_api.json` usa Wan 2.1 T2V 1.3B, texto-para-vídeo, em 480×832 e 81 frames por tomada. Ele é adequado para protótipos e testes rápidos. Como cada tomada é gerada independentemente a partir de texto, ele não garante identidade consistente entre cenas nem fidelidade exata de produto ou ambiente.

Para campanhas baseadas em fotos reais, a próxima evolução é um workflow image-to-video, acompanhado de composição do produto e revisão por tomada. O modelo e as configurações devem ser validados na GPU disponível antes de prometer prazo ou fidelidade.

## Regra de status

Usar estes rótulos no projeto:

- **Rascunho:** ideia, prompt ou storyboard ainda não gerado.
- **Teste técnico:** geração confirma que o pipeline funciona, sem aprovação de qualidade para cliente.
- **Em revisão:** vídeo renderizado aguardando inspeção de imagem, movimento, som e marca.
- **Pronto para publicação:** passou por todos os itens de controle de qualidade e foi aprovado para o canal definido.

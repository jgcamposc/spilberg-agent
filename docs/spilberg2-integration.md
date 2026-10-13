# Spilberg 2.0 — core, uso e integração

## Arquitetura aplicada

O core mantém os planos auditáveis e a aprovação humana. O render padrão continua aceitando os efeitos existentes. O relógio da fonte é lido pelo FFprobe e preservado como razão exata (por exemplo24000/1001), sem arredondamento a duas casas ou conversão implícita de zoom para30FPS. Os cortes referenciam o master original e rebaseiam PTS de vídeo/áudio; renderizações não alteram velocidade por padrão.

O perfil `cibo` passa pela mesma execução de plano aprovado e usa `spilberg2_engine`: análise facial por mediana somente no intervalo escolhido, corte do master, abertura zoom/blur sobre o relógio do vídeo, filmburn, Cal Sans em streams RGB/alpha, cliques e capa separada. A abertura sobrepõe os primeiros frames; não troca trechos por concatenação de duração aproximada. Não presume que detecção facial identifica host/convidado ou quem fala.

## Seleção do perfil

Em um EditPlan existente, acrescentar:

```json
{
  "render_profile": "cibo",
  "render_encoder": "auto"
}
```

Esses campos complementam o plano: fonte, segmentos, efeitos e aprovação continuam obrigatórios. A escolha de hardware em `render_encoder` aplica-se ao perfil CIBO; `standard` mantém CPU e rejeita uma escolha de hardware que não executaria. `cibo` aceita um corte vertical por plano, legendas do corte inteiro e headline da capa. O estilo de legenda deve ser `cibo`, sem parâmetros de cor/fonte conflitantes; intervalos parciais exigem `standard`. Efeitos adicionais, montagens com vários segmentos ou formato horizontal exigem `standard`; combinações não suportadas são rejeitadas explicitamente. Não são descartadas silenciosamente.

O fluxo normal `prepare → submit-plan → approve → finish` preserva essa escolha. `finish` entrega vídeo, capa e recibo de render no diretório final e registra seus hashes. Retomada completa a promoção de arquivos após checkpoint; uma versão final divergente não é substituída.

Para uso técnico direto, depois da instalação local:

```bash
spilberg2 --master master.mp4 --start 10 --end 20 --output versao-01.mp4   --caps-json captions.json --headline "UMA IDEIA CENTRAL" --encoder auto
```

O JSON de legendas usa tempos relativos ao corte: `s`, `e`, `words`, `flags` e, quando disponíveis, `word_starts`. Não altera a lista fornecida pelo chamador. Quando há timestamps de palavras, a entrada cinética e os destaques sonoros usam esses tempos. Sem eles, o sistema mantém uma legenda/clique por frase; não fabrica sincronismo palavra a palavra. Legenda que cruza a seleção sem tempos individuais pede correção do limite/transcrição.

Saídas: MP4, `.cover.jpg` quando existe headline e `.render.json`. A headline permanece fora do vídeo por padrão. `--embed-cover` é uma opção explícita de compatibilidade que acrescenta um frame e silêncio correspondente; não deve ser ativada pela Content Hub automaticamente. `--no-intro`, `--no-filmburn`, `--no-clicks` permitem acabamento simples.

## Dependências e portabilidade

Pillow é uma dependência declarada. FFmpeg e FFprobe podem ser configurados por `SPILBERG_FFMPEG`/`SPILBERG_FFPROBE`. Para assets locais, use `--assets-dir` ou `SPILBERG_CIBO_ASSETS`, contendo:

- `CalSans-Regular.ttf`
- `filmburn_blue.mp4`
- `click.wav`

Na operação atual, a pasta CIBO irmã do repositório é reconhecida. Os assets não são copiados para o Git. Disponibilidade/licença desses arquivos deve acompanhar cada instalação. O diagnóstico `spilberg doctor` informa dependências e recursos presentes, sem baixar mídia em runtime.

`auto` usa VideoToolbox no macOS e CPU em outras plataformas. `cpu` e `videotoolbox` são escolhas explícitas. Falha de hardware não muda o plano silenciosamente; selecionarCPU exige nova tentativa consciente. Não há garantia universal de taxa de render100FPS.

## Contrato para Content Hub

`spilberg.contenthub_adapter` recebe o contrato do worker de prévia já utilizado pela Content Hub (`source`, `asset`, `clip`, `cues`, `options`, `output`, `report`):

```bash
python -m spilberg.contenthub_adapter render-request.json
```

Retorna recibo com `output`, `captionsBurned`, `engine` e `qa`. A Content Hub deve escolher o renderer explicitamente, preservar sua fila/checkpoints/IDs e considerar a revisão do motor na assinatura da mídia. Quando o pedido já contém `options.captionStyle`, o adaptador deixa as legendas para o finalizador compartilhado e retorna `captionsBurned=false`, preservando o estilo escolhido. Sem estilo compartilhado, aplica Cal Sans e retorna `captionsBurned=true`; nessa situação o finalizador não deve queimar legendas novamente. Capa, textos, aprovação e publicação continuam sob responsabilidade do app.

**O adaptador foi testado; o app em produção não foi trocado nesta entrega.** Sua adoção na interface ainda exige seleção de preset/configuração, vínculo de versões e piloto comparativo. Manter os enquadramentos existentes para comparação. Em edição com remoção de pausas ou vários trechos, transportar o mapa de tempos e o plano do master antes de chamar esse renderer; não usar uma cópia intermediária como se fosse o original.

## Validações desta entrega

- Suíte ampliada com renders de24,30 e24000/1001FPS; corte+zoom mantém a razão nativa.
- Pipeline CIBO completo em três taxas, com saída decodificável, duração de áudio/vídeo conferida, capa separada e dados de legenda preservados.
- Teste de entrada visual das palavras pelos timestamps e sinal sintético flash/pulso sonoro para alinhamento após o corte.
- Fluxo aprovado atéLOCAL_READY e adaptador de prévia; perfis incompatíveis, dados fora do corte, saída existente e aprovação pendente são bloqueados.
- Vídeos de teste gerados localmente; testes do compositor exigem assets CIBO e declaram essa dependência. Não representam homologação editorial de um podcast completo ou de todas as capturas VFR/HDR/rotação.

A verificação de relógio e decodificação não garante que uma fala foi escolhida corretamente. A edição editorial, seleção da pessoa, transcrição e conferência perceptiva continuam necessárias.

## Preservação

Branch de trabalho: `feature/spilberg2-native-master`. Motor fornecido preservado em `.local/spilberg2-upgrade/spilberg2_engine.original.py`, fora do Git. Skills originais e mídia preservadas. Nenhuma API paga, publicação, mensagem externa ou alteração do vault foi necessária.

## Revisão independente

Foram reproduzidos e corrigidos três problemas: o estilo compartilhado da Content Hub não pode ser trocado silenciosamente; parâmetros de legenda incompatíveis com o preset fixo CIBO são rejeitados; os renderers usam o mesmo resolvedor de executáveis, incluindo ambiente Python e FFmpeg empacotado. Uma montagem sintética de vinte segmentos em30FPS também foi conferida, com duração de vídeo4,0s e áudio4,034s; isso não representa promessa de diferença temporal absoluta zero em todo arquivo.

Verificação final local:34 testes aprovados, zero falhas/skips; diagnóstico pronto, compilação Python e contrato de publicação do repositório aprovados. A revisão independente confirmou as três correções delimitadas; não equivale a uma homologação audiovisual/editorial completa.

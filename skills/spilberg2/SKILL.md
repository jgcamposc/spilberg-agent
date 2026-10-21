---
name: spilberg2
description: Prepare e execute cortes verticais locais com o perfil CIBO do Spilberg 2.0, a partir do master e de um plano aprovado, com legendas Cal Sans, abertura, cliques e capa separada.
---

# Spilberg 2.0

Use o motor instalado do pacote `spilberg-agent` para um corte vertical por plano. O perfil CIBO combina corte do master com relógio nativo da fonte, enquadramento facial por mediana, legendas Cal Sans e acabamento local. A detecção facial não identifica quem fala. Verificação de FPS e decodificação não substitui conferência editorial e perceptiva.

## Preparação

- Execute `spilberg doctor` para verificar o motor, FFmpeg/FFprobe, Pillow e assets. Instalar o plugin não instala o runtime Python.
- Configure `SPILBERG_CIBO_ASSETS` com `CalSans-Regular.ttf`, `filmburn_blue.mp4` e `click.wav`, obtidos pelo usuário com licença aplicável. Não baixe nem publique esses assets implicitamente.
- Use o master original e tempos confirmados. Preserve fontes e saídas existentes.

## Plano e execução

Crie um AgentPlan com `$spilberg-editor`, mantendo `PENDING_APPROVAL`, e acrescente no EditPlan:

```json
{"render_profile": "cibo", "render_encoder": "auto"}
```

Mantenha fonte, segmentos, efeitos, SEO e vínculo de hash/job exigidos pelo contrato. Siga o fluxo instalado `prepare → submit-plan → approve → finish`; consulte `spilberg --help` e a ajuda do subcomando para a sintaxe. Registre a aprovação humana antes de renderizar o plano.

CIBO aceita um segmento vertical, headline de capa e `subtitle_style` com `{"style":"cibo"}` no corte inteiro. Montagens, formato horizontal, legendas parciais ou efeitos extras exigem `standard`; não remova efeitos aprovados para adaptar o plano.

Para execução técnica direta já autorizada, o comando do motor é:

```bash
spilberg2 --master master.mp4 --start 10 --end 20 --output corte-01.mp4 \
  --caps-json captions.json --headline "UMA IDEIA CENTRAL" --encoder auto
```

A CLI direta não registra a aprovação de um job; confirme a autorização e a seleção antes de usá-la. O JSON de legenda usa tempos relativos ao corte (`s`, `e`, `words`, `flags`, `word_starts` quando disponíveis). Use timestamps reais de palavras; sem eles, mantenha entrada e clique por frase. Trechos que cruzam o limite sem timestamps pedem correção da seleção ou transcrição.

`auto` seleciona VideoToolbox no macOS e CPU nas demais plataformas. Falha de hardware exige nova tentativa consciente com `cpu`. Não prometa velocidade ou sincronismo absoluto em toda fonte.

A saída inclui MP4, recibo `.render.json` e `.cover.jpg` quando existe headline. A headline fica fora do vídeo por padrão. `--embed-cover` insere explicitamente um frame com silêncio correspondente; não ative automaticamente para Content Hub. `--no-intro`, `--no-filmburn` e `--no-clicks` permitem acabamento simples.


## Retenção editorial

Ao selecionar trecho, revisar roteiro/transcrição, definir headline ou avaliar o ritmo de um corte curto, use também `content-principles` como raciocínio editorial. A skill deve orientar a decisão em silêncio: pensar na pessoa que verá o vídeo, no valor por segundo, na progressão entre linhas, na curiosidade, na especificidade e no que não sustenta a promessa central.

Não transforme esses princípios em fórmula, checklist exibido ou alegação de resultado. Preserve fatos, sequência e contexto da fonte; se o gancho pretendido não for sustentado pelo material, sinalize a limitação editorial em vez de inventar prova ou mudar o sentido da fala.

## Conferência e entrega

Confira duração, relógio da fonte, diferença A/V e decodificação no recibo; assista ao corte para validar enquadramento, fala, legendas e acabamento. Diferencie render local verificado, integração no app e publicação. O adaptador `spilberg.contenthub_adapter` existe, mas a adoção pelo app depende da configuração dele. Se o pedido contém `options.captionStyle`, preserve o finalizador compartilhado (`captionsBurned=false`).

Entregue apenas os arquivos finais solicitados. Aprovação editorial não autoriza publicação, envio externo ou alteração de credenciais.

## Revisão do resultado (2.1)

No fluxo de jobs, `finish` gera os cortes e relatórios por ID e retorna `REVIEW_REQUIRED`.
Leia os relatórios, confira o MP4 completo e os alertas de fala/legenda/imagem.
Registre a revisão com `spilberg review JOB_ID CANDIDATE_ID --decision approve|reject --reviewer NOME --notes JUSTIFICATIVA --report-sha256 HASH`.
Use a identidade de quem realmente revisou e respeite a autorização da tarefa; não registre revisão sem assistir/escutar.
Só `LOCAL_READY` permite entrega. ASR indisponível pede escuta manual; falha determinística não pode ser dispensada.
O hash vincula a revisão ao relatório e vídeo exatos. Consulte `spilberg review --help` e a documentação `docs/quality-review.md` do repositório quando precisar retomar um job antigo.

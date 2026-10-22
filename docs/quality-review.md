# Revisão confiável dos cortes — Spilberg 2.1

O JobStore mantém plano, fonte, aprovação e entrega; as capacidades inspiradas
no CIBO entram como módulos internos de revisão. `quality.py` coordena resultados
e `visual_review.py` produz eventos e imagens para o editor.

## Fluxo

`prepare → submit-plan → approve → finish → review → deliver`

`finish` preserva o MP4 de trabalho, gera um relatório por `candidate_id` e retorna
`REVIEW_REQUIRED` quando as verificações determinísticas passam. Não promove o
corte a `LOCAL_READY` antes da revisão editorial. O estado inclui os caminhos dos
relatórios; `render-manifest.json` contém o SHA-256 de cada um.

Depois de assistir e escutar o MP4 completo, conferir legenda, contexto, pessoa,
nomes/números e todos os alertas, registre a revisão:

```sh
spilberg review JOB_ID clip-01 --decision approve --reviewer "editor" \
  --notes "Conferi vídeo, áudio, legendas e os alertas identificados no relatório" \
  --report-sha256 SHA256_DO_RELATORIO
```

Use `--decision reject` para reprovar. Uma justificativa é obrigatória; alertas de
ASR ou de imagem podem ser falsos positivos e devem ser resolvidos nessa revisão.
Quem registra é responsável por ter feito a conferência: a CLI não autentica a
identidade do revisor nem infere aprovação humana da transcrição. A aprovação do
plano anterior ao render não substitui esta revisão do resultado.

Uma falha determinística retorna `QA_FAILED`, código de saída não zero no `finish`,
e impede a aprovação final. Para mudar uma decisão de corte ou dependência
aprovada, prepare um novo job com o material corrigido, sem sobrescrever o anterior.
Retomar `finish` num job em revisão reaproveita os artefatos íntegros, sem render novo.
Após uma falha transitória de verificação, `finish` refaz o QA do mesmo MP4,
preservando relatórios e imagens anteriores em caminhos exclusivos. A nova revisão
invalida qualquer aceite editorial anterior; não autoriza trocar o vídeo ou o plano.

## O que é conferido

- Decodificação integral, duração, dimensões e amostras de preto do QA existente.
- FPS racional da fonte, duração e diferença A/V com tolerância de `2/fps + 0,025s`;
  áudio obrigatório quando a fonte o possui.
- Sidecar de legendas associado explicitamente ao ID e hash do MP4, contendo os
  blocos usados pelo render; validação de vazio, tempos, duração e sobreposição.
- Comparação do áudio final retranscrito com blocos temporais da legenda ou da
  fonte selecionada. Diferenças, nomes/números e evidência insuficiente pedem revisão.
- Palavras cujos timestamps atravessam os limites dos cortes, inclusive o último.
- Variações visuais em quadros reduzidos: retorno à imagem anterior após 1–4
  quadros e planos intermediários abaixo de 1,2 s. Gera folhas com antes/evento/depois.

Os detectores visuais são heurísticos; não identificam semanticamente locutores,
não detectam todo reenquadramento e não provam qualidade criativa. A comparação ASR
usa texto estruturado vinculado ao render, não OCR dos pixels. Legibilidade,
cor, grafia e enquadramento continuam na inspeção editorial.

## Modelos e caches

A revisão de fala usa Whisper local em CPU, português, tempos por palavra e
temperatura zero. Por padrão procura `large-v3.pt` já instalado. Pode-se escolher
outro modelo local com `SPILBERG_QA_MODEL` e a pasta de pesos com
`SPILBERG_WHISPER_CACHE`. Não instala dependências nem baixa pesos durante o QA.
Sem pasta explícita, preparação e QA resolvem os mesmos pesos em
`$XDG_CACHE_HOME/whisper` ou `~/.cache/whisper`. O arquivo efetivamente carregado
é o mesmo cujo hash integra a chave de cache.
Sem o modelo, registra a indisponibilidade para revisão auditiva manual.

O cache final usa hash do WAV extraído, hash dos pesos, versão do backend e
parâmetros. Temporários são exclusivos por execução; a gravação do JSON é atômica.
O cache da preparação também distingue fonte, modelo/pesos, versão e parâmetros.
Transcrição fornecida pelo editor não contamina o cache de inferência automática.

## Recibos, alteração e retomada

Os dois perfis de render publicam `.captions.json` e `.render.json`. O recibo contém
hashes da fonte, MP4, captions e assets locais utilizados; o fluxo de plano aprovado
acrescenta hashes do plano e transcrição. Fontes resolvidas pelo sistema/libass são
identificadas como tal, sem inventar hash de um arquivo de fonte desconhecido.

A aprovação do job fixa as dependências locais conhecidas antes do render.
Assets Pexels obtidos pelo plano explícito são registrados pelo conteúdo efetivamente
usado no render. O relatório fixa entradas e recibo; revisão, retomada e entrega
revalidam os hashes. Nenhum cache antigo ou simples `qa_passed=true` autoriza entrega.
Capa e imagens de inspeção também ficam vinculadas ao relatório; remover ou alterar
esses artefatos bloqueia o aceite. Caminhos de saída no manifesto precisam coincidir
com os artefatos efetivamente revisados, inclusive durante a promoção local.

O manifesto de render passa a `schema_version: 2.0`, mantendo os campos existentes
e acrescentando relatório/revisão por corte. Jobs antigos precisam gerar revisão
pelo novo fluxo antes de uma nova entrega. Finais já existentes são preservados;
para um job legado já pronto, crie um novo job em vez de editar o manifesto.

O adaptador Content Hub e a CLI direta continuam gerando render técnico com o
mesmo contrato. A revisão e o novo estado pertencem ao JobStore. Render direto
não prova aceite editorial nem publicação.

## Piloto e evolução seguinte

Os testes usam fontes sintéticas, comparação/cache de ASR com inferência controlada
e renders reais de FFmpeg. Isso comprova os bloqueios e contratos, não melhoria de
retenção ou preferência do editor. Ainda é necessário comparar os mesmos materiais
reais nos dois fluxos: podcast com duas pessoas, pessoa em movimento e FPS diferente.
Registrar duração do processamento, correções e cortes aceitos antes de afirmar ganho.

Temas por cliente, motion, adaptador DaVinci e benchmark de encoders ficam na etapa
seguinte. Não são ativados por esta versão.

Referência estudada: [CIBO, snapshot 1654520](https://github.com/Be-Grow/CIBO/tree/16545209e931d2033c23e864ee6ff28f50a995b6).
Os módulos desta versão são implementações próprias; assets e código de cliente
não são copiados do CIBO para o repositório público do Spilberg.

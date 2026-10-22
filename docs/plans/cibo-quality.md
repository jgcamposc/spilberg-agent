# Spilberg: distribuição e revisão confiável

Plano aprovado na conversa em 2026-10-21. Primeira entrega: completar PR 13,
unificar QA por corte, conferir áudio/legenda final com cache por conteúdo,
detectar flashes/planos curtos e registrar hashes de fontes/legendas/assets.
Preservar relógio, aprovação, motor e contrato do Content Hub.

## Tarefas

1. Distribuição: paridade recursiva de todas as skills no marketplace.
2. Revisores locais: estrutura/identidade de captions, comparação temporal de fala,
   cache ASR por conteúdo/modelo/parâmetros e auditoria visual com evidências.
3. Render: persistir captions efetivamente usadas e proveniência dos assets.
4. Job: vincular dependências à aprovação, agregar checks e exigir revisão
   editorial do relatório/MP4 exatos antes de LOCAL_READY e entrega.
5. Verificar regressões, smoke renders, revisão independente e atualizar PR 13.

## Aceite

Falha determinística bloqueia entrega; ausência de ASR ou julgamento perceptivo
fica REVIEW_REQUIRED. Revisão explícita resolve alertas heurísticos, com nome
do revisor e justificativa. Ela não pode dispensar erro determinístico.
Caches/relatórios/revisões antigos não podem validar vídeo ou dependência nova.
Os testes devem cobrir final de fala, IDs trocados, caches e fontes alterados,
flashes 1–4 frames, emenda limpa, duration/FPS/A-V e distribuição do plugin.

Motion, temas de cliente e DaVinci são a evolução seguinte, fora desta entrega.
Piloto com materiais reais dos mesmos três cenários e aceite do editor requer
as mídias autorizadas e feedback; não inferir ganho de qualidade de testes sintéticos.

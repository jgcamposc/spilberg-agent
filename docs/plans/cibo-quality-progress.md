# SDD ledger — plan: docs/plans/cibo-quality.md

Base: 845cac4281d7e6135b158ae957b47817110090e4, PR 13.
Baseline: PYTHONPATH=src python -m pytest -q → 25 passed, 9 skipped.
Isolamento: clone dedicado; ferramentas nativas deste chat apontam para o Lab,
não para o repositório do produto. Instalação existente permanece intacta.
Pre-flight: captions do render → revisão exige identidade por ID/hash; revisão
→ promoção precisa validar o mesmo vídeo e dependências em toda retomada.
Ruling: usar o plano aprovado da conversa como spec e registrar sua cópia aqui;
nenhuma aprovação extra de design necessária. Custo se errado: revisar o contrato.
Ruling: ASR só usa modelos locais já disponíveis; ausência é pendência explícita,
sem download implícito. Custo: revisão auditiva manual quando não houver modelo.
Ruling: piloto editorial real fica identificado como pendente sem material/aceite;
testes sintéticos não serão apresentados como ganho editorial comprovado.

Task 1: complete — teste de paridade falhou com skill ausente/drift, depois passou.
Task 2: complete — testes de identidade/timing/cache/limites de fala e flashes
falharam antes dos módulos e passaram após implementação. Inferência pesada é
controlada nos testes de cache; extração e hashing são reais.
Task 3: complete — renders standard e CIBO inicialmente sem os recibos exigidos,
depois com captions e hashes conferidos. A preparação agora mantém words.
Task 4: complete — finish antes chegava a LOCAL_READY sem revisão; teste RED→GREEN.
Alteração de transcrição, vídeo final e captions também ganhou regressão observada.
Fonte de cache trocada de modelo reproduziu reutilização indevida, corrigida.
Ruling: JobStore exige revisão do resultado, novo estado REVIEW_REQUIRED e comando
review; Content Hub/CLI direta mantêm contrato de render técnico. Custo: um passo
de revisão adicional nos jobs e novo job para migração de entregas legadas.
Validação: suíte completa com assets locais → 63 passed, sem skips (20,34 s).
Execução no sandbox havia negado encoder VideoToolbox; repetição autorizada fora
do sandbox passou. Os assets locais não são adicionados ao repositório.
Build: sdist e wheel 2.1.0 gerados; três skills passaram quick_validate.
Task 5: revisão independente pendente; piloto editorial real pendente conforme spec.

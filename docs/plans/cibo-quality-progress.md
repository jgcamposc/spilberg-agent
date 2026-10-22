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
Task 5: implementação e revisão técnica completas; piloto editorial real pendente.

## Revisão independente e única rodada de correção

Revisão fresca da branch inteira: 0 Critical, 5 Important, 0 Minor.
As cinco falhas foram reproduzidas por regressões antes das correções:

1. Assets relativos de B-roll eram resolvidos fora do projeto no recibo. Agora
   o hash aponta para o mesmo arquivo utilizado pelo render, mesmo com homônimo.
2. Uma falha transitória de QA não admitia nova verificação. Agora a retomada
   revalida o MP4 inalterado sem renderizar de novo, invalida revisão anterior e
   preserva relatórios e imagens em caminhos exclusivos. A colisão de caminhos
   das imagens também foi observada em RED antes de corrigida.
3. Capa e imagens de inspeção não estavam vinculadas ao aceite. Agora os hashes
   e a presença desses artefatos são exigidos na revisão e na entrega.
4. Trocar o caminho do MP4 no manifesto podia promover um arquivo não revisado.
   Agora caminho e conteúdo devem corresponder ao relatório, antes e após copiar.
5. O cache podia identificar pesos diferentes dos usados pelo Whisper. Um único
   resolvedor atende preparação, QA, SPILBERG_WHISPER_CACHE e XDG_CACHE_HOME.

Validação final após correções: 70 passed, 0 skipped, 23,39 s, com assets locais.
Build wheel/sdist 2.1.0 e fronteira pública passaram novamente; diff sem erros.
Smoke adicional com voz sintética e Whisper base real local: primeira inferência
sem cache e segunda com cache. A diferença contextual entre número por extenso e
algarismos resultou em REVIEW_REQUIRED, não aprovação automática. Não é piloto.

## Julgamentos não emitidos pela revisão técnica

- Retenção, preferência do editor e redução medida de retrabalho: exigem piloto
  comparativo dos três cenários reais e feedback, ainda não fornecidos.
- Legibilidade, grafia nos pixels, qualidade perceptiva e contexto: continuam
  revisão humana; sidecars vinculados não equivalem a OCR nem prova perceptiva.
- Instalação pelo aplicativo marketplace e encoders Windows/Linux: sem ambiente
  observado nesta execução. Paridade recursiva do pacote foi testada; CI separado.
- Dois processos escrevendo simultaneamente no mesmo JobStore: não validado;
  temporários atômicos de cache não são garantia de coordenação de jobs.
- Autenticação do revisor, uploads e publicação: fora deste fluxo local. Nome e
  justificativa são registro auditável, não comprovação de identidade.
- Motion, temas por cliente, DaVinci e benchmarks: fora da primeira entrega,
  conforme plano aprovado. Nenhum desses itens foi declarado operacional.

Sem achados Minor adiados. Instalação local, vault, merge e release não alterados.

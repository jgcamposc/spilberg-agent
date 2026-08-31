# Arquitetura local-first

```text
vídeo → SHA-256 + metadados → Whisper local → EvidencePack local
      → $spilberg-editor (decisão editorial) → AgentPlan pendente
      → aprovação humana → FFmpeg local → QA local → saída local
```

O JSON é a fonte de verdade. O Codex só decide cortes e escreve o `AgentPlan`; ele não calcula filtros FFmpeg, hashes, duração, legendas, renderização ou QA.

| Parte | Arquivo | Papel | Limite importante |
| --- | --- | --- | --- |
| CLI | `src/spilberg/cli.py` | Interface para jobs e diagnóstico | `deliver` apenas registra uma entrega que já ocorreu; não envia arquivos ao Drive. |
| JobStore | `src/spilberg/jobs.py` | Estado, hash, cache, aprovação e retomada | Uma fonte ou plano alterado invalida a aprovação. |
| EvidencePack | `src/spilberg/local_analysis.py` | Escolhe até 20 candidatos e texto integral para até 12 | Heurística local; a decisão de qualidade continua sendo editorial. |
| Orquestrador | `src/spilberg/editing.py` | Monta filtros FFmpeg e renderiza | Não gera vídeo sintético nem publica em redes. |
| Reframe | `src/spilberg/reframer.py` | Crop vertical com âncora fixa pela mediana | Sem face confiável, usa centro estável. Não rastreia rosto em tempo real. |
| QA | `src/spilberg/qa.py` | Decodificação, metadados, frames pretos e contact sheet | A inspeção editorial da contact sheet continua humana/Codex. |
| Skill | `skills/spilberg-editor/` | Direção editorial e JSON estrito | Nunca autoaprova ou renderiza. |

## Efeitos verificáveis

- Headline, CTA, legendas ASS, punch-in, concatenação e formatos verticais/horizontais.
- B-roll local; B-roll Pexels opcional, com falha bloqueante por padrão. A integração externa ainda precisa de validação com uma credencial real do usuário.
- `fade` e `cut` aplicados a inserções de B-roll. Isto não é biblioteca de transições entre segmentos.
- Tela dividida de quadro inteiro (`top_bottom` ou `side_by_side`) com mídia local.
- Uma trilha local com ducking durante a fala.

Não são recursos presentes: xfade entre cortes, tracking facial dinâmico, redução de ruído, correção de cor, múltiplas faixas de música, geração sintética, upload Drive automático e publicação social.

## Contrato operacional

```text
PREPARED → READY_FOR_EDITORIAL → PENDING_APPROVAL → APPROVED
         → RENDERING → QA_PASSED → LOCAL_READY → DELIVERED
```

`STALE_SOURCE`, `INVALID_PLAN`, `QA_FAILED` e `DRIVE_BLOCKED` interrompem a promoção. O máximo é de duas renderizações por job. Uma aprovação autoriza apenas os arquivos e o plano cujo SHA-256 estão registrados.

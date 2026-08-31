# Regras e Aprendizados (Learned Rules)

Este arquivo contém aprendizados empíricos do sistema que devem ser respeitados durante a geração de planos de edição (EditPlan).

## 1. Escopo público v1
- Os planos públicos suportam headline, CTA, legendas Hormozi ou cinematográficas e punch-ins.
- O motor também aceita B-roll local, B-roll Pexels opcional, tela dividida de quadro inteiro e uma trilha local com ducking. Cada um exige um `EditPlan` explícito e passa por QA.
- Não há transições entre segmentos, tracking facial dinâmico, limpeza de áudio, correção de cor, geração sintética de vídeo nem publicação em redes sociais.

## 2. Banco de Imagens (Pexels API)
- **Buscas Simples:** O motor de busca da API do Pexels falha ("0 resultados") quando a query de busca é complexa ou longa (ex: `productivity office meeting`).
- **Ação Obrigatória:** Ao gerar um `search_query` para o efeito `b_roll` com o source `pexels_api`, sempre utilize **palavras únicas ou duplas de sentido amplo** (ex: `office`, `podcast`, `studying`, `computer`, `team`, `business`).

## 3. Fade de B-roll e comportamento de mídia (Engine FFmpeg)
- **Congelamento de Frames (Bug corrigido):** O FFmpeg inicia a reprodução de todos os inputs no instante `t=0`. Para evitar que clipes curtos congelem antes de aparecerem na tela, a engine aplica o offset de tempo automático (`-itsoffset`) e loop infinito (`-stream_loop -1`) no nível do orquestrador. **O Agente Criador não precisa se preocupar com isso no JSON.**
- **Fade de B-roll, não transição de corte:** a engine suporta `transition: "fade"` e `transition: "cut"` somente ao inserir um B-roll. O `fade` converte o B-roll para `yuva420p` e aplica opacidade de 0,3 segundos na entrada e na saída. Não use isso para prometer `xfade` entre segmentos.

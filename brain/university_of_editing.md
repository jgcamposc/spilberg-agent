# Spilberg University of Editing
**Versão:** 1.0
**Objetivo:** Sistematizar as regras de edição focadas em retenção para plataformas de vídeos curtos (TikTok, Reels, Shorts).

## 1. Princípios de Retenção
- **Padrão dos 3 Segundos:** O primeiro take (Hook) não pode ter silêncio, precisa ter movimento ou zoom-in imediato e legenda grande e amarela.
- **Micro-interrupções Visuais:** Use um `zoom_in` pontual para reforçar uma declaração importante, sem prejudicar a clareza.

## 2. Padrões de Legenda (Estilo Hormozi)
- **Cores:** Palavras de ênfase e palavras atualmente sendo faladas devem ficar em Amarelo (Yellow). O restante em Branco.
- **Tipografia:** Fonte forte e pesada (ex: Arial Black, Montserrat, TheBoldFont), sem serifa.
- **Tamanho:** Muito grande na tela.
- **Estilo:** Sombra grossa e borda grossa preta (`Outline=4, Shadow=3`) para preservar leitura sobre o vídeo.

## 3. Estrutura do Plano de Edição (EditPlan)
O editor Codex deve gerar o array de `effects` aplicando as regras acima:
- `EffectType.SUBTITLE_STYLE`: Obrigatório para setar o estilo "hormozi".
- `EffectType.HEADLINE` / `EffectType.CTA`: Usados para começo e fim do vídeo.
- `EffectType.ZOOM_IN`: Para reforçar declarações importantes, com `amount` entre 0 e 0,35.

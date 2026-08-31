# Universidade de Edição auditada

Este manual separa direção editorial de capacidade técnica. Diretrizes podem
orientar um plano; só recursos presentes no engine podem ser executados.

## Hierarquia

1. Fidelidade: não alterar fala, intenção ou contexto.
2. Inteligibilidade: voz e ideia precisam ser compreensíveis.
3. Enquadramento: sujeito e objeto citado devem permanecer visíveis.
4. Retenção: remover tempo morto e ordenar a atenção.
5. Estética: legenda, headline e efeitos servem à mensagem.

Um efeito que prejudica um nível anterior deve ser removido.

## Ritmo por tipo

Palestra: preserve apresentador, tela e raciocínio. Evite punch-in enquanto um
slide é explicado.

Podcast ou entrevista: preserve pergunta, resposta e reação quando fizerem
parte do payoff. Não fabrique continuidade.

Aula: preserve premissas, passos e exemplos. Clareza vence velocidade.

Talking head: blocos menores e punch-ins pontuais podem marcar mudanças de
argumento.

Demonstração: se o crop esconder informação essencial, não use o crop.

## Âncora fixa por mediana

O reenquadramento amostra frames distribuídos, detecta o maior rosto frontal
ou de perfil, coleta centros no eixo X, calcula a mediana e usa uma única
âncora durante o clipe.

A mediana ignora extremos e a posição fixa evita jitter. Isso é
reenquadramento inteligente estático, não tracking facial quadro a quadro.
Para as palestras testadas, é uma decisão aprovada.

## Texto e safe area

Canvas vertical: 1080 × 1920. Preset conservador atual:

- laterais: 110 a 120 px;
- headline: margem superior de 230 px;
- legenda cinematic: margem inferior de 430 px;
- CTA: margem inferior de 300 px;
- legenda hormozi: centro geométrico.

São presets, não garantias universais. Cada rede e render exigem QA visual.

## Legendas ASS

O ASS entra depois do crop e do punch-in. O texto não recebe zoom.

Hormozi configurado: até 3 palavras, Arial em negrito, tamanho 64, contorno de
4 px e alinhamento central.

Cinematic configurado: até 6 palavras, Arial 48, contorno discreto e terço
inferior conservador.

Limite: não existe highlight palavra por palavra; o bloco inteiro é exibido.

## Headline e CTA

- headline: 2 a 5 segundos, salvo justificativa;
- CTA: final ou ponto semanticamente adequado;
- textos longos precisam de quebra de linha;
- caracteres especiais são escapados no ASS.

## Punch-in

O zoom atual é uma escala estável durante um intervalo:

- 10% a 20% normalmente;
- máximo técnico de 35%;
- não usar o vídeo inteiro;
- não esconder slide ou objeto essencial.

Zoom gradual e tracking dinâmico não estão validados.

## Áudio

O núcleo preserva ou recodifica a faixa original em AAC. Não oferece redução
de ruído, equalização, compressão, remoção de reverb, música, ducking ou
loudness. Auto-Editor remove silêncios em etapa separada.

## Cadeia técnica

Entrada → cortes → concatenação → crop pela mediana → punch-in opcional →
textos e legendas ASS → H.264/AAC → validação.

## QA obrigatório

- hook compreensível sem contexto?
- fala fiel e sem sílaba cortada?
- apresentador e objeto citado visíveis?
- headline, legenda e CTA dentro do quadro?
- texto conflita com UI da plataforma?
- tremor ou salto não intencional?
- áudio e vídeo sincronizados?
- duração bate com o plano?
- arquivo decodifica do início ao fim?

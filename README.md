# Spilberg Agent v2.0

Agente local-first para edição de vídeo auditável com uma etapa editorial no Codex e execução técnica local.

## Instalação

```bash
# macOS Apple Silicon
chmod +x scripts/install.sh
./scripts/install.sh

# Windows
pwsh scripts/install.ps1
```

## Arquitetura

O Spilberg Agent orquestra FFmpeg e mantém jobs, renderização, QA, cache e arquivos na máquina do usuário. Downloads por URL e B-roll Pexels são opcionais e só ocorrem por comando ou plano explícito. O Codex recebe um EvidencePack reduzido e devolve um JSON pendente de aprovação.

Consulte `docs/installation.md` e `docs/architecture.md` para os sistemas suportados, limites funcionais e fluxo completo.


## Core Spilberg 2.0

Relógio nativo do master e perfil CIBO estão integrados aos planos aprovados. Veja [uso, validação e adaptador Content Hub](docs/spilberg2-integration.md). O perfil anterior continua disponível; capa separada é o padrão do CIBO.

## Spilberg 2.0 e plugin Codex

O pacote e o plugin passam a usar a versão `2.0.0`. O plugin distribui `$spilberg-editor` para decisão editorial e `$spilberg2` para orientar o perfil CIBO. A instalação do plugin disponibiliza as instruções; o motor Python e os assets CIBO precisam estar disponíveis localmente.

O perfil padrão continua disponível. O perfil CIBO suporta um corte vertical por plano, Cal Sans, entrada zoom/blur, filmburn, cliques e capa separada. Os assets não são distribuídos no repositório: configure `SPILBERG_CIBO_ASSETS` e execute `spilberg doctor`. Confira [o contrato e os limites da integração](docs/spilberg2-integration.md) antes de selecionar esse perfil.

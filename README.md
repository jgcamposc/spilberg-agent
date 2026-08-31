# Spilberg Agent v1.0

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

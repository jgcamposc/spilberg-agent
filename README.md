# Spilberg Agent v1.0

Agent autônomo local-first para edição modular de vídeos no ecossistema BeGrow.

## Instalação

```bash
# macOS / Linux
chmod +x scripts/install.sh
./scripts/install.sh

# Windows
pwsh scripts/install.ps1
```

## Arquitetura

O Spilberg Agent é local-first: orquestra FFmpeg e mantém jobs, renderização e QA na máquina do usuário. Downloads por URL e B-roll Pexels são opcionais e só ocorrem por comando ou plano explícito.
Consulte `docs/architecture.md` para detalhes.

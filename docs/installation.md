# Instalação

A v2.0 é suportada em macOS Apple Silicon e Windows x64, com Python 3.11 ou 3.12. Linux e macOS Intel não fazem parte da matriz oficial.

O instalador cria um ambiente Python isolado, jobs, cache e regras pessoais fora do clone. Ele não pede chave de API, cookies ou dados de cliente. O primeiro `prepare` que usar Whisper poderá baixar o modelo escolhido.

## Ferramentas de vídeo

Instale FFmpeg e FFprobe antes do motor e mantenha ambos no PATH. A dependência Python `imageio-ffmpeg` fornece FFmpeg, mas não fornece FFprobe. Alternativamente, configure os caminhos dos executáveis em `SPILBERG_FFMPEG` e `SPILBERG_FFPROBE`. O relógio nativo da versão 2.0 depende de FFprobe.

Confira `ffprobe -version` antes da instalação e `spilberg doctor` depois. A CI instala essas ferramentas explicitamente em cada plataforma.

## macOS Apple Silicon

No diretório clonado:

```bash
chmod +x scripts/install.sh
./scripts/install.sh
source "$HOME/Library/Application Support/Spilberg/venv/bin/activate"
spilberg doctor
```

## Windows x64

No PowerShell, no diretório clonado:

```powershell
pwsh -ExecutionPolicy Bypass -File .\scripts\install.ps1
& "$env:LOCALAPPDATA\Spilberg\venv\Scripts\spilberg.exe" doctor
```

## Plugin no Codex

O manifesto público fica em `.codex-plugin/plugin.json` e as skills em `skills/spilberg-editor/` e `skills/spilberg2/`. Depois de instalar o plugin pelo painel de Plugins do Codex a partir desta cópia ou do repositório público, use `$spilberg-editor` para a etapa editorial e `$spilberg2` para o perfil CIBO. Os assets CIBO são locais e opcionais para o perfil padrão; configure-os conforme `docs/spilberg2-integration.md`. O instalador não tenta alterar o marketplace nem a configuração do Codex sem uma ação explícita do usuário.

## Estado privado

```text
macOS:   ~/Library/Application Support/Spilberg/
Windows: %LOCALAPPDATA%\Spilberg\
├── venv/        ambiente isolado
├── brain-local/ preferências aceitas explicitamente
├── jobs/        planos, aprovações e manifestos
├── cache/       transcrições reaproveitadas por SHA-256
└── outputs/     entregas locais promovidas
```

Para remover somente o runtime, de forma explícita, execute `python scripts/uninstall.py --remove-runtime`. Sem essa opção, o script preserva jobs, cache e preferências; o plugin deve ser removido pelo próprio painel do Codex.

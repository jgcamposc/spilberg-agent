# Instalação

A v1 é suportada em macOS Apple Silicon e Windows x64, com Python 3.11 ou 3.12. Linux e macOS Intel não fazem parte da matriz oficial.

O instalador cria um ambiente Python isolado, jobs, cache e regras pessoais fora do clone. Ele não pede chave de API, cookies ou dados de cliente. O primeiro `prepare` que usar Whisper poderá baixar o modelo escolhido.

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

O manifesto público fica em `.codex-plugin/plugin.json` e o skill em `skills/spilberg-editor/`. Depois de instalar o plugin pelo painel de Plugins do Codex a partir desta cópia ou do repositório público, use `$spilberg-editor` para a única etapa editorial. O instalador não tenta alterar o marketplace nem a configuração do Codex sem uma ação explícita do usuário.

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

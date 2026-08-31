# Arquitetura Local-First

## Componentes

1. **CLI (cli.py)**: Interface de linha de comando.
2. **JobStore (jobs.py)**: Gerenciamento de estado das edições baseado em sistema de arquivos.
3. **Orchestrator (editing.py)**: Encadeamento de comandos FFmpeg.
4. **Data Models (edit_plan.py)**: Estruturas de dados fortemente tipadas com Pydantic.

## Fluxo de Execução
`spilberg job submit` -> Validação Pydantic -> Fila no JobStore -> Execução pelo Orchestrator.

# Privacidade e Segurança

- O processamento, os jobs, os renders, o cache e as configurações permanecem locais na máquina do usuário.
- O Spilberg não faz upload, publicação em redes ou entrega em nuvem automaticamente.
- `spilberg ingest <url>` acessa uma URL apenas quando o usuário o executa. O B-roll Pexels é opcional, exige `PEXELS_API_KEY` local e só é consultado por um plano que o peça explicitamente.
- O histórico de jobs e arquivos temporários ficam restritos a `~/Library/Application Support/Spilberg` no macOS e `%LOCALAPPDATA%\\Spilberg` no Windows.

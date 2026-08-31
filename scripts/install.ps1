Write-Host "Instalando Spilberg Agent..."

python -m venv .venv
.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -e .

Write-Host "Instalação concluída! Rode 'spilberg doctor' para testar."

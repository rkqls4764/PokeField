$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    Write-Host '먼저 README에 따라 가상환경과 라이브러리를 설치하세요.'
    exit 1
}
& $pythonPath -m streamlit run (Join-Path $PSScriptRoot 'app.py')

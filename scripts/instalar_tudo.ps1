# Instala o kit da GG Explica no Windows, do zero, e liga a publicação automática.
# Basta dar dois cliques em INSTALAR.cmd (na pasta do kit). Pode rodar de novo quando quiser: o que
# já está instalado é pulado.
#
# Passos: Python e ffmpeg (winget), ambiente .venv, dependências, navegador do Playwright, .env,
# token da Meta (configurar_meta.ps1), teste do acesso, Agendador de Tarefas (instalar_automacao.ps1).
param([switch]$SemAgendador)
$ErrorActionPreference = "Stop"
$kit = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location $kit
$env:PYTHONUTF8 = "1"

function Passo($t) { Write-Host ""; Write-Host "== $t" -ForegroundColor Cyan }
function Tem($cmd) { return [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }
function Recarregar-Path {
  $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}

Passo "1/8 Python"
# Versões novas demais (3.14+) ainda não têm todos os pacotes prontos para Windows: o kit usa 3.12 ou 3.13.
if ($kit -like "*\AppData\Local\Temp\*") {
  Write-Host "Você abriu o INSTALAR.cmd de dentro do zip. Feche, clique com o botão direito no zip >" -ForegroundColor Red
  Write-Host "Extrair tudo... > destino Projetos\gg-explica, e rode o INSTALAR.cmd da pasta extraída." -ForegroundColor Red
  exit 1
}
function Achar-Python {
  foreach ($v in @("3.12", "3.13")) {
    try { $s = & py "-$v" --version 2>$null; if ($LASTEXITCODE -eq 0 -and $s -match "Python") { return $v } } catch {}
  }
  return $null
}
$pyv = Achar-Python
if (-not $pyv) {
  Write-Host "Instalando Python 3.12..."
  try { & py install 3.12 2>$null } catch {}   # gerenciador de instalação novo do Python
  $pyv = Achar-Python
}
if (-not $pyv) {
  winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements --silent
  Recarregar-Path
  $pyv = Achar-Python
}
if (-not $pyv) { Write-Host "Não achei o Python 3.12. Feche e abra o INSTALAR.cmd de novo." -ForegroundColor Red; exit 1 }
Write-Host "ok: Python $pyv"

Passo "2/8 ffmpeg"
if (-not (Tem "ffmpeg")) {
  winget install -e --id Gyan.FFmpeg --accept-package-agreements --accept-source-agreements --silent
  Recarregar-Path
}
if (Tem "ffmpeg") { Write-Host "ok" } else { Write-Host "ffmpeg instalado; feche e abra o INSTALAR.cmd de novo se o teste falhar." -ForegroundColor Yellow }

Passo "3/8 Ambiente do kit (.venv)"
$vpy = Join-Path $kit ".venv\Scripts\python.exe"
if (Test-Path $vpy) {
  $atual = & $vpy --version
  if ($atual -notmatch "Python $([regex]::Escape($pyv))") { Remove-Item -Recurse -Force ".venv" }   # .venv de outra versão
}
if (-not (Test-Path $vpy)) { & py "-$pyv" -m venv .venv }
& $vpy -m pip install --upgrade pip --quiet
& $vpy -m pip install -e ".[dev]" --quiet
if ($LASTEXITCODE -ne 0) { Write-Host "A instalação dos pacotes falhou (acima). Mande o print para o Claude." -ForegroundColor Red; exit 1 }
Write-Host "ok"

Passo "4/8 Navegador que desenha os slides"
& $vpy -m playwright install chromium
if ($LASTEXITCODE -ne 0) { Write-Host "Falhou ao baixar o navegador. Mande o print para o Claude." -ForegroundColor Red; exit 1 }
Write-Host "ok"

Passo "5/8 Identidade visual e teste rápido"
& $vpy scripts\gerar_identidade.py | Out-Null
& $vpy -m pytest -m "not lento" -q
if ($LASTEXITCODE -ne 0) { Write-Host "Algum teste falhou; mande o print para o Claude." -ForegroundColor Yellow }

Passo "6/8 Token da Meta (Instagram + Página)"
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }
$temToken = Select-String -Path ".env" -Pattern "^META_TOKEN_GG_EXPLICA=.{50,}" -Quiet
if ($temToken) {
  Write-Host "Já existe um token no .env. Testando..."
  & (Join-Path $kit ".venv\Scripts\paginas.exe") meta conferir --marca gg_explica
} else {
  & powershell -ExecutionPolicy Bypass -File (Join-Path $kit "scripts\configurar_meta.ps1")
}

Passo "7/8 Posts prontos para sair"
$exe = Join-Path $kit ".venv\Scripts\paginas.exe"
$pautas = Get-ChildItem "pautas\*.json" | Where-Object { $_.Name -notmatch "^(demo|exemplo|hoje)" }
foreach ($f in $pautas) {
  Write-Host ""
  Write-Host "Pauta $($f.Name): responda s para cada post que pode ir ao ar no horario marcado." -ForegroundColor Yellow
  & $exe aprovar $f.FullName --desde-hoje
  & $exe renderizar $f.FullName --desde-hoje
}
& $exe fila

Passo "8/8 Agendador de Tarefas"
if ($SemAgendador) { Write-Host "pulado (-SemAgendador)" }
else { & powershell -ExecutionPolicy Bypass -File (Join-Path $kit "scripts\instalar_automacao.ps1") }

Write-Host ""
Write-Host "Baixando a biblioteca oficial da Rockstar (uns 400 MB, só na primeira vez; pode demorar)..."
& $exe biblioteca

Write-Host ""
Write-Host "Pronto. Fila de publicação: .venv\Scripts\paginas.exe fila" -ForegroundColor Green

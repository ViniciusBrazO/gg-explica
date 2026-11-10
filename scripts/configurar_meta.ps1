# Guarda o token da Meta no .env sem mostrá-lo na tela e testa o acesso.
#   powershell -ExecutionPolicy Bypass -File scripts\configurar_meta.ps1
#   (outra marca: ... -Marca seul_no_bolso -Pagina 123456)
param(
  [string]$Marca = "gg_explica",
  [string]$Pagina = "1368551089682268"
)
$ErrorActionPreference = "Stop"
$kit = (Resolve-Path "$PSScriptRoot\..").Path
$env_ = Join-Path $kit ".env"
if (-not (Test-Path $env_)) { Copy-Item (Join-Path $kit ".env.example") $env_ }

Write-Host ""
Write-Host "Cole o token do usuario do sistema (Ctrl+V) e aperte Enter. Ele nao aparece na tela." -ForegroundColor Cyan
$seguro = Read-Host -AsSecureString "Token"
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($seguro)
try { $token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr).Trim() }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
if ($token.Length -lt 50) { Write-Host "Isso nao parece um token (curto demais). Nada foi gravado." -ForegroundColor Red; exit 1 }

$chave = $Marca.ToUpper()
$linhas = [System.Collections.Generic.List[string]]::new()
foreach ($l in [IO.File]::ReadAllLines($env_)) {
  if ($l -match "^(META_TOKEN_$chave|FB_PAGE_ID_$chave)=") { continue }
  $linhas.Add($l)
}
$linhas.Add("META_TOKEN_$chave=$token")
$linhas.Add("FB_PAGE_ID_$chave=$Pagina")
[IO.File]::WriteAllLines($env_, $linhas, (New-Object System.Text.UTF8Encoding($false)))
$token = $null
Write-Host "Token guardado no .env." -ForegroundColor Green

$paginas = Join-Path $kit ".venv\Scripts\paginas.exe"
if (Test-Path $paginas) {
  Write-Host "Testando o acesso (nada e publicado)..."
  $env:PYTHONUTF8 = "1"
  Push-Location $kit
  & $paginas meta conferir --marca $Marca
  Pop-Location
} else {
  Write-Host "O kit ainda nao esta instalado; rode INSTALAR.cmd e o teste roda no fim."
}

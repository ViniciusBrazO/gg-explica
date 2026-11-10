# Liga a automação da GG Explica no Agendador de Tarefas do Windows.
# Rode no PowerShell, dentro da pasta do kit, com o kit já instalado (README):
#   powershell -ExecutionPolicy Bypass -File scripts\instalar_automacao.ps1
# Para desligar tudo:  powershell -ExecutionPolicy Bypass -File scripts\instalar_automacao.ps1 -Remover
#
# O que fica agendado (só roda com você logado no Windows e o computador ligado):
#   a cada 15 min   paginas ciclo          biblioteca oficial (1x por dia), radar, Telegram, publicação
#   todo dia 07:10  paginas claude radar   o Claude escreve o Radar do dia
#   segunda 07:40   paginas claude pauta   o Claude monta a pauta da semana
#   todo dia 08:10  paginas claude traducao  versão em espanhol (só se ligada em config/automacao.yaml)
#   a cada 24 h     paginas biblioteca (dentro do ciclo)  confere os pacotes oficiais da Rockstar
#   todo dia 23:30  paginas metricas       números do Instagram para a revisão
param(
  [switch]$Remover
)
$ErrorActionPreference = "Stop"
$kit = (Resolve-Path "$PSScriptRoot\..").Path
$oculto = Join-Path $kit "scripts\rodar_oculto.vbs"
$prefixo = "GG Explica - "

# tarefas antigas do primeiro kit (publicavam sozinhas; agora o ciclo faz isso)
foreach ($antiga in @("Paginas - publicar Instagram", "Paginas - coletar metricas")) {
  if (Get-ScheduledTask -TaskName $antiga -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $antiga -Confirm:$false
    Write-Host "removida a tarefa antiga: $antiga"
  }
}
Get-ScheduledTask | Where-Object { $_.TaskName -like "$prefixo*" } | Unregister-ScheduledTask -Confirm:$false
if ($Remover) { Write-Host "Automação desligada."; exit 0 }

if (-not (Test-Path (Join-Path $kit ".venv\Scripts\paginas.exe"))) {
  Write-Error "Não achei .venv\Scripts\paginas.exe. Instale o kit primeiro (README)."
}
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
  Write-Warning "O comando 'claude' (Claude Code) não foi encontrado. As tarefas do Claude vão falhar até você instalar e fazer login."
}
New-Item -ItemType Directory -Force -Path (Join-Path $kit "clipes\entrada"), (Join-Path $kit "saida") | Out-Null

$config = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
  -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 1)

function Agendar($nome, $argumentos, $gatilho) {
  $acao = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$oculto`" $argumentos" -WorkingDirectory $kit
  Register-ScheduledTask -TaskName ($prefixo + $nome) -Action $acao -Trigger $gatilho -Settings $config -Force | Out-Null
  Write-Host ("agendado: " + $prefixo + $nome)
}

$cada15 = New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddMinutes(2) `
  -RepetitionInterval (New-TimeSpan -Minutes 15) -RepetitionDuration (New-TimeSpan -Days 3650)
Agendar "ciclo (15 min)" "ciclo" $cada15
Agendar "radar do dia (Claude)" "claude radar" (New-ScheduledTaskTrigger -Daily -At "07:10")
Agendar "pauta semanal (Claude)" "claude pauta" (New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At "07:40")
Agendar "traducao ES (Claude)" "claude traducao" (New-ScheduledTaskTrigger -Daily -At "08:10")
Agendar "metricas" "metricas" (New-ScheduledTaskTrigger -Daily -At "23:30")

# O kit não depende mais de gravar jogo: apaga o atalho antigo do "modo gravação", se existir.
$atalhoAntigo = Join-Path ([Environment]::GetFolderPath("Desktop")) "GG Explica - modo gravacao.cmd"
if (Test-Path $atalhoAntigo) { Remove-Item $atalhoAntigo; Write-Host "removido o atalho antigo do modo gravação" }

Write-Host ""
Write-Host "Pronto. Na primeira vez, rode 'paginas biblioteca' para baixar o material oficial agora."
Write-Host "Imagem oficial salva à mão vai para: $(Join-Path $kit 'clipes\entrada')"
Write-Host "Acompanhe em saida\automacao.log. Para desligar: scripts\instalar_automacao.ps1 -Remover"

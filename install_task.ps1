<#
    install_task.ps1 -- 注册 / 删除「每日壁纸」Windows 计划任务。

    为什么存成 UTF-8 + BOM：
      PowerShell 5.1 读没有 BOM 的 .ps1 会按 GBK 解码，那时文件必须保持纯 ASCII，
      否则中文变乱码。加了 BOM 之后 5.1 能正确按 UTF-8 解析，才可以放心写中文提示。
      （和 run_daily.bat 那个坑同源：Windows 脚本的编码必须显式声明。）

    用法：
      install_task.bat                创建 / 更新任务
      install_task.bat -Remove        删除任务
#>
[CmdletBinding()]
param(
    [switch]$Remove,
    [string]$TaskName = 'DailyWallpaper',
    [string]$RunAt    = '06:00'
)

$ErrorActionPreference = 'Stop'

$root  = $PSScriptRoot
if (-not $root) { $root = Split-Path -Parent $MyInvocation.MyCommand.Definition }
$entry = Join-Path $root 'run_daily.bat'

function Write-Ok   { param([string]$m) Write-Host "[ OK ] $m" -ForegroundColor Green }
function Write-Warn { param([string]$m) Write-Host "[WARN] $m" -ForegroundColor Yellow }
function Write-Info { param([string]$m) Write-Host "[INFO] $m" -ForegroundColor Cyan }

Write-Host ''
Write-Host '===== 每日壁纸 · Windows 计划任务 =====' -ForegroundColor White
Write-Host ''

# ---------- 删除模式 ----------
if ($Remove) {
    $t = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($null -eq $t) {
        Write-Warn "计划任务 '$TaskName' 不存在，无需删除。"
    } else {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Ok "已删除计划任务 '$TaskName'。"
    }
    Write-Host ''
    exit 0
}

# ---------- 创建 / 更新模式 ----------
if (-not (Test-Path -LiteralPath $entry)) {
    Write-Host "[FAIL] 找不到入口脚本：$entry" -ForegroundColor Red
    exit 1
}

$action    = New-ScheduledTaskAction -Execute $entry -WorkingDirectory $root
$trigger   = New-ScheduledTaskTrigger -Daily -At $RunAt
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
                                       -LogonType Interactive -RunLevel Limited
$settings  = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
                                          -DontStopIfGoingOnBatteries `
                                          -StartWhenAvailable `
                                          -MultipleInstances IgnoreNew

Write-Info "入口      : $entry"
Write-Info "触发时间  : 每天 $RunAt（错过的会在下次可用时补跑）"
Write-Info "运行身份  : $env:USERDOMAIN\$env:USERNAME（当前用户，不需要管理员）"
Write-Host ''

$old = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

try {
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
                           -Principal $principal -Settings $settings -Force | Out-Null
}
catch {
    Write-Warn "完整设置被拒绝：$($_.Exception.Message)"
    Write-Warn "改用最小设置重试……"
    $minimal = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -StartWhenAvailable
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
                           -Principal $principal -Settings $minimal -Force | Out-Null
}

$info = Get-ScheduledTask -TaskName $TaskName
if ($null -eq $old) { Write-Ok "已创建计划任务 '$TaskName'。" }
else                { Write-Ok "已更新计划任务 '$TaskName'。" }

$info2 = Get-ScheduledTaskInfo -TaskName $TaskName

Write-Host ''
Write-Host '  任务名   : ' -NoNewline; Write-Host $info.TaskName
Write-Host '  状态     : ' -NoNewline; Write-Host $info.State
Write-Host '  下次触发 : ' -NoNewline; Write-Host $info2.NextRunTime
Write-Host ''
Write-Host '  立刻试跑一次：' -ForegroundColor Cyan
Write-Host "      schtasks /run /tn `"$TaskName`"" -ForegroundColor Cyan
Write-Host '  删除这个任务：' -ForegroundColor Cyan
Write-Host '      install_task.bat -Remove' -ForegroundColor Cyan
Write-Host ''
exit 0

# ============================================================
#  注册 Windows 计划任务：每天 08:00 执行 run_daily.bat
#  用法：右键 → 使用 PowerShell 运行（管理员）
# ============================================================

$TaskName   = "PromptForge_Daily"
$ProjectDir = "E:\SD_OpenVINO\PromptForge"
$BatPath    = Join-Path $ProjectDir "scripts\run_daily.bat"

if (-not (Test-Path $BatPath)) {
    Write-Error "找不到 $BatPath，请确认项目路径"
    exit 1
}

# 删除旧任务（如果存在）
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

# 触发器：每天 08:00
$Trigger = New-ScheduledTaskTrigger -Daily -At "08:00"

# 动作：运行 bat
$Action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$BatPath`"" -WorkingDirectory $ProjectDir

# 设置：允许网络、允许电池
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1)

# 注册（当前用户）
Register-ScheduledTask `
    -TaskName $TaskName `
    -Trigger $Trigger `
    -Action $Action `
    -Settings $Settings `
    -Description "PromptForge 每日生图 + 鉴赏 + 排版" `
    -Force

Write-Host "✅ 计划任务已注册：$TaskName" -ForegroundColor Green
Write-Host "   每天 08:00 执行：$BatPath"
Write-Host ""
Write-Host "验证：" -ForegroundColor Yellow
Write-Host "   Get-ScheduledTask -TaskName $TaskName | Format-List"
Write-Host "   Start-ScheduledTask -TaskName $TaskName   # 立即测试"
# Parent 백필 실시간 진행 뷰. VSCode 터미널에서: powershell -File scripts\parent_backfill\watch_progress.ps1
# 종료: Ctrl+C
$ckpt   = "scripts\parent_backfill\checkpoint.json"
$errLog = "$env:TEMP\bf_watchdog_err.log"
$TOTAL  = 1013   # 전체 대상(대략). 목표치.

while ($true) {
    # 완료 수(체크포인트 = 성공마다 즉시 기록되는 진짜 진행도)
    try { $done = (((Get-Content $ckpt -Raw | ConvertFrom-Json).PSObject.Properties) | Measure-Object).Count }
    catch { $done = 0 }
    $pct = [math]::Round(($done / $TOTAL) * 100, 1)
    $barLen = 40
    $fill = [math]::Min($barLen, [int]($barLen * $done / $TOTAL))
    $bar = ('#' * $fill) + ('-' * ($barLen - $fill))

    # 현재 처리 중인 문서 / 최근 재시도·실패
    $cur = ""; $note = ""
    if (Test-Path $errLog) {
        $tail = Get-Content $errLog -Tail 400 -ErrorAction SilentlyContinue
        $lastDoc = $tail | Where-Object { $_ -match '\[\d+/\d+\] doc=' } | Select-Object -Last 1
        if ($lastDoc -match '\[(\d+)/(\d+)\] doc=([0-9a-f-]+)') { $cur = "run $($matches[1])/$($matches[2])  doc=$($matches[3].Substring(0,8))" }
        $lastWarn = $tail | Where-Object { $_ -match '재시도|-> fail' } | Select-Object -Last 1
        if ($lastWarn) { $note = ($lastWarn -replace '.*(WARNING|INFO)\s+','') }
    }

    # python 살아있나(=워치독 동작 중)
    $alive = (Get-Process python -ErrorAction SilentlyContinue | Measure-Object).Count

    Clear-Host
    Write-Host "=== Parent 백필 진행 ===  $(Get-Date -Format 'HH:mm:ss')" -ForegroundColor Cyan
    Write-Host ""
    Write-Host ("  [{0}] {1}%" -f $bar, $pct)
    Write-Host ("  완료 {0} / {1}   (남은 ~{2})" -f $done, $TOTAL, ($TOTAL - $done))
    Write-Host ""
    Write-Host ("  현재: {0}" -f $cur)
    if ($note) { Write-Host ("  최근: {0}" -f $note) -ForegroundColor Yellow }
    Write-Host ("  백필 프로세스: {0}개 {1}" -f $alive, $(if ($alive -gt 0) { '(실행 중)' } else { '(대기/완료)' }))
    Write-Host ""
    Write-Host "  (Ctrl+C 로 종료 — 이 뷰만 닫힘, 백필은 계속 돎)" -ForegroundColor DarkGray

    Start-Sleep -Seconds 3
}

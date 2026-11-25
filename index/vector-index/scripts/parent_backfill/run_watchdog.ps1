# Parent 백필 워치독 실행기.
# Windows에선 VPN 블립으로 쿼리 도중 죽은 소켓(recv 무한대기)을 소켓 옵션으로 못 끊음.
# → 체크포인트(성공마다 기록)가 StallSec 동안 안 늘면 프로세스를 죽이고 재개(멱등·resumable).
# 재시도(in-script, ~52s)는 정상 흐름이므로 StallSec는 그보다 넉넉히 크게 잡아 오탐 방지.

$ErrorActionPreference = "Stop"
$py       = ".venv\Scripts\python.exe"
$script   = "scripts/parent_backfill/backfill_parents.py"
$ckpt     = "scripts\parent_backfill\checkpoint.json"
$outLog   = "$env:TEMP\bf_watchdog_out.log"
$errLog   = "$env:TEMP\bf_watchdog_err.log"
$StallSec     = 120   # 이 시간 동안 체크포인트 정지 = hang으로 간주
$PollSec      = 15
$MaxRestarts  = 60

function CkptCount {
    try { (((Get-Content $ckpt -Raw | ConvertFrom-Json).PSObject.Properties) | Measure-Object).Count }
    catch { -1 }
}

$restart = 0
while ($true) {
    $before = CkptCount
    Write-Output "[$(Get-Date -f HH:mm:ss)] 시작(재시작 $restart) — 체크포인트 $before"
    $p = Start-Process -FilePath $py -ArgumentList @($script, "--apply") -PassThru -NoNewWindow `
            -RedirectStandardOutput $outLog -RedirectStandardError $errLog

    $lastMtime  = (Get-Item $ckpt).LastWriteTimeUtc
    $lastChange = Get-Date
    while (-not $p.HasExited) {
        Start-Sleep -Seconds $PollSec
        $m = (Get-Item $ckpt).LastWriteTimeUtc
        if ($m -ne $lastMtime) { $lastMtime = $m; $lastChange = Get-Date }
        elseif (((Get-Date) - $lastChange).TotalSeconds -gt $StallSec) {
            Write-Output "[$(Get-Date -f HH:mm:ss)] STALL ${StallSec}s — PID $($p.Id) kill 후 재개 (체크포인트 $(CkptCount))"
            Stop-Process -Id $p.Id -Force
            $p.WaitForExit(8000) | Out-Null
            break
        }
    }

    if ($p.HasExited -and $p.ExitCode -eq 0) {
        Write-Output "[$(Get-Date -f HH:mm:ss)] 정상 완료(exit 0) — 체크포인트 $(CkptCount)"
        break
    }
    # 킬됐거나 비정상 종료 → 진행이 있었으면 재시작 카운트 리셋(무한루프 방지는 진짜 정체 시에만)
    $after = CkptCount
    if ($after -le $before) { $restart++ } else { $restart = 0 }
    if ($restart -ge $MaxRestarts) {
        Write-Output "[$(Get-Date -f HH:mm:ss)] 진전 없이 재시작 $MaxRestarts회 — 중단(수동 확인 필요)"
        break
    }
    Start-Sleep -Seconds 2
}
Write-Output "[$(Get-Date -f HH:mm:ss)] 워치독 종료 — 최종 체크포인트 $(CkptCount)"

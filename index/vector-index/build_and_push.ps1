#!/usr/bin/env pwsh
<#
.SYNOPSIS
    ER/EW Docker 이미지를 빌드하고 Docker Hub에 푸시하는 스크립트

.DESCRIPTION
    dy-llm/er 및 dy-llm/ew 이미지를 빌드하고 Docker Hub에 푸시합니다.
    태그는 -Tag 파라미터로 지정하며, 기본값은 'latest'입니다.

.PARAMETER Tag
    Docker 이미지 태그 (기본값: latest)

.EXAMPLE
    .\build_and_push.ps1 -Tag 0.1.0
    .\build_and_push.ps1
#>

param(
    [string]$Tag = "latest"
)

# 에러 발생 시 즉시 종료
$ErrorActionPreference = "Stop"

# 현재 위치 저장
$originalLocation = Get-Location

try {
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "Docker Build & Push Script" -ForegroundColor Cyan
    Write-Host "Tag: $Tag" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""

    # 프로젝트 루트로 이동 (스크립트가 있는 디렉터리)
    $scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
    Set-Location $scriptRoot

    # Dockerfile 존재 확인
    if (-not (Test-Path "Dockerfile.er")) {
        throw "Dockerfile.er을 찾을 수 없습니다."
    }
    if (-not (Test-Path "Dockerfile.ew")) {
        throw "Dockerfile.ew을 찾을 수 없습니다."
    }

    # ER 이미지 빌드
    Write-Host "[1/4] Building ER image: dy-llm/er:$Tag" -ForegroundColor Green
    docker build -t "dy-llm/er:$Tag" -f Dockerfile.er .
    if ($LASTEXITCODE -ne 0) {
        throw "ER 이미지 빌드 실패"
    }
    Write-Host "✓ ER 이미지 빌드 완료" -ForegroundColor Green
    Write-Host ""

    # ER 이미지 푸시
    Write-Host "[2/4] Pushing ER image: dy-llm/er:$Tag" -ForegroundColor Green
    docker push "dy-llm/er:$Tag"
    if ($LASTEXITCODE -ne 0) {
        throw "ER 이미지 푸시 실패"
    }
    Write-Host "✓ ER 이미지 푸시 완료" -ForegroundColor Green
    Write-Host ""

    # EW 이미지 빌드
    Write-Host "[3/4] Building EW image: dy-llm/ew:$Tag" -ForegroundColor Green
    docker build -t "dy-llm/ew:$Tag" -f Dockerfile.ew .
    if ($LASTEXITCODE -ne 0) {
        throw "EW 이미지 빌드 실패"
    }
    Write-Host "✓ EW 이미지 빌드 완료" -ForegroundColor Green
    Write-Host ""

    # EW 이미지 푸시
    Write-Host "[4/4] Pushing EW image: dy-llm/ew:$Tag" -ForegroundColor Green
    docker push "dy-llm/ew:$Tag"
    if ($LASTEXITCODE -ne 0) {
        throw "EW 이미지 푸시 실패"
    }
    Write-Host "✓ EW 이미지 푸시 완료" -ForegroundColor Green
    Write-Host ""

    # 성공 메시지
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "DONE: dy-llm/er:$Tag, dy-llm/ew:$Tag" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Cyan

} catch {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "ERROR: $_" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    exit 1
} finally {
    # 원래 위치로 복귀
    Set-Location $originalLocation
}



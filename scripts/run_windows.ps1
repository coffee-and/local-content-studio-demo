$ErrorActionPreference = "Stop"

# 스크립트를 어느 위치에서 실행하더라도 프로젝트 루트로 이동
Set-Location (Split-Path -Parent $PSScriptRoot)

Write-Host "[1/4] Python 3.12 확인 중..."

py -3.12 --version

if ($LASTEXITCODE -ne 0) {
    throw @"
Python 3.12를 찾을 수 없습니다.

아래 명령으로 설치한 뒤 PowerShell을 다시 열어주세요.

winget install -e --id Python.Python.3.12
"@
}

Write-Host "[2/4] 가상환경 확인 중..."

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "가상환경을 생성합니다..."

    py -3.12 -m venv .venv

    if ($LASTEXITCODE -ne 0) {
        throw "가상환경 생성에 실패했습니다."
    }
}

$VenvPython = ".\.venv\Scripts\python.exe"

Write-Host "[3/4] 패키지를 설치합니다..."

& $VenvPython -m pip install --upgrade pip

if ($LASTEXITCODE -ne 0) {
    throw "pip 업그레이드에 실패했습니다."
}

& $VenvPython -m pip install -r requirements.txt

if ($LASTEXITCODE -ne 0) {
    throw "requirements.txt 패키지 설치에 실패했습니다."
}

Write-Host "[4/4] 프로그램을 실행합니다..."

& $VenvPython -m app

if ($LASTEXITCODE -ne 0) {
    throw "프로그램 실행 중 오류가 발생했습니다."
}
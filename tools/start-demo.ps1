# Arranca Docker Desktop si hace falta y deja la demo lista.
# Uso: powershell -ExecutionPolicy Bypass -File tools/start-demo.ps1
$ErrorActionPreference = 'Continue'
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

function Test-Docker {
    $null = cmd /c 'docker info --format {{.ServerVersion}} 2>nul'
    return $LASTEXITCODE -eq 0
}

if (-not (Test-Docker)) {
    $exe = 'C:\Program Files\Docker\Docker\Docker Desktop.exe'
    if (Test-Path $exe) { Start-Process $exe }
    $limite = (Get-Date).AddMinutes(4)
    while (-not (Test-Docker)) {
        if ((Get-Date) -gt $limite) { throw 'Docker Desktop no arrancó a tiempo.' }
        Start-Sleep -Seconds 4
    }
}

docker compose up -d db redis
if ($LASTEXITCODE -ne 0) { throw 'No se pudo levantar PostgreSQL/Redis.' }

docker compose run --rm migrate
if ($LASTEXITCODE -ne 0) { throw 'Fallaron las migraciones o el seed demo.' }

docker compose up -d api web
if ($LASTEXITCODE -ne 0) { throw 'No se pudo levantar API/SPA.' }

$limite = (Get-Date).AddMinutes(3)
while ($true) {
    try {
        $respuesta = Invoke-WebRequest -UseBasicParsing -Uri http://localhost:8000/api/health -TimeoutSec 3
        if ($respuesta.StatusCode -eq 200) { break }
    } catch {
        # todavía arrancando
    }
    if ((Get-Date) -gt $limite) { throw 'La API no respondió a tiempo.' }
    Start-Sleep -Seconds 4
}

Write-Host 'Demo lista en http://localhost:5173'
Start-Process 'http://localhost:5173'

# Script de sincronizacion instantanea Overleaf -> Local -> GitHub
$projectId = "6af054a70e2efc15383d3c22"
$cookieFile = "$PSScriptRoot\.olauth"

if (-not (Test-Path $cookieFile)) {
    Write-Host "[ERROR] No se encontro el archivo .olauth con la cookie overleaf_session2." -ForegroundColor Red
    exit 1
}

$cookieVal = (Get-Content $cookieFile -Raw).Trim()

Write-Host "[1/3] Descargando ultima version desde Overleaf ($projectId)..." -ForegroundColor Cyan
$zipFile = "$env:TEMP\overleaf_sync.zip"

curl.exe -sSL "https://www.overleaf.com/project/$projectId/download/zip" -H "Cookie: overleaf_session2=$cookieVal" -H "User-Agent: Mozilla/5.0" -o $zipFile

if (-not (Test-Path $zipFile) -or (Get-Item $zipFile).Length -lt 500) {
    Write-Host "[ERROR] La descarga fallo. Comprueba que la cookie no haya caducado." -ForegroundColor Red
    exit 1
}

Write-Host "[2/3] Extrayendo archivos en local..." -ForegroundColor Cyan
tar.exe -xf $zipFile -C $PSScriptRoot
Remove-Item $zipFile -Force

Write-Host "[3/3] Comprobando cambios en Git..." -ForegroundColor Cyan
git add .
git diff --staged --quiet
if ($LASTEXITCODE -ne 0) {
    git commit -m "chore: sync from Overleaf"
    git push origin main
    Write-Host "[OK] Sincronizado con Overleaf y subido a GitHub!" -ForegroundColor Green
} else {
    Write-Host "[OK] Todo esta al dia con Overleaf." -ForegroundColor Green
}

# 建置 huff-server / huff-sim（Windows）到 output\slot\huffnpuff-open-house\game\go-server\bin
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$out = Join-Path $PSScriptRoot '..\..\..\..\..\output\slot\huffnpuff-open-house\game\go-server\bin'
New-Item -ItemType Directory -Force -Path $out | Out-Null
go test ./...
if ($LASTEXITCODE -ne 0) { throw 'go test 失敗' }
$env:CGO_ENABLED = '0'
go build -trimpath -ldflags '-s -w' -o (Join-Path $out 'huff-server.exe') ./cmd/server
go build -trimpath -ldflags '-s -w' -o (Join-Path $out 'huff-sim.exe') ./cmd/sim
Get-ChildItem $out

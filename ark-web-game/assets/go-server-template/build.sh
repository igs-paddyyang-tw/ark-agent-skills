#!/usr/bin/env bash
# 建置 huff-server / huff-sim 到 output/slot/huffnpuff-open-house/game/go-server/bin（data 不放二進位）
set -euo pipefail
cd "$(dirname "$0")"
OUT=../../../../../output/slot/huffnpuff-open-house/game/go-server/bin
mkdir -p "$OUT"
go test ./...
for os_arch in linux/amd64 windows/amd64 darwin/arm64; do
  GOOS=${os_arch%/*} GOARCH=${os_arch#*/}
  ext=""; [ "$GOOS" = windows ] && ext=".exe"
  for c in server sim; do
    GOOS=$GOOS GOARCH=$GOARCH CGO_ENABLED=0 go build -trimpath -ldflags "-s -w" -o "$OUT/huff-$c-$GOOS-$GOARCH$ext" ./cmd/$c
  done
done
ls -la "$OUT"

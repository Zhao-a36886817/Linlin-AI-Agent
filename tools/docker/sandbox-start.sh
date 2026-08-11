#!/usr/bin/env bash

# Linlin Agent Docker 測試沙盒的啟動程序。
#
# 正式專案位於 /source，Docker 以唯讀方式掛載。每次容器啟動時，本程序會把
# 原始碼複製到記憶體中的 /workspace，讓測試可以建立暫存檔，但不會寫回 F:\。
# 模型、依賴、編譯產物與測試資料都有獨立掛載點，因此複製時必須排除。
set -euo pipefail

# tar 串流可完整保留隱藏檔與 Git metadata，也不需要在映像中額外安裝 rsync。
# /workspace 每次啟動都是新的 tmpfs，所以不會殘留上一次測試的舊程式碼。
tar \
  --directory=/source \
  --exclude='./models' \
  --exclude='./frontend/node_modules' \
  --exclude='./frontend/dist' \
  --exclude='./desktop/src-tauri/target' \
  --exclude='./data' \
  --exclude='./logs' \
  --exclude='./outputs' \
  --exclude='./workspace' \
  --create \
  --file=- \
  . \
  | tar --directory=/workspace --extract --file=-

# Windows bind mount 不保存 Unix executable bit，Docker Desktop 會把一般檔案呈現為
# 0777。Ruff 的 EXE002 會把這誤判成「可執行但沒有 shebang」。只在容器暫存副本
# 中把後端 Python 原始碼與測試正規化為 0644；F:\Linlin-Agent 完全不受影響。
find /workspace/backend \
  -type f \
  -name '*.py' \
  -exec chmod 0644 '{}' +

# 此標記必須最後建立。Windows 測試選單看到它後，才可安全開始 Ruff/Cargo。
touch /workspace/.linlin-sandbox-ready

# 保持容器待命；測試必須透過明確的 docker exec 命令啟動。
exec bash -lc 'trap : TERM INT; sleep infinity & wait'

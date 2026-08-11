# Linlin Agent Docker 測試沙盒

此資料夾是正式專案的測試工具，位於 `F:\Linlin-Agent\tools\docker`，用來建立
Docker Desktop 中名稱為 `Linlin-Agent` 的隔離測試容器。正式專案以唯讀方式掛載到 `/source`，每次啟動再把
程式碼複製到記憶體暫存的 `/workspace`；安裝依賴、編譯、測試、快取與輸出因此不會
改動 P24 工作樹。

## 最簡單的使用方式

不熟悉 PowerShell 或 Docker 指令時，直接雙擊：

`F:\Linlin-Agent\tools\docker\Linlin-Agent-Test.bat`

畫面出現後輸入 `1`，程式會自動啟動 Docker、準備缺少的免費依賴，並依序執行
後端、前端與桌面版測試。也可以輸入 `2`、`3` 或 `4` 只測特定部分。

## 安全邊界

- 只掛載 `F:\Linlin-Agent`，而且掛載模式為唯讀。
- `/workspace` 是每次啟動重新建立的記憶體副本，不會殘留過期原始碼。
- 約 1 GB 的模型不會複製到記憶體，而是直接以唯讀方式掛載。
- 不掛載 Docker socket，也不提供主機連接埠。
- 執行階段使用 internal Docker 網路，不會直接連到外部網路。
- `node_modules`、`dist`、Cargo `target`、log、output 與 workspace 使用獨立 volume。
- 不含 API key，不會猜測或寫死雲端憑證。
- 基本映像不安裝大型 LoRA/GPU 訓練套件；需要時必須另行明確核准。

## 建立與啟動

在 PowerShell 執行：

```powershell
docker compose -f F:\Linlin-Agent\tools\docker\compose.yaml up -d --build
```

完成後，Docker Desktop 應顯示容器 `Linlin-Agent`。確認工具版本：

```powershell
docker exec Linlin-Agent bash -lc "python --version && node --version && npm --version && rustc --version && cargo --version"
```

## 驗證命令

後端編譯、Ruff 與測試：

```powershell
docker exec Linlin-Agent bash -lc "cd /workspace/backend && python -m compileall -q app tests && python -m ruff check app tests && python -m pytest tests -q -p no:cacheprovider"
```

前端依賴、建置與 lint。`node_modules` 與 `dist` 只會寫入 Docker volume：

```powershell
docker exec Linlin-Agent bash -lc "cd /workspace/frontend && npm ci && npm run build && npm run lint"
```

Tauri/Cargo 檢查。`target` 與 Cargo 快取只會寫入 Docker volume：

```powershell
docker exec Linlin-Agent bash -lc "cd /workspace/desktop/src-tauri && cargo check --locked"
```

## 停止與再次啟動

停止容器但保留測試 volume：

```powershell
docker compose -f F:\Linlin-Agent\tools\docker\compose.yaml stop
```

再次啟動：

```powershell
docker compose -f F:\Linlin-Agent\tools\docker\compose.yaml start
```

## 清理說明

一般情況只需 `stop`，不要刪除 volume。若未來確定要清除所有可重新產生的 Docker
依賴與測試資料，才使用 `docker compose down --volumes`；此命令具有刪除性，執行前
必須再次確認。正式專案與本機 Qwen 模型不在這些 volume 中。

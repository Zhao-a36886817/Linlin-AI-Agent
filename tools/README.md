# Linlin Agent 本機工具

此資料夾集中保存目前正式版本的本機操作工具，避免在 `F:\` 第一層散落多個
看似獨立的 Linlin Agent 專案。核心程式仍位於 `backend`、`frontend` 與 `desktop`。

## `launcher`

- 固定使用 `C:\Users\Zhao\Anaconda3\envs\Linlin_agent`。
- 檢查必要環境與套件後啟動前後端。
- 執行時資料只寫到 `launcher\runtime`；此目錄可重新產生，不是原始碼。
- 正式入口仍是 `F:\Linlin-Agent\Linlin-Agent.bat`。

## `docker`

- 建立 Docker Desktop 中名稱為 `Linlin-Agent` 的隔離測試容器。
- 正式專案以唯讀方式掛載到容器 `/source`。
- 測試寫入記憶體或 Docker volumes，不會改寫正式專案。
- 操作入口是 `docker\Linlin-Agent-Test.bat`。

## 版本與封存原則

- `F:\Linlin-Agent` 永遠代表目前正式工作版本。
- 舊轉移包與舊副本統一放到 `F:\Linlin-Agent-Archive`，不混入目前執行路徑。
- 新一輪大幅迭代若需要完整封存，使用日期建立新的 Archive 子資料夾，避免產生
  `Linlin-Agent-copy`、`Linlin-Agent-new` 或多層巢狀專案。


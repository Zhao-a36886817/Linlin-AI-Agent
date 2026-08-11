# Linlin Agent 治理文件

此資料夾集中保存 LAES 階段治理產物，讓專案根目錄只保留日常啟動與全域設定。
治理文件是稽核證據，不是可隨意刪除的快取；整理時只改變位置，不改寫審查結論。

## 資料夾結構

- `phase-artifacts/P0` ～ `phase-artifacts/P34`：依迭代編號保存完成報告、Supervisor
  Review Package、決策與證據索引。
- `roadmaps`：依時間形成的 P10～P34 路線圖。
- `checksums`：治理規格、模板與路線圖的 SHA-256 清單。
- `charters`：適合文件閱讀器使用的 Word 版協作章程；根目錄 Markdown 版仍是
  工具啟動時的主要規則來源。
- `relocations`：保存舊根目錄路徑、新路徑與搬移前 SHA-256，供日後稽核。
- `../development`：每一個 phase 的需求、範圍、驗證及 Stop Gate 規格。
- `../../.laes/phases`：LAES 可機器讀取的 phase 模板。

## 不可推論或補造的檔案

P0～P9 的完成報告及 P30 完成報告在原始專案中就不存在。整理工作不會根據記憶
補造報告，也不會把不存在的證據標示為通過。P24 的正式狀態仍是
`WAITING_REVIEW / FAIL / NO_GO`。

## 新迭代規則

未來執行 `scripts/laes_supervisor.py validate` 時，審查包會直接寫到目前 phase 的
`phase-artifacts/Px`，不再回到專案根目錄。新增完成報告或決策檔時也應使用相同
資料夾，並同步更新當期 policy 與證據索引。

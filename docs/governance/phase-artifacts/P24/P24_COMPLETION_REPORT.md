# P24 完成報告 — 企業就緒與 v1.0 RC 閘門

## 審查結論

P24 僅稽核 P0–P23 的治理證據、目前原始碼、供應鏈安全及可發布性，
不得在本階段補做新功能。2026-08-11 重新驗證後，應用程式可執行的測試路徑
大致正常，但企業發布證據仍有兩個 High 等級阻擋，因此結論維持
`NO_GO`，不得建立、簽署、推送或發布 v1.0 RC。

專案擁有者在 `P24_RC_DECISION.yaml` 中記錄的決策仍是 `NO_GO`。該檔案是
歷史決策證據，本次未改寫或偽造新的擁有者核准。

## 本次 P24 範圍內修正

- 將 Supervisor 內已失效的舊帳號 `C:\Users\a3688` 路徑改為目前已確認的
  `C:\Users\Zhao\Anaconda3\envs\Linlin_agent` 環境。
- 前端驗證改由 Conda 啟動 npm，並使用 `--no-capture-output`，避免 Windows
  CP950 在轉印 Vite Unicode 輸出時誤判失敗。
- 企業證據稽核加入 `--require-go`，使任何 High 發布阻擋存在時必須非零結束；
  Supervisor 不得把顯示 `NO_GO` 的稽核當成 PASS。
- 將 backend、frontend、desktop、Tauri 與 Cargo 的正式版本來源統一為
  `1.0.0-rc.1`，並重跑 frontend build/lint 與 Cargo `--locked` 檢查。
- 將約 953 MB 的本機免費模型、Claude UI 參考 ZIP、Python `*.egg-info` 及
  Supervisor 可重建執行狀態精確排除於 Git；實體資料仍保留在 F 槽。
- 依專案擁有者於目前 task transcript 的明確授權，建立 P0–P23 回溯
  approval ledger 與 P0–P9 回溯完成報告。全部紀錄均綁定最小化 transcript
  證據、原完整 transcript SHA-256、對應 Supervisor PASS package 的 SHA-256
  與精確行號，並由嚴格 schema 驗證；完整 task export 保留於 F 槽、不隨
  release 公開。此授權及回溯證據均不構成 P24 RC 發布核准。
- 重新產生 P24 證據索引與 Supervisor 審查包。所有修正皆限於 P24 允許的
  治理與證據檔案，未以 P24 名義新增產品功能。

## 兩個發布阻擋

1. `SOURCE-001`：Git 工作樹仍有大量修改或未追蹤項目，並非乾淨、不可變且
   可追溯的發布 revision。
2. `ARTIFACT-001`：目前 commit 對應的 Windows、Linux、macOS 成品紀錄、
   provenance 與 signing attestation 尚未齊全。

`EVIDENCE-002` 已解除：P0–P9 的十份完成報告已依現存 transcript 與 Supervisor
PASS package 回溯重建，並明確標示為 retrospective record，不冒充當時原始報告。
`EVIDENCE-003` 已解除：P0–P23 共 24/24 份 approval ledger 通過來源路徑、
行號、reviewer/owner 語意及雙重 SHA-256 驗證；它們不取代原始 `REVIEW_STATE`，
也不表示 P24 已獲發布核准。
`INTEGRITY-001` 已解除：可重現 manifest 現已涵蓋 477 個 Git 發布來源，重算
驗證一致；Gate 另會以 Git 反向比對，任何未列來源、重複/不安全路徑、遺失或
雜湊不符都會 fail closed。P24 動態審查輸出不納入被審查來源，以避免循環雜湊。
`SECURITY-001` 已解除：目前 repository secret scan 通過，未輸出任何秘密值。
`VERSION-001` 亦已解除：五個正式版本來源均為 `1.0.0-rc.1`。

## 2026-08-11 驗證摘要

- 企業證據測試：`8 passed`；enterprise/supply-chain 合併驗證：`14 passed`；
  Ruff：PASS。
- 治理 manifest：`477 files`，重算驗證 PASS，未列來源測試 PASS。
- 回溯證據 drift check：35 個檔案一致；approval ledger：`24/24 valid`；
  P0–P9 必要完成報告缺漏：`0`。
- 企業稽核：`recommendation=NO_GO; blockers=2; owner_decision=NO_GO`；
  `--require-go` 預期回傳非零並阻擋發布。
- 治理與供應鏈 regression：`34 passed, 1 skipped`。
- Repository secret scan：PASS。
- Release integrity 與 Windows launcher：`12 passed, 1 skipped`。
- Portability/recovery：`14 passed, 1 skipped`。
- Backend compile 與 Ruff：PASS。
- Backend regression：`196 passed, 2 skipped, 24 warnings`。
- Frontend production build：PASS；frontend lint：PASS。
- Windows 一鍵啟動器隱藏啟動/關閉 smoke：PASS。
- Tauri `cargo check --locked`：PASS；F: 檔案系統不支援 hard-link，因此
  Cargo incremental cache 退回複製並產生 warning，但不影響檢查結果。

兩個 backend skip 分別是環境相依的訓練執行測試，以及 Windows 帳號無法建立
來源 symlink 時的測試；惡意 archive symlink 與特殊檔案拒絕測試仍有執行並通過。
現有 24 個 warnings 主要來自 FastAPI、Starlette TestClient 與 ORJSONResponse
棄用通知，未被隱藏，後續應在專屬維護階段處理。

## 治理偏差紀錄

在本次載入 P24 治理限制之前，對話中曾修改下列受保護的前端檔案：

- `frontend/src/App.tsx`
- `frontend/src/App.css`
- `frontend/src/index.css`

這些 UI 修改不是 P24 允許的證據工作，不能宣稱為 P24 合規成果，也不能在此
階段繼續擴充。為避免破壞使用者資料，本次未擅自回復或刪除；它們保留在 dirty
worktree，明確計入 `SOURCE-001`。最小修正方式是由專案擁有者決定：在未來經
核准的新功能階段正式承接並審查，或在建立可回復備份後撤回。

## 安全、隱私與跨平台

P24 稽核只輸出 finding 的路徑、類型與計數，不列印命中的秘密內容；未讀取簽章
金鑰、雲端憑證或使用者工作區內容。Windows 本機建置成功不等同三平台已簽章
發布證據，Linux/macOS workflow 定義也不能取代實際 attestation。

本專案模型政策維持本機或可完整免費使用的模型/API；P24 未增加付費供應商依賴。
本次未執行資料格式、資料庫或 API migration。

## 回復與下一步限制

目前沒有 RC 或 production 發布狀態可回復。保留現有 release channel、擁有者
`NO_GO` 決策與 P24 證據供稽核。必須先解除兩個 High 阻擋，再重新執行 P24，
取得指定 ChatGPT architecture reviewer 的 PASS 與專案擁有者發布核准，才可
變更 `CURRENT_PHASE` 或建立/啟動承接五項 UI/本機檔案功能的新階段與 RFC。

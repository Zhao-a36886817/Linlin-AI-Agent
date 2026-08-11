# syntax=docker/dockerfile:1

# 使用 conda-forge 維護的免費 Miniforge 映像。
# 「latest」只負責提供 conda 啟動層；真正的 Python、Node 與 Rust 版本由
# environment.docker.yml 約束。建置完成後 README 會要求記錄本機映像 ID。
FROM condaforge/miniforge3:latest

# 這些 Debian 套件是 Linux 上檢查 Tauri/Cargo 所需的編譯與 WebView 開發函式庫。
# --no-install-recommends 可避免加入瀏覽器、桌面環境等與測試無關的大型套件。
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        curl \
        libappindicator3-dev \
        libgtk-3-dev \
        librsvg2-dev \
        libssl-dev \
        libwebkit2gtk-4.1-dev \
        patchelf \
    && rm -rf /var/lib/apt/lists/*

# 先複製環境宣告，讓日後只修改說明文件時可以重用 Docker 建置快取。
COPY environment.docker.yml /tmp/environment.docker.yml
COPY requirements-test.txt /tmp/requirements-test.txt
COPY sandbox-start.sh /usr/local/bin/linlin-sandbox-start

# 建立名稱與使用者指定完全一致的 conda 環境，並安裝核心測試依賴。
# pip 使用 --no-cache-dir，避免把可重新下載的 wheel 留在最終映像中。
RUN conda env create --file /tmp/environment.docker.yml \
    && conda run --name Linlin-Agent python -m pip install \
        --no-cache-dir \
        --requirement /tmp/requirements-test.txt \
    && conda clean --all --yes \
    && rm -f /tmp/environment.docker.yml /tmp/requirements-test.txt \
    && chmod 0755 /usr/local/bin/linlin-sandbox-start

# 讓 docker exec 進入容器時直接使用 Linlin-Agent 環境，不必每次手動 activate。
ENV PATH="/opt/conda/envs/Linlin-Agent/bin:${PATH}" \
    CONDA_DEFAULT_ENV="Linlin-Agent" \
    PYTHONPATH="/workspace/backend" \
    PYTHONDONTWRITEBYTECODE="1" \
    PIP_DISABLE_PIP_VERSION_CHECK="1" \
    npm_config_cache="/sandbox-cache/npm" \
    CARGO_HOME="/sandbox-cache/cargo"

WORKDIR /workspace

# 容器預設只保持待命，不會自行啟動後端、下載模型、執行測試或修改專案。
# 所有驗證命令都必須由使用者或 Codex 明確觸發。
CMD ["/usr/local/bin/linlin-sandbox-start"]


import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import {
  cancelOrchestration,
  cancelScheduledJob,
  cancelTrainingJob,
  chat,
  applyCodeProposal,
  connectCloudProvider,
  configureRag,
  connectMcp,
  createMemory,
  createCodeProposal,
  createTrainingJob,
  deleteMemory,
  deleteCloudProvider,
  discardCodeProposal,
  discoverCloudProvider,
  disconnectMcp,
  getSchedulerState,
  getRuntimeOverview,
  getTrainingCapabilities,
  ingestRag,
  invokeMcp,
  listModels,
  listCloudProviders,
  listCodeProposals,
  listMemory,
  listOrchestration,
  listTrainingJobs,
  scheduleChat,
  searchRag,
  setSchedulerEnabled,
  setMemoryEnabled,
  startOrchestration,
  streamChat,
} from "./api";
import type {
  ChatMessage,
  CloudProviderInfo,
  CodeProposal,
  McpToolDefinition,
  MemoryRecord,
  ModelInfo,
  OrchestrationRun,
  RagResult,
  RuntimeFeature,
  RuntimeKey,
  SchedulerState,
  TrainingCapabilities,
  TrainingJob,
} from "./types";
import "./App.css";

type View = "overview" | "chat" | "providers" | "code" | RuntimeKey;
type ChatUiMessage = ChatMessage & {
  kind?: "model" | "error" | "code";
  thinking?: string;
  provider?: string;
  model?: string;
  proposal?: CodeProposal;
};
type ChatMode = "chat" | "code";
type ThemeName = "light" | "dark" | "ocean" | "forest" | "twilight" | "sand";

const LAST_CHAT_MODEL_KEY = "linlin-last-chat-model";
const LAST_CHAT_MODEL_MANUAL_KEY = "linlin-last-chat-model-manual";

/**
 * 選擇對話模型的順序：目前選擇 → 使用者上次手動選擇 → 一般用途本機模型 → 其他模型。
 * 預設模型會避開 OCR、Embedding 與純程式模型，防止把專用模型當成日常聊天助理。
 */
function chooseChatModel(items: ModelInfo[], current = ""): string {
  const stored = window.localStorage.getItem(LAST_CHAT_MODEL_KEY) ?? "";
  const hasManualSelection = window.localStorage.getItem(LAST_CHAT_MODEL_MANUAL_KEY) === "1";
  const isAvailable = (value: string) => items.some((item) => `${item.provider}\n${item.name}` === value);
  if (current && isAvailable(current)) return current;
  if (hasManualSelection && stored && isAvailable(stored)) return stored;
  const specializedName = /(ocr|embed|coder|code[-_:]|vision-only)/i;
  const preferred = items.find((item) => (
    item.local
    && item.capabilities.includes("completion")
    && (item.capabilities.includes("tools") || item.capabilities.includes("thinking"))
    && !specializedName.test(item.name)
  )) ?? items.find((item) => item.local && !specializedName.test(item.name)) ?? items.find((item) => item.local) ?? items[0];
  return preferred ? `${preferred.provider}\n${preferred.name}` : "";
}

const themes: Array<{ value: ThemeName; label: string }> = [
  { value: "light", label: "明亮" },
  { value: "dark", label: "黑暗" },
  { value: "ocean", label: "海洋" },
  { value: "forest", label: "森林" },
  { value: "twilight", label: "暮光" },
  { value: "sand", label: "暖沙" },
];

function getInitialTheme(): ThemeName {
  const stored = window.localStorage.getItem("linlin-theme");
  return themes.some((theme) => theme.value === stored) ? stored as ThemeName : "light";
}

const primaryNavigation: Array<{ key: View; label: string; icon: string }> = [
  { key: "overview", label: "首頁", icon: "◫" },
  { key: "chat", label: "對話", icon: "✦" },
  { key: "code", label: "工作區", icon: "</>" },
  { key: "providers", label: "模型", icon: "⬡" },
];

// 進階功能仍完整保留，但收進「更多功能」，避免日常操作時一次面對太多選項。
const advancedNavigation: Array<{ key: View; label: string; icon: string }> = [
  { key: "memory", label: "記憶", icon: "◉" },
  { key: "rag", label: "知識庫", icon: "◇" },
  { key: "orchestration", label: "團隊分析", icon: "⌁" },
  { key: "scheduler", label: "排程", icon: "◷" },
  { key: "mcp", label: "開發者工具", icon: "⌘" },
];

const navigation = [...primaryNavigation, ...advancedNavigation];

const runtimeCopy: Record<RuntimeKey, { eyebrow: string; title: string; description: string }> = {
  memory: { eyebrow: "對話記憶", title: "記憶管理", description: "只保存你明確同意的內容，並依不同對話分開管理。" },
  rag: { eyebrow: "個人知識", title: "知識庫", description: "從工作區文件建立可追溯、附引用來源的知識。" },
  mcp: { eyebrow: "開發者工具", title: "外部工具連線", description: "管理經核准的外部能力與最小權限。" },
  orchestration: { eyebrow: "團隊分析", title: "團隊分析工作流", description: "讓多個分析角色分工處理較複雜的任務。" },
  scheduler: { eyebrow: "自動任務", title: "排程中心", description: "建立可取消、可查閱紀錄且需同意的自動任務。" },
};

function StatusBadge({ feature }: { feature: RuntimeFeature }) {
  const label = feature.status === "ready" ? "運作中" : feature.status === "disabled" ? "已關閉" : "需要設定";
  return <span className={`status status--${feature.status}`}><i />{label}</span>;
}

function App() {
  const [view, setView] = useState<View>("overview");
  const [moreOpen, setMoreOpen] = useState(false);
  const [mobileMoreOpen, setMobileMoreOpen] = useState(false);
  const [theme, setTheme] = useState<ThemeName>(getInitialTheme);
  const [features, setFeatures] = useState<RuntimeFeature[]>([]);
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState("");
  const [backendOnline, setBackendOnline] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const data = await getRuntimeOverview();
      setFeatures(data.features);
      setNotice("");
      setBackendOnline(true);
    } catch {
      setNotice("Linlin 服務尚未啟動，部分功能暫時無法使用。");
      setBackendOnline(false);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    getRuntimeOverview()
      .then((data) => { if (active) { setFeatures(data.features); setNotice(""); setBackendOnline(true); } })
      .catch(() => { if (active) { setNotice("Linlin 服務尚未啟動，部分功能暫時無法使用。"); setBackendOnline(false); } })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, [view]);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = ["dark", "ocean", "forest", "twilight"].includes(theme) ? "dark" : "light";
    window.localStorage.setItem("linlin-theme", theme);
  }, [theme]);
  const currentFeature = useMemo(() => features.find((item) => item.key === view), [features, view]);

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand__mark">L</span><div><strong>Linlin</strong><small>個人智慧助理</small></div></div>
        <nav aria-label="主要功能">
          {primaryNavigation.map((item) => (
            <button key={item.key} className={view === item.key ? "nav-item active" : "nav-item"} onClick={() => setView(item.key)}>
              <span aria-hidden="true">{item.icon}</span>{item.label}
              {features.find((feature) => feature.key === item.key)?.status === "setup_required" && <b title="需要設定" />}
            </button>
          ))}
          <button className={advancedNavigation.some((item) => item.key === view) ? "nav-item active" : "nav-item"} onClick={() => setMoreOpen((current) => !current)} aria-expanded={moreOpen || advancedNavigation.some((item) => item.key === view)}>
            <span aria-hidden="true">•••</span>更多功能<b className="nav-chevron">⌄</b>
          </button>
          <div className={moreOpen || advancedNavigation.some((item) => item.key === view) ? "advanced-nav advanced-nav--open" : "advanced-nav"}>
            {advancedNavigation.map((item) => <button key={item.key} className={view === item.key ? "advanced-nav__item active" : "advanced-nav__item"} onClick={() => setView(item.key)}><span aria-hidden="true">{item.icon}</span>{item.label}</button>)}
          </div>
        </nav>
        <div className="sidebar__footer"><span className="local-dot" /><div><strong>本機優先</strong><small>資料優先留在這台電腦</small></div></div>
      </aside>

      <main className="main">
        <header className="topbar">
          <button className="mobile-brand" onClick={() => setView("overview")}>L</button>
          <div className="breadcrumb">工作區 <span>/</span> {navigation.find((item) => item.key === view)?.label}</div>
          <div className="topbar__actions">
            <label className="theme-picker">
              <span aria-hidden="true">◐</span>
              <select aria-label="主題" value={theme} onChange={(event) => setTheme(event.target.value as ThemeName)}>
                {themes.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
              </select>
            </label>
            <span className={backendOnline ? "health" : "health health--offline"}><i /> {backendOnline ? "服務正常" : "服務未連線"}</span>
            <button className="avatar" title="本機使用者">LL</button>
          </div>
        </header>
        <div className="mobile-nav" aria-label="行動版功能列">
          {primaryNavigation.slice(0, 3).map((item) => <button key={item.key} className={view === item.key ? "active" : ""} onClick={() => { setView(item.key); setMobileMoreOpen(false); }}>{item.icon}<small>{item.label}</small></button>)}
          <button className={view === "providers" || advancedNavigation.some((item) => item.key === view) ? "active" : ""} onClick={() => setMobileMoreOpen(true)} aria-expanded={mobileMoreOpen}>•••<small>更多</small></button>
        </div>
        {mobileMoreOpen && <div className="mobile-more-backdrop" onClick={() => setMobileMoreOpen(false)}><section className="mobile-more" aria-label="更多功能" onClick={(event) => event.stopPropagation()}><div className="mobile-more__header"><div><strong>更多功能</strong><small>模型與進階工具</small></div><button className="icon-button" onClick={() => setMobileMoreOpen(false)} aria-label="關閉更多功能">×</button></div>{[primaryNavigation[3], ...advancedNavigation].map((item) => <button key={item.key} className={view === item.key ? "mobile-more__item active" : "mobile-more__item"} onClick={() => { setView(item.key); setMobileMoreOpen(false); }}><span>{item.icon}</span><strong>{item.label}</strong><small>{item.key === "providers" ? "管理本機模型" : item.key === "mcp" ? "外部工具與進階設定" : "開啟功能"}</small></button>)}</section></div>}
        {notice && <div className="banner banner--error banner--action"><span>{notice}</span><button className="secondary" onClick={() => void refresh()}>重新連線</button></div>}
        {loading ? <LoadingState /> : (
          <section className="content">
            {view === "overview" && <Overview features={features} onOpen={setView} />}
            {view === "chat" && <ChatPanel />}
            {view === "providers" && <ProviderPanel />}
            {view === "code" && <CodePanel />}
            {view === "memory" && currentFeature && <MemoryPanel feature={currentFeature} onChanged={refresh} />}
            {view === "rag" && currentFeature && <RagPanel feature={currentFeature} onChanged={refresh} />}
            {view === "mcp" && currentFeature && <McpPanel feature={currentFeature} onChanged={refresh} />}
            {view === "orchestration" && currentFeature && <OrchestrationPanel feature={currentFeature} />}
            {view === "scheduler" && currentFeature && <SchedulerPanel feature={currentFeature} onChanged={refresh} />}
          </section>
        )}
      </main>
    </div>
  );
}

function LoadingState() {
  return <section className="content"><div className="skeleton hero-skeleton" /><div className="card-grid">{[1,2,3].map((n) => <div className="skeleton card-skeleton" key={n} />)}</div></section>;
}

function Overview({ features, onOpen }: { features: RuntimeFeature[]; onOpen: (view: View) => void }) {
  const ready = features.filter((feature) => feature.status === "ready").length;
  return <>
    <div className="hero">
      <div><p className="eyebrow">個人工作台</p><h1>早安，準備好開始了嗎？</h1><p>你可以從對話開始，需要時再開啟知識庫、團隊分析或自動任務。</p></div>
      <button className="primary" onClick={() => onOpen("chat")}><span>✦</span> 開始新對話</button>
    </div>
    <div className="metrics">
      <div><span className="metric-icon violet">◆</span><p>可使用功能<strong>{ready} / {features.length}</strong></p></div>
      <div><span className="metric-icon mint">✓</span><p>安全模式<strong>本機優先</strong></p></div>
      <div><span className="metric-icon amber">◷</span><p>待設定<strong>{features.length - ready} 項</strong></p></div>
    </div>
    <div className="section-heading"><div><p className="eyebrow">需要時再使用</p><h2>進階功能</h2></div><span>所有功能都會清楚顯示目前狀態</span></div>
    <div className="card-grid">
      {features.map((feature) => <button className="runtime-card" key={feature.key} onClick={() => onOpen(feature.key)}>
        <div className={`runtime-icon runtime-icon--${feature.key}`}>{navigation.find((item) => item.key === feature.key)?.icon}</div>
        <StatusBadge feature={feature} />
        <h3>{feature.label}</h3><p>{feature.summary}</p><span className="card-link">開啟控制頁 <b>→</b></span>
      </button>)}
    </div>
  </>;
}

function ChatPanel() {
  const [messages, setMessages] = useState<ChatUiMessage[]>([]);
  const [input, setInput] = useState("");
  const [mode, setMode] = useState<ChatMode>("chat");
  const [targetPath, setTargetPath] = useState("src/generated.py");
  const [contextText, setContextText] = useState("");
  const [cloudConsent, setCloudConsent] = useState(false);
  const [applyConfirmation, setApplyConfirmation] = useState("");
  const [conversationId, setConversationId] = useState(() => crypto.randomUUID());
  const [trainingOpen, setTrainingOpen] = useState(false);
  const [trainingCapabilities, setTrainingCapabilities] = useState<TrainingCapabilities | null>(null);
  const [trainingSelection, setTrainingSelection] = useState("");
  const [trainingJobs, setTrainingJobs] = useState<TrainingJob[]>([]);
  const [trainingConsent, setTrainingConsent] = useState(false);
  const [trainingBusy, setTrainingBusy] = useState(false);
  const [trainingError, setTrainingError] = useState("");
  const [sending, setSending] = useState(false);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [model, setModel] = useState("");
  const [modelError, setModelError] = useState("");
  const [loadingModels, setLoadingModels] = useState(true);
  const [toolsEnabled, setToolsEnabled] = useState(false);
  const [thinking, setThinking] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const selectedModel = models.find((item) => `${item.provider}\n${item.name}` === model);
  const selectedTrainingModel = trainingCapabilities?.models.find(
    (item) => `${item.provider}\n${item.model}` === trainingSelection,
  );
  const trainingMessages = messages
    .filter((message) => message.kind === "model" && (message.role === "user" || message.role === "assistant") && message.content.trim())
    .map((message) => ({ role: message.role as "user" | "assistant", content: message.content }));
  const hasTrainingPair = trainingMessages.some((message) => message.role === "user")
    && trainingMessages.some((message) => message.role === "assistant");

  const refreshTrainingJobs = useCallback(async () => {
    try {
      setTrainingJobs(await listTrainingJobs(conversationId));
      setTrainingError("");
    } catch (error) {
      setTrainingError(error instanceof Error ? error.message : String(error));
    }
  }, [conversationId]);

  useEffect(() => {
    if (!trainingOpen) return;
    let active = true;
    getTrainingCapabilities()
      .then((result) => { if (active) setTrainingCapabilities(result); })
      .catch((error) => { if (active) setTrainingError(error instanceof Error ? error.message : String(error)); });
    void refreshTrainingJobs();
    const timer = window.setInterval(() => { void refreshTrainingJobs(); }, 2_000);
    return () => { active = false; window.clearInterval(timer); };
  }, [refreshTrainingJobs, trainingOpen]);

  const refreshModels = useCallback(async () => {
    setLoadingModels(true);
    try {
      const result = await listModels(true);
      setModels(result.items);
      setModel((current) => chooseChatModel(result.items, current));
      setModelError(result.items.length ? "" : "尚未找到可用的本機模型，請確認 Ollama 已啟動。");
    } catch {
      setModels([]);
      setModel("");
      setModelError("模型服務目前沒有回應，請確認 Ollama 已啟動後重新檢查。");
    } finally {
      setLoadingModels(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    listModels(true)
      .then((result) => {
        if (!active) return;
        setModels(result.items);
        setModel((current) => chooseChatModel(result.items, current));
        setModelError(result.items.length ? "" : "尚未找到可用的本機模型，請確認 Ollama 已啟動。");
      })
      .catch(() => { if (active) setModelError("模型服務目前沒有回應，請確認 Ollama 已啟動後重新檢查。"); })
      .finally(() => { if (active) setLoadingModels(false); });
    return () => { active = false; abortRef.current?.abort(); };
  }, []);

  function stop() {
    abortRef.current?.abort();
    abortRef.current = null;
    setMessages((current) => {
      const last = current[current.length - 1];
      return last?.role === "assistant" && !last.content.trim() ? current.slice(0, -1) : current;
    });
    setSending(false);
  }

  function reset() {
    stop();
    setMessages([]);
    setInput("");
    setApplyConfirmation("");
    setConversationId(crypto.randomUUID());
    setTrainingJobs([]);
    setTrainingSelection("");
    setTrainingConsent(false);
    setTrainingError("");
  }

  async function send(event: FormEvent) {
    event.preventDefault();
    if (!input.trim() || sending || !selectedModel) return;
    const userMessage: ChatUiMessage = { role: "user", content: input.trim(), kind: "model" };
    const next = [...messages, userMessage];
    setInput("");
    setSending(true);
    if (mode === "code") {
      setMessages(next);
      try {
        const proposal = await createCodeProposal({
          provider: selectedModel.provider,
          model: selectedModel.name,
          instruction: userMessage.content,
          target_path: targetPath.trim(),
          context_paths: contextText.split(/[\n,]/).map((item) => item.trim()).filter(Boolean),
          cloud_consent: selectedModel.local ? false : cloudConsent,
        });
        setMessages([...next, {
          role: "assistant",
          content: proposal.summary,
          kind: "code",
          provider: proposal.provider,
          model: proposal.model,
          proposal,
        }]);
        setApplyConfirmation("");
      } catch (error) {
        setMessages([...next, {
          role: "assistant",
          content: error instanceof Error ? error.message : String(error),
          kind: "error",
        }]);
      } finally {
        setSending(false);
      }
      return;
    }
    const conversation: ChatMessage[] = [
      ...messages
        .filter((message) => message.kind !== "error" && message.content.trim())
        .map(({ role, content }) => ({ role, content })),
      { role: "user", content: userMessage.content },
    ];
    const request = {
      provider: selectedModel.provider,
      model: selectedModel.name,
      tools_enabled: toolsEnabled,
      messages: conversation,
      options: { temperature: 0.3, max_tokens: 512, think: thinking },
    };
    setMessages([...next, { role: "assistant", content: "", kind: "model", provider: selectedModel.provider, model: selectedModel.name }]);
    try {
      if (toolsEnabled) {
        const result = await chat(request);
        if (!result.content.trim()) throw new Error("模型完成請求，但沒有提供最終回答內容。");
        setMessages([...next, {
          role: "assistant",
          content: result.content,
          thinking: result.thinking ?? undefined,
          kind: "model",
          provider: result.provider,
          model: result.model,
        }]);
      } else {
        const controller = new AbortController();
        abortRef.current = controller;
        let answer = "";
        let reasoning = "";
        let responseProvider = selectedModel.provider;
        let responseModel = selectedModel.name;
        await streamChat(request, (chunk) => {
          answer += chunk.content;
          reasoning += chunk.thinking ?? "";
          responseProvider = chunk.provider;
          responseModel = chunk.model;
          setMessages([...next, {
            role: "assistant",
            content: answer,
            thinking: reasoning || undefined,
            kind: "model",
            provider: responseProvider,
            model: responseModel,
          }]);
        }, controller.signal);
        if (!answer.trim()) throw new Error("模型串流已結束，但沒有提供最終回答內容。");
      }
    } catch (error) {
      if ((error as Error).name !== "AbortError") {
        setMessages([...next, {
          role: "assistant",
          content: error instanceof Error ? error.message : String(error),
          kind: "error",
        }]);
      }
    } finally {
      abortRef.current = null;
      setSending(false);
    }
  }

  function replaceProposal(proposal: CodeProposal) {
    setMessages((current) => current.map((message) => (
      message.proposal?.id === proposal.id ? { ...message, content: proposal.summary, proposal } : message
    )));
  }

  async function applyConversationProposal(proposal: CodeProposal) {
    if (applyConfirmation !== "APPLY CODE") return;
    if (!window.confirm(`確認將完整內容寫入 workspace/${proposal.target_path}？Linlin 不會執行它。`)) return;
    setSending(true);
    try {
      replaceProposal(await applyCodeProposal(proposal.id));
      setApplyConfirmation("");
    } catch (error) {
      setMessages((current) => [...current, { role: "assistant", content: String(error), kind: "error" }]);
    } finally {
      setSending(false);
    }
  }

  async function discardConversationProposal(proposal: CodeProposal) {
    setSending(true);
    try {
      await discardCodeProposal(proposal.id);
      replaceProposal({ ...proposal, status: "discarded" });
      setApplyConfirmation("");
    } catch (error) {
      setMessages((current) => [...current, { role: "assistant", content: String(error), kind: "error" }]);
    } finally {
      setSending(false);
    }
  }

  async function startTraining() {
    if (!selectedTrainingModel || !hasTrainingPair || !trainingConsent) return;
    setTrainingBusy(true);
    setTrainingError("");
    try {
      const job = await createTrainingJob({
        conversation_id: conversationId,
        provider: selectedTrainingModel.provider,
        model: selectedTrainingModel.model,
        messages: trainingMessages,
        engine: selectedTrainingModel.engine,
        cloud_consent: !selectedTrainingModel.local && trainingConsent,
        local_consent: selectedTrainingModel.local && trainingConsent,
        max_steps: 20,
      });
      setTrainingJobs((current) => [...current.filter((item) => item.id !== job.id), job]);
      setTrainingConsent(false);
    } catch (error) {
      setTrainingError(error instanceof Error ? error.message : String(error));
    } finally {
      setTrainingBusy(false);
    }
  }

  async function cancelTraining(job: TrainingJob) {
    setTrainingBusy(true);
    try {
      const cancelled = await cancelTrainingJob(job.id, conversationId);
      setTrainingJobs((current) => current.map((item) => item.id === cancelled.id ? cancelled : item));
    } catch (error) {
      setTrainingError(error instanceof Error ? error.message : String(error));
    } finally {
      setTrainingBusy(false);
    }
  }

  const canSend = Boolean(selectedModel && input.trim()) && (mode === "chat" || Boolean(targetPath.trim()) && (selectedModel?.local || cloudConsent));

  return <div className="page-stack chat-page"><PageTitle eyebrow="智慧助理" title="開始對話" description="已為你優先選擇本機模型；需要寫程式時可切換成程式協助。" action={<div className="chat-title-actions"><button className="primary" onClick={reset}>＋ 新對話</button><button className={trainingOpen ? "secondary training-toggle active" : "secondary training-toggle"} onClick={() => setTrainingOpen((current) => !current)} aria-expanded={trainingOpen}>••• 進階</button></div>} />
    <div className="chat-toolbar">
      <label className="chat-mode-select"><span>用途</span><select value={mode} onChange={(event) => { setMode(event.target.value as ChatMode); setCloudConsent(false); }}><option value="chat">一般對話</option><option value="code">程式協助</option></select></label>
      <label className="model-select"><span>目前模型（共 {models.length} 個）</span><select value={model} onChange={(event) => { const value = event.target.value; setModel(value); setCloudConsent(false); if (value) { window.localStorage.setItem(LAST_CHAT_MODEL_KEY, value); window.localStorage.setItem(LAST_CHAT_MODEL_MANUAL_KEY, "1"); } }} disabled={loadingModels || !models.length}><option value="">{loadingModels ? "正在尋找模型…" : models.length ? "選擇模型" : "沒有可用模型"}</option>{models.map((item) => <option key={`${item.provider}:${item.name}`} value={`${item.provider}\n${item.name}`}>{item.name}{item.local ? " · 本機" : ` · ${item.provider_label ?? item.provider}`}{item.parameter_size ? ` · ${item.parameter_size}` : ""}</option>)}</select></label>
      <button className="icon-button model-refresh" onClick={() => void refreshModels()} disabled={loadingModels} aria-label="重新尋找模型" title="重新尋找模型">{loadingModels ? "…" : "↻"}</button>
      <label className="switch"><input type="checkbox" checked={thinking} onChange={(event) => setThinking(event.target.checked)} disabled={mode === "code"}/><span />深入思考</label>
      <label className="switch"><input type="checkbox" checked={toolsEnabled} onChange={(event) => setToolsEnabled(event.target.checked)} disabled={mode === "code"}/><span />使用工具</label>
    </div>
    {selectedModel && !selectedModel.local && <div className="cloud-notice"><strong>將使用外部服務</strong><span>訊息會送往你設定的 {selectedModel.provider_label ?? selectedModel.provider}；存取金鑰只會由後端安全儲存區讀取。</span></div>}
    {mode === "code" && <div className="chat-code-config surface"><label><span>要修改的工作區檔案</span><input value={targetPath} onChange={(event) => setTargetPath(event.target.value)} placeholder="src/example.py"/></label><label className="chat-code-context"><span>參考檔案（選填）</span><input value={contextText} onChange={(event) => setContextText(event.target.value)} placeholder="src/types.py, README.md"/></label>{selectedModel && !selectedModel.local && <label className="chat-code-consent"><input type="checkbox" checked={cloudConsent} onChange={(event) => setCloudConsent(event.target.checked)}/><span>我同意將指令與列出的程式碼內容送往 {selectedModel.provider_label ?? selectedModel.provider}</span></label>}<p>只會先建立可檢查的修改提案，不會自動執行程式或碰觸受保護的路徑。</p></div>}
    {trainingOpen && <section className="chat-training surface"><div className="training-header"><div><p className="eyebrow">進階功能</p><h3>使用這段對話訓練模型</h3><span>此功能會使用較多電腦資源；開始前會再次要求你確認。</span></div><b>{trainingMessages.length} 則可用訊息</b></div><div className="training-controls"><label><span>可訓練模型</span><select value={trainingSelection} onChange={(event) => { setTrainingSelection(event.target.value); setTrainingConsent(false); }}><option value="">{trainingCapabilities?.models.length ? "選擇已註冊的本機權重或外部候選模型" : "目前沒有可用訓練模型"}</option>{trainingCapabilities?.models.map((item) => <option key={`${item.provider}:${item.model}`} value={`${item.provider}\n${item.model}`}>{item.provider_label} · {item.model} · {item.local ? "本機 LoRA" : "外部微調"}{item.size_bytes ? ` · ${(item.size_bytes / 1_073_741_824).toFixed(1)} GB` : ""}</option>)}</select></label><label className="training-consent"><input type="checkbox" checked={trainingConsent} onChange={(event) => setTrainingConsent(event.target.checked)} disabled={!selectedTrainingModel}/><span>{!selectedTrainingModel ? "請先選擇模型；本機資料不會上傳。" : selectedTrainingModel.local ? "我同意在本機使用運算資源訓練，並將訓練結果寫入 outputs/training。" : "我同意將這段對話資料送到所選外部服務，並了解它可能產生費用。"}</span></label><button className="primary" onClick={() => void startTraining()} disabled={trainingBusy || !selectedTrainingModel || !hasTrainingPair || !trainingConsent}>{trainingBusy ? "處理中…" : "建立訓練工作"}</button></div><div className={trainingCapabilities?.local.available ? "local-training-status local-training-status--ready" : "local-training-status"}><strong>本機訓練</strong><span>{trainingCapabilities?.local.reason ?? "正在檢查本機訓練套件與權重…"}</span></div>{trainingError && <div className="banner-inline banner--error">{trainingError}</div>}<div className="training-jobs">{trainingJobs.length === 0 ? <p>此對話尚無訓練工作。完成至少一輪問答後，才能將它整理成訓練資料。</p> : trainingJobs.map((job) => <article key={job.id}><div className="training-job-heading"><div><strong>{job.provider_label} · {job.model}</strong><span>{job.examples} 組訓練範例 · {job.engine === "local_lora" ? "本機" : "外部服務"} · 更新 {new Date(job.updated_at).toLocaleTimeString()}</span></div><b className={`training-status training-status--${job.status}`}>{job.status}</b></div><TrainingChart job={job}/>{job.error && <div className="code-warning">{job.error}</div>}{job.trained_model && <div className="provider-success banner-inline">已產生模型：{job.trained_model}</div>}{["validating", "uploading", "queued", "running", "unknown"].includes(job.status) && <button className="secondary danger" onClick={() => void cancelTraining(job)} disabled={trainingBusy}>取消訓練</button>}</article>)}</div></section>}
    {modelError && <div className="chat-setup"><div><strong>目前無法開始對話</strong><p>{modelError}</p><small>啟動 Ollama 後按下「重新檢查」即可，不需要重新開啟頁面。</small></div><button className="secondary" onClick={() => void refreshModels()}>重新檢查</button></div>}
    <div className="chat-panel"><div className="chat-messages" aria-live="polite">
      {messages.length === 0 && !modelError && <div className="empty-chat"><span>✦</span><h3>今天想完成什麼？</h3><p>{selectedModel ? `${selectedModel.name} 已準備好` : "正在準備本機模型…"}</p><div className="prompt-chips"><button onClick={() => setInput("幫我整理今天最重要的三件事")}>整理今日重點</button><button onClick={() => setInput("請用繁體中文幫我整理以下內容：")}>寫作與整理</button><button onClick={() => setInput("請用簡單的方式解釋這個問題：")}>解釋一個問題</button><button onClick={() => { setMode("code"); setInput("請幫我規劃並撰寫這項程式功能："); }}>程式協助</button></div></div>}
      {messages.map((message, index) => <div key={index} className={`bubble bubble--${message.kind === "error" ? "error" : message.role}${message.proposal ? " bubble--code" : ""}`}>
        <small>{message.role === "user" ? "你" : message.kind === "error" ? "系統狀態（非模型回答）" : `${message.provider ?? "ollama"} · ${message.model ?? model}`}</small>
        {message.thinking && <details className="model-thinking"><summary>查看模型實際思考內容</summary><div>{message.thinking}</div></details>}
        {message.proposal ? <ConversationCodeCard proposal={message.proposal} busy={sending} confirmation={applyConfirmation} onConfirmation={setApplyConfirmation} onApply={applyConversationProposal} onDiscard={discardConversationProposal}/> : message.content || (sending && index === messages.length - 1 ? <span className="typing"><i/><i/><i/></span> : "")}
      </div>)}
    </div><form className="composer" onSubmit={send}><textarea value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } }} placeholder={!selectedModel ? "正在準備模型…" : mode === "code" ? `描述要在 ${targetPath || "目標檔案"} 完成的功能…` : `輸入你想詢問 ${selectedModel.name} 的內容…`} rows={2} disabled={!selectedModel}/>{sending ? mode === "chat" ? <button type="button" className="stop-button" onClick={stop}>停止 ■</button> : <button type="button" className="primary" disabled>正在產生程式提案…</button> : <button className="primary" disabled={!canSend}>{mode === "code" ? "產生修改提案 ↑" : "送出 ↑"}</button>}</form><div className="composer-hint"><span>Enter 送出 · Shift + Enter 換行</span><span>{mode === "code" ? "程式協助：確認後才會套用，不會自動執行" : toolsEnabled ? "使用工具：完成後一次顯示" : "即時回答"}</span></div></div>
  </div>;
}

function ConversationCodeCard({ proposal, busy, confirmation, onConfirmation, onApply, onDiscard }: {
  proposal: CodeProposal;
  busy: boolean;
  confirmation: string;
  onConfirmation: (value: string) => void;
  onApply: (proposal: CodeProposal) => Promise<void>;
  onDiscard: (proposal: CodeProposal) => Promise<void>;
}) {
  return <div className="conversation-code-card"><div className="conversation-code-heading"><div><strong>{proposal.target_path}</strong><span>{proposal.summary}</span></div><b className={`proposal-status proposal-status--${proposal.status}`}>{proposal.status}</b></div>{proposal.warnings.map((warning) => <div className="code-warning" key={warning}>⚠ {warning}</div>)}<pre className="code-diff">{proposal.diff || "內容沒有差異。"}</pre><details className="full-code"><summary>查看完整產生內容</summary><pre>{proposal.content}</pre></details>{proposal.status === "pending" && <div className="conversation-code-confirm"><label><span>輸入 APPLY CODE 才能寫入</span><input value={confirmation} onChange={(event) => onConfirmation(event.target.value)} placeholder="APPLY CODE" autoComplete="off"/></label><div className="code-actions"><button className="secondary danger" onClick={() => void onDiscard(proposal)} disabled={busy}>捨棄</button><button className="primary" onClick={() => void onApply(proposal)} disabled={busy || confirmation !== "APPLY CODE" || !proposal.diff}>確認並套用</button></div></div>}{proposal.status === "applied" && <div className="provider-success banner-inline">已寫入 workspace/{proposal.target_path}；Linlin 沒有執行它。</div>}{proposal.status === "discarded" && <div className="code-warning">此提案已捨棄，沒有寫入檔案。</div>}</div>;
}

function TrainingChart({ job }: { job: TrainingJob }) {
  const samples = job.metrics.filter((metric) => typeof metric.train_loss === "number");
  if (!samples.length) {
    return <div className="training-chart training-chart--empty"><span className="training-pulse"/><p>{["validating", "uploading", "queued", "running", "unknown"].includes(job.status) ? "等待模型服務回傳實際訓練數值…" : "模型服務沒有提供可繪製的訓練數值。"}</p></div>;
  }
  const losses = samples.map((metric) => metric.train_loss as number);
  const minimum = Math.min(...losses);
  const maximum = Math.max(...losses);
  const range = maximum - minimum || 1;
  const points = samples.map((metric, index) => {
    const x = samples.length === 1 ? 160 : 12 + index * (296 / (samples.length - 1));
    const y = 82 - (((metric.train_loss as number) - minimum) / range) * 64;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  return <div className="training-chart"><div><span>訓練損失值</span><strong>{losses.at(-1)?.toFixed(4)}</strong><small>步驟 {samples.at(-1)?.step}</small></div><svg viewBox="0 0 320 96" role="img" aria-label={`包含 ${samples.length} 筆數值的訓練圖表`}><line x1="12" y1="82" x2="308" y2="82"/><line x1="12" y1="18" x2="12" y2="82"/><polyline points={points}/>{samples.map((metric, index) => { const [x, y] = points.split(" ")[index].split(","); return <circle key={metric.step} cx={x} cy={y} r="3"/>; })}</svg></div>;
}

function ProviderPanel() {
  const { models: localModels, loading: loadingLocalModels, error: localModelError, refresh: refreshLocalModels } = useLocalModels();
  const [providers, setProviders] = useState<CloudProviderInfo[]>([]);
  const [name, setName] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [credentialEnv, setCredentialEnv] = useState("");
  const [kind, setKind] = useState("auto");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    try { setProviders((await listCloudProviders()).items); setError(""); }
    catch (reason) { setError(String(reason)); }
  }, []);
  useEffect(() => {
    let active = true;
    listCloudProviders()
      .then((result) => { if (active) setProviders(result.items); })
      .catch((reason) => { if (active) setError(String(reason)); });
    return () => { active = false; };
  }, []);
  async function connect(event: FormEvent) {
    event.preventDefault(); setBusy(true); setMessage("");
    try {
      const result = await connectCloudProvider({
        name: name.trim(),
        base_url: baseUrl.trim(),
        api_key: apiKey || undefined,
        credential_env: credentialEnv.trim() || undefined,
        kind: kind === "auto" ? undefined : kind,
        consent: true,
      });
      setApiKey("");
      setName("");
      setMessage(`已辨識為 ${result.detected_kind}，探索到 ${result.models.length} 個模型。密鑰儲存：${result.credential_persistent ? "作業系統保險庫" : "本次執行階段"}。`);
      await load();
    } catch (reason) { setError(String(reason)); }
    finally { setBusy(false); }
  }
  async function discover(provider: CloudProviderInfo) {
    setBusy(true);
    try { const result = await discoverCloudProvider(provider.id); setMessage(`${provider.name} 已重新探索 ${result.models.length} 個模型；回到對話頁重新掃描即可使用。`); setError(""); }
    catch (reason) { setError(String(reason)); }
    finally { setBusy(false); }
  }
  async function remove(provider: CloudProviderInfo) {
    if (!window.confirm(`刪除 ${provider.name} 與保存在安全儲存區的密鑰？`)) return;
    setBusy(true);
    try { await deleteCloudProvider(provider.id); await load(); setMessage(`${provider.name} 已移除。`); }
    catch (reason) { setError(String(reason)); }
    finally { setBusy(false); }
  }
  return <div className="page-stack"><PageTitle eyebrow="模型管理" title="可用模型" description="優先使用本機 Ollama 免費模型；需要時才展開其他模型服務。"/>
    <section className="surface local-model-summary"><div className="list-header"><div><p className="eyebrow">本機模型</p><h3>{loadingLocalModels ? "正在檢查…" : `找到 ${localModels.length} 個模型`}</h3></div><button className="secondary" onClick={() => void refreshLocalModels()} disabled={loadingLocalModels}>重新檢查</button></div>{localModelError ? <div className="banner-inline banner--error">目前無法讀取本機模型，請確認 Ollama 已啟動。</div> : localModels.length ? <div className="local-model-list">{localModels.map((item) => <span key={`${item.provider}:${item.name}`}><i/> {item.name}{item.parameter_size ? <small>{item.parameter_size}</small> : null}</span>)}</div> : !loadingLocalModels && <EmptyState icon="⬡" title="尚未找到本機模型" text="啟動 Ollama 並安裝至少一個免費模型後，再按下重新檢查。"/>}</section>
    <details className="surface cloud-provider-advanced"><summary><span><strong>加入其他模型服務</strong><small>進階設定：API 金鑰與外部服務網址</small></span><b>展開設定⌄</b></summary><div className="cloud-provider-advanced__body">
      <div className="safety-strip"><span>✓</span><div><strong>金鑰安全保護</strong><p>API 金鑰只送到本機後端並交由作業系統保險庫保存，不會寫入專案或瀏覽器儲存空間。</p></div><span className="status status--ready"><i/>安全輸入</span></div>
      {error && <div className="banner-inline banner--error">{error}</div>}{message && <div className="banner-inline provider-success">{message}</div>}
      <div className="two-column"><form className="surface form-card" onSubmit={connect} autoComplete="off"><p className="eyebrow">連線設定</p><h3>加入外部模型服務</h3><label>顯示名稱<input value={name} onChange={(event) => setName(event.target.value)} placeholder="例如：免費模型服務"/></label><label>服務網址<input value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} type="url" placeholder="由服務商提供，包含 API 版本路徑"/></label><label>自動辨識<select value={kind} onChange={(event) => setKind(event.target.value)}><option value="auto">自動辨識（建議）</option><option value="openai">OpenAI</option><option value="anthropic">Anthropic</option><option value="gemini">Gemini</option><option value="openrouter">OpenRouter</option><option value="groq">Groq</option><option value="deepseek">DeepSeek</option><option value="mistral">Mistral</option><option value="openai_compatible">其他相容服務</option></select></label><label>API 金鑰<input value={apiKey} onChange={(event) => setApiKey(event.target.value)} type="password" placeholder="輸入後只傳給本機安全儲存區" autoComplete="new-password" disabled={Boolean(credentialEnv)}/></label><div className="field-divider"><span>或</span></div><label>既有環境變數<input value={credentialEnv} onChange={(event) => setCredentialEnv(event.target.value.toUpperCase())} placeholder="例如 COMPANY_AI_API_KEY" pattern="[A-Z][A-Z0-9_]*" disabled={Boolean(apiKey)}/></label><p className="consent-note">按下連線代表你同意 Linlin 向這個服務驗證金鑰並尋找模型；外部網址強制使用 HTTPS。</p><button className="primary" disabled={busy || !name.trim() || !baseUrl.trim() || (!apiKey && !credentialEnv.trim())}>{busy ? "正在安全連線…" : "同意、辨識並連線"}</button></form>
        <div className="surface list-card"><div className="list-header"><div><p className="eyebrow">已加入服務</p><h3>外部服務</h3></div><button className="icon-button" onClick={() => void load()}>↻</button></div>{providers.length === 0 ? <EmptyState icon="⬡" title="尚未加入外部服務" text="本機 Ollama 不受影響；確定有免費額度時再加入即可。"/> : <div className="provider-list">{providers.map((provider) => <article key={provider.id}><div><strong>{provider.name}</strong><small>{provider.kind} · 費用狀態 {provider.cost_class}</small><p>{provider.base_url}</p></div><span className={`status ${provider.has_api_key ? "status--ready" : "status--setup_required"}`}><i/>{provider.has_api_key ? "密鑰可用" : "缺少密鑰"}</span><div className="provider-actions"><button className="secondary" onClick={() => void discover(provider)} disabled={busy || !provider.has_api_key}>同意並尋找模型</button><button className="secondary danger" onClick={() => void remove(provider)} disabled={busy}>刪除</button></div></article>)}</div>}</div></div>
    </div></details>
  </div>;
}

function CodePanel() {
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [selection, setSelection] = useState("");
  const [targetPath, setTargetPath] = useState("src/generated.py");
  const [instruction, setInstruction] = useState("");
  const [contextText, setContextText] = useState("");
  const [cloudConsent, setCloudConsent] = useState(false);
  const [proposal, setProposal] = useState<CodeProposal | null>(null);
  const [history, setHistory] = useState<CodeProposal[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const selectedModel = models.find((item) => `${item.provider}\n${item.name}` === selection);
  const loadHistory = useCallback(async () => {
    try { setHistory(await listCodeProposals()); } catch (reason) { setError(String(reason)); }
  }, []);
  useEffect(() => {
    let active = true;
    Promise.all([listModels(true), listCodeProposals()])
      .then(([modelResult, proposals]) => { if (active) { setModels(modelResult.items); setHistory(proposals); } })
      .catch((reason) => { if (active) setError(String(reason)); });
    return () => { active = false; };
  }, []);
  async function generate(event: FormEvent) {
    event.preventDefault();
    if (!selectedModel) return;
    setBusy(true); setProposal(null); setError("");
    try {
      const result = await createCodeProposal({
        provider: selectedModel.provider,
        model: selectedModel.name,
        instruction: instruction.trim(),
        target_path: targetPath.trim(),
        context_paths: contextText.split(/[\n,]/).map((item) => item.trim()).filter(Boolean),
        cloud_consent: selectedModel.local ? false : cloudConsent,
      });
      setProposal(result);
      await loadHistory();
    } catch (reason) { setError(String(reason)); }
    finally { setBusy(false); }
  }
  async function applyProposal() {
    if (!proposal || !window.confirm(`確認將預覽中的完整內容寫入 workspace/${proposal.target_path}？Linlin 不會執行它。`)) return;
    setBusy(true);
    try { const applied = await applyCodeProposal(proposal.id); setProposal(applied); await loadHistory(); setError(""); }
    catch (reason) { setError(String(reason)); }
    finally { setBusy(false); }
  }
  async function discardProposal() {
    if (!proposal) return;
    setBusy(true);
    try { await discardCodeProposal(proposal.id); setProposal(null); await loadHistory(); }
    catch (reason) { setError(String(reason)); }
    finally { setBusy(false); }
  }
  return <div className="page-stack"><PageTitle eyebrow="程式工作區" title="程式協助" description="由你選擇的模型建立修改提案，確認差異後才會套用到安全工作區。"/>
    <div className="safety-strip"><span>✓</span><div><strong>只預覽，不自動執行</strong><p>路徑必須位於 workspace；模型無法直接寫檔，套用前會檢查語法、原檔版本與你的確認。</p></div><span className="status status--ready"><i/>Workspace-safe</span></div>{error && <div className="banner-inline banner--error">{error}</div>}
    <div className="code-layout"><form className="surface form-card" onSubmit={generate}><p className="eyebrow">建立提案</p><h3>建立程式修改提案</h3><label>模型<select value={selection} onChange={(event) => { setSelection(event.target.value); setCloudConsent(false); }}><option value="">選擇本機或外部模型</option>{models.map((item) => <option key={`${item.provider}:${item.name}`} value={`${item.provider}\n${item.name}`}>{item.provider_label ?? item.provider} · {item.name} · {item.local ? "本機" : "外部服務"}</option>)}</select></label><label>要修改的工作區檔案<input value={targetPath} onChange={(event) => setTargetPath(event.target.value)} placeholder="src/example.py"/></label><label>要完成的功能<textarea value={instruction} onChange={(event) => setInstruction(event.target.value)} rows={7} placeholder="例如：建立 FastAPI 健康檢查功能，包含型別與錯誤處理"/></label><label>參考檔案（選填，以逗號或換行分隔）<textarea value={contextText} onChange={(event) => setContextText(event.target.value)} rows={3} placeholder="src/types.py, README.md"/></label>{selectedModel && !selectedModel.local && <label className="code-consent"><input type="checkbox" checked={cloudConsent} onChange={(event) => setCloudConsent(event.target.checked)}/><span>我同意將指令與列出的程式碼內容送往 {selectedModel.provider_label ?? selectedModel.provider}</span></label>}<p className="consent-note">受保護的設定檔與工作區外路徑會被拒絕；提案也不會自動執行。</p><button className="primary" disabled={busy || !selectedModel || !targetPath.trim() || !instruction.trim() || (!selectedModel.local && !cloudConsent)}>{busy ? "模型正在產生與驗證…" : "產生可檢查的提案"}</button></form>
      <div className="surface code-preview"><div className="list-header"><div><p className="eyebrow">預覽與套用</p><h3>{proposal ? proposal.target_path : "尚無提案"}</h3></div>{proposal && <span className={`proposal-status proposal-status--${proposal.status}`}>{proposal.status}</span>}</div>{!proposal ? <EmptyState icon="</>" title="等待修改提案" text="模型回傳後會先顯示摘要、警告與程式差異，不會直接寫入。"/> : <><p className="proposal-summary">{proposal.summary}</p>{proposal.warnings.map((warning) => <div className="code-warning" key={warning}>⚠ {warning}</div>)}<pre className="code-diff">{proposal.diff || "內容沒有差異。"}</pre><details className="full-code"><summary>查看完整產生內容</summary><pre>{proposal.content}</pre></details>{proposal.status === "pending" && <div className="code-actions"><button className="secondary danger" onClick={() => void discardProposal()} disabled={busy}>捨棄</button><button className="primary" onClick={() => void applyProposal()} disabled={busy || !proposal.diff}>確認並套用</button></div>}{proposal.status === "applied" && <div className="provider-success banner-inline">已寫入工作區/{proposal.target_path}；程式碼尚未執行。</div>}</>}</div></div>
    {history.length > 0 && <div className="surface proposal-history"><p className="eyebrow">本次紀錄</p><div>{history.slice().reverse().map((item) => <button key={item.id} onClick={() => setProposal(item)}><strong>{item.target_path}</strong><span>{item.status} · {item.model}</span></button>)}</div></div>}
  </div>;
}

function MemoryPanel({ feature, onChanged }: { feature: RuntimeFeature; onChanged: () => Promise<void> }) {
  const [records, setRecords] = useState<MemoryRecord[]>([]);
  const [session, setSession] = useState("default");
  const [content, setContent] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [confirming, setConfirming] = useState(false);
  const load = useCallback(async () => {
    if (!feature.enabled) { setRecords([]); return; }
    try { setRecords(await listMemory(session)); setError(""); } catch (reason) { setError(String(reason)); }
  }, [feature.enabled, session]);
  useEffect(() => {
    let active = true;
    if (!feature.enabled) return () => { active = false; };
    listMemory(session)
      .then((items) => { if (active) { setRecords(items); setError(""); } })
      .catch((reason) => { if (active) setError(String(reason)); });
    return () => { active = false; };
  }, [feature.enabled, session]);
  async function toggle() {
    setBusy(true); try { await setMemoryEnabled(!feature.enabled); await onChanged(); } catch (reason) { setError(String(reason)); } finally { setBusy(false); }
    setConfirming(false);
  }
  async function add(event: FormEvent) {
    event.preventDefault(); if (!content.trim()) return;
    setBusy(true); try { await createMemory(content.trim(), session); setContent(""); await load(); } catch (reason) { setError(String(reason)); } finally { setBusy(false); }
  }
  async function remove(id: string) {
    if (!window.confirm("確定永久刪除這筆記憶？")) return;
    try { await deleteMemory(id, session); await load(); } catch (reason) { setError(String(reason)); }
  }
  return <div className="page-stack"><PageTitle eyebrow="對話記憶" title="記憶管理" description="只保存你明確同意的內容，並依不同對話分開管理。" action={<button className={feature.enabled ? "secondary danger" : "primary"} onClick={() => setConfirming(true)} disabled={busy}>{feature.enabled ? "關閉記憶" : "啟用記憶"}</button>} />
    <SafetyStrip feature={feature} />{error && <div className="banner banner--error">{error}</div>}
    <div className="two-column"><form className="surface form-card" onSubmit={add}><p className="eyebrow">新增記憶</p><h3>記住一件事情</h3><label>對話名稱<input value={session} onChange={(event) => setSession(event.target.value)} maxLength={200}/></label><label>想讓 Linlin 記住的內容<textarea value={content} onChange={(event) => setContent(event.target.value)} placeholder="例如：回答時偏好繁體中文" rows={5} maxLength={4000}/></label><p className="consent-note">送出即代表你同意將此內容暫存在本機；疑似密鑰會被拒絕。</p><button className="primary" disabled={!feature.enabled || busy || !content.trim()}>儲存記憶</button></form>
      <div className="surface list-card"><div className="list-header"><div><p className="eyebrow">已儲存</p><h3>目前記憶</h3></div><button className="icon-button" onClick={() => void load()} title="重新整理">↻</button></div>{!feature.enabled ? <EmptyState icon="◉" title="記憶功能目前關閉" text="啟用後即可新增與管理本機記憶。"/> : records.length === 0 ? <EmptyState icon="◉" title="還沒有記憶" text="新增第一筆偏好或背景資訊。"/> : <div className="record-list">{records.map((record) => <article key={record.id}><p>{record.content}</p><small>到期：{new Date(record.expires_at).toLocaleString()}</small><button onClick={() => void remove(record.id)}>刪除</button></article>)}</div>}</div></div>
    {confirming && <div className="modal-backdrop" role="presentation"><div className="modal" role="dialog" aria-modal="true" aria-labelledby="memory-confirm-title"><span className="modal__icon">◉</span><h3 id="memory-confirm-title">{feature.enabled ? "關閉記憶功能？" : "啟用記憶功能？"}</h3><p>{feature.enabled ? "關閉後不會新增或讀取記憶，尚未到期的內容仍會保留。" : "啟用後只會儲存你明確送出的內容；疑似憑證與密鑰會被拒絕。"}</p><div className="modal__actions"><button className="secondary" onClick={() => setConfirming(false)}>取消</button><button className="primary" onClick={() => void toggle()} disabled={busy}>{feature.enabled ? "確認關閉" : "確認啟用"}</button></div></div></div>}
  </div>;
}

function useLocalModels() {
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const response = await listModels();
      setModels(response.items.filter((item) => item.local));
      setError("");
    } catch (reason) { setError(String(reason)); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => {
    let active = true;
    listModels()
      .then((response) => { if (active) { setModels(response.items.filter((item) => item.local)); setError(""); } })
      .catch((reason) => { if (active) setError(String(reason)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);
  return { models, loading, error, refresh };
}

function LocalModelSelect({ models, value, onChange, loading }: { models: ModelInfo[]; value: string; onChange: (value: string) => void; loading: boolean }) {
  return <select value={value} onChange={(event) => onChange(event.target.value)} disabled={loading || !models.length}>
    <option value="">{loading ? "正在掃描本機模型…" : models.length ? "選擇本機模型" : "沒有可用模型"}</option>
    {models.map((item) => <option key={`${item.provider}:${item.name}`} value={`${item.provider}\n${item.name}`}>{item.provider} · {item.name}</option>)}
  </select>;
}

function splitModel(value: string): [string, string] {
  const [provider = "", model = ""] = value.split("\n", 2);
  return [provider, model];
}

function RagPanel({ feature, onChanged }: { feature: RuntimeFeature; onChanged: () => Promise<void> }) {
  const { models, loading, error: modelError, refresh } = useLocalModels();
  const [selection, setSelection] = useState("");
  const [path, setPath] = useState("");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<RagResult[]>([]);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function configure(enabled: boolean) {
    const [provider, model] = splitModel(selection);
    if (enabled && (!provider || !model)) return setError("請先選擇本機 embeddings 模型。");
    setBusy(true);
    try { await configureRag(enabled, provider || "ollama", model || "disabled"); await onChanged(); setError(""); }
    catch (reason) { setError(String(reason)); }
    finally { setBusy(false); }
  }
  async function ingest(event: FormEvent) {
    event.preventDefault(); setBusy(true);
    try { const response = await ingestRag(path.trim()); setMessage(`已加入 ${response.added} 份文件、${response.chunks} 個段落。`); setError(""); }
    catch (reason) { setError(String(reason)); }
    finally { setBusy(false); }
  }
  async function search(event: FormEvent) {
    event.preventDefault(); setBusy(true);
    try { setResults(await searchRag(query.trim())); setError(""); }
    catch (reason) { setError(String(reason)); }
    finally { setBusy(false); }
  }
  return <div className="page-stack"><PageTitle {...runtimeCopy.rag} action={<button className={feature.enabled ? "secondary danger" : "primary"} onClick={() => void configure(!feature.enabled)} disabled={busy || (!feature.enabled && !selection)}>{feature.enabled ? "關閉知識庫" : "啟用知識庫"}</button>} /><SafetyStrip feature={feature}/>{(error || modelError) && <div className="banner-inline banner--error">{error || modelError}</div>}
    <div className="two-column"><form className="surface form-card" onSubmit={ingest}><p className="eyebrow">加入資料</p><h3>建立本機知識庫</h3><label>用來理解文件的模型<LocalModelSelect models={models} value={selection} onChange={setSelection} loading={loading}/></label><button type="button" className="secondary" onClick={() => void refresh()}>重新檢查模型</button><label>工作區內的資料夾或檔案<input value={path} onChange={(event) => setPath(event.target.value)} placeholder="例如 docs 或 README.md"/></label><p className="consent-note">只讀取 Linlin 工作區內的文字檔；送出代表你同意整理這個路徑的內容。</p><button className="primary" disabled={!feature.enabled || busy || !path.trim()}>加入知識庫</button>{message && <p className="success-text">{message}</p>}</form>
      <form className="surface list-card runtime-result" onSubmit={search}><p className="eyebrow">附來源搜尋</p><h3>搜尋知識庫</h3><label>想查找的內容<textarea value={query} onChange={(event) => setQuery(event.target.value)} rows={3} placeholder="輸入想查找的內容"/></label><button className="primary" disabled={!feature.enabled || busy || !query.trim()}>搜尋</button>{results.length === 0 ? <EmptyState icon="◇" title="尚無搜尋結果" text="完成資料整理後即可搜尋並查看來源。"/> : <div className="result-list">{results.map((result, index) => <article key={`${result.citation.source}:${result.citation.start}:${index}`}><strong>{result.citation.source}</strong><small>位置 {result.citation.start}–{result.citation.end} · 相似度 {result.score.toFixed(3)}</small><p>{result.text}</p>{result.untrusted_instructions && <em>此段包含不可信指令，只作資料使用。</em>}</article>)}</div>}</form></div>
  </div>;
}

function McpPanel({ feature, onChanged }: { feature: RuntimeFeature; onChanged: () => Promise<void> }) {
  const [serverId, setServerId] = useState("local-tools");
  const [endpoint, setEndpoint] = useState("http://127.0.0.1:3001/mcp");
  const [tools, setTools] = useState<McpToolDefinition[]>([]);
  const [selected, setSelected] = useState("");
  const [argumentsText, setArgumentsText] = useState("{}");
  const [result, setResult] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function connect(event: FormEvent) {
    event.preventDefault(); setBusy(true);
    try { const response = await connectMcp(serverId.trim(), endpoint.trim()); setTools(response.tools); setSelected(response.tools[0]?.name ?? ""); setError(""); await onChanged(); }
    catch (reason) { setError(String(reason)); }
    finally { setBusy(false); }
  }
  async function disconnect() {
    setBusy(true); try { await disconnectMcp(); setTools([]); setSelected(""); setResult(""); await onChanged(); } catch (reason) { setError(String(reason)); } finally { setBusy(false); }
  }
  async function invoke(event: FormEvent) {
    event.preventDefault(); setBusy(true);
    try { const parsed = JSON.parse(argumentsText) as Record<string, unknown>; setResult(JSON.stringify(await invokeMcp(selected, parsed), null, 2)); setError(""); }
    catch (reason) { setError(String(reason)); }
    finally { setBusy(false); }
  }
  return <div className="page-stack"><PageTitle {...runtimeCopy.mcp} action={feature.enabled ? <button className="secondary danger" onClick={() => void disconnect()} disabled={busy}>中斷連線</button> : undefined}/><SafetyStrip feature={feature}/>{error && <div className="banner-inline banner--error">{error}</div>}
    <div className="two-column"><form className="surface form-card" onSubmit={connect}><p className="eyebrow">本機工具服務</p><h3>連接工具伺服器</h3><label>服務識別名稱<input value={serverId} onChange={(event) => setServerId(event.target.value)} pattern="[a-zA-Z][a-zA-Z0-9_-]*"/></label><label>本機服務網址<input value={endpoint} onChange={(event) => setEndpoint(event.target.value)} type="url"/></label><p className="consent-note">只接受這台電腦上的網址。按下連線即同意讀取這個服務公開的工具。</p><button className="primary" disabled={busy || !serverId.trim() || !endpoint.trim()}>同意、連線並尋找工具</button></form>
      <form className="surface form-card" onSubmit={invoke}><p className="eyebrow">工具執行</p><h3>使用已連接工具</h3><label>工具<select value={selected} onChange={(event) => setSelected(event.target.value)} disabled={!tools.length}><option value="">{tools.length ? "選擇工具" : "尚未連線"}</option>{tools.map((tool) => <option key={tool.name} value={tool.name}>{tool.name} — {tool.description}</option>)}</select></label><label>進階參數（JSON）<textarea value={argumentsText} onChange={(event) => setArgumentsText(event.target.value)} rows={7} spellCheck={false}/></label><button className="primary" disabled={busy || !selected}>執行工具</button>{result && <pre className="result-code">{result}</pre>}</form></div>
  </div>;
}

function OrchestrationPanel({ feature }: { feature: RuntimeFeature }) {
  const { models, loading, error: modelError } = useLocalModels();
  const [selection, setSelection] = useState("");
  const [task, setTask] = useState("");
  const [runs, setRuns] = useState<OrchestrationRun[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => { try { setRuns(await listOrchestration()); } catch (reason) { setError(String(reason)); } }, []);
  useEffect(() => {
    let active = true;
    listOrchestration().then((items) => { if (active) setRuns(items); }).catch((reason) => { if (active) setError(String(reason)); });
    const timer = window.setInterval(() => void load(), 1800);
    return () => { active = false; window.clearInterval(timer); };
  }, [load]);
  async function start(event: FormEvent) {
    event.preventDefault(); const [provider, model] = splitModel(selection); setBusy(true);
    try { await startOrchestration(provider, model, task.trim()); setTask(""); await load(); setError(""); }
    catch (reason) { setError(String(reason)); }
    finally { setBusy(false); }
  }
  return <div className="page-stack"><PageTitle {...runtimeCopy.orchestration}/><SafetyStrip feature={feature}/>{(error || modelError) && <div className="banner-inline banner--error">{error || modelError}</div>}
    <div className="two-column"><form className="surface form-card" onSubmit={start}><p className="eyebrow">分工處理</p><h3>開始團隊分析</h3><label>本機模型<LocalModelSelect models={models} value={selection} onChange={setSelection} loading={loading}/></label><label>想分析的任務<textarea value={task} onChange={(event) => setTask(event.target.value)} rows={8} placeholder="描述想要分析、比較或檢查的內容"/></label><p className="consent-note">會由協調、分析與檢查三個角色分工；最多進行 4 輪，避免無止境執行。</p><button className="primary" disabled={busy || !selection || !task.trim()}>開始分析</button></form>
      <div className="surface list-card"><div className="list-header"><div><p className="eyebrow">執行紀錄</p><h3>分析結果</h3></div><button className="icon-button" onClick={() => void load()}>↻</button></div>{runs.length === 0 ? <EmptyState icon="⌁" title="尚無團隊分析" text="建立任務後可在此查看分析與檢查結果。"/> : <div className="result-list">{runs.map((run) => <article key={run.id}><div className="result-heading"><strong>{run.task}</strong><span>{run.status}</span></div><small>{run.provider} · {run.model}</small>{run.output && <><h4>分析</h4><p>{run.output.analysis}</p><h4>檢查</h4><p>{run.output.review}</p></>}{run.error && <em>{run.error}</em>}{["pending", "running"].includes(run.status) && <button className="secondary danger" onClick={() => void cancelOrchestration(run.id).then(load)}>取消</button>}</article>)}</div>}</div></div>
  </div>;
}

function SchedulerPanel({ feature, onChanged }: { feature: RuntimeFeature; onChanged: () => Promise<void> }) {
  const { models, loading, error: modelError } = useLocalModels();
  const [selection, setSelection] = useState("");
  const [prompt, setPrompt] = useState("");
  const [runAt, setRunAt] = useState("");
  const [state, setState] = useState<SchedulerState>({ enabled: false, jobs: [], audit: [], results: {} });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => { try { setState(await getSchedulerState()); } catch (reason) { setError(String(reason)); } }, []);
  useEffect(() => {
    let active = true;
    getSchedulerState().then((value) => { if (active) setState(value); }).catch((reason) => { if (active) setError(String(reason)); });
    const timer = window.setInterval(() => void load(), 2500);
    return () => { active = false; window.clearInterval(timer); };
  }, [load]);
  async function toggle() {
    setBusy(true); try { setState(await setSchedulerEnabled(!state.enabled)); await onChanged(); setError(""); } catch (reason) { setError(String(reason)); } finally { setBusy(false); }
  }
  async function schedule(event: FormEvent) {
    event.preventDefault(); const [provider, model] = splitModel(selection); setBusy(true);
    try { await scheduleChat(provider, model, prompt.trim(), new Date(runAt).toISOString()); setPrompt(""); setRunAt(""); await load(); setError(""); }
    catch (reason) { setError(String(reason)); }
    finally { setBusy(false); }
  }
  return <div className="page-stack"><PageTitle {...runtimeCopy.scheduler} action={<button className={state.enabled ? "secondary danger" : "primary"} onClick={() => void toggle()} disabled={busy}>{state.enabled ? "關閉排程" : "確認並啟用排程"}</button>}/><SafetyStrip feature={{ ...feature, enabled: state.enabled, status: state.enabled ? "ready" : "disabled" }}/>{(error || modelError) && <div className="banner-inline banner--error">{error || modelError}</div>}
    <div className="two-column"><form className="surface form-card" onSubmit={schedule}><p className="eyebrow">建立自動任務</p><h3>安排模型工作</h3><label>本機模型<LocalModelSelect models={models} value={selection} onChange={setSelection} loading={loading}/></label><label>執行時間<input type="datetime-local" value={runAt} onChange={(event) => setRunAt(event.target.value)}/></label><label>想讓模型完成的內容<textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} rows={6}/></label><p className="consent-note">任務可以隨時取消，執行結果與操作紀錄都會保留在本機。</p><button className="primary" disabled={!state.enabled || busy || !selection || !prompt.trim() || !runAt}>建立排程</button></form>
      <div className="surface list-card"><div className="list-header"><div><p className="eyebrow">排程紀錄</p><h3>任務與操作紀錄</h3></div><button className="icon-button" onClick={() => void load()}>↻</button></div>{state.jobs.length === 0 ? <EmptyState icon="◷" title="尚無排程" text="啟用後建立第一個本機模型任務。"/> : <div className="result-list">{state.jobs.map((job) => <article key={job.id}><div className="result-heading"><strong>{String(job.arguments.prompt ?? job.action)}</strong><span>{job.status}</span></div><small>{new Date(job.run_at).toLocaleString()} · 嘗試 {job.attempts}/{job.max_attempts}</small>{state.results[job.id]?.content && <p>{state.results[job.id].content}</p>}{job.status === "scheduled" && <button className="secondary danger" onClick={() => void cancelScheduledJob(job.id).then(load)}>取消</button>}</article>)}</div>}<p className="audit-count">操作紀錄：{state.audit.length}</p></div></div>
  </div>;
}

function PageTitle({ eyebrow, title, description, action }: { eyebrow: string; title: string; description: string; action?: ReactNode }) { return <div className="page-title"><div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><p>{description}</p></div>{action}</div>; }
function SafetyStrip({ feature }: { feature: RuntimeFeature }) { return <div className="safety-strip"><span>✓</span><div><strong>安全邊界</strong><p>{feature.safety}</p></div><StatusBadge feature={feature}/></div>; }
function EmptyState({ icon, title, text }: { icon: string; title: string; text: string }) { return <div className="empty-state"><span>{icon}</span><h4>{title}</h4><p>{text}</p></div>; }

export default App;

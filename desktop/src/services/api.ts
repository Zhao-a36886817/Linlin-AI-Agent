import type {
  AgentStatusResponse,
  DashboardData,
  HealthResponse,
  SystemInfoResponse,
} from "../types/api";

const API_BASE_URL = "http://127.0.0.1:8000/api";
const REQUEST_TIMEOUT_MS = 6000;

class ApiError extends Error {
  public readonly statusCode?: number;

  constructor(message: string, statusCode?: number) {
    super(message);
    this.name = "ApiError";
    this.statusCode = statusCode;
  }
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {},
): Promise<T> {
  const controller = new AbortController();

  const timeoutId = window.setTimeout(() => {
    controller.abort();
  }, REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        ...options.headers,
      },
      signal: controller.signal,
    });

    if (!response.ok) {
      throw new ApiError(
        `Backend 回傳錯誤：${response.status} ${response.statusText}`,
        response.status,
      );
    }

    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError("Backend 連線逾時");
    }

    if (error instanceof ApiError) {
      throw error;
    }

    throw new ApiError(
      error instanceof Error
        ? error.message
        : "無法連接 Linlin Agent Backend",
    );
  } finally {
    window.clearTimeout(timeoutId);
  }
}

export const api = {
  getHealth(): Promise<HealthResponse> {
    return request<HealthResponse>("/health");
  },

  getSystemInfo(): Promise<SystemInfoResponse> {
    return request<SystemInfoResponse>("/system/info");
  },

  getAgentStatus(): Promise<AgentStatusResponse> {
    return request<AgentStatusResponse>("/agents/status");
  },

  async getDashboardData(): Promise<DashboardData> {
    const [health, system, agents] = await Promise.all([
      this.getHealth(),
      this.getSystemInfo(),
      this.getAgentStatus(),
    ]);

    return {
      health,
      system,
      agents,
    };
  },
};
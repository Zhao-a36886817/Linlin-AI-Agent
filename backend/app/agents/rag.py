from app.rag import RagRuntime


class AgentRag:
    """Agent Runtime facade for bounded retrieval; providers do not own RAG."""

    def __init__(self, runtime: RagRuntime) -> None:
        self.runtime = runtime

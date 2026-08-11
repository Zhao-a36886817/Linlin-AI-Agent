# Conversation-Bound LLM Training

P32 adds a bounded Training Runtime, not a simulated progress screen. Chat sends
explicit conversation examples to a selected eligible training provider only after
the operator accepts the cloud data-transfer and billing notice.

## Engines and model discovery

The built-in real engine implements the OpenAI-compatible files and fine-tuning job
protocol. Candidate models come from dynamically configured OpenAI or compatible
providers; the provider makes the final eligibility decision when creating the job.
Anthropic, Gemini, OpenRouter, Groq, DeepSeek, Mistral, and Ollama inference models
are not silently claimed to support this protocol.

Local LoRA status is capability-detected. Linlin checks for Torch, Transformers,
PEFT, Datasets, and Accelerate, and still refuses to present local training until an
approved trainable weight directory is registered. Prompt templates and Ollama
`create` are not represented as weight training.

## Job flow

1. Chat creates a random conversation identity. Starting a new conversation creates
   a new identity and isolates its job list.
2. Only completed user/assistant messages are transformed into bounded JSONL
   examples. Errors and Code proposal cards are excluded.
3. The backend retrieves the provider credential through Credential Store, uploads
   the in-memory JSONL file, and creates the remote fine-tuning job. Raw conversation
   training data is not persisted by Linlin.
4. The UI polls that conversation's jobs every two seconds. The backend refreshes
   real provider status and checkpoint metrics.
5. The chart renders provider `train_loss` values by checkpoint step. If the
   provider supplies no metrics or percentage, Linlin shows an indeterminate state
   rather than inventing one.
6. Cancel is conversation-scoped and calls the provider cancellation endpoint.

## Limits and privacy

- Two concurrent active jobs and fifty retained in-process job records.
- At most 200 messages, 20,000 characters per message, and 512 KB encoded dataset.
- Credentials are excluded from API responses, job records, errors, logs, and data.
- Provider error bodies are not forwarded to the UI.
- Jobs and metadata are process-local in P32; the remote provider remains the
  authoritative durable record and controls its own retention and billing.


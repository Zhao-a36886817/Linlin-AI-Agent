# Local LLM Training

Linlin supports real conversation-bound LoRA training with registered local
Hugging Face causal-language-model weights. It does not relabel Ollama/GGUF
inference files as trainable weights.

## Install

Open `Linlin-Agent.bat` and choose **Install local LoRA training support**, or run:

```text
Linlin-Agent.bat install-training
```

This installs the optional, pinned PyTorch, Transformers, PEFT, Accelerate,
SentencePiece, and NumPy stack into Linlin's Python environment.

## Register a model

Place each local Hugging Face model in its own directory under `models/`. Linlin
discovers directories at most three levels deep that contain:

- `config.json`;
- a tokenizer file such as `tokenizer.json`, `tokenizer_config.json`,
  `tokenizer.model`, or `spiece.model`;
- one or more `*.safetensors` files, or `pytorch_model.bin`.

Symlinks that resolve outside `models/`, client-supplied absolute paths, traversal,
and unregistered directories are rejected. Restart Linlin or reopen the training
panel after adding weights.

## Train from Chat

1. Open **對話** and select the inference model used to create the conversation.
2. Complete at least one user/assistant exchange.
3. Select the always-visible **模型訓練** button beside **新對話**.
4. Choose a registered **本機 LoRA** model.
5. Approve local resource use, then create the job.

The job runs in a bounded background worker. Status and actual trainer loss are
read every two seconds in the same conversation. Cancellation is cooperative at
the next training step. Successful adapters are written beneath
`outputs/training/<job-id>/adapter`; the original model weights are never overwritten.

## Operational limits

- Maximum two active local/cloud jobs.
- Maximum 100 steps per request; the UI uses a conservative 20-step default.
- Maximum 200 messages and 512 KB of serialized conversation data.
- Maximum 50 discovered model directories and 200 retained metric samples.
- Data remains in memory for local training and is not uploaded.

Model memory requirements still apply. On low-memory hardware, select a genuinely
small trainable base model; a multi-billion-parameter model may fail cleanly with
an error instead of completing.

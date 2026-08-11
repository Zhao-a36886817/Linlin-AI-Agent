from __future__ import annotations

import importlib.util
import math
import shutil
from collections.abc import Callable
from pathlib import Path
from threading import Event
from typing import Protocol

from app.training.models import TrainingMessage

ProgressCallback = Callable[[int, float | None], None]


class LocalTrainingCancelled(RuntimeError):
    pass


class LocalRunner(Protocol):
    def missing_packages(self) -> list[str]: ...

    def run(
        self,
        *,
        model_path: Path,
        output_path: Path,
        messages: list[TrainingMessage],
        max_steps: int,
        cancelled: Event,
        progress: ProgressCallback,
    ) -> None: ...


class TransformersLoraRunner:
    """Loads registered local weights and writes only a PEFT LoRA adapter."""

    packages = ("torch", "transformers", "peft", "accelerate")

    def missing_packages(self) -> list[str]:
        return [name for name in self.packages if importlib.util.find_spec(name) is None]

    def run(
        self,
        *,
        model_path: Path,
        output_path: Path,
        messages: list[TrainingMessage],
        max_steps: int,
        cancelled: Event,
        progress: ProgressCallback,
    ) -> None:
        if self.missing_packages():
            raise RuntimeError("Local training dependencies are not installed.")

        import torch
        from peft import LoraConfig, get_peft_model
        from torch.utils.data import Dataset
        from transformers import (
            AutoModelForCausalLM,
            AutoTokenizer,
            DataCollatorForLanguageModeling,
            Trainer,
            TrainerCallback,
            TrainingArguments,
        )

        class ConversationDataset(Dataset):  # type: ignore[misc]
            def __init__(self, samples: list[dict[str, list[int]]]) -> None:
                self.samples = samples

            def __len__(self) -> int:
                return len(self.samples)

            def __getitem__(self, index: int) -> dict[str, list[int]]:
                return self.samples[index]

        class Progress(TrainerCallback):  # type: ignore[misc]
            def on_log(self, _args, state, _control, logs=None, **_kwargs):
                loss = (logs or {}).get("loss")
                normalized = float(loss) if isinstance(loss, int | float) else None
                if normalized is not None:
                    progress(int(state.global_step), normalized)

            def on_step_end(self, _args, _state, control, **_kwargs):
                if cancelled.is_set():
                    control.should_training_stop = True
                return control

        output_path.mkdir(parents=True, exist_ok=False)
        try:
            tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
            if tokenizer.pad_token_id is None:
                tokenizer.pad_token = tokenizer.eos_token
            model = AutoModelForCausalLM.from_pretrained(
                model_path,
                local_files_only=True,
                dtype=torch.float32,
                low_cpu_mem_usage=True,
            )
            model = get_peft_model(
                model,
                LoraConfig(
                    task_type="CAUSAL_LM",
                    r=8,
                    lora_alpha=16,
                    lora_dropout=0.05,
                ),
            )
            serialized = [{"role": item.role, "content": item.content} for item in messages]
            try:
                text = tokenizer.apply_chat_template(
                    serialized,
                    tokenize=False,
                    add_generation_prompt=False,
                )
            except (AttributeError, ValueError):
                text = "\n".join(f"{item.role}: {item.content}" for item in messages)
            encoded = tokenizer(text, truncation=True, max_length=1024)
            dataset = ConversationDataset([dict(encoded)])
            arguments = TrainingArguments(
                output_dir=str(output_path / "work"),
                max_steps=max_steps,
                per_device_train_batch_size=1,
                gradient_accumulation_steps=1,
                learning_rate=2e-4,
                logging_steps=1,
                save_strategy="no",
                report_to=[],
                disable_tqdm=True,
                use_cpu=not torch.cuda.is_available(),
            )
            trainer = Trainer(
                model=model,
                args=arguments,
                train_dataset=dataset,
                data_collator=DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False),
                callbacks=[Progress()],
            )
            trainer.train()
            if cancelled.is_set():
                raise LocalTrainingCancelled("Local training was cancelled.")
            adapter_path = output_path / "adapter"
            model.save_pretrained(adapter_path, safe_serialization=True)
            tokenizer.save_pretrained(adapter_path)
            shutil.rmtree(output_path / "work", ignore_errors=True)
        except Exception:
            shutil.rmtree(output_path, ignore_errors=True)
            raise


def valid_loss(value: float | None) -> float | None:
    return value if value is not None and math.isfinite(value) else None

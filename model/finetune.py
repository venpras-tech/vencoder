#!/usr/bin/env python3
import json
import argparse
import torch
from unsloth import FastLanguageModel
from datasets import Dataset
from trl import SFTConfig, SFTTrainer
from unsloth.chat_templates import standardize_sharegpt


def load_local_dataset(path: str) -> Dataset:
    with open(path, encoding="utf-8") as f:
        if path.lower().endswith(".jsonl"):
            records = [json.loads(line) for line in f if line.strip()]
        else:
            data = json.load(f)
            records = data if isinstance(data, list) else [data]
    return Dataset.from_list(records)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True, help="Path to local JSON/JSONL (ShareGPT format)")
    parser.add_argument("--max-steps", type=int, default=60)
    parser.add_argument("--max-seq-length", type=int, default=4096)
    parser.add_argument("--output-dir", default="outputs")
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--grad-accum", type=int, default=4)
    args = parser.parse_args()

    model_name = "unsloth/gpt-oss-20b"
    max_seq_length = args.max_seq_length

    print(f"Loading model: {model_name}")

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=model_name,
        dtype=None,
        max_seq_length=max_seq_length,
        load_in_4bit=True,
        full_finetuning=False,
    )

    model = FastLanguageModel.get_peft_model(
        model,
        r=8,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_alpha=16,
        lora_dropout=0,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=3407,
        use_rslora=False,
        loftq_config=None,
    )

    dataset = load_local_dataset(args.dataset)

    def format_prompts(examples):
        convos = examples["messages"]
        texts = [
            tokenizer.apply_chat_template(convo, tokenize=False, add_generation_prompt=False)
            for convo in convos
        ]
        return {"text": texts}

    dataset = standardize_sharegpt(dataset)
    dataset = dataset.map(format_prompts, batched=True)

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        args=SFTConfig(
            per_device_train_batch_size=args.batch_size,
            gradient_accumulation_steps=args.grad_accum,
            warmup_steps=5,
            max_steps=args.max_steps,
            learning_rate=2e-4,
            logging_steps=1,
            optim="adamw_8bit",
            weight_decay=0.01,
            lr_scheduler_type="linear",
            seed=3407,
            output_dir=args.output_dir,
            report_to="none",
        ),
    )

    gpu_stats = torch.cuda.get_device_properties(0)
    start_gpu_memory = round(torch.cuda.max_memory_reserved() / 1024 / 1024 / 1024, 3)
    max_memory = round(gpu_stats.total_memory / 1024 / 1024 / 1024, 3)
    print(f"GPU: {gpu_stats.name}. Max memory: {max_memory} GB. Reserved: {start_gpu_memory} GB")

    trainer.train()

    model.save_pretrained(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)

    used_memory = round(torch.cuda.max_memory_reserved() / 1024 / 1024 / 1024, 3)
    print(f"Training done. Peak memory: {used_memory} GB. Model saved to {args.output_dir}")


if __name__ == "__main__":
    main()

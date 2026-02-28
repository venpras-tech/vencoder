#!/usr/bin/env python3
import os
import subprocess
import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", default="outputs", help="Path to fine-tuned model (LoRA adapters)")
    parser.add_argument("--gguf-dir", default="gguf", help="Output directory for GGUF files")
    parser.add_argument("--quantization", default="Q8_0", choices=["Q8_0", "q4_k_m", "q5_k_m", "F16"],
                        help="GGUF quantization (Q8_0 recommended for quality)")
    parser.add_argument("--ollama-name", default="vencoder-gpt-oss:20b", help="Ollama model name")
    args = parser.parse_args()

    model_dir = Path(args.model_dir)
    gguf_dir = Path(args.gguf_dir)
    gguf_dir.mkdir(parents=True, exist_ok=True)

    has_adapter = (model_dir / "adapter_config.json").exists()
    has_full = (model_dir / "config.json").exists()
    if not has_adapter and not has_full:
        print(f"Error: No fine-tuned model found in {model_dir}")
        print("Run finetune.py first, or point --model-dir to your outputs folder.")
        return 1

    print("Loading model for GGUF export...")
    from unsloth import FastLanguageModel
    from peft import PeftModel

    if has_adapter:
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name="unsloth/gpt-oss-20b",
            dtype=None,
            max_seq_length=4096,
            load_in_4bit=True,
        )
        model = PeftModel.from_pretrained(model, str(model_dir))
        model = model.merge_and_unload()
    else:
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=str(model_dir),
            dtype=None,
            max_seq_length=4096,
        )

    quant_map = {
        "Q8_0": "q8_0",
        "q4_k_m": "q4_k_m",
        "q5_k_m": "q5_k_m",
        "F16": "f16",
    }
    quant_method = quant_map.get(args.quantization, "q8_0")

    print(f"Exporting to GGUF ({args.quantization})...")
    model.save_pretrained_gguf(
        str(gguf_dir / "vencoder-gpt-oss"),
        tokenizer,
        quantization_method=quant_method,
    )

    gguf_files = list(gguf_dir.glob("*.gguf"))
    if not gguf_files:
        print("Error: No GGUF file produced. Check Unsloth version: pip install --upgrade unsloth")
        return 1

    gguf_path = gguf_files[0]
    print(f"GGUF saved: {gguf_path}")

    modelfile_path = gguf_dir / "Modelfile"
    with open(modelfile_path, "w") as f:
        f.write(f"FROM {gguf_path.absolute()}\n")
        f.write("PARAMETER temperature 0.2\n")
        f.write("PARAMETER num_ctx 4096\n")

    print(f"Modelfile written: {modelfile_path}")

    try:
        result = subprocess.run(
            ["ollama", "create", args.ollama_name, "-f", str(modelfile_path)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print("Ollama create failed:", result.stderr)
            print("Ensure Ollama is installed and running (ollama serve).")
            return 1
        print(f"Ollama model created: {args.ollama_name}")
        print("Run with: ollama run", args.ollama_name)
    except FileNotFoundError:
        print("Ollama not found. Install from https://ollama.com and run:")
        print(f"  ollama create {args.ollama_name} -f {modelfile_path}")

    return 0


if __name__ == "__main__":
    exit(main())

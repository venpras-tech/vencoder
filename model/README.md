# Fine-tuned GPT-OSS 20B for vencoder

Unsloth-based fine-tuning of `gpt-oss:20b` for faster training and reduced VRAM, with export to Ollama for use in the vencoder application.

## Requirements

- **GPU**: NVIDIA GPU with ~14GB VRAM (QLoRA 4-bit) or ~44GB (BF16 LoRA)
- **Python**: 3.10+
- **CUDA**: 11.8, 12.1, or 12.4 (matching your PyTorch/CUDA install)
- **Ollama**: [ollama.com](https://ollama.com)

---

## Step 1: Install Ollama

1. Download Ollama from [ollama.com](https://ollama.com)
2. Install and start Ollama
3. In a terminal, run:
   ```bash
   ollama serve
   ```
4. (Optional) Pull the base model to test:
   ```bash
   ollama pull gpt-oss:20b
   ```

---

## Step 2: Create a Python environment

```bash
cd model
python -m venv venv
```

**Windows:**
```bash
venv\Scripts\activate
```

**Linux/macOS:**
```bash
source venv/bin/activate
```

---

## Step 3: Install dependencies

```bash
pip install --upgrade pip
pip install torch
pip install -r requirements.txt
```

Install `torch` first; other packages depend on it.

If you get dependency errors, try:

```bash
pip install --upgrade --force-reinstall --no-cache-dir unsloth
```

For the latest Unsloth from git (if PyPI is outdated):

```bash
pip install --no-deps git+https://github.com/unslothai/unsloth-zoo.git
pip install --no-deps git+https://github.com/unslothai/unsloth.git
```

---

## Step 4: Fine-tune the model

```bash
python finetune.py --max-steps 60 --output-dir outputs
```

Options:
- `--dataset`: Dataset ID or path to local JSON/JSONL (ShareGPT format)
- `--max-steps`: Training steps (default: 60)
- `--max-seq-length`: Context length (default: 4096)
- `--batch-size`: Per-device batch size (default: 4)
- `--grad-accum`: Gradient accumulation steps (default: 4)

Example with custom data:

```bash
python finetune.py --dataset data/your_data.jsonl --max-steps 100 --output-dir outputs
```

---

## Step 5: Export to GGUF and create Ollama model

```bash
python export_ollama.py --model-dir outputs --ollama-name vencoder-gpt-oss:20b
```

Options:
- `--model-dir`: Path to fine-tuned model (default: outputs)
- `--gguf-dir`: Output directory for GGUF (default: gguf)
- `--quantization`: Q8_0 (quality), q4_k_m (smaller), q5_k_m, F16
- `--ollama-name`: Ollama model name (default: vencoder-gpt-oss:20b)

Ensure Ollama is running before this step (`ollama serve`).

---

## Step 6: Run the model in Ollama

```bash
ollama run vencoder-gpt-oss:20b
```

---

## Step 7: Use in vencoder

**Windows (PowerShell):**
```powershell
$env:LLM_MODEL="vencoder-gpt-oss:20b"
```

**Windows (CMD):**
```cmd
set LLM_MODEL=vencoder-gpt-oss:20b
```

**Linux/macOS:**
```bash
export LLM_MODEL=vencoder-gpt-oss:20b
```

Then start the vencoder application. Or configure the model in the app UI if model selection is available.

---

## Custom training data

Place ShareGPT-format JSON/JSONL in `data/` and run:

```bash
python finetune.py --dataset data/your_data.jsonl --max-steps 100
```

Each line in JSONL:
```json
{"messages": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}
```

See `data/sample.jsonl.example` for format reference.

---

## Quick reference (all steps)

```bash
cd model
python -m venv venv
venv\Scripts\activate
pip install --upgrade pip && pip install -r requirements.txt
python finetune.py --max-steps 60 --output-dir outputs
ollama serve
python export_ollama.py --model-dir outputs --ollama-name vencoder-gpt-oss:20b
ollama run vencoder-gpt-oss:20b
```

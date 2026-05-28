"""
Fase 2: Fine-tuning QLoRA do EPI Assistant no RunPod.

Roda em GPU A40/RTX4090 no RunPod (~2h, custo ~$1-2).
Output: models/epi-assistant-3b-q4.gguf para importar no Ollama.

Uso no RunPod:
    pip install "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"
    pip install --no-deps trl peft accelerate bitsandbytes datasets
    python finetune_assistant.py
"""
import builtins
import unsloth  # must be first
from pathlib import Path

from unsloth import FastLanguageModel
from datasets import load_dataset
from trl import SFTTrainer, SFTConfig

# Unsloth 2026.x chama input() para perguntar sobre push ao Ollama/Hub.
# Em sessão SSH não-interativa isso gera EOFError. Patch preventivo:
builtins.input = lambda prompt="": "n"

DATASET_FILE = "data/epi_assistant_dataset.jsonl"
BASE_MODEL = "unsloth/Llama-3.2-3B-Instruct"
OUTPUT_DIR = "models/epi-assistant-lora"
GGUF_SAVE_DIR = "models/epi-gguf-out"   # Unsloth salva GGUF dentro de um dir
GGUF_OUTPUT = "models/epi-assistant-3b-q4.gguf"  # caminho final esperado
MAX_SEQ_LEN = 2048
SYSTEM_PROMPT = (
    "Você é o EPI Monitor Assistant, um assistente especializado no sistema "
    "EPI Monitor V2. Responda apenas sobre funcionalidades, fluxos e dúvidas "
    "relacionadas à plataforma. Seja direto e claro."
)


def format_alpaca(sample: dict) -> str:
    instruction = sample.get("instruction", "")
    inp = sample.get("input", "")
    output = sample.get("output", "")
    prompt = f"{instruction}\n{inp}".strip() if inp else instruction
    return (
        f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n"
        f"{SYSTEM_PROMPT}<|eot_id|>"
        f"<|start_header_id|>user<|end_header_id|>\n{prompt}<|eot_id|>"
        f"<|start_header_id|>assistant<|end_header_id|>\n{output}<|eot_id|>"
    )


def main() -> None:
    Path("models").mkdir(exist_ok=True)

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=BASE_MODEL,
        max_seq_length=MAX_SEQ_LEN,
        load_in_4bit=True,
    )

    model = FastLanguageModel.get_peft_model(
        model,
        r=16,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
        lora_alpha=16,
        lora_dropout=0,
        bias="none",
        use_gradient_checkpointing="unsloth",
    )

    full_dataset = load_dataset("json", data_files=DATASET_FILE, split="train")
    full_dataset = full_dataset.map(lambda x: {"text": format_alpaca(x)})

    split = full_dataset.train_test_split(test_size=0.1, seed=42)
    train_dataset = split["train"]
    eval_dataset = split["test"]
    print(f"Train: {len(train_dataset)} | Eval: {len(eval_dataset)}")

    trainer = SFTTrainer(
        model=model,
        processing_class=tokenizer,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        args=SFTConfig(
            dataset_text_field="text",
            per_device_train_batch_size=2,
            gradient_accumulation_steps=4,
            warmup_steps=10,
            num_train_epochs=5,
            learning_rate=2e-4,
            bf16=True,
            logging_steps=10,
            eval_steps=50,
            eval_strategy="steps",
            output_dir=OUTPUT_DIR,
            save_strategy="no",
            optim="adamw_8bit",
        ),
    )

    trainer.train()
    print("Treinamento concluído. Salvando GGUF...")

    import glob, shutil
    Path(GGUF_SAVE_DIR).mkdir(parents=True, exist_ok=True)
    model.save_pretrained_gguf(
        GGUF_SAVE_DIR,
        tokenizer,
        quantization_method="q4_k_m",
    )

    # Unsloth appends _gguf to the save directory name (e.g. models/epi-gguf-out_gguf/)
    gguf_files = (
        glob.glob(f"{GGUF_SAVE_DIR}_gguf/*.gguf")
        or glob.glob(f"{GGUF_SAVE_DIR}/*.gguf")
        or list(Path(".").rglob("*.gguf"))
    )
    if gguf_files:
        shutil.move(gguf_files[0], GGUF_OUTPUT)
        print(f"GGUF salvo em: {GGUF_OUTPUT}")
    else:
        print(f"AVISO: GGUF não encontrado, listando workspace:")
        for f in Path(".").rglob("*"):
            if f.suffix in (".gguf", ".bin"):
                print(f"  {f}")


if __name__ == "__main__":
    main()

import os
import sys
from pathlib import Path
from typing import List, Dict, Any
import yaml

# Load prompt from YAML file in configs
_prompts_path = Path(__file__).resolve().parents[1] / "configs" / "prompts.yml"
with open(_prompts_path, "r", encoding="utf-8") as _f:
    _prompts = yaml.safe_load(_f)

# Type-annotated constants
SYSTEM_PROMPT: str = _prompts["be_my_ai_prompt"]

PROMPT: str = "Here is the first picture that you must give a description of."

IMAGE_URL: str = "https://vizwiz.cs.colorado.edu/VizWiz_visualization_img/VizWiz_train_00014868.jpg"

# Edit these model identifiers to match what is available to your API key / account.
MODEL_CONFIGS: List[Dict[str, str]] = [
    {"name": "openai_demo", "provider": "openai", "model": "gpt-4o"},
    #ANthropic is costing money
    {"name": "anthropic_demo", "provider": "anthropic", "model": "claude-3-sonnet-20240229"},
    #Does not cost money with ai studio key
    {"name": "gemini_demo", "provider": "gemini", "model": "gemini-2.5-flash"},
]


sys.path.append(os.path.dirname(__file__)) 

def main() -> None:
    import importlib
    visual_interpreter = importlib.import_module("visual_interpreter")
    models: Dict[str, Any] = visual_interpreter.create_models(MODEL_CONFIGS) 

    for name, model in models.items():
        print(f"\n=== {name} ===")
        try:
            text, *_ = model.generate(PROMPT, mode="standard", image_urls=[IMAGE_URL], system_prompt=SYSTEM_PROMPT)  # type: ignore
            print(text)
        except Exception as e:
            print(f"Error for {name}: {e}")


if __name__ == "__main__":
    main()

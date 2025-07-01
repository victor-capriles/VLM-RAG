import os
import sys
PROMPT = "Describe what you see in the image."
IMAGE_URL = "https://upload.wikimedia.org/wikipedia/commons/thumb/4/47/PNG_transparency_demonstration_1.png/640px-PNG_transparency_demonstration_1.png"

# Edit these model identifiers to match what is available to your API key / account.
MODEL_CONFIGS = [
    {"name": "openai_demo", "provider": "openai", "model": "gpt-4o-mini"},
    {"name": "anthropic_demo", "provider": "anthropic", "model": "claude-3-sonnet-20240229"},
    {"name": "gemini_demo", "provider": "gemini", "model": "gemini-2.5-flash"},
]


sys.path.append(os.path.dirname(__file__)) 

def main():
    import importlib
    visual_interpreter = importlib.import_module("visual_interpreter")
    models = visual_interpreter.create_models(MODEL_CONFIGS)
    for name, model in models.items():
        print(f"\n=== {name} ===")
        try:
            text, _, _, _ = model.generate(PROMPT, mode="standard", image_urls=[IMAGE_URL])
            print(text)
        except Exception as e:
            print(f"Error for {name}: {e}")


if __name__ == "__main__":
    main()

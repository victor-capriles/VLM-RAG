from vector_db import SimpleVectorDB  # type: ignore
import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
import yaml
import random
import base64
import requests
import cohere  # type: ignore
import json

# Flip for testing
with_context = True
fixed_validation = False

def cohere_generate_image_embedding(image_path: str) -> List[float]:
    """Generate float embedding for an image via Cohere embed-v4.0."""
    co = cohere.ClientV2(api_key=os.getenv("COHERE_API_KEY"))

    if image_path.startswith(("http://", "https://")):
        resp = requests.get(image_path, timeout=10)
        resp.raise_for_status()
        img_bytes = resp.content
        mime = resp.headers.get("Content-Type", "image/jpeg")
    else:
        with open(image_path, "rb") as f:
            img_bytes = f.read()
        mime = "image/jpeg"

    data_uri = f"data:{mime};base64,{base64.b64encode(img_bytes).decode()}"

    resp = co.embed(
        model="embed-v4.0",
        input_type="image",
        embedding_types=["float"],
        images=[data_uri],
    )

    return resp.embeddings.float

# Load prompt from YAML file in configs
_prompts_path = Path(__file__).resolve().parents[1] / "configs" / "prompts.yml"
with open(_prompts_path, "r", encoding="utf-8") as _f:
    _prompts = yaml.safe_load(_f)

# Type-annotated constants
SYSTEM_PROMPT: str = _prompts["be_my_ai_prompt"]

# Edit these model identifiers to match what is available to your API key / account.
MODEL_CONFIGS: List[Dict[str, str]] = [
    #{"name": "openai_demo", "provider": "openai", "model": "gpt-4o"},
    #ANthropic is costing money
    #{"name": "anthropic_demo", "provider": "anthropic", "model": "claude-3-sonnet-20240229"},
    #Does not cost money with ai studio key
    {"name": "gemini_demo", "provider": "gemini", "model": "gemini-2.5-flash"},
]


sys.path.append(os.path.dirname(__file__)) 

# ------------------------------------------------------------
# Vector database setup (mirrors notebook logic)
# ------------------------------------------------------------
# Allow static analyzers to resolve; this module is in same directory


# Initialize vector DB (will open existing persisted chroma_db)
CHROMA_PATH = Path(__file__).resolve().parents[1] / "notebooks" / "data" / "chroma_db"
db: SimpleVectorDB = SimpleVectorDB(db_path=str(CHROMA_PATH))
db.use_collection("vizwiz_500_sample", "500 random VizWiz samples") 
# Print database stats to validate collection
print(f"Database stats: {db.get_collection_stats()}")

# ------------------------------------------------------------
# Load original VizWiz JSON so it is ready for later steps
# ------------------------------------------------------------

ALL_JSON_PATH = (
    Path(__file__).resolve().parents[1]
    / "notebooks"
    / "data"
    / "original"
    / "all.json"
)

ALL_DATA: Dict[str, Any] = {}

try:
    with open(ALL_JSON_PATH, "r", encoding="utf-8") as _f:
        ALL_DATA = json.load(_f)
    print(f"Loaded original VizWiz data: {len(ALL_DATA)} entries")
except FileNotFoundError:
    print(f"⚠️ all.json not found at {ALL_JSON_PATH}")

# ------------------------------------------------------------
# Pull existing items and create sample / validation subsets
# ------------------------------------------------------------

collection_snapshot = db.current_collection.get()
ALL_IDS: List[str] = collection_snapshot["ids"]

print(f"Total items in collection: {len(ALL_IDS)}")

# Inspection make sure that everything is working
SAMPLE_PREVIEW: List[str] = ALL_IDS[:2]
print("First 10 IDs:", SAMPLE_PREVIEW)

# Validation set: the 100 IDs in [1..600] that are NOT in the collection
existing_ids_int = {int(x) for x in ALL_IDS if str(x).isdigit()}
VALIDATION_IDS: List[str] = [str(i) for i in range(1, 601) if i not in existing_ids_int]
validation_id = -1
print(f"Validation sample size (missing IDs): {len(VALIDATION_IDS)}")

if fixed_validation:
    validation_id = VALIDATION_IDS[0]
else:
    validation_id = random.choice(VALIDATION_IDS)

# Retrieve the image URL for the chosen validation ID
VALIDATION_IMAGE_URL: str = ""
VALIDATION_IMAGE_REAL_QUESTION: str = ""
if validation_id in ALL_DATA:
    VALIDATION_IMAGE_URL = ALL_DATA[validation_id].get("image_url", "")
    VALIDATION_IMAGE_REAL_QUESTION = ALL_DATA[validation_id].get("question", "")

# Fallback constant used later for model call
IMAGE_URL: str = VALIDATION_IMAGE_URL 

# ------------------------------------------------------------
# Load pre-computed embeddings file (if present)
# ------------------------------------------------------------

EMB_PATHS: List[str] = [
    str(Path(__file__).resolve().parents[1] / "notebooks" / "data" / "embeddings" / "lf_vqa_validation_embeddings_cohere.json"),
    str(Path(__file__).resolve().parents[1] / "notebooks" / "data" / "embeddings" / "lf_vqa_db_embeddings_cohere.json"),
]

validation_embeddings: Optional[Dict] = None
for p in EMB_PATHS:
    if Path(p).exists():
        with open(p, "r", encoding="utf-8") as _f:
            validation_embeddings = yaml.safe_load(_f)  # using yaml to preserve order/float
        break

# ------------------------------------------------------------
PROMPT: str = "Here is the first picture that you must give a description of."

if with_context:
    # --- Similarity search using precomputed embedding for validation_id ---
    if validation_embeddings:
        v_item = None
        for itm in validation_embeddings.get("items", []):
            if str(itm.get("id")) == str(validation_id):
                v_item = itm
                break

        if v_item:
            emb_vec = v_item["embedding"][0] if isinstance(v_item["embedding"], list) else v_item["embedding"]
            try:
                sim_results = db.search_similar_images(emb_vec, n_results=3)
                print("Top 3 similar images:")
                for res in sim_results["similar_images"]:
                    print(f"  ID {res['id']} distance {res['distance']:.3f}")
                # Extract and display metadata from similar images
                print("\nSimilar Image Questions:")

                PROMPT = """You goal is to optimize your first response to answer the example questions briefly and to the point but also describing the image.\n For images with similar visual context, users typically ask the following questions:"""
                
                for idx, res in enumerate(sim_results["similar_images"]):
                    metadata = res["metadata"]
                    question = metadata.get("question", "No question available")
                    image_url = metadata.get("image_url", "No URL available")
                    crowd_majority = metadata.get("crowd_majority", "No answer available")
                    
                    print(f"  {idx+1}. Image ID: {res['id']}")
                    print(f"     Question: {question}")
                    PROMPT += f"\n - {question}"
                    print(f"     Image URL: {image_url}")
                    print(f"     Crowd Answer: {crowd_majority}")
                    print(f"     Distance: {res['distance']:.3f}")
                    print()
                
                PROMPT += "\n\nHere is the first picture that you must give a description of."
                
            except Exception as e:
                print(f"Similarity search failed: {e}")
        else:
            print(f"Embedding for validation ID {validation_id} not found in precomputed file.")

    

def main() -> None:
    import importlib
    visual_interpreter = importlib.import_module("visual_interpreter")
    models: Dict[str, Any] = visual_interpreter.create_models(MODEL_CONFIGS) 

    for name, model in models.items():
        print(f"\n=== {name} ===")
        try:
            print(PROMPT)
            print("--------------------------------")
            text, *_ = model.generate(PROMPT, mode="standard", image_urls=[IMAGE_URL], system_prompt=SYSTEM_PROMPT)  # type: ignore
            print(text)
            print("--------------------------------")
            print(f"Real question: {VALIDATION_IMAGE_REAL_QUESTION}")
            print("--------------------------------")
        except Exception as e:
            print(f"Error for {name}: {e}")


if __name__ == "__main__":
    main()

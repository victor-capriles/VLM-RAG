from vector_db import SimpleVectorDB  # type: ignore
import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
import yaml
import json
import base64
import requests
import cohere  # type: ignore
from datetime import datetime
import time
from tqdm import tqdm  # type: ignore

# Load prompt from YAML file in configs
_prompts_path = Path(__file__).resolve().parents[1] / "configs" / "prompts.yml"
with open(_prompts_path, "r", encoding="utf-8") as _f:
    _prompts = yaml.safe_load(_f)

# Type-annotated constants
SYSTEM_PROMPT: str = _prompts["be_my_ai_prompt"]

# Configuration for evaluation
EVALUATION_CONFIG = {
    "with_context": True,
    "without_context": True,  # Run both modes for comparison
    "top_k_similar": 4,
    "max_validation_samples": 100,  # Default to 3 samples for quick testing, set to None for all samples
    "embedding_provider": "cohere",  # Provider used for embeddings and similarity search
}

# Model configurations
MODEL_CONFIGS: List[Dict[str, str]] = [
    {"name": "gemini-2.5-flash", "provider": "gemini", "model": "gemini-2.5-pro"},
    # Add other models as needed
    # {"name": "openai_demo", "provider": "openai", "model": "gpt-4o"},
    # {"name": "anthropic_demo", "provider": "anthropic", "model": "claude-3-sonnet-20240229"},
]

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


class ValidationEvaluator:
    def __init__(self):
        # Setup paths
        self.base_path = Path(__file__).resolve().parents[1]
        self.results_path = self.base_path / "notebooks" / "data" / "results"
        self.results_path.mkdir(exist_ok=True)
        
        # Initialize vector DB
        chroma_path = self.base_path / "notebooks" / "data" / "chroma_db"
        self.db = SimpleVectorDB(db_path=str(chroma_path))
        self.db.use_collection("vizwiz_500_sample", "500 random VizWiz samples")
        
        # Load original data
        self.all_data = self._load_original_data()
        
        # Get validation IDs
        self.validation_ids = self._get_validation_ids()
        
        # Load precomputed embeddings
        self.validation_embeddings = self._load_validation_embeddings()
        
        # Initialize models
        sys.path.append(os.path.dirname(__file__))
        import importlib
        visual_interpreter = importlib.import_module("visual_interpreter")
        self.models = visual_interpreter.create_models(MODEL_CONFIGS)
        
        print(f"Initialized evaluator with {len(self.validation_ids)} validation samples")
        print(f"Available models: {list(self.models.keys())}")
        print(f"Embedding provider: {EVALUATION_CONFIG['embedding_provider']}")
        print(f"Similar images per query: {EVALUATION_CONFIG['top_k_similar']}")

    def _load_original_data(self) -> Dict[str, Any]:
        """Load original VizWiz data."""
        all_json_path = self.base_path / "notebooks" / "data" / "original" / "all.json"
        try:
            with open(all_json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"⚠️ all.json not found at {all_json_path}")
            return {}

    def _get_validation_ids(self) -> List[str]:
        """Get validation IDs (IDs not in the collection)."""
        collection_snapshot = self.db.current_collection.get()
        all_ids = collection_snapshot["ids"]
        existing_ids_int = {int(x) for x in all_ids if str(x).isdigit()}
        return [str(i) for i in range(1, 601) if i not in existing_ids_int]

    def _load_validation_embeddings(self) -> Optional[Dict]:
        """Load precomputed validation embeddings."""
        emb_path = self.base_path / "notebooks" / "data" / "embeddings" / "lf_vqa_validation_embeddings_cohere.json"
        if emb_path.exists():
            with open(emb_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        return None

    def _get_similar_images(self, validation_id: str) -> Optional[Dict[str, Any]]:
        """Get similar images for a validation ID using precomputed embeddings."""
        if not self.validation_embeddings:
            return None
            
        # Find embedding for validation_id
        v_item = None
        for item in self.validation_embeddings.get("items", []):
            if str(item.get("id")) == str(validation_id):
                v_item = item
                break
                
        if not v_item:
            return None
            
        # Get embedding vector
        emb_vec = v_item["embedding"][0] if isinstance(v_item["embedding"], list) else v_item["embedding"]
        
        try:
            sim_results = self.db.search_similar_images(emb_vec, n_results=EVALUATION_CONFIG["top_k_similar"])
            return sim_results
        except Exception as e:
            print(f"Similarity search failed for ID {validation_id}: {e}")
            return None

    def _build_context_prompt(self, similar_images: Dict[str, Any]) -> str:
        """Build context prompt from similar images."""
        prompt = """Your goal is to optimize your first response by generating a brief, but detailed description of the picture and prioritize what the user most likely needs.
        
        We have retrieved pictures with similar visual context. In these pictures, users asked the following questions:"""
        
        for res in similar_images["similar_images"]:
            metadata = res["metadata"]
            question = metadata.get("question", "No question available")
            prompt += f"\n - {question}"
        
        prompt += "\nUse these questions as a guide for what kind of information is important to users."

        prompt += "\nIf the past questions are not relevant to the picture, you can ignore them and prioritize describing it based on the user's most likely needs."

        prompt += "\nHere is the first picture that you must give a description of."
        return prompt

    def _evaluate_single_sample(self, validation_id: str, model_name: str, model: Any, with_context: bool) -> Dict[str, Any]:
        """Evaluate a single validation sample."""
        # Get validation data
        validation_data = self.all_data.get(validation_id, {})
        image_url = validation_data.get("image_url", "")
        real_question = validation_data.get("question", "")
        crowd_majority = validation_data.get("crowd_majority", "")
        
        # Initialize result
        result = {
            "validation_id": validation_id,
            "model_name": model_name,
            "with_context": with_context,
            "embedding_provider": EVALUATION_CONFIG["embedding_provider"],
            "top_k_similar": EVALUATION_CONFIG["top_k_similar"],
            "image_url": image_url,
            "real_question": real_question,
            "crowd_majority": crowd_majority,
            "timestamp": datetime.now().isoformat(),
            "similar_images": [],
            "prompt_used": "",
            "llm_response": "",
            "error": None,
            "processing_time": 0.0
        }
        
        if not image_url:
            result["error"] = "No image URL found for validation ID"
            return result
            
        start_time = time.time()
        
        try:
            # Build prompt
            if with_context:
                similar_images = self._get_similar_images(validation_id)
                if similar_images:
                    # Store similar images info
                    for res in similar_images["similar_images"]:
                        result["similar_images"].append({
                            "id": res["id"],
                            "distance": res["distance"],
                            "question": res["metadata"].get("question", ""),
                            "image_url": res["metadata"].get("image_url", ""),
                            "crowd_majority": res["metadata"].get("crowd_majority", "")
                        })
                    
                    prompt = self._build_context_prompt(similar_images)
                else:
                    prompt = """Your goal is to optimize your first response by generating a brief, but detailed description of the picture and prioritize what the user most likely needs.
                    
                    Here is the first picture that you must give a description of."""
            else:
                prompt = """Your goal is to optimize your first response by generating a brief, but detailed description of the picture and prioritize what the user most likely needs.
                    
                    Here is the first picture that you must give a description of."""
            
            result["prompt_used"] = prompt
            
            # Generate response
            response, *_ = model.generate(
                prompt, 
                mode="standard", 
                image_urls=[image_url], 
                system_prompt=SYSTEM_PROMPT
            )
            
            result["llm_response"] = response
            result["processing_time"] = time.time() - start_time
            
        except Exception as e:
            result["error"] = str(e)
            result["processing_time"] = time.time() - start_time
            
        return result

    def run_evaluation(self, output_filename: Optional[str] = None) -> str:
        """Run full evaluation on validation dataset."""
        if output_filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"validation_evaluation_{timestamp}.jsonl"
        
        output_path = self.results_path / output_filename
        
        # Determine samples to process
        validation_samples = self.validation_ids
        if EVALUATION_CONFIG["max_validation_samples"]:
            validation_samples = validation_samples[:EVALUATION_CONFIG["max_validation_samples"]]
        
        print(f"Starting evaluation of {len(validation_samples)} validation samples")
        print(f"Results will be saved to: {output_path}")
        
        # Calculate total iterations
        total_iterations = len(validation_samples) * len(self.models)
        if EVALUATION_CONFIG["with_context"] and EVALUATION_CONFIG["without_context"]:
            total_iterations *= 2
        
        with open(output_path, "w", encoding="utf-8") as f:
            with tqdm(total=total_iterations, desc="Evaluating") as pbar:
                for validation_id in validation_samples:
                    for model_name, model in self.models.items():
                        # Run with context if enabled
                        if EVALUATION_CONFIG["with_context"]:
                            result = self._evaluate_single_sample(validation_id, model_name, model, True)
                            f.write(json.dumps(result) + "\n")
                            f.flush()
                            pbar.update(1)
                            
                            # Small delay to avoid rate limiting
                            time.sleep(0.1)
                        
                        # Run without context if enabled
                        if EVALUATION_CONFIG["without_context"]:
                            result = self._evaluate_single_sample(validation_id, model_name, model, False)
                            f.write(json.dumps(result) + "\n")
                            f.flush()
                            pbar.update(1)
                            
                            # Small delay to avoid rate limiting
                            time.sleep(0.1)
        
        print(f"Evaluation completed. Results saved to: {output_path}")
        return str(output_path)


def main():
    """Main function to run the evaluation."""
    print("Starting VisionRAG Validation Dataset Evaluation")
    print("=" * 50)
    
    # Initialize evaluator
    evaluator = ValidationEvaluator()
    
    # Run evaluation
    jsonl_path = evaluator.run_evaluation()
    
    print("\n" + "=" * 50)
    print("Evaluation completed successfully!")
    print(f"Results saved to: {jsonl_path}")
    print("\nYou can analyze the JSONL file to review the evaluation results.")


if __name__ == "__main__":
    main() 
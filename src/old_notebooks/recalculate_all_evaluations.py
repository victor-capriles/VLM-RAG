import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
import yaml
import json
import jsonlines
import time
from datetime import datetime
import importlib
from tqdm import tqdm

from vector_db import SimpleVectorDB

# Mapeo de validation_ids que necesitan recálculo y sus train_ids contaminados
CONTAMINATED_MAPPING = {
    "35": ["504"],
    "369": ["426", "458"], 
    "107": ["504"],
    "97": ["507"],
    "496": ["289"],
    "86": ["289"],
    "72": ["504"],
    "170": ["598"]
}

# Configuration
RECALC_CONFIG = {
    "embedding_provider": "cohere",
    "with_context": True,
    "top_k_retrieve": 6,  # Retrieve más de lo necesario para compensar filtros
    "final_context_count": 4,  # Contexto final después de filtrar
}

# Load prompt from YAML file
_prompts_path = Path(__file__).resolve().parents[1] / "configs" / "prompts.yml"
with open(_prompts_path, "r", encoding="utf-8") as _f:
    _prompts = yaml.safe_load(_f)

SYSTEM_PROMPT: str = _prompts["be_my_ai_prompt"]

# Model Configuration
MODEL_CONFIGS: List[Dict[str, str]] = [
    {"name": "gemini-2.5-pro", "provider": "gemini", "model": "gemini-2.5-pro"},
]

class BatchEvaluationRecalculator:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.embedding_provider = self.config["embedding_provider"]
        
        self.base_path = Path(__file__).resolve().parents[1]
        
        chroma_path = self.base_path / "notebooks" / "data" / "chroma_db"
        self.db = SimpleVectorDB(db_path=str(chroma_path))
        
        self.train_collection_name = f"vizwiz_500_sample_cosine"
        
        print(f"Using embedding provider: {self.embedding_provider.upper()}")
        print(f"Train collection: {self.train_collection_name}")
        
        self.validation_embeddings = self._load_validation_embeddings()
        if not self.validation_embeddings:
            raise FileNotFoundError("Could not load validation embeddings file.")
        
        sys.path.append(os.path.dirname(__file__))
        
        visual_interpreter = importlib.import_module("visual_interpreter")
        self.models = visual_interpreter.create_models(MODEL_CONFIGS)
        
        print(f"Available models: {list(self.models.keys())}")

    def _load_validation_embeddings(self) -> Optional[Dict]:
        """Loads precomputed validation embeddings based on the provider."""
        file_name = f"lf_vqa_validation_embeddings_{self.embedding_provider}.json"
        emb_path = self.base_path / "notebooks" / "data" / "embeddings" / file_name
        print(f"Loading validation embeddings from: {emb_path}")
        if emb_path.exists():
            with open(emb_path, "r", encoding="utf-8") as f:
                return json.load(f)
        print(f"⚠️ Embeddings file not found at {emb_path}")
        return None

    def _get_similar_images_filtered(self, validation_id: str, contaminated_ids: List[str]) -> Optional[Dict[str, Any]]:
        """Gets similar images for a validation ID and filters out contaminated train IDs."""
        v_item = next((item for item in self.validation_embeddings.get("items", []) if str(item.get("id")) == str(validation_id)), None)
        if not v_item:
            return None
        
        raw_embedding = v_item["embedding"]
        emb_vec = raw_embedding[0] if isinstance(raw_embedding[0], list) else raw_embedding
        
        try:
            # Retrieve more than needed to account for filtering
            similar_result = self.db.search_similar_images(
                emb_vec,
                n_results=self.config["top_k_retrieve"],
                collection_name=self.train_collection_name
            )
            
            # Filter out contaminated IDs
            contaminated_set = set(contaminated_ids)
            filtered_images = []
            filtered_count = 0
            
            for img in similar_result["similar_images"]:
                img_id = str(img.get("id", ""))
                if img_id not in contaminated_set:
                    filtered_images.append(img)
                else:
                    filtered_count += 1
            
            # Take only the final count needed (best by cosine distance)
            final_images = filtered_images[:self.config["final_context_count"]]
            
            return {
                "similar_images": final_images,
                "total_retrieved": len(similar_result['similar_images']),
                "filtered_count": filtered_count,
                "final_count": len(final_images)
            }
            
        except Exception as e:
            print(f"Similarity search failed for ID {validation_id}: {e}")
            return None

    def _build_context_prompt(self, similar_images: Dict[str, Any]) -> str:
        """Builds context prompt from similar images (same as original)."""
        prompt = "Your goal is to optimize your first response by generating a brief, but detailed description of the picture and prioritize what the user most likely needs.\n\n"
        prompt += "We have retrieved pictures with similar visual context. In these pictures, users asked the following questions:"
        
        for res in similar_images["similar_images"]:
            prompt += f"\n - {res['metadata'].get('question', 'No question available')}"
        
        prompt += "\n\nUse these questions as a guide for what kind of information is important to users."
        prompt += "\nIf the past questions conflict with the visual information, ignore them and prioritize describing the image's most prominent features."
        prompt += "\nHere is the first picture that you must give a description of."
        return prompt

    def _recalculate_single_sample(self, validation_id: str, model_name: str, model: Any) -> Dict[str, Any]:
        """Recalculates a single validation sample with filtered context."""
        
        contaminated_ids = CONTAMINATED_MAPPING.get(validation_id, [])
        if not contaminated_ids:
            return {"error": f"No contaminated mapping found for validation ID {validation_id}"}
        
        v_item = next((item for item in self.validation_embeddings.get("items", []) if str(item.get("id")) == str(validation_id)), None)
        if not v_item:
            return {"error": f"Data for ID {validation_id} not found."}
            
        metadata = v_item.get("metadata", {})
        
        result = {
            "validation_id": validation_id, 
            "model_name": model_name, 
            "with_context": True,
            "embedding_provider": self.embedding_provider, 
            "top_k_similar": self.config["final_context_count"],
            "image_url": metadata.get("image_url", ""), 
            "real_question": metadata.get("question", ""),
            "crowd_majority": metadata.get("crowd_majority", ""), 
            "timestamp": datetime.now().isoformat(),
            "similar_images": [], 
            "prompt_used": "", 
            "llm_response": "", 
            "error": None, 
            "processing_time": 0.0
        }
        
        if not result["image_url"]:
            result["error"] = "No image URL found"
            return result
            
        start_time = time.time()
        
        try:
            # Get filtered similar images
            similar_images_result = self._get_similar_images_filtered(validation_id, contaminated_ids)
            
            if not similar_images_result or not similar_images_result["similar_images"]:
                result["error"] = "No clean similar images found after filtering"
                return result
            
            # Build context with clean examples only
            saved_similar_images = []
            for res in similar_images_result["similar_images"]:
                sim_meta = res.get("metadata", {})
                saved_similar_images.append({
                    "id": res.get("id"),
                    "distance": res.get("distance"),
                    "question": sim_meta.get("question", ""),
                    "image_url": sim_meta.get("image_url", ""),
                    "crowd_majority": sim_meta.get("crowd_majority", "")
                })
            
            result["similar_images"] = saved_similar_images
            
            # Build prompt with clean context
            prompt = self._build_context_prompt(similar_images_result)
            result["prompt_used"] = prompt
            
            # Generate response
            response, *_ = model.generate(prompt, mode="standard", image_urls=[result["image_url"]], system_prompt=SYSTEM_PROMPT)
            result["llm_response"] = response
            
        except Exception as e:
            result["error"] = str(e)
        
        result["processing_time"] = time.time() - start_time
        return result

    def recalculate_all(self) -> Dict[str, Any]:
        """Recalculates all validation IDs that need recalculation."""
        
        print(f"🔄 Starting batch recalculation for {len(CONTAMINATED_MAPPING)} validation IDs")
        print(f"📊 Configuration:")
        print(f"   - Top-K retrieve: {self.config['top_k_retrieve']}")
        print(f"   - Final context count: {self.config['final_context_count']}")
        print(f"   - IDs to recalculate: {list(CONTAMINATED_MAPPING.keys())}")
        print("-" * 60)
        
        # Use first available model
        model_name = list(self.models.keys())[0]
        model = self.models[model_name]
        
        results = {}
        failed_ids = []
        
        for validation_id in tqdm(CONTAMINATED_MAPPING.keys(), desc="Recalculating evaluations"):
            print(f"\n🎯 Processing validation_id {validation_id}")
            print(f"🚫 Will filter train IDs: {CONTAMINATED_MAPPING[validation_id]}")
            
            result = self._recalculate_single_sample(validation_id, model_name, model)
            
            if "error" in result and result["error"]:
                print(f"❌ Failed: {result['error']}")
                failed_ids.append(validation_id)
            else:
                print(f"✅ Success: {result['processing_time']:.2f}s, {len(result['similar_images'])} clean examples")
                results[validation_id] = result
        
        return {
            "successful_results": results,
            "failed_ids": failed_ids,
            "total_processed": len(CONTAMINATED_MAPPING),
            "successful_count": len(results),
            "failed_count": len(failed_ids)
        }

def update_jsonl_file(recalculated_results: Dict[str, Any], input_file: str) -> str:
    """Updates the JSONL file with recalculated results."""
    
    input_path = Path(input_file)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")
    
    # Create output filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = input_path.parent / f"evaluation_fully_cleaned_{timestamp}.jsonl"
    
    successful_results = recalculated_results["successful_results"]
    recalc_ids = set(successful_results.keys())
    
    print(f"\n📝 Updating JSONL file...")
    print(f"   📄 Input: {input_path}")
    print(f"   📄 Output: {output_path}")
    print(f"   🔄 Will replace {len(recalc_ids)} validation IDs (only with_context=true)")
    
    updated_count = 0
    total_lines = 0
    
    with jsonlines.open(input_path, 'r') as reader, jsonlines.open(output_path, 'w') as writer:
        for line in reader:
            total_lines += 1
            validation_id = line.get('validation_id')
            with_context = line.get('with_context', False)
            
            # Only replace lines that have with_context=true AND are in our recalc list
            if validation_id in recalc_ids and with_context:
                # Replace with recalculated result
                writer.write(successful_results[validation_id])
                updated_count += 1
                print(f"   🔄 Updated validation_id {validation_id} (with_context=true)")
            else:
                # Keep original line (either not in recalc list, or with_context=false)
                writer.write(line)
                if validation_id in recalc_ids and not with_context:
                    print(f"   ✅ Kept original validation_id {validation_id} (with_context=false)")
    
    print(f"\n✅ JSONL update completed:")
    print(f"   📊 Total lines: {total_lines}")
    print(f"   🔄 Updated lines (with_context=true): {updated_count}")
    print(f"   ✅ Kept original: {total_lines - updated_count}")
    
    return str(output_path)

def main():
    """Main function to run the batch recalculation."""
    print("🔄 VisionRAG Batch Evaluation Recalculator")
    print("=" * 60)
    
    try:
        # Recalculate all contaminated evaluations
        recalculator = BatchEvaluationRecalculator(config=RECALC_CONFIG)
        batch_results = recalculator.recalculate_all()
        
        print("\n" + "=" * 60)
        print("📊 BATCH RECALCULATION SUMMARY:")
        print(f"   ✅ Successful: {batch_results['successful_count']}/{batch_results['total_processed']}")
        print(f"   ❌ Failed: {batch_results['failed_count']}")
        
        if batch_results['failed_ids']:
            print(f"   🚫 Failed IDs: {batch_results['failed_ids']}")
        
        if batch_results['successful_count'] > 0:
            # Update the JSONL file
            input_jsonl = Path(__file__).parent / "evaluation_cleaned.jsonl"
            updated_jsonl = update_jsonl_file(batch_results, str(input_jsonl))
            
            print(f"\n📁 FILES GENERATED:")
            print(f"   📄 Updated JSONL: {updated_jsonl}")
            
            # Save detailed results
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            results_file = Path(__file__).parent / f"batch_recalculation_results_{timestamp}.json"
            with open(results_file, 'w', encoding='utf-8') as f:
                json.dump(batch_results, f, indent=2, ensure_ascii=False)
            print(f"   📋 Detailed results: {results_file}")
            
            print(f"\n🎉 Process completed successfully!")
            print(f"   📊 {batch_results['successful_count']} evaluations recalculated and updated")
        else:
            print(f"\n❌ No successful recalculations. Check the errors above.")
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 
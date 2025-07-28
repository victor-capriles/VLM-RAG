import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
import yaml
import json
import time
from datetime import datetime
import importlib

from vector_db import SimpleVectorDB

# ===================================================================
# CONFIGURACIÓN MANUAL - CAMBIAR ESTOS VALORES PARA CADA EJECUCIÓN
# ===================================================================

# ID de validation que quieres recalcular (uno de: 35, 369, 107, 97, 496, 86, 72, 170)
TARGET_VALIDATION_ID = "369"

# Cuántos ejemplos de contexto quieres (el código filtrará automáticamente los contaminados)
# Se recomienda pedir más de lo que necesitas para compensar por los filtrados
TOP_K_RETRIEVE = 6  # Retrieve más de lo necesario

# Cuántos ejemplos finales quieres en el prompt (después de filtrar contaminados)
FINAL_CONTEXT_COUNT = 4

# ===================================================================

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

# Load prompt from YAML file
_prompts_path = Path(__file__).resolve().parents[1] / "configs" / "prompts.yml"
with open(_prompts_path, "r", encoding="utf-8") as _f:
    _prompts = yaml.safe_load(_f)

SYSTEM_PROMPT: str = _prompts["be_my_ai_prompt"]

# Configuration based on original
RECALC_CONFIG = {
    "embedding_provider": "cohere",
    "with_context": True,
    "top_k_retrieve": TOP_K_RETRIEVE,
    "final_context_count": FINAL_CONTEXT_COUNT,
}

# Model Configuration (same as original)
MODEL_CONFIGS: List[Dict[str, str]] = [
    {"name": "gemini-2.5-pro", "provider": "gemini", "model": "gemini-2.5-pro"},
]

class SingleEvaluationRecalculator:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.embedding_provider = self.config["embedding_provider"]
        
        self.base_path = Path(__file__).resolve().parents[1]
        
        chroma_path = self.base_path / "notebooks" / "data" / "chroma_db"
        self.db = SimpleVectorDB(db_path=str(chroma_path))
        
        # Same collection as original
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
            
            print(f"🔍 Retrieved {len(similar_result['similar_images'])} initial results")
            print(f"🚫 Filtering out contaminated train IDs: {contaminated_ids}")
            
            for img in similar_result["similar_images"]:
                img_id = str(img.get("id", ""))
                if img_id not in contaminated_set:
                    filtered_images.append(img)
                else:
                    print(f"   🗑️  Filtered out contaminated ID {img_id}: {img.get('metadata', {}).get('question', '')[:50]}...")
            
            # Take only the final count needed
            final_images = filtered_images[:self.config["final_context_count"]]
            
            print(f"✅ Final clean context: {len(final_images)} examples")
            for i, img in enumerate(final_images, 1):
                print(f"   {i}. ID {img.get('id')}: {img.get('metadata', {}).get('question', '')[:50]}...")
            
            return {
                "similar_images": final_images,
                "total_retrieved": len(similar_result['similar_images']),
                "filtered_count": len(similar_result['similar_images']) - len(filtered_images),
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
        
        # Get contaminated IDs for this validation_id
        contaminated_ids = CONTAMINATED_MAPPING.get(validation_id, [])
        if not contaminated_ids:
            return {"error": f"No contaminated mapping found for validation ID {validation_id}"}
        
        print(f"\n🎯 Recalculating validation_id {validation_id}")
        print(f"🚫 Will filter out train IDs: {contaminated_ids}")
        
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
            "processing_time": 0.0,
            "recalculation_info": {
                "contaminated_train_ids": contaminated_ids,
                "top_k_retrieved": self.config["top_k_retrieve"],
                "final_context_count": self.config["final_context_count"],
                "filtered_count": 0
            }
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
            result["recalculation_info"]["filtered_count"] = similar_images_result["filtered_count"]
            
            # Build prompt with clean context
            prompt = self._build_context_prompt(similar_images_result)
            result["prompt_used"] = prompt
            
            # Generate response (same as original)
            response, *_ = model.generate(prompt, mode="standard", image_urls=[result["image_url"]], system_prompt=SYSTEM_PROMPT)
            result["llm_response"] = response
            
        except Exception as e:
            result["error"] = str(e)
        
        result["processing_time"] = time.time() - start_time
        return result

    def recalculate(self, validation_id: str) -> Dict[str, Any]:
        """Recalculates evaluation for a single validation ID."""
        
        if validation_id not in CONTAMINATED_MAPPING:
            return {"error": f"Validation ID {validation_id} is not in the recalculation list. Valid IDs: {list(CONTAMINATED_MAPPING.keys())}"}
        
        print(f"🔄 Starting recalculation for validation_id: {validation_id}")
        print(f"📊 Configuration:")
        print(f"   - Top-K retrieve: {self.config['top_k_retrieve']}")
        print(f"   - Final context count: {self.config['final_context_count']}")
        print(f"   - Contaminated train IDs to filter: {CONTAMINATED_MAPPING[validation_id]}")
        
        # Use first available model (same as original uses gemini-2.5-pro)
        model_name = list(self.models.keys())[0]
        model = self.models[model_name]
        
        result = self._recalculate_single_sample(validation_id, model_name, model)
        
        return result

def main():
    """Main function to run the recalculation."""
    print("🔄 VisionRAG Single Evaluation Recalculator")
    print("=" * 60)
    
    print(f"🎯 Target validation_id: {TARGET_VALIDATION_ID}")
    print(f"📊 Top-K retrieve: {TOP_K_RETRIEVE}")
    print(f"📋 Final context count: {FINAL_CONTEXT_COUNT}")
    
    if TARGET_VALIDATION_ID not in CONTAMINATED_MAPPING:
        print(f"❌ ERROR: {TARGET_VALIDATION_ID} is not in the recalculation list.")
        print(f"Valid validation IDs: {list(CONTAMINATED_MAPPING.keys())}")
        return
    
    print(f"🚫 Will filter out train IDs: {CONTAMINATED_MAPPING[TARGET_VALIDATION_ID]}")
    print("-" * 60)
    
    try:
        recalculator = SingleEvaluationRecalculator(config=RECALC_CONFIG)
        result = recalculator.recalculate(TARGET_VALIDATION_ID)
        
        print("\n" + "=" * 60)
        
        if "error" in result and result["error"]:
            print(f"❌ ERROR: {result['error']}")
        else:
            print("✅ Recalculation completed successfully!")
            print(f"📊 Processing time: {result['processing_time']:.2f} seconds")
            print(f"🔄 Filtered out: {result['recalculation_info']['filtered_count']} contaminated examples")
            print(f"✅ Final context: {len(result['similar_images'])} clean examples")
            print(f"\n📝 Generated response:")
            print("-" * 40)
            print(result['llm_response'][:200] + "..." if len(result['llm_response']) > 200 else result['llm_response'])
            print("-" * 40)
            
            # Save result to file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = Path(__file__).parent / f"recalculated_validation_{TARGET_VALIDATION_ID}_{timestamp}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            
            print(f"\n💾 Result saved to: {output_file}")
            print(f"\n🎯 To recalculate another ID, change TARGET_VALIDATION_ID and run again.")
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 
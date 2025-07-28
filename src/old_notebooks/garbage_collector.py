import os
import sys
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
import yaml
from tqdm import tqdm
from datetime import datetime
import importlib

from vector_db import SimpleVectorDB

# Load configuration
_prompts_path = Path(__file__).resolve().parents[1] / "configs" / "prompts.yml"
with open(_prompts_path, "r", encoding="utf-8") as _f:
    _prompts = yaml.safe_load(_f)

SYSTEM_PROMPT: str = _prompts["be_my_ai_prompt"]

# Configuration
CONFIG = {
    "embedding_provider": "cohere",  # Choose 'cohere' or 'openclip'
    "max_train_samples": None,  # Process ALL training samples (500)
    "max_validation_samples": None,  # Process ALL validation samples (100)
}

# Model Configuration for Gemini
MODEL_CONFIGS: List[Dict[str, str]] = [
    {"name": "gemini-2.5-pro", "provider": "gemini", "model": "gemini-2.5-pro"},
]

RELEVANCE_PROMPT = """
Evaluate if this question is useful for training a vision-language model. 

You will ONLY see the question text, not the image. Evaluate based on whether the question:

MARK AS NOT RELEVANT if the question:
- Is a thank you message ("Thanks", "Thank you", "Thanks for your help")
- Is a greeting ("Hello", "Hi")  
- Is nonsensical text ("???", random letters, gibberish)
- Is just punctuation (".", "...", "!!!")
- Is a complaint about image quality instead of asking something useful
- Is a statement/comment rather than a question
- Is unclear, vague, or incomprehensible
- Expresses frustration without asking anything specific
- Is a test message or placeholder
- Uses ambiguous pronouns without clear referents ("it", "this", "that" without specifying what)
- Requires context from previous conversation ("Oh so...", "So then...", "But what about...")
- Is a conversational fragment rather than a standalone question
- Doesn't actually ask about visual content that could be seen in an image
- Is incomplete or requires external context to understand
- Ambiguous questions
- Questions that are not about the image
- Questions that requires external context more than the image, like comes from a past conversation.

MARK AS RELEVANT only if it:
- Asks something specific that would be useful to answer about visual content
- Is a clear, standalone, understandable question
- Could reasonably be answered by looking at an image
- Would help train a vision-language model
- Doesn't require additional context to understand what is being asked

EXAMPLES OF NOT RELEVANT:
- "Thanks for your help"
- "This image is blurry"
- "I can't see anything" 
- "This image does not show who the mail is for"
- "Hello there"
- "???"
- "how do I need to do?" 
- "What am I doing wrong?" (not about visual content)
- "So then what happens next?" (requires previous context)

EXAMPLES OF RELEVANT:
- "What color is this shirt?"
- "What does the label say?"
- "How many people are in this photo?"
- "What time does the clock show?"

Your response must be EXACTLY in this JSON format (no other text):
{"is_relevant": false, "reason": "explanation"}

Remember: Use true or false (not True/False), include all quotes, no extra formatting.
"""

class GarbageCollector:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.embedding_provider = self.config["embedding_provider"]
        
        self.base_path = Path(__file__).resolve().parents[1]
        self.results_path = self.base_path / "src"
        
        # Initialize vector database
        chroma_path = self.base_path / "notebooks" / "data" / "chroma_db"
        self.db = SimpleVectorDB(db_path=str(chroma_path))
        self.train_collection_name = "vizwiz_500_sample_cosine"
        
        print(f"Using embedding provider: {self.embedding_provider.upper()}")
        print(f"Train collection: {self.train_collection_name}")
        
        # Load validation embeddings
        self.validation_embeddings = self._load_validation_embeddings()
        if not self.validation_embeddings:
            raise FileNotFoundError("Could not load validation embeddings file.")
        
        # Initialize Gemini model
        sys.path.append(os.path.dirname(__file__))
        visual_interpreter = importlib.import_module("visual_interpreter")
        self.models = visual_interpreter.create_models(MODEL_CONFIGS)
        self.model = self.models["gemini-2.5-pro"]
        
        print(f"Initialized garbage collector")
        print(f"Available models: {list(self.models.keys())}")

    def _load_validation_embeddings(self) -> Optional[Dict]:
        """Load precomputed validation embeddings based on the provider."""
        file_name = f"lf_vqa_validation_embeddings_{self.embedding_provider}.json"
        emb_path = self.base_path / "notebooks" / "data" / "embeddings" / file_name
        print(f"Loading validation embeddings from: {emb_path}")
        if emb_path.exists():
            with open(emb_path, "r", encoding="utf-8") as f:
                return json.load(f)
        print(f"⚠️ Embeddings file not found at {emb_path}")
        return None

    def _evaluate_relevance(self, image_url: str, question: str) -> Dict[str, Any]:
        """Evaluate if a question is relevant using only the question text (no image to avoid bias)."""
        print(f"Evaluating: '{question[:50]}...'")
        try:
            full_prompt = f"{RELEVANCE_PROMPT}\n\nQuestion to evaluate: '{question}'"
            
            # Send only text prompt, no image to avoid bias
            response, *_ = self.model.generate(
                full_prompt, 
                mode="standard", 
                image_urls=None,  # No image - evaluate only the question text
                system_prompt=SYSTEM_PROMPT
            )
            
            # Try to parse JSON response
            try:
                # Clean the response - remove any markdown formatting
                json_str = response.strip()
                
                # Remove markdown code blocks if present
                if "```json" in json_str:
                    json_str = json_str.split("```json")[1].split("```")[0].strip()
                elif "```" in json_str:
                    json_str = json_str.split("```")[1].split("```")[0].strip()
                
                # Try to find JSON-like content in the response
                if not json_str.startswith("{"):
                    # Look for JSON in the middle of the response
                    start_idx = json_str.find("{")
                    if start_idx != -1:
                        end_idx = json_str.rfind("}") + 1
                        if end_idx > start_idx:
                            json_str = json_str[start_idx:end_idx]
                
                result = json.loads(json_str)
                
                # Validate expected fields  
                if not all(key in result for key in ["is_relevant", "reason"]):
                    raise ValueError("Missing required fields in response")
                
                print(f"  -> Relevant: {result['is_relevant']}")
                
                return {
                    "success": True,
                    "is_relevant": result["is_relevant"],
                    "reason": result["reason"],
                    "raw_response": response
                }
                
            except (json.JSONDecodeError, ValueError) as e:
                print(f"  -> JSON parsing failed, using fallback heuristic")
                
                # FALLBACK: If JSON parsing fails, make a simple heuristic decision
                # Check if the question contains obvious irrelevant patterns
                question_lower = question.lower().strip()
                
                # Expanded patterns for better detection
                irrelevant_patterns = [
                    "thank", "thanks", "hello", "hi there", "test", "???", 
                    ".", "..", "...", "asdf", "gibberish", "this image",
                    "can't see", "blurry", "not clear", "poor quality",
                    "doesn't show", "does not show", "oh so", "so then",
                    "but what", "what am i doing", "am i doing wrong"
                ]
                
                is_irrelevant = any(pattern in question_lower for pattern in irrelevant_patterns)
                is_irrelevant = is_irrelevant or len(question.strip()) < 3
                
                # Check if it's more of a statement/complaint than a question
                if not question.strip().endswith('?') and len(question.split()) > 5:
                    is_irrelevant = True
                
                # Check for ambiguous pronouns without clear referents
                ambiguous_patterns = [" it ", " this ", " that "]
                has_ambiguous_pronouns = any(pattern in question_lower for pattern in ambiguous_patterns)
                
                # Check for conversational fragments
                conversational_starts = ["oh so", "so then", "but what", "and then"]
                starts_conversational = any(question_lower.startswith(start) for start in conversational_starts)
                
                if has_ambiguous_pronouns or starts_conversational:
                    is_irrelevant = True
                
                print(f"  -> Fallback decision - Relevant: {not is_irrelevant}")
                
                return {
                    "success": True,  # Mark as success to continue processing
                    "is_relevant": not is_irrelevant,
                    "reason": f"Fallback heuristic decision - parsing failed: {e}",
                    "raw_response": response
                }
                
        except Exception as e:
            print(f"Error evaluating relevance: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _process_train_data(self) -> List[Dict[str, Any]]:
        """Process training data from ChromaDB."""
        print("Processing training data...")
        
        # Set the collection
        self.db.use_collection(self.train_collection_name, "500 random VizWiz samples")
        
        # Get all data from the collection
        collection_snapshot = self.db.current_collection.get()
        all_ids = collection_snapshot["ids"]
        all_metadatas = collection_snapshot["metadatas"]
        
        print(f"Found {len(all_ids)} training samples")
        
        # Limit samples if specified
        if self.config["max_train_samples"]:
            all_ids = all_ids[:self.config["max_train_samples"]]
            all_metadatas = all_metadatas[:self.config["max_train_samples"]]
            print(f"Limited to {len(all_ids)} samples for processing")
        
        irrelevant_samples = []
        
        for i, (sample_id, metadata) in enumerate(tqdm(zip(all_ids, all_metadatas), 
                                                      desc="Processing train samples", 
                                                      total=len(all_ids))):
            image_url = metadata.get("image_url", "")
            question = metadata.get("question", "")
            
            if not image_url or not question:
                print(f"Skipping sample {sample_id}: missing image_url or question")
                continue
            
            # Evaluate relevance
            evaluation = self._evaluate_relevance(image_url, question)
            
            # Save samples that are NOT relevant (to be discarded)
            if evaluation.get("success") and not evaluation.get("is_relevant"):
                irrelevant_samples.append({
                    "id": sample_id,
                    "image_url": image_url,
                    "question": question,
                    "crowd_majority": metadata.get("crowd_majority", ""),
                    "evaluation": {
                        "is_relevant": evaluation.get("is_relevant"),
                        "reason": evaluation.get("reason"),
                        "method": "text_only_evaluation"  # Note that no image was used
                    }
                })
            
            # Small delay to avoid rate limits
            time.sleep(0.1)
        
        print(f"Found {len(irrelevant_samples)} irrelevant training samples out of {len(all_ids)} (candidates for removal)")
        return irrelevant_samples

    def _process_validation_data(self) -> List[Dict[str, Any]]:
        """Process validation data from embeddings file."""
        print("Processing validation data...")
        
        validation_items = self.validation_embeddings.get("items", [])
        print(f"Found {len(validation_items)} validation samples")
        
        # Limit samples if specified
        if self.config["max_validation_samples"]:
            validation_items = validation_items[:self.config["max_validation_samples"]]
            print(f"Limited to {len(validation_items)} samples for processing")
        
        irrelevant_samples = []
        
        for item in tqdm(validation_items, desc="Processing validation samples"):
            metadata = item.get("metadata", {})
            image_url = metadata.get("image_url", "")
            question = metadata.get("question", "")
            sample_id = str(item.get("id", ""))
            
            if not image_url or not question:
                print(f"Skipping validation sample {sample_id}: missing image_url or question")
                continue
            
            # Evaluate relevance
            evaluation = self._evaluate_relevance(image_url, question)
            
            # Save samples that are NOT relevant (to be discarded)
            if evaluation.get("success") and not evaluation.get("is_relevant"):
                irrelevant_samples.append({
                    "id": sample_id,
                    "image_url": image_url,
                    "question": question,
                    "crowd_majority": metadata.get("crowd_majority", ""),
                    "evaluation": {
                        "is_relevant": evaluation.get("is_relevant"),
                        "reason": evaluation.get("reason"),
                        "method": "text_only_evaluation"  # Note that no image was used
                    }
                })
            
            # Small delay to avoid rate limits
            time.sleep(0.1)
        
        print(f"Found {len(irrelevant_samples)} irrelevant validation samples out of {len(validation_items)} (candidates for removal)")
        return irrelevant_samples

    def run_garbage_collection(self) -> None:
        """Run the complete garbage collection process."""
        print("Starting Garbage Collection Process")
        print("=" * 50)
        
        # Process training data
        train_irrelevant = self._process_train_data()
        
        # Process validation data
        validation_irrelevant = self._process_validation_data()
        
        # Save results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        train_output = self.results_path / f"train_to_discard_{timestamp}.json"
        validation_output = self.results_path / f"validation_to_discard_{timestamp}.json"
        
        # Save training results (samples to discard)
        with open(train_output, "w", encoding="utf-8") as f:
            json.dump(train_irrelevant, f, indent=2, ensure_ascii=False)
        
        # Save validation results (samples to discard)
        with open(validation_output, "w", encoding="utf-8") as f:
            json.dump(validation_irrelevant, f, indent=2, ensure_ascii=False)
        
        # Print summary
        print("\n" + "=" * 50)
        print("Garbage Collection Completed!")
        print(f"Training samples: {len(train_irrelevant)} samples to discard saved to {train_output}")
        print(f"Validation samples: {len(validation_irrelevant)} samples to discard saved to {validation_output}")
        
        # Save summary statistics
        summary = {
            "timestamp": timestamp,
            "config": self.config,
            "results": {
                "train": {
                    "total_to_discard": len(train_irrelevant),
                    "output_file": str(train_output)
                },
                "validation": {
                    "total_to_discard": len(validation_irrelevant),
                    "output_file": str(validation_output)
                }
            }
        }
        
        summary_output = self.results_path / f"garbage_collection_summary_{timestamp}.json"
        with open(summary_output, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        print(f"Summary saved to {summary_output}")
        print(f"\n📋 Review the samples before permanently removing them from the dataset.")

def main():
    """Main function to run the garbage collection."""
    print("VisionRAG Garbage Collector")
    print("Identifying irrelevant question-image pairs for potential removal")
    print("=" * 50)
    
    collector = GarbageCollector(config=CONFIG)
    collector.run_garbage_collection()

if __name__ == "__main__":
    main()

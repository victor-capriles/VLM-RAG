import os
import json
from typing import Dict, Any, List
from datetime import datetime

def ensure_directory_exists(path: str):
    """Create directory if it doesn't exist"""
    os.makedirs(path, exist_ok=True)

def save_results_to_json(results: Dict[str, Any], filename: str):
    """Save evaluation results to JSON file"""
    ensure_directory_exists("data/results")
    
    filepath = f"data/results/{filename}"
    
    # Add timestamp to results
    results["timestamp"] = datetime.now().isoformat()
    
    with open(filepath, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"Results saved to {filepath}")

def load_results_from_json(filename: str) -> Dict[str, Any]:
    """Load evaluation results from JSON file"""
    filepath = f"data/results/{filename}"
    
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Results file not found: {filepath}")
    
    with open(filepath, 'r') as f:
        return json.load(f)

def print_evaluation_summary(results: Dict[str, Any]):
    """Print a nice summary of evaluation results"""
    print("\n" + "="*50)
    print("EVALUATION SUMMARY")
    print("="*50)
    
    print(f"Query: {results.get('user_query', 'N/A')}")
    print(f"Overall Winner: {results.get('overall_winner', 'N/A')}")
    
    if 'accuracy' in results:
        acc = results['accuracy']
        print(f"\nACCURACY:")
        print(f"  Baseline Score: {acc.get('baseline_score', 0)}/10")
        print(f"  RAG Score: {acc.get('rag_score', 0)}/10")
        print(f"  Winner: {acc.get('winner', 'N/A')}")
    
    if 'length' in results:
        length = results['length']
        print(f"\nLENGTH:")
        print(f"  Baseline: {length.get('baseline_word_count', 0)} words")
        print(f"  RAG: {length.get('rag_word_count', 0)} words")
        print(f"  RAG Shorter: {length.get('rag_shorter', False)}")
        print(f"  Improvement: {length.get('improvement_percentage', 0)}%")
    
    if 'summary' in results:
        summary = results['summary']
        print(f"\nSUMMARY:")
        print(f"  RAG More Accurate: {summary.get('rag_more_accurate', False)}")
        print(f"  RAG Shorter: {summary.get('rag_shorter', False)}")
    
    print("="*50)

def get_supported_image_extensions():
    """Get list of supported image file extensions"""
    return ['.jpg', '.jpeg', '.png', '.webp']

def is_valid_image_file(filepath: str) -> bool:
    """Check if file is a supported image format"""
    if not os.path.exists(filepath):
        return False
    
    ext = os.path.splitext(filepath)[1].lower()
    return ext in get_supported_image_extensions()

def list_images_in_directory(directory: str) -> List[str]:
    """Get list of all valid image files in a directory"""
    if not os.path.exists(directory):
        return []
    
    images = []
    for filename in os.listdir(directory):
        filepath = os.path.join(directory, filename)
        if is_valid_image_file(filepath):
            images.append(filepath)
    
    return sorted(images)

def create_test_data_structure():
    """Create the basic test data directories"""
    directories = [
        "data/images",
        "data/user_interactions", 
        "data/results",
        "data/chroma_db"
    ]
    
    for directory in directories:
        ensure_directory_exists(directory)
    
    print("Test data structure created!")

def format_model_list():
    """Return a formatted list of recommended OpenRouter models"""
    models = {
        "Vision Models": [
            "google/gemini-pro-vision - Good balance of speed and quality",
            "anthropic/claude-3-sonnet - High quality, supports images",
            "openai/gpt-4-vision-preview - Very capable but slower",
            "google/gemini-flash-1.5 - Fast and affordable"
        ],
        "Judge Models": [
            "anthropic/claude-3-haiku - Fast and cheap for evaluation",
            "anthropic/claude-3-sonnet - More thorough evaluation",
            "openai/gpt-4 - Excellent reasoning for complex comparisons",
            "google/gemini-pro - Good alternative judge"
        ]
    }
    
    output = "\nRECOMMENDED OPENROUTER MODELS:\n"
    output += "=" * 40 + "\n"
    
    for category, model_list in models.items():
        output += f"\n{category}:\n"
        for model in model_list:
            output += f"  • {model}\n"
    
    return output

if __name__ == "__main__":
    print("VLM-RAG Utilities")
    print(format_model_list())
    
    # Create test structure
    create_test_data_structure()
    
    # List any existing images
    images = list_images_in_directory("data/images")
    if images:
        print(f"\nFound {len(images)} images in data/images/:")
        for img in images:
            print(f"  • {img}")
    else:
        print("\nNo images found in data/images/ - add some test images to get started!")
    
    print("\nUtilities ready! 🛠️") 
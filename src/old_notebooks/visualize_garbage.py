import json
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

def load_discard_data(train_file: str, validation_file: str) -> tuple:
    """Load both train and validation discard files."""
    with open(train_file, 'r', encoding='utf-8') as f:
        train_data = json.load(f)
    
    with open(validation_file, 'r', encoding='utf-8') as f:
        validation_data = json.load(f)
    
    return train_data, validation_data

def generate_markdown_report(train_data: List[Dict[str, Any]], 
                           validation_data: List[Dict[str, Any]], 
                           output_file: str):
    """Generate a markdown report of samples to discard."""
    
    with open(output_file, 'w', encoding='utf-8') as f:
        # Header
        f.write("# Garbage Collection Report\n\n")
        f.write(f"**Generated on:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**Summary:**\n")
        f.write(f"- Training samples to discard: {len(train_data)}\n")
        f.write(f"- Validation samples to discard: {len(validation_data)}\n")
        f.write(f"- Total samples to discard: {len(train_data) + len(validation_data)}\n\n")
        
        f.write("---\n\n")
        
        # Training samples section
        if train_data:
            f.write("## 🗑️ Training Samples to Discard\n\n")
            for i, sample in enumerate(train_data, 1):
                f.write(f"### Sample {i}: ID #{sample['id']}\n\n")
                f.write(f"**Question:** {sample['question']}\n\n")
                f.write(f"**Crowd Majority:** `{sample['crowd_majority']}`\n\n")
                f.write(f"**Reason for discard:** {sample['evaluation']['reason']}\n\n")
                f.write(f"**Image:** [View Image]({sample['image_url']})\n\n")
                f.write(f"<img src=\"{sample['image_url']}\" alt=\"Sample {sample['id']}\" width=\"300\">\n\n")
                f.write("---\n\n")
        
        # Validation samples section
        if validation_data:
            f.write("## 🗑️ Validation Samples to Discard\n\n")
            for i, sample in enumerate(validation_data, 1):
                f.write(f"### Sample {i}: ID #{sample['id']}\n\n")
                f.write(f"**Question:** {sample['question']}\n\n")
                f.write(f"**Crowd Majority:** `{sample['crowd_majority']}`\n\n")
                f.write(f"**Reason for discard:** {sample['evaluation']['reason']}\n\n")
                f.write(f"**Image:** [View Image]({sample['image_url']})\n\n")
                f.write(f"<img src=\"{sample['image_url']}\" alt=\"Sample {sample['id']}\" width=\"300\">\n\n")
                f.write("---\n\n")
        
        # Summary by category
        f.write("## 📊 Summary by Discard Reason\n\n")
        
        # Analyze reasons
        all_samples = train_data + validation_data
        reason_counts = {}
        
        for sample in all_samples:
            reason = sample['evaluation']['reason']
            # Simplify reason for categorization
            if 'ambiguous pronoun' in reason.lower():
                category = "Ambiguous pronouns (this, that, it)"
            elif 'conversational' in reason.lower() or 'follow-up' in reason.lower():
                category = "Conversational fragments"
            elif 'general knowledge' in reason.lower():
                category = "General knowledge questions"
            elif 'statement' in reason.lower() or 'comment' in reason.lower():
                category = "Statements/comments, not questions"
            elif 'context' in reason.lower():
                category = "Requires external context"
            elif 'instruction' in reason.lower() or 'how to' in reason.lower():
                category = "How-to/instruction questions"
            elif 'incomplete' in reason.lower() or 'fragment' in reason.lower():
                category = "Incomplete sentences/fragments"
            elif 'external knowledge' in reason.lower():
                category = "Requires external knowledge"
            elif 'subjective' in reason.lower() or 'opinion' in reason.lower():
                category = "Subjective/opinion questions"
            else:
                category = "Other"
            
            reason_counts[category] = reason_counts.get(category, 0) + 1
        
        # Sort by frequency
        sorted_reasons = sorted(reason_counts.items(), key=lambda x: x[1], reverse=True)
        
        for category, count in sorted_reasons:
            percentage = (count / len(all_samples)) * 100
            f.write(f"- **{category}:** {count} samples ({percentage:.1f}%)\n")
        
        f.write("\n---\n\n")
        f.write("## 🔍 Review Instructions\n\n")
        f.write("1. Review each sample above\n")
        f.write("2. Click on image links to view the actual images\n")
        f.write("3. Decide if you agree with the discard decision\n")
        f.write("4. Note any samples that should NOT be discarded\n")
        f.write("5. Use this information to refine the garbage collection criteria if needed\n\n")

def main():
    """Main function with default file paths."""
    # Use the most recent files
    base_path = Path(__file__).parent
    
    # Find the most recent files
    train_files = list(base_path.glob("train_to_discard.json"))
    validation_files = list(base_path.glob("validation_to_discard.json"))
    
    if not train_files or not validation_files:
        print("Error: Could not find discard files. Make sure you've run the garbage collector first.")
        return
    
    # Use the most recent files (assuming timestamp in filename)
    train_file = str(sorted(train_files)[-1])
    validation_file = str(sorted(validation_files)[-1])
    
    print(f"Using files:")
    print(f"  Train: {train_file}")
    print(f"  Validation: {validation_file}")
    
    # Load data
    print("Loading discard data...")
    train_data, validation_data = load_discard_data(train_file, validation_file)
    
    print(f"Loaded {len(train_data)} training samples to discard")
    print(f"Loaded {len(validation_data)} validation samples to discard")
    
    # Generate markdown report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = base_path / f"garbage_collection_report_{timestamp}.md"
    
    print(f"Generating markdown report...")
    generate_markdown_report(train_data, validation_data, str(output_file))
    
    print(f"✅ Report generated: {output_file}")
    print(f"\n📋 Open the markdown file to review all {len(train_data) + len(validation_data)} samples marked for discard.")
    print(f"   You can view it in VS Code, GitHub, or any markdown viewer.")

if __name__ == "__main__":
    main() 
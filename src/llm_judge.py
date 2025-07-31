import json
import csv
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import sys
import os

# Add the src directory to Python path to import visual_interpreter
sys.path.append(os.path.dirname(__file__))
from visual_interpreter import AnthropicModel, API_KEYS


class LLMJudge:
    def __init__(self, model_name: str = "claude-sonnet-4-20250514"):
        """Initialize the LLM Judge with Anthropic model."""
        self.model = AnthropicModel(name="claude-sonnet-4", model=model_name)
        self.base_path = Path(__file__).resolve().parent
        self.data_path = self.base_path / "data"
        
        # Load debiased evaluation data for context
        self.debiased_data = self._load_debiased_data()
        self.swap_keys = self._load_swap_keys()
        
    def _load_debiased_data(self) -> List[Dict]:
        """Load the human evaluation data from debiased_data.csv."""
        debiased_path = self.data_path / "debiased_data.csv"
        evaluations = []
        
        with open(debiased_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                evaluations.append({
                    'id': row['ID'],
                    'user_question': row['User Question'],
                    'a': row['A'],
                    'b': row['B'],
                    'preferred_option': row['Preferred option'],
                    'explanation': row['Explanation'],
                    'other_observations': row['Other Observations']
                })
        
        return evaluations
    
    def _load_swap_keys(self) -> Dict[str, bool]:
        """Load the swap key mapping to understand label shuffling."""
        swap_path = self.data_path / "swap_key.json"
        with open(swap_path, 'r') as f:
            return json.load(f)
    
    def load_evaluation_pairs(self, jsonl_path: str, include_debiased: bool = False) -> List[Tuple[Dict, Dict]]:
        """Load evaluation pairs from the JSONL file."""
        # Get IDs that are already evaluated in the CSV
        evaluated_ids = set(eval_data['id'] for eval_data in self.debiased_data)
        
        pairs = []
        data_by_id = {}
        
        with open(jsonl_path, 'r', encoding='utf-8') as f:
            for line in f:
                item = json.loads(line)
                val_id = item['validation_id']
                
                # Skip evaluated IDs only if we're not including them
                if not include_debiased and val_id in evaluated_ids:
                    continue
                
                if val_id not in data_by_id:
                    data_by_id[val_id] = {}
                
                if item['with_context']:
                    data_by_id[val_id]['with_context'] = item
                else:
                    data_by_id[val_id]['without_context'] = item
        
        # Create pairs, maintaining order
        unique_ids = []
        seen = set()
        
        # Read the file again to maintain original order
        with open(jsonl_path, 'r', encoding='utf-8') as f:
            for line in f:
                item = json.loads(line)
                val_id = item['validation_id']
                if val_id not in seen:
                    if include_debiased or val_id not in evaluated_ids:
                        seen.add(val_id)
                        unique_ids.append(val_id)
        
        # Create pairs in order
        for val_id in unique_ids:
            if val_id in data_by_id and 'with_context' in data_by_id[val_id] and 'without_context' in data_by_id[val_id]:
                pairs.append((
                    data_by_id[val_id]['with_context'],
                    data_by_id[val_id]['without_context']
                ))
        
        return pairs
    
    def _build_judge_prompt(self, sample_a: str, sample_b: str, user_question: str, image_url: str, exclude_id: Optional[str] = None) -> str:
        """Build the prompt for the LLM judge with context examples."""
        prompt = """You are an expert evaluator assessing which text better helps a blind person understand an object they photographed. You must evaluate based on:

1. **Proactivity**: Does the text anticipate what the user needs without requiring a specific question? Could answer the user's question or more than the user's question?
2. **Conciseness**: Is it direct and focused without being overly verbose?
3. **Relevance**: Does it focus on important objects rather than describing every single detail without a clear purpose?
4. **Usefulness**: Does it provide practical information the blind user would need?

IMPORTANT: In the context examples below, the labels A and B have been randomly shuffled. This means that A does not consistently represent one approach and B does not consistently represent another. Each example's A and B are independent assignments. Focus on the quality of each response, not on any perceived pattern in the labels.

Below are example evaluations to guide your judgment:

CONTEXT EXAMPLES:
"""
        
        # Add context examples from debiased data, excluding one if specified
        context_examples = self.debiased_data[:30] if exclude_id is None else [
            eval_data for eval_data in self.debiased_data[:30] if eval_data['id'] != exclude_id
        ]
        
        for eval_data in context_examples:
            prompt += f"\n---\nUser Question: {eval_data['user_question']}\n"
            prompt += f"A: {eval_data['a']}\n"
            prompt += f"B: {eval_data['b']}\n"
            prompt += f"Preferred option: {eval_data['preferred_option']}\n"
            prompt += f"Explanation: {eval_data['explanation']}\n"
            if eval_data['other_observations'].strip():
                prompt += f"Other Observations: {eval_data['other_observations']}\n"
        
        prompt += f"""
---
NEW EVALUATION:
User Question: {user_question}
A: {sample_a}
B: {sample_b}

Based on the context examples above, evaluate which option (A, B, or Neither) better helps the blind user understand what they photographed.

IMPORTANT: Choose "Neither" when:
- Both responses are truly equivalent in quality and usefulness
- Both responses are equally poor or inadequate
- The differences between them are genuinely negligible
However, if one response has even a slight advantage in addressing the user's needs, answering their question more directly, or being more concise/proactive, choose that option rather than "Neither"

Respond ONLY with a JSON object in this exact format:
{{
    "preferred_option": "[A/B/Neither]",
    "explanation": "[Your explanation]",
    "other_observations": "[Optional observations or empty string]"
}}
"""
        
        return prompt
    
    def evaluate_pair(self, with_context_data: Dict, without_context_data: Dict) -> Tuple[Dict, Dict]:
        """Evaluate a single pair of responses."""
        # Determine which is A and which is B based on swap_key
        val_id = with_context_data['validation_id']
        swapped = self.swap_keys.get(val_id, False)
        
        if swapped:
            # If swapped, with_context becomes B and without_context becomes A
            sample_a = without_context_data['llm_response']
            sample_b = with_context_data['llm_response']
        else:
            # Normal order: with_context is A, without_context is B
            sample_a = with_context_data['llm_response']
            sample_b = without_context_data['llm_response']
        
        user_question = with_context_data['real_question']
        image_url = with_context_data['image_url']
        
        # Build the judge prompt
        # If this ID is in the first 30 (debiased data), exclude it from context
        evaluated_ids = [eval_data['id'] for eval_data in self.debiased_data[:30]]
        exclude_id = val_id if val_id in evaluated_ids else None
        
        prompt = self._build_judge_prompt(sample_a, sample_b, user_question, image_url, exclude_id)
        
        # Save the prompt for debugging
        prompt_data = {
            'validation_id': val_id,
            'prompt': prompt,
            'image_url': image_url,
            'timestamp': datetime.now().isoformat()
        }
        
        # Get evaluation from the model
        try:
            response, _, _, _ = self.model.generate(
                prompt, 
                mode="standard",
                image_urls=[image_url]
            )
            
            # Parse the JSON response
            evaluation = json.loads(response)
            
            # Translate A/B to actual categories based on swap status
            if 'preferred_option' in evaluation and evaluation['preferred_option'] in ['A', 'B']:
                if evaluation['preferred_option'] == 'A':
                    evaluation['actual_preferred'] = 'without_context' if swapped else 'with_context'
                elif evaluation['preferred_option'] == 'B':
                    evaluation['actual_preferred'] = 'with_context' if swapped else 'without_context'
            elif 'preferred_option' in evaluation and evaluation['preferred_option'] == 'Neither':
                evaluation['actual_preferred'] = 'Neither'
            
            # Add metadata
            evaluation['validation_id'] = val_id
            evaluation['swapped'] = swapped
            evaluation['timestamp'] = datetime.now().isoformat()
            
            return evaluation, prompt_data
            
        except Exception as e:
            print(f"Error evaluating pair {val_id}: {e}")
            error_result = {
                'validation_id': val_id,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
            return error_result, prompt_data
    
    def run_evaluations(self, jsonl_path: str, output_path: str, num_samples: Optional[int] = None, include_debiased: bool = False):
        """Run evaluations on multiple pairs and save results."""
        pairs = self.load_evaluation_pairs(jsonl_path, include_debiased=include_debiased)
        
        if num_samples:
            pairs = pairs[:num_samples]
        
        print(f"Evaluating {len(pairs)} pairs...")
        
        results = []
        prompts = []
        
        for i, (with_ctx, without_ctx) in enumerate(pairs):
            print(f"Evaluating pair {i+1}/{len(pairs)} (ID: {with_ctx['validation_id']})...")
            result, prompt_data = self.evaluate_pair(with_ctx, without_ctx)
            results.append(result)
            prompts.append(prompt_data)
            
            # Save results incrementally
            with open(output_path, 'w') as f:
                json.dump(results, f, indent=2)
            
            # Save prompts separately
            prompts_path = output_path.replace('.json', '_prompts.json')
            with open(prompts_path, 'w') as f:
                json.dump(prompts, f, indent=2)
        
        print(f"Evaluations complete. Results saved to {output_path}")
        print(f"Prompts saved to {prompts_path}")
        return results


def main():
    """Main function to run the LLM judge."""
    judge = LLMJudge()
    
    # Input and output paths
    jsonl_path = judge.data_path / "evaluation_fully_cleaned_20250728_022449.jsonl"
    output_path = judge.data_path / f"llm_judge_results_consistency_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    # Run evaluations for consistency check (100 samples including the 30 from debiased data)
    judge.run_evaluations(
        jsonl_path=str(jsonl_path),
        output_path=str(output_path),
        num_samples=100,  # First 100 samples
        include_debiased=True  # Include the 30 samples from debiased_data
    )


if __name__ == "__main__":
    main()
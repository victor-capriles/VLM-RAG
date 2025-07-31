import json
import csv
from llm_judge import LLMJudge
from datetime import datetime

# Load previous results to find disagreements
with open('src/data/llm_judge_results_consistency_20250731_022037.json', 'r') as f:
    previous_results = json.load(f)

# Load human evaluations
with open('src/data/debiased_data.csv', 'r') as f:
    reader = csv.DictReader(f)
    human_evals = {row['ID']: row['Preferred option'] for row in reader}

# Find disagreement IDs
disagreement_ids = []
for result in previous_results:
    id = result['validation_id']
    llm = result['preferred_option']
    human = human_evals.get(id)
    if llm != human:
        disagreement_ids.append(id)

print(f"Found {len(disagreement_ids)} disagreements to re-evaluate: {disagreement_ids}")

# Initialize judge
judge = LLMJudge()

# Load the evaluation data
jsonl_path = judge.data_path / "evaluation_fully_cleaned_20250728_022449.jsonl"
output_path = judge.data_path / f"llm_judge_disagreements_retest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

# Load all pairs but only evaluate the disagreements
all_pairs = judge.load_evaluation_pairs(str(jsonl_path), include_debiased=True)

# Filter to only disagreement pairs
disagreement_pairs = []
for with_ctx, without_ctx in all_pairs:
    if with_ctx['validation_id'] in disagreement_ids:
        disagreement_pairs.append((with_ctx, without_ctx))

print(f"\nRe-evaluating {len(disagreement_pairs)} pairs with updated prompt...")

# Run evaluations
results = []
prompts = []

for i, (with_ctx, without_ctx) in enumerate(disagreement_pairs):
    print(f"Evaluating pair {i+1}/{len(disagreement_pairs)} (ID: {with_ctx['validation_id']})...")
    result, prompt_data = judge.evaluate_pair(with_ctx, without_ctx)
    results.append(result)
    prompts.append(prompt_data)
    
    # Save incrementally
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    prompts_path = str(output_path).replace('.json', '_prompts.json')
    with open(prompts_path, 'w') as f:
        json.dump(prompts, f, indent=2)

# Analyze new results
print("\nNew results:")
print("ID  | Human | Old LLM | New LLM | Improved?")
print("----|-------|---------|---------|----------")

improved = 0
for new_result in results:
    id = new_result['validation_id']
    human = human_evals[id]
    
    # Find old result
    old_llm = next(r['preferred_option'] for r in previous_results if r['validation_id'] == id)
    new_llm = new_result['preferred_option']
    
    is_improved = (new_llm == human)
    if is_improved:
        improved += 1
    
    status = "✓" if is_improved else "✗"
    print(f"{id:3} | {human:^5} | {old_llm:^7} | {new_llm:^7} | {status}")

print(f"\nImproved: {improved}/{len(disagreement_pairs)} ({improved/len(disagreement_pairs)*100:.1f}%)")
print(f"Results saved to: {output_path}")
import json
import csv

with open('src/data/llm_judge_results_consistency_20250731_022037.json', 'r') as f:
    old_results = json.load(f)

with open('src/data/debiased_data.csv', 'r') as f:
    reader = csv.DictReader(f)
    human_evals = {row['ID']: row['Preferred option'] for row in reader}

# Find cases where LLM chose Neither but human didn't
neither_cases = []
for result in old_results:
    id = result['validation_id']
    llm = result['preferred_option']
    human = human_evals.get(id)
    if llm == 'Neither' and human != 'Neither':
        neither_cases.append((id, human, result.get('explanation', '')))

print(f'Cases where LLM chose Neither but human chose something else ({len(neither_cases)} total):\n')
for id, human, explanation in neither_cases:
    print(f'ID {id}: Human chose {human}')
    print(f'LLM reasoning: {explanation[:250]}')
    print('-' * 80)
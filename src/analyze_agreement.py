import json
import csv

# Load results
with open('src/data/llm_judge_results_consistency_20250731_022037.json', 'r') as f:
    llm_results = json.load(f)

with open('src/data/debiased_data.csv', 'r') as f:
    reader = csv.DictReader(f)
    human_evals = {row['ID']: row['Preferred option'] for row in reader}

# Analyze results
matches = 0
disagreements = []
neither_analysis = {'human_neither': 0, 'llm_neither': 0, 'both_neither': 0}

for result in llm_results:
    id = result['validation_id']
    llm = result['preferred_option']
    human = human_evals.get(id)
    
    if human == 'Neither':
        neither_analysis['human_neither'] += 1
    if llm == 'Neither':
        neither_analysis['llm_neither'] += 1
    if human == 'Neither' and llm == 'Neither':
        neither_analysis['both_neither'] += 1
    
    if llm == human:
        matches += 1
    else:
        disagreements.append((id, human, llm))

print(f'Agreement: {matches}/30 ({matches/30*100:.1f}%)')
print(f'\nNeither usage:')
print(f'Human chose Neither: {neither_analysis["human_neither"]} times')
print(f'LLM chose Neither: {neither_analysis["llm_neither"]} times')
print(f'Both chose Neither: {neither_analysis["both_neither"]} times')

# Analyze disagreement patterns
print(f'\nDisagreements ({len(disagreements)} total):')
patterns = {}
for _, human, llm in disagreements:
    pattern = f'{human} -> {llm}'
    patterns[pattern] = patterns.get(pattern, 0) + 1

for pattern, count in sorted(patterns.items(), key=lambda x: x[1], reverse=True):
    print(f'{pattern}: {count} times')
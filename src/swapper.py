import csv
import json
import random
from pathlib import Path

def debias_by_swapping(input_path: str, output_csv_path: str, output_key_path: str):
    """
    Reads a CSV, randomly swaps the 'A' and 'B' columns for each row to
    debias the dataset, updates dependent columns, and saves the new CSV
    and a swap key.

    Args:
        input_path (str): Path to the source CSV file.
        output_csv_path (str): Path to save the new, debiased CSV file.
        output_key_path (str): Path to save the JSON file tracking the swaps.
    """
    input_file = Path(input_path)
    if not input_file.is_file():
        print(f"❌ Error: Input file not found at '{input_path}'")
        return

    # Ensure output directories exist
    Path(output_csv_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_key_path).parent.mkdir(parents=True, exist_ok=True)

    processed_rows = []
    swap_key = {}

    with input_file.open(mode='r', encoding='utf-8', newline='') as infile:
        reader = csv.DictReader(infile)
        # Ensure all expected columns are present
        expected_cols = ['ID', 'A', 'B', 'Preferred option', 'Explanation', 'Other Observations']
        if not all(col in reader.fieldnames for col in expected_cols):
            print(f"❌ Error: CSV is missing one of the expected columns: {expected_cols}")
            return
            
        fieldnames = reader.fieldnames

        for row in reader:
            new_row = row.copy()
            
            # Randomly decide whether to swap this row (50% chance)
            should_swap = random.choice([True, False])
            
            # Use 'ID' as the unique identifier for the key
            row_identifier = row['ID']
            swap_key[row_identifier] = should_swap
            
            if should_swap:
                # 1. Swap the content of columns 'A' and 'B'
                new_row['A'], new_row['B'] = new_row['B'], new_row['A']
                
                # 2. Update the 'Preferred option' column, respecting 'Neither'
                if new_row['Preferred option'] == 'A':
                    new_row['Preferred option'] = 'B'
                elif new_row['Preferred option'] == 'B':
                    new_row['Preferred option'] = 'A'
                
                # 3. Update the text in 'Explanation' and 'Other Observations'
                # We use a temporary placeholder to avoid swapping back and forth
                placeholder = "___TEMP_SWAP_PLACEHOLDER___"
                for col in ['Explanation', 'Other Observations']:
                    if col in new_row and new_row[col]:
                        text = new_row[col]
                        # Perform the three-step swap
                        text = text.replace('(A)', placeholder)
                        text = text.replace('(B)', '(A)')
                        text = text.replace(placeholder, '(B)')
                        new_row[col] = text
                        
            processed_rows.append(new_row)

    # Write the new debiased CSV file
    with open(output_csv_path, mode='w', newline='', encoding='utf-8') as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(processed_rows)
        
    # Write the JSON key file
    with open(output_key_path, mode='w', encoding='utf-8') as keyfile:
        json.dump(swap_key, keyfile, indent=4)
        
    print(f"✅ Success! Processed {len(processed_rows)} rows.")
    print(f"Debiased data saved to: {output_csv_path}")
    print(f"Swap key saved to:     {output_key_path}")


# --- Main execution ---
if __name__ == "__main__":
    # Define your file paths
    INPUT_CSV_PATH = "src/data/entry_analysis_consensus_blinded.csv"
    OUTPUT_CSV_PATH = "src/data/debiased_data.csv"
    OUTPUT_KEY_PATH = "src/data/swap_key.json"
    
    # Run the debiasing function
    debias_by_swapping(INPUT_CSV_PATH, OUTPUT_CSV_PATH, OUTPUT_KEY_PATH)
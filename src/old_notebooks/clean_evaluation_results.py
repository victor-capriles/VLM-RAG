import json
import jsonlines
from pathlib import Path
from datetime import datetime
from typing import Set, List, Dict, Any

def load_discard_ids(file_path: Path) -> Set[str]:
    """Load IDs from discard JSON file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        discard_data = json.load(f)
    return {str(item['id']) for item in discard_data}

def process_evaluation_file():
    """Process the evaluation JSONL file to clean and identify recalculation needs."""
    
    base_path = Path(__file__).parent
    
    # Load discard IDs
    validation_discard_ids = load_discard_ids(base_path / "validation_to_discard.json")
    train_discard_ids = load_discard_ids(base_path / "train_to_discard.json")
    
    print(f"📋 Loaded {len(validation_discard_ids)} validation IDs to discard")
    print(f"📋 Loaded {len(train_discard_ids)} train IDs to discard")
    
    # Input and output files
    input_file = base_path.parent / "notebooks" / "data" / "results" / "evaluation_cohere_20250713_203535_gemini_25_pro.jsonl"
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = base_path / f"evaluation_cleaned_{timestamp}.jsonl"
    recalc_report_file = base_path / f"evaluations_to_recalculate_{timestamp}.json"
    
    # Process data
    eliminated_validations = []
    needs_recalculation = []
    all_evaluations = []  # This will include both clean and recalc-needed evaluations
    
    total_lines = 0
    eliminated_count = 0
    recalc_count = 0
    clean_count = 0
    
    print(f"\n🔍 Processing evaluation file...")
    
    with jsonlines.open(input_file, 'r') as reader:
        for line in reader:
            total_lines += 1
            
            validation_id = line.get('validation_id')
            similar_images = line.get('similar_images', [])
            
            # Check if validation_id should be eliminated
            if validation_id in validation_discard_ids:
                eliminated_validations.append({
                    "validation_id": validation_id,
                    "real_question": line.get('real_question'),
                    "reason": "validation_id in discard list"
                })
                eliminated_count += 1
                print(f"   ❌ Eliminating validation_id {validation_id}: {line.get('real_question', '')[:50]}...")
                continue  # Skip this evaluation completely
            
            # Check if any similar_images IDs are in train_discard
            contaminated_train_ids = []
            for img in similar_images:
                img_id = str(img.get('id', ''))
                if img_id in train_discard_ids:
                    contaminated_train_ids.append({
                        "id": img_id,
                        "question": img.get('question'),
                        "distance": img.get('distance')
                    })
            
            if contaminated_train_ids:
                needs_recalculation.append({
                    "validation_id": validation_id,
                    "real_question": line.get('real_question'),
                    "contaminated_train_ids": contaminated_train_ids,
                    "total_similar_images": len(similar_images),
                    "contaminated_count": len(contaminated_train_ids),
                    "reason": f"{len(contaminated_train_ids)} similar_images IDs are in train discard list"
                })
                recalc_count += 1
                print(f"   🔄 Needs recalc validation_id {validation_id}: {len(contaminated_train_ids)} contaminated train IDs (KEPT in JSONL)")
                # Add to output JSONL even though it needs recalculation
                all_evaluations.append(line)
            else:
                clean_count += 1
                print(f"   ✅ Clean validation_id {validation_id}")
                # Add clean evaluation to output JSONL
                all_evaluations.append(line)
    
    # Save ALL evaluations (clean + needs recalculation) - excluding only eliminated ones
    with jsonlines.open(output_file, 'w') as writer:
        for evaluation in all_evaluations:
            writer.write(evaluation)
    
    # Save recalculation report
    recalc_report = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_evaluations_processed": total_lines,
            "eliminated_validations": eliminated_count,
            "needs_recalculation": recalc_count,
            "clean_evaluations": clean_count,
            "kept_in_jsonl": clean_count + recalc_count
        },
        "eliminated_validations": eliminated_validations,
        "evaluations_needing_recalculation": needs_recalculation,
        "validation_discard_ids_used": sorted(list(validation_discard_ids)),
        "train_discard_ids_used": sorted(list(train_discard_ids)),
        "note": "Evaluations needing recalculation are KEPT in the cleaned JSONL to preserve order. Only validations with discard IDs are eliminated."
    }
    
    with open(recalc_report_file, 'w', encoding='utf-8') as f:
        json.dump(recalc_report, f, indent=2, ensure_ascii=False)
    
    # Print summary
    print(f"\n✅ **RESUMEN DEL PROCESAMIENTO:**")
    print(f"   📊 Total evaluaciones procesadas: {total_lines}")
    print(f"   ❌ Eliminadas (validation_id en descarte): {eliminated_count}")
    print(f"   🔄 Necesitan recálculo (MANTENIDAS en JSONL): {recalc_count}")
    print(f"   ✅ Limpias (sin problemas): {clean_count}")
    print(f"   📄 Total en JSONL final: {clean_count + recalc_count}")
    print(f"\n📁 **ARCHIVOS GENERADOS:**")
    print(f"   📄 Evaluaciones (limpias + recálculo): {output_file}")
    print(f"   📋 Reporte de recálculo: {recalc_report_file}")
    
    # Detailed breakdown of recalculation cases
    if needs_recalculation:
        print(f"\n🔄 **CASOS QUE NECESITAN RECÁLCULO (MANTENIDOS EN JSONL):**")
        for i, case in enumerate(needs_recalculation[:10], 1):  # Show first 10
            print(f"   {i}. validation_id {case['validation_id']}")
            print(f"      Question: {case['real_question'][:60]}...")
            print(f"      Contaminated: {case['contaminated_count']}/{case['total_similar_images']} similar_images")
            contaminated_ids = [str(train['id']) for train in case['contaminated_train_ids']]
            print(f"      Train IDs: {', '.join(contaminated_ids)}")
        
        if len(needs_recalculation) > 10:
            print(f"   ... y {len(needs_recalculation) - 10} casos más (ver reporte completo)")
    
    # Detailed breakdown of eliminated cases
    if eliminated_validations:
        print(f"\n❌ **VALIDATION IDs ELIMINADOS COMPLETAMENTE:**")
        for i, case in enumerate(eliminated_validations[:10], 1):  # Show first 10
            print(f"   {i}. validation_id {case['validation_id']}")
            print(f"      Question: {case['real_question'][:60]}...")
        
        if len(eliminated_validations) > 10:
            print(f"   ... y {len(eliminated_validations) - 10} casos más")
    
    return {
        "total": total_lines,
        "eliminated": eliminated_count,
        "needs_recalc": recalc_count,
        "clean": clean_count,
        "kept_in_jsonl": clean_count + recalc_count,
        "output_file": str(output_file),
        "report_file": str(recalc_report_file)
    }

def main():
    """Main function."""
    print("🧹 Limpiando archivo de evaluaciones (conservando orden)...")
    print("=" * 60)
    
    try:
        results = process_evaluation_file()
        print(f"\n🎉 ¡Proceso completado exitosamente!")
        print(f"   📊 {results['kept_in_jsonl']}/{results['total']} evaluaciones mantenidas en JSONL")
        print(f"   🔄 {results['needs_recalc']} necesitan recálculo (pero se conservan)")
        print(f"   ✅ {results['clean']} están completamente limpias")
        print(f"   ❌ {results['eliminated']} fueron eliminadas completamente")
        
    except Exception as e:
        print(f"\n❌ Error durante el proceso: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 
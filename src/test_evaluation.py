#!/usr/bin/env python3
"""
Test script for validation evaluation - runs on a small subset.
"""

from evaluate_validation_dataset import ValidationEvaluator, EVALUATION_CONFIG

def main():
    """Run evaluation on a small subset for testing."""
    print("Testing VisionRAG Evaluation with small subset")
    print("=" * 50)
    
    # Override config for testing
    original_max = EVALUATION_CONFIG["max_validation_samples"]
    EVALUATION_CONFIG["max_validation_samples"] = 3  # Test with just 3 samples
    
    try:
        # Initialize evaluator
        evaluator = ValidationEvaluator()
        
        # Run evaluation
        jsonl_path = evaluator.run_evaluation("test_evaluation_results.jsonl")
        
        # Generate HTML report
        html_path = evaluator.generate_html_report(jsonl_path, "test_evaluation_report.html")
        
        print("\n" + "=" * 50)
        print("Test evaluation completed successfully!")
        print(f"Results saved to: {jsonl_path}")
        print(f"HTML report: {html_path}")
        
    finally:
        # Restore original config
        EVALUATION_CONFIG["max_validation_samples"] = original_max


if __name__ == "__main__":
    main() 
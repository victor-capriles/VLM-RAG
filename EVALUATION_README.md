# VisionRAG Validation Dataset Evaluation

This evaluation system allows you to comprehensively test your VisionRAG prototype on the entire validation dataset and analyze the results through an interactive HTML report.

## Overview

The evaluation system processes all validation samples (images not in your training collection) and tests them with and without context from similar images retrieved from your vector database. Results are stored in JSONL format for easy analysis and visualized in an HTML report.

## Data Storage Format

**JSONL (JSON Lines)** format is used for storing evaluation results. Each line contains a complete JSON record with the following structure:

```json
{
  "validation_id": "123",
  "model_name": "gemini_demo",
  "with_context": true,
  "image_url": "https://example.com/image.jpg",
  "real_question": "What color is the car?",
  "crowd_majority": "Red",
  "timestamp": "2024-01-15T10:30:00",
  "similar_images": [
    {
      "id": "456",
      "distance": 0.234,
      "question": "What vehicle is shown?",
      "image_url": "https://example.com/similar.jpg",
      "crowd_majority": "Car"
    }
  ],
  "prompt_used": "You goal is to optimize...",
  "llm_response": "This image shows a red car...",
  "error": null,
  "processing_time": 2.34
}
```

## Files Created

1. **`src/evaluate_validation_dataset.py`** - Main evaluation script
2. **`src/test_evaluation.py`** - Test script for small subset evaluation
3. **`notebooks/data/results/validation_evaluation_YYYYMMDD_HHMMSS.jsonl`** - Results data
4. **`notebooks/data/results/validation_evaluation_YYYYMMDD_HHMMSS_report.html`** - Interactive HTML report

## Usage

### Full Evaluation

Run the complete evaluation on all validation samples:

```bash
cd src
python evaluate_validation_dataset.py
```

### Test Evaluation

Run a quick test on just 3 samples to verify everything works:

```bash
cd src
python test_evaluation.py
```

### Configuration

Edit the `EVALUATION_CONFIG` in `evaluate_validation_dataset.py`:

```python
EVALUATION_CONFIG = {
    "with_context": True,          # Test with context from similar images
    "without_context": True,       # Test without context for comparison
    "top_k_similar": 3,           # Number of similar images to retrieve
    "max_validation_samples": None # None = all samples, int = limit for testing
}
```

### Model Configuration

Add/remove models in `MODEL_CONFIGS`:

```python
MODEL_CONFIGS = [
    {"name": "gemini_demo", "provider": "gemini", "model": "gemini-2.5-flash"},
    {"name": "openai_demo", "provider": "openai", "model": "gpt-4o"},
    {"name": "anthropic_demo", "provider": "anthropic", "model": "claude-3-sonnet-20240229"},
]
```

## HTML Report Features

The generated HTML report includes:

### Summary Section
- Total samples processed
- Success rate
- Models tested
- Processing statistics

### Per-Sample Analysis
- **Query image**: The validation image being analyzed
- **Real question**: The actual question from the dataset
- **Ground truth answer**: The crowd-sourced correct answer
- **Retrieved similar images**: Top-K similar images with:
  - Distance scores
  - Questions asked about similar images
  - Crowd-sourced answers for context
- **Prompt used**: The exact prompt sent to the model
- **LLM response**: The model's generated response
- **Processing time**: Time taken for each request

### Visual Features
- **Color coding**: Green for with-context, red for without-context
- **Collapsible sections**: Click to show/hide detailed prompts
- **Error highlighting**: Failed requests clearly marked
- **Responsive design**: Works on desktop and mobile

## Analysis Capabilities

### Quantitative Analysis
- Success rates with vs without context
- Processing time comparisons
- Error rate analysis
- Model performance comparison

### Qualitative Analysis
- Visual inspection of retrieved similar images
- Prompt effectiveness assessment
- Response quality evaluation
- Context relevance analysis

## Data Processing

The evaluation system:

1. **Loads validation dataset**: IDs not in your training collection
2. **Retrieves precomputed embeddings**: Uses existing Cohere embeddings
3. **Performs similarity search**: Finds top-K similar images for context
4. **Builds context-aware prompts**: Incorporates questions from similar images
5. **Generates responses**: Tests both with and without context
6. **Stores structured results**: JSONL format for easy analysis
7. **Creates interactive report**: HTML visualization for exploration

## Performance Considerations

- **Rate limiting**: Small delays between API calls to avoid limits
- **Progress tracking**: tqdm progress bars for long evaluations
- **Error handling**: Graceful handling of API failures
- **Memory efficient**: Streaming writes to avoid memory issues
- **Resumable**: JSONL format allows partial result recovery

## Extending the System

### Adding New Models
1. Add model config to `MODEL_CONFIGS`
2. Ensure your `visual_interpreter.py` supports the provider
3. Run evaluation

### Custom Metrics
1. Modify the `_evaluate_single_sample` method
2. Add new fields to the result dictionary
3. Update HTML template to display new metrics

### Different Datasets
1. Modify `_get_validation_ids` method
2. Update data loading paths
3. Adjust embedding handling if needed

## Troubleshooting

### Common Issues

1. **Import errors**: Ensure you're running from the `src/` directory
2. **API key errors**: Check environment variables for all models
3. **Memory issues**: Reduce `max_validation_samples` for testing
4. **Rate limiting**: Increase delays in the evaluation loop

### Debug Mode

Set `max_validation_samples` to a small number (3-5) for debugging:

```python
EVALUATION_CONFIG["max_validation_samples"] = 3
```

## Expected Runtime

- **Full evaluation**: ~2-3 hours for 100 validation samples with 1 model
- **Test evaluation**: ~2-3 minutes for 3 samples
- **HTML generation**: ~10-30 seconds depending on result size

The evaluation system provides comprehensive insights into your VisionRAG system's performance, helping you understand when and how context from similar images improves response quality. 
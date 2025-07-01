# VLM-RAG: Vision-Language Model Retrieval Augmented Generation

A research system to investigate visual interpretation needs for Blind and Low Vision (BLV) users using RAG (Retrieval Augmented Generation).

## 🎯 Research Questions

1. **To what degree do BLV users visual needs change across similar visual contexts?**
2. **Can we leverage past users interactions to provide more relevant future visual interpretations?**

## 🏗️ System Architecture

```
VLM-RAG/
├── src/
│   ├── 1_vector_db.py         # ChromaDB for storing interactions
│   ├── 2_visual_interpreter.py # OpenRouter API for vision models
│   ├── 3_validator.py         # LLM judge for evaluation
│   └── utils.py               # Helper functions
├── notebooks/
│   └── test_vlm_rag.ipynb     # Complete system demonstration
├── data/
│   ├── images/                # Test images
│   ├── user_interactions/     # Past user data
│   └── results/               # Evaluation results
└── requirements.txt           # Dependencies
```

## 🚀 Quick Start

### 1. Setup Environment
```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate
# Activate (Mac/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Get OpenRouter API Key
1. Sign up at [OpenRouter](https://openrouter.ai/keys)
2. Create `.env` file in project root:
```env
OPENROUTER_API_KEY=your_key_here
OPENROUTER_APP_NAME=VLM-RAG
```

### 3. Run the Test Notebook
```bash
jupyter notebook notebooks/test_vlm_rag.ipynb
```

## 🤖 Supported Models

### Vision Models (via OpenRouter):
- `google/gemini-pro-vision` - Good balance of speed and quality
- `anthropic/claude-3-sonnet` - High quality, supports images  
- `openai/gpt-4-vision-preview` - Very capable but slower
- `google/gemini-flash-1.5` - Fast and affordable

### Judge Models:
- `anthropic/claude-3-haiku` - Fast and cheap for evaluation
- `anthropic/claude-3-sonnet` - More thorough evaluation
- `openai/gpt-4` - Excellent reasoning for complex comparisons

## 📊 System Components

### 1. Vector Database (`src/1_vector_db.py`)
- Stores past BLV user interactions
- Semantic search for similar contexts
- ChromaDB for persistence

### 2. Visual Interpreter (`src/2_visual_interpreter.py`)
- Baseline interpretation (no context)
- RAG interpretation (with retrieved context)
- Easy model switching via OpenRouter

### 3. Validation Judge (`src/3_validator.py`)
- Accuracy evaluation (1-10 scoring)
- Length analysis (shorter is better)
- Comprehensive comparison reports

## 🔬 Usage Examples

```python
# Initialize components
from src.vector_db import SimpleVectorDB
from src.visual_interpreter import VisualInterpreter
from src.validator import ValidationJudge

db = SimpleVectorDB()
interpreter = VisualInterpreter(model="google/gemini-pro-vision")
judge = ValidationJudge()

# Add sample data
db.add_sample_data()

# Generate responses
baseline = interpreter.interpret_baseline(image_path, query)
context = db.get_context_for_rag(query)
rag_response = interpreter.interpret_with_context(image_path, query, context)

# Evaluate results
results = judge.comprehensive_evaluation(query, baseline, rag_response)
```

## 📈 Evaluation Metrics

- **Accuracy**: LLM judge scores (1-10) for factual correctness
- **Length**: Word count comparison (shorter preferred for BLV)
- **Relevance**: Semantic similarity to past successful interactions
- **Helpfulness**: Task-specific utility for BLV users

## 🛠️ Development

### Running Individual Components
```bash
# Test vector database
python src/1_vector_db.py

# Test visual interpreter
python src/2_visual_interpreter.py

# Test validator
python src/3_validator.py

# Test utilities
python src/utils.py
```

### Adding New Data
```python
# Add new interaction
db.add_interaction(
    user_query="What's in this room?",
    image_path="path/to/image.jpg", 
    visual_interpretation="Generated response...",
    context="indoor, navigation"
)
```

## 📝 Research Applications

### Investigating Visual Context Changes
1. Collect interactions across similar contexts (kitchens, crosswalks, etc.)
2. Analyze how user needs vary within context categories
3. Measure RAG effectiveness by context type

### Measuring RAG Impact
1. Compare baseline vs RAG response quality
2. Track length improvements (conciseness)
3. Evaluate user satisfaction metrics

## 🤝 Contributing

1. Add test images to `data/images/`
2. Experiment with different models and prompts
3. Add new evaluation metrics
4. Contribute BLV user interaction data

## 🔗 Links

- [OpenRouter Documentation](https://openrouter.ai/docs)
- [ChromaDB Documentation](https://docs.trychroma.com/)
- [Research Methodology](docs/research_methodology.md) (coming soon)

---

**Built for advancing accessibility research through AI** 🌟

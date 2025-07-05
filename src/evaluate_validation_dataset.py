from vector_db import SimpleVectorDB  # type: ignore
import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
import yaml
import json
import base64
import requests
import cohere  # type: ignore
from datetime import datetime
import time
from tqdm import tqdm  # type: ignore

# Load prompt from YAML file in configs
_prompts_path = Path(__file__).resolve().parents[1] / "configs" / "prompts.yml"
with open(_prompts_path, "r", encoding="utf-8") as _f:
    _prompts = yaml.safe_load(_f)

# Type-annotated constants
SYSTEM_PROMPT: str = _prompts["be_my_ai_prompt"]

# Configuration for evaluation
EVALUATION_CONFIG = {
    "with_context": True,
    "without_context": True,  # Run both modes for comparison
    "top_k_similar": 3,
    "max_validation_samples": None,  # None = all samples, or set to int for testing
}

# Model configurations
MODEL_CONFIGS: List[Dict[str, str]] = [
    {"name": "gemini_demo", "provider": "gemini", "model": "gemini-2.5-flash"},
    # Add other models as needed
    # {"name": "openai_demo", "provider": "openai", "model": "gpt-4o"},
    # {"name": "anthropic_demo", "provider": "anthropic", "model": "claude-3-sonnet-20240229"},
]

def cohere_generate_image_embedding(image_path: str) -> List[float]:
    """Generate float embedding for an image via Cohere embed-v4.0."""
    co = cohere.ClientV2(api_key=os.getenv("COHERE_API_KEY"))

    if image_path.startswith(("http://", "https://")):
        resp = requests.get(image_path, timeout=10)
        resp.raise_for_status()
        img_bytes = resp.content
        mime = resp.headers.get("Content-Type", "image/jpeg")
    else:
        with open(image_path, "rb") as f:
            img_bytes = f.read()
        mime = "image/jpeg"

    data_uri = f"data:{mime};base64,{base64.b64encode(img_bytes).decode()}"

    resp = co.embed(
        model="embed-v4.0",
        input_type="image",
        embedding_types=["float"],
        images=[data_uri],
    )

    return resp.embeddings.float


class ValidationEvaluator:
    def __init__(self):
        # Setup paths
        self.base_path = Path(__file__).resolve().parents[1]
        self.results_path = self.base_path / "notebooks" / "data" / "results"
        self.results_path.mkdir(exist_ok=True)
        
        # Initialize vector DB
        chroma_path = self.base_path / "notebooks" / "data" / "chroma_db"
        self.db = SimpleVectorDB(db_path=str(chroma_path))
        self.db.use_collection("vizwiz_500_sample", "500 random VizWiz samples")
        
        # Load original data
        self.all_data = self._load_original_data()
        
        # Get validation IDs
        self.validation_ids = self._get_validation_ids()
        
        # Load precomputed embeddings
        self.validation_embeddings = self._load_validation_embeddings()
        
        # Initialize models
        sys.path.append(os.path.dirname(__file__))
        import importlib
        visual_interpreter = importlib.import_module("visual_interpreter")
        self.models = visual_interpreter.create_models(MODEL_CONFIGS)
        
        print(f"Initialized evaluator with {len(self.validation_ids)} validation samples")
        print(f"Available models: {list(self.models.keys())}")

    def _load_original_data(self) -> Dict[str, Any]:
        """Load original VizWiz data."""
        all_json_path = self.base_path / "notebooks" / "data" / "original" / "all.json"
        try:
            with open(all_json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"⚠️ all.json not found at {all_json_path}")
            return {}

    def _get_validation_ids(self) -> List[str]:
        """Get validation IDs (IDs not in the collection)."""
        collection_snapshot = self.db.current_collection.get()
        all_ids = collection_snapshot["ids"]
        existing_ids_int = {int(x) for x in all_ids if str(x).isdigit()}
        return [str(i) for i in range(1, 601) if i not in existing_ids_int]

    def _load_validation_embeddings(self) -> Optional[Dict]:
        """Load precomputed validation embeddings."""
        emb_path = self.base_path / "notebooks" / "data" / "embeddings" / "lf_vqa_validation_embeddings_cohere.json"
        if emb_path.exists():
            with open(emb_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        return None

    def _get_similar_images(self, validation_id: str) -> Optional[Dict[str, Any]]:
        """Get similar images for a validation ID using precomputed embeddings."""
        if not self.validation_embeddings:
            return None
            
        # Find embedding for validation_id
        v_item = None
        for item in self.validation_embeddings.get("items", []):
            if str(item.get("id")) == str(validation_id):
                v_item = item
                break
                
        if not v_item:
            return None
            
        # Get embedding vector
        emb_vec = v_item["embedding"][0] if isinstance(v_item["embedding"], list) else v_item["embedding"]
        
        try:
            sim_results = self.db.search_similar_images(emb_vec, n_results=EVALUATION_CONFIG["top_k_similar"])
            return sim_results
        except Exception as e:
            print(f"Similarity search failed for ID {validation_id}: {e}")
            return None

    def _build_context_prompt(self, similar_images: Dict[str, Any]) -> str:
        """Build context prompt from similar images."""
        prompt = """You goal is to optimize your first response to answer the example questions briefly and to the point but also describing the image.\n For images with similar visual context, users typically ask the following questions:"""
        
        for res in similar_images["similar_images"]:
            metadata = res["metadata"]
            question = metadata.get("question", "No question available")
            prompt += f"\n - {question}"
        
        prompt += "\n\nHere is the first picture that you must give a description of."
        return prompt

    def _evaluate_single_sample(self, validation_id: str, model_name: str, model: Any, with_context: bool) -> Dict[str, Any]:
        """Evaluate a single validation sample."""
        # Get validation data
        validation_data = self.all_data.get(validation_id, {})
        image_url = validation_data.get("image_url", "")
        real_question = validation_data.get("question", "")
        crowd_majority = validation_data.get("crowd_majority", "")
        
        # Initialize result
        result = {
            "validation_id": validation_id,
            "model_name": model_name,
            "with_context": with_context,
            "image_url": image_url,
            "real_question": real_question,
            "crowd_majority": crowd_majority,
            "timestamp": datetime.now().isoformat(),
            "similar_images": [],
            "prompt_used": "",
            "llm_response": "",
            "error": None,
            "processing_time": 0.0
        }
        
        if not image_url:
            result["error"] = "No image URL found for validation ID"
            return result
            
        start_time = time.time()
        
        try:
            # Build prompt
            if with_context:
                similar_images = self._get_similar_images(validation_id)
                if similar_images:
                    # Store similar images info
                    for res in similar_images["similar_images"]:
                        result["similar_images"].append({
                            "id": res["id"],
                            "distance": res["distance"],
                            "question": res["metadata"].get("question", ""),
                            "image_url": res["metadata"].get("image_url", ""),
                            "crowd_majority": res["metadata"].get("crowd_majority", "")
                        })
                    
                    prompt = self._build_context_prompt(similar_images)
                else:
                    prompt = "Here is the first picture that you must give a description of."
            else:
                prompt = "Here is the first picture that you must give a description of."
            
            result["prompt_used"] = prompt
            
            # Generate response
            response, *_ = model.generate(
                prompt, 
                mode="standard", 
                image_urls=[image_url], 
                system_prompt=SYSTEM_PROMPT
            )
            
            result["llm_response"] = response
            result["processing_time"] = time.time() - start_time
            
        except Exception as e:
            result["error"] = str(e)
            result["processing_time"] = time.time() - start_time
            
        return result

    def run_evaluation(self, output_filename: Optional[str] = None) -> str:
        """Run full evaluation on validation dataset."""
        if output_filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"validation_evaluation_{timestamp}.jsonl"
        
        output_path = self.results_path / output_filename
        
        # Determine samples to process
        validation_samples = self.validation_ids
        if EVALUATION_CONFIG["max_validation_samples"]:
            validation_samples = validation_samples[:EVALUATION_CONFIG["max_validation_samples"]]
        
        print(f"Starting evaluation of {len(validation_samples)} validation samples")
        print(f"Results will be saved to: {output_path}")
        
        # Calculate total iterations
        total_iterations = len(validation_samples) * len(self.models)
        if EVALUATION_CONFIG["with_context"] and EVALUATION_CONFIG["without_context"]:
            total_iterations *= 2
        
        with open(output_path, "w", encoding="utf-8") as f:
            with tqdm(total=total_iterations, desc="Evaluating") as pbar:
                for validation_id in validation_samples:
                    for model_name, model in self.models.items():
                        # Run with context if enabled
                        if EVALUATION_CONFIG["with_context"]:
                            result = self._evaluate_single_sample(validation_id, model_name, model, True)
                            f.write(json.dumps(result) + "\n")
                            f.flush()
                            pbar.update(1)
                            
                            # Small delay to avoid rate limiting
                            time.sleep(0.1)
                        
                        # Run without context if enabled
                        if EVALUATION_CONFIG["without_context"]:
                            result = self._evaluate_single_sample(validation_id, model_name, model, False)
                            f.write(json.dumps(result) + "\n")
                            f.flush()
                            pbar.update(1)
                            
                            # Small delay to avoid rate limiting
                            time.sleep(0.1)
        
        print(f"Evaluation completed. Results saved to: {output_path}")
        return str(output_path)

    def generate_html_report(self, jsonl_path: str, html_filename: Optional[str] = None) -> str:
        """Generate HTML report from JSONL results."""
        if html_filename is None:
            base_name = Path(jsonl_path).stem
            html_filename = f"{base_name}_report.html"
        
        html_path = self.results_path / html_filename
        
        # Load results
        results = []
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                results.append(json.loads(line.strip()))
        
        # Generate HTML
        html_content = self._generate_html_content(results)
        
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        print(f"HTML report generated: {html_path}")
        return str(html_path)

    def _generate_html_content(self, results: List[Dict[str, Any]]) -> str:
        """Generate HTML content for the evaluation report."""
        # Group results by validation_id and model to create consolidated rows
        grouped_results = {}
        for result in results:
            key = (result['validation_id'], result['model_name'])
            if key not in grouped_results:
                grouped_results[key] = {'with_context': None, 'without_context': None}
            
            if result.get('with_context'):
                grouped_results[key]['with_context'] = result
            else:
                grouped_results[key]['without_context'] = result
        
        # Calculate summary statistics
        total_samples = len(results)
        successful_samples = len([r for r in results if not r.get("error")])
        models_tested = list(set(r["model_name"] for r in results))
        with_context_count = len([r for r in results if r.get("with_context")])
        without_context_count = len([r for r in results if not r.get("with_context")])
        
        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VisionRAG Validation Evaluation Report</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1600px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .header {{
            text-align: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 2px solid #eee;
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }}
        .summary-card {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 6px;
            text-align: center;
        }}
        .summary-card h3 {{
            margin: 0 0 10px 0;
            color: #333;
            font-size: 14px;
        }}
        .summary-card .number {{
            font-size: 20px;
            font-weight: bold;
            color: #007bff;
        }}
        .filters {{
            margin-bottom: 20px;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 6px;
            display: flex;
            gap: 15px;
            align-items: center;
            flex-wrap: wrap;
        }}
        .filter-group {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .filter-group label {{
            font-weight: bold;
            color: #333;
        }}
        .filter-select {{
            padding: 5px 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            background: white;
        }}
        .results-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
            font-size: 12px;
        }}
        .results-table th {{
            background: #007bff;
            color: white;
            padding: 12px 8px;
            text-align: left;
            font-weight: bold;
            border: 1px solid #0056b3;
            position: sticky;
            top: 0;
            z-index: 10;
        }}
        .results-table td {{
            padding: 8px 6px;
            border: 1px solid #ddd;
            vertical-align: top;
            word-wrap: break-word;
        }}
        .results-table tr:nth-child(even) {{
            background: #f8f9fa;
        }}
        .results-table tr:hover {{
            background: #e3f2fd;
        }}
        .image-cell {{
            text-align: center;
            width: 180px;
        }}
        .image-cell img {{
            max-width: 160px;
            max-height: 160px;
            border-radius: 4px;
            border: 1px solid #ddd;
            cursor: pointer;
        }}
        .question-cell {{
            width: 200px;
            max-width: 200px;
        }}
        .similar-images-cell {{
            width: 300px;
            max-width: 300px;
        }}
        .similar-item {{
            background: #f0f0f0;
            padding: 8px;
            margin: 4px 0;
            border-radius: 4px;
            border-left: 3px solid #007bff;
            position: relative;
        }}
        .similar-item img {{
            max-width: 60px;
            max-height: 60px;
            border-radius: 3px;
            border: 1px solid #ddd;
            float: left;
            margin-right: 8px;
        }}
        .similar-item-content {{
            overflow: hidden;
            font-size: 11px;
        }}
        .distance-score {{
            font-weight: bold;
            color: #007bff;
            display: block;
            margin-bottom: 2px;
        }}
        .response-cell {{
            width: 300px;
            max-width: 300px;
        }}
        .response-content {{
            max-height: 150px;
            overflow-y: auto;
            padding: 5px;
            background: #f9f9f9;
            border-radius: 3px;
            margin-bottom: 5px;
        }}
        .error-cell {{
            background: #fff3cd;
            color: #856404;
            font-weight: bold;
            padding: 5px;
            border-radius: 3px;
        }}
        .processing-time {{
            font-size: 10px;
            color: #666;
        }}
        .toggle-button {{
            background: #007bff;
            color: white;
            border: none;
            padding: 2px 6px;
            border-radius: 3px;
            cursor: pointer;
            font-size: 10px;
            margin: 2px;
        }}
        .toggle-button:hover {{
            background: #0056b3;
        }}
        .collapsible-content {{
            max-height: 150px;
            overflow-y: auto;
            border: 1px solid #ddd;
            padding: 5px;
            margin-top: 5px;
            border-radius: 3px;
            font-size: 11px;
            background: #f9f9f9;
        }}
        .hidden {{
            display: none;
        }}
        .context-column {{
            background: #e8f5e8;
            border-left: 3px solid #28a745;
        }}
        .no-context-column {{
            background: #ffeaea;
            border-left: 3px solid #dc3545;
        }}
        .context-header {{
            font-weight: bold;
            font-size: 11px;
            margin-bottom: 5px;
            padding: 3px;
            border-radius: 3px;
        }}
        .context-header.with {{
            background: #28a745;
            color: white;
        }}
        .context-header.without {{
            background: #dc3545;
            color: white;
        }}
        .image-modal {{
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0,0,0,0.8);
        }}
        .modal-content {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            max-width: 90%;
            max-height: 90%;
        }}
        .modal-content img {{
            max-width: 100%;
            max-height: 100%;
            border-radius: 8px;
        }}
        .close {{
            position: absolute;
            top: 15px;
            right: 35px;
            color: #f1f1f1;
            font-size: 40px;
            font-weight: bold;
            cursor: pointer;
        }}
        .close:hover {{
            color: #bbb;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>VisionRAG Validation Evaluation Report</h1>
            <p>Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        </div>
        
        <div class="summary">
            <div class="summary-card">
                <h3>Total Samples</h3>
                <div class="number">{total_samples}</div>
            </div>
            <div class="summary-card">
                <h3>Successful</h3>
                <div class="number">{successful_samples}</div>
            </div>
            <div class="summary-card">
                <h3>Success Rate</h3>
                <div class="number">{(successful_samples/total_samples*100):.1f}%</div>
            </div>
            <div class="summary-card">
                <h3>With Context</h3>
                <div class="number">{with_context_count}</div>
            </div>
            <div class="summary-card">
                <h3>Without Context</h3>
                <div class="number">{without_context_count}</div>
            </div>
            <div class="summary-card">
                <h3>Models Tested</h3>
                <div class="number">{len(models_tested)}</div>
            </div>
        </div>
        
        <div class="filters">
            <div class="filter-group">
                <label>
                    <input type="checkbox" id="showWithContext" checked onchange="toggleColumns()"> Show With Context
                </label>
            </div>
            <div class="filter-group">
                <label>
                    <input type="checkbox" id="showWithoutContext" checked onchange="toggleColumns()"> Show Without Context
                </label>
            </div>
            <div class="filter-group">
                <label for="modelFilter">Model:</label>
                <select id="modelFilter" class="filter-select" onchange="filterResults()">
                    <option value="all">All Models</option>
        """
        
        # Add model options
        for model in models_tested:
            html += f'<option value="{model}">{model}</option>'
        
        html += """
                </select>
            </div>
            <div class="filter-group">
                <label for="statusFilter">Status:</label>
                <select id="statusFilter" class="filter-select" onchange="filterResults()">
                    <option value="all">All</option>
                    <option value="success">Success Only</option>
                    <option value="error">Errors Only</option>
                </select>
            </div>
        </div>
        
        <table class="results-table">
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Query Image</th>
                    <th>Real Question</th>
                    <th>Ground Truth</th>
                    <th>Model</th>
                    <th>Similar Images</th>
                    <th class="with-context-col">With Context Response</th>
                    <th class="without-context-col">Without Context Response</th>
                    <th>Processing Time</th>
                </tr>
            </thead>
            <tbody>
        """
        
        # Add each grouped result as a table row
        for (validation_id, model_name), result_pair in grouped_results.items():
            with_result = result_pair['with_context']
            without_result = result_pair['without_context']
            
            # Get common data (prefer with_context if available, otherwise without_context)
            base_result = with_result if with_result else without_result
            
            # Build similar images display with actual images
            similar_images_html = ""
            if with_result and with_result.get("similar_images"):
                for i, sim_img in enumerate(with_result["similar_images"]):
                    similar_images_html += f"""
                        <div class="similar-item">
                            <img src="{sim_img.get('image_url', '')}" alt="Similar {i+1}" onclick="openImageModal(this.src)">
                            <div class="similar-item-content">
                                <span class="distance-score">#{i+1} (d:{sim_img['distance']:.3f})</span>
                                <strong>Q:</strong> {sim_img['question']}<br>
                                <strong>A:</strong> {sim_img['crowd_majority']}
                            </div>
                        </div>
                    """
            
            # Build response cells
            with_context_cell = ""
            without_context_cell = ""
            
            if with_result:
                if with_result.get("error"):
                    with_context_cell = f'<div class="error-cell">Error: {with_result["error"]}</div>'
                else:
                    prompt_html = with_result.get('prompt_used', '').replace('\n', '<br>')
                    response_html = with_result.get('llm_response', '').replace('\n', '<br>')
                    with_context_cell = f"""
                        <div class="context-header with">WITH CONTEXT</div>
                        <div class="response-content">{response_html}</div>
                        <button class="toggle-button" onclick="togglePrompt(this)">Show Prompt</button>
                        <div class="collapsible-content" style="display: none;">{prompt_html}</div>
                        <div class="processing-time">{with_result.get('processing_time', 0):.2f}s</div>
                    """
            else:
                with_context_cell = '<div style="color: #999; font-style: italic;">Not evaluated</div>'
            
            if without_result:
                if without_result.get("error"):
                    without_context_cell = f'<div class="error-cell">Error: {without_result["error"]}</div>'
                else:
                    prompt_html = without_result.get('prompt_used', '').replace('\n', '<br>')
                    response_html = without_result.get('llm_response', '').replace('\n', '<br>')
                    without_context_cell = f"""
                        <div class="context-header without">WITHOUT CONTEXT</div>
                        <div class="response-content">{response_html}</div>
                        <button class="toggle-button" onclick="togglePrompt(this)">Show Prompt</button>
                        <div class="collapsible-content" style="display: none;">{prompt_html}</div>
                        <div class="processing-time">{without_result.get('processing_time', 0):.2f}s</div>
                    """
            else:
                without_context_cell = '<div style="color: #999; font-style: italic;">Not evaluated</div>'
            
            # Determine row status for filtering
            has_error = (with_result and with_result.get("error")) or (without_result and without_result.get("error"))
            status = "error" if has_error else "success"
            
            # Calculate total processing time
            total_time = 0
            if with_result:
                total_time += with_result.get('processing_time', 0)
            if without_result:
                total_time += without_result.get('processing_time', 0)
            
            html += f"""
                <tr class="result-row" data-model="{model_name}" data-status="{status}">
                    <td>{validation_id}</td>
                    <td class="image-cell">
                        <img src="{base_result.get('image_url', '')}" alt="Query Image {validation_id}" onclick="openImageModal(this.src)">
                    </td>
                    <td class="question-cell">{base_result.get('real_question', 'N/A')}</td>
                    <td class="question-cell">{base_result.get('crowd_majority', 'N/A')}</td>
                    <td>{model_name}</td>
                    <td class="similar-images-cell">{similar_images_html}</td>
                    <td class="context-column with-context-col">{with_context_cell}</td>
                    <td class="no-context-column without-context-col">{without_context_cell}</td>
                    <td>
                        <span class="processing-time">{total_time:.2f}s total</span>
                    </td>
                </tr>
            """
        
        html += """
            </tbody>
        </table>
    </div>
    
    <!-- Image Modal -->
    <div id="imageModal" class="image-modal">
        <span class="close" onclick="closeImageModal()">&times;</span>
        <div class="modal-content">
            <img id="modalImage" src="" alt="Full Size Image">
        </div>
    </div>
    
    <script>
        function filterResults() {
            const modelFilter = document.getElementById('modelFilter').value;
            const statusFilter = document.getElementById('statusFilter').value;
            
            const rows = document.querySelectorAll('.result-row');
            
            rows.forEach(row => {
                let show = true;
                
                // Model filter
                if (modelFilter !== 'all') {
                    const rowModel = row.getAttribute('data-model');
                    if (modelFilter !== rowModel) {
                        show = false;
                    }
                }
                
                // Status filter
                if (statusFilter !== 'all') {
                    const rowStatus = row.getAttribute('data-status');
                    if (statusFilter !== rowStatus) {
                        show = false;
                    }
                }
                
                row.style.display = show ? '' : 'none';
            });
        }
        
        function toggleColumns() {
            const showWithContext = document.getElementById('showWithContext').checked;
            const showWithoutContext = document.getElementById('showWithoutContext').checked;
            
            const withContextCols = document.querySelectorAll('.with-context-col');
            const withoutContextCols = document.querySelectorAll('.without-context-col');
            
            withContextCols.forEach(col => {
                col.style.display = showWithContext ? '' : 'none';
            });
            
            withoutContextCols.forEach(col => {
                col.style.display = showWithoutContext ? '' : 'none';
            });
        }
        
        function togglePrompt(button) {
            const content = button.nextElementSibling;
            if (content.style.display === 'none') {
                content.style.display = 'block';
                button.textContent = 'Hide Prompt';
            } else {
                content.style.display = 'none';
                button.textContent = 'Show Prompt';
            }
        }
        
        function openImageModal(src) {
            const modal = document.getElementById('imageModal');
            const modalImg = document.getElementById('modalImage');
            modal.style.display = 'block';
            modalImg.src = src;
        }
        
        function closeImageModal() {
            document.getElementById('imageModal').style.display = 'none';
        }
        
        // Close modal when clicking outside the image
        window.onclick = function(event) {
            const modal = document.getElementById('imageModal');
            if (event.target == modal) {
                modal.style.display = 'none';
            }
        }
    </script>
</body>
</html>
        """
        
        return html


def main():
    """Main function to run the evaluation."""
    print("Starting VisionRAG Validation Dataset Evaluation")
    print("=" * 50)
    
    # Initialize evaluator
    evaluator = ValidationEvaluator()
    
    # Run evaluation
    jsonl_path = evaluator.run_evaluation()
    
    # Generate HTML report
    html_path = evaluator.generate_html_report(jsonl_path)
    
    print("\n" + "=" * 50)
    print("Evaluation completed successfully!")
    print(f"Results saved to: {jsonl_path}")
    print(f"HTML report: {html_path}")
    print("\nYou can open the HTML file in your browser to view the results.")


if __name__ == "__main__":
    main() 
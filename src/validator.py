import requests
import json
import os
from dotenv import load_dotenv
from typing import Dict, Tuple, Any
import re

load_dotenv()

class ValidationJudge:
    def __init__(self, model: str = "anthropic/claude-3-haiku"):
        """
        Initialize the Validation Judge using OpenRouter
        
        Good judge models:
        - anthropic/claude-3-haiku (fast and cheap)
        - anthropic/claude-3-sonnet (more thorough)
        - openai/gpt-4 (good reasoning)
        - google/gemini-pro (alternative)
        """
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.app_name = os.getenv("OPENROUTER_APP_NAME", "VLM-RAG")
        self.model = model
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY not found in environment variables")
    
    def get_headers(self):
        """Get headers for OpenRouter API"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/your-repo/vlm-rag",
            "X-Title": self.app_name,
        }
    
    def evaluate_accuracy(self, 
                         user_query: str, 
                         baseline_response: str, 
                         rag_response: str,
                         image_description: str = "") -> Dict[str, Any]:
        """
        Compare accuracy of baseline vs RAG response using LLM judge
        
        Args:
            user_query: The original user question
            baseline_response: Response without retrieval context
            rag_response: Response with retrieval context
            image_description: Optional description of what's actually in the image
        
        Returns:
            Dictionary with accuracy scores and reasoning
        """
        
        prompt = f"""
        You are an expert evaluator for visual interpretation systems designed for blind and low vision (BLV) users.
        
        TASK: Compare the accuracy of two visual interpretations and rate them on a scale of 1-10.
        
        USER QUERY: {user_query}
        
        BASELINE RESPONSE (without context): {baseline_response}
        
        RAG RESPONSE (with context): {rag_response}
        
        {f"ACTUAL IMAGE CONTENT: {image_description}" if image_description else ""}
        
        INSTRUCTIONS:
        1. Rate each response's accuracy from 1-10 (10 = perfect accuracy)
        2. Consider: factual correctness, relevance to query, helpful details for BLV users
        3. Provide brief reasoning for each score
        
        RESPOND IN THIS EXACT FORMAT:
        BASELINE_SCORE: [number]
        RAG_SCORE: [number]
        BASELINE_REASONING: [brief explanation]
        RAG_REASONING: [brief explanation]
        WINNER: [BASELINE/RAG/TIE]
        """
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 400
        }
        
        try:
            response = requests.post(
                self.base_url,
                headers=self.get_headers(),
                json=payload
            )
            response.raise_for_status()
            
            result = response.json()
            judgment_text = result['choices'][0]['message']['content']
            
            # Parse the structured response
            parsed = self._parse_accuracy_judgment(judgment_text)
            
            return {
                "baseline_score": parsed["baseline_score"],
                "rag_score": parsed["rag_score"],
                "baseline_reasoning": parsed["baseline_reasoning"],
                "rag_reasoning": parsed["rag_reasoning"],
                "winner": parsed["winner"],
                "raw_judgment": judgment_text
            }
            
        except Exception as e:
            return {
                "error": f"Evaluation failed: {str(e)}",
                "baseline_score": 0,
                "rag_score": 0,
                "winner": "ERROR"
            }
    
    def evaluate_length(self, baseline_response: str, rag_response: str) -> Dict[str, Any]:
        """
        Compare response lengths (shorter is generally better for BLV users)
        
        Args:
            baseline_response: Response without retrieval context
            rag_response: Response with retrieval context
        
        Returns:
            Dictionary with length analysis
        """
        baseline_words = len(baseline_response.split())
        rag_words = len(rag_response.split())
        
        baseline_chars = len(baseline_response)
        rag_chars = len(rag_response)
        
        # Calculate improvement (negative means RAG is longer)
        word_improvement = baseline_words - rag_words
        char_improvement = baseline_chars - rag_chars
        
        # Determine winner (shorter is better)
        if rag_words < baseline_words:
            winner = "RAG"
        elif rag_words > baseline_words:
            winner = "BASELINE"
        else:
            winner = "TIE"
        
        return {
            "baseline_word_count": baseline_words,
            "rag_word_count": rag_words,
            "baseline_char_count": baseline_chars,
            "rag_char_count": rag_chars,
            "word_improvement": word_improvement,
            "char_improvement": char_improvement,
            "rag_shorter": rag_words < baseline_words,
            "winner": winner,
            "improvement_percentage": round((word_improvement / baseline_words) * 100, 1) if baseline_words > 0 else 0
        }
    
    def comprehensive_evaluation(self, 
                               user_query: str,
                               baseline_response: str,
                               rag_response: str,
                               image_description: str = "") -> Dict[str, Any]:
        """
        Run both accuracy and length evaluations
        
        Returns:
            Combined evaluation results
        """
        accuracy_eval = self.evaluate_accuracy(user_query, baseline_response, rag_response, image_description)
        length_eval = self.evaluate_length(baseline_response, rag_response)
        
        # Calculate overall winner
        accuracy_winner = accuracy_eval.get("winner", "TIE")
        length_winner = length_eval.get("winner", "TIE")
        
        # Simple scoring: accuracy is weighted more heavily
        overall_winner = "TIE"
        if accuracy_winner == "RAG" and length_winner != "BASELINE":
            overall_winner = "RAG"
        elif accuracy_winner == "BASELINE" and length_winner != "RAG":
            overall_winner = "BASELINE"
        elif accuracy_winner == length_winner and accuracy_winner != "TIE":
            overall_winner = accuracy_winner
        
        return {
            "user_query": user_query,
            "accuracy": accuracy_eval,
            "length": length_eval,
            "overall_winner": overall_winner,
            "summary": {
                "rag_more_accurate": accuracy_eval.get("rag_score", 0) > accuracy_eval.get("baseline_score", 0),
                "rag_shorter": length_eval.get("rag_shorter", False),
                "rag_improvement": length_eval.get("improvement_percentage", 0)
            }
        }
    
    def _parse_accuracy_judgment(self, judgment_text: str) -> Dict[str, Any]:
        """Parse the structured judgment response"""
        try:
            # Extract scores using regex
            baseline_score = re.search(r'BASELINE_SCORE:\s*(\d+)', judgment_text)
            rag_score = re.search(r'RAG_SCORE:\s*(\d+)', judgment_text)
            baseline_reasoning = re.search(r'BASELINE_REASONING:\s*(.+?)(?=RAG_REASONING|WINNER|$)', judgment_text, re.DOTALL)
            rag_reasoning = re.search(r'RAG_REASONING:\s*(.+?)(?=WINNER|$)', judgment_text, re.DOTALL)
            winner = re.search(r'WINNER:\s*(\w+)', judgment_text)
            
            return {
                "baseline_score": int(baseline_score.group(1)) if baseline_score else 0,
                "rag_score": int(rag_score.group(1)) if rag_score else 0,
                "baseline_reasoning": baseline_reasoning.group(1).strip() if baseline_reasoning else "No reasoning provided",
                "rag_reasoning": rag_reasoning.group(1).strip() if rag_reasoning else "No reasoning provided",
                "winner": winner.group(1) if winner else "TIE"
            }
        except Exception as e:
            return {
                "baseline_score": 0,
                "rag_score": 0,
                "baseline_reasoning": "Parse error",
                "rag_reasoning": "Parse error",
                "winner": "ERROR"
            }
    
    def switch_model(self, new_model: str):
        """Switch to a different judge model"""
        self.model = new_model
        print(f"Switched judge model to: {new_model}")

if __name__ == "__main__":
    # Quick test
    try:
        judge = ValidationJudge()
        print("Validation judge initialized!")
        print(f"Current judge model: {judge.model}")
        
        # Test with sample data
        sample_query = "What's in this kitchen?"
        sample_baseline = "There's a kitchen with appliances and cabinets."
        sample_rag = "The kitchen has a white stove with 4 burners, a microwave above it, and wooden cabinets. There's a coffee maker on the counter."
        
        print("\nTesting accuracy evaluation...")
        accuracy_result = judge.evaluate_accuracy(sample_query, sample_baseline, sample_rag)
        print(f"Accuracy winner: {accuracy_result.get('winner', 'ERROR')}")
        
        print("\nTesting length evaluation...")
        length_result = judge.evaluate_length(sample_baseline, sample_rag)
        print(f"Length winner: {length_result.get('winner', 'ERROR')}")
        print(f"RAG is shorter: {length_result.get('rag_shorter', False)}")
        
        print("\nValidation judge is ready! 🚀")
        
    except ValueError as e:
        print(f"Setup error: {e}")
        print("Please create a .env file with your OPENROUTER_API_KEY") 
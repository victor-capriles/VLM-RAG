import requests
import json
import base64
import os
from dotenv import load_dotenv
from PIL import Image
from typing import Optional

load_dotenv()

class VisualInterpreter:
    def __init__(self, model: str = "google/gemini-pro-vision"):
        """
        Initialize the Visual Interpreter with OpenRouter
        
        Popular vision models on OpenRouter:
        - google/gemini-pro-vision
        - anthropic/claude-3-sonnet
        - openai/gpt-4-vision-preview
        - google/gemini-flash-1.5
        """
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.app_name = os.getenv("OPENROUTER_APP_NAME", "VLM-RAG")
        self.model = model
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY not found in environment variables")
    
    def encode_image_to_base64(self, image_path: str) -> str:
        """Convert image to base64 for API"""
        try:
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            raise ValueError(f"Error encoding image {image_path}: {str(e)}")
    
    def get_headers(self):
        """Get headers for OpenRouter API"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/your-repo/vlm-rag",  # Optional
            "X-Title": self.app_name,  # Optional
        }
    
    def interpret_baseline(self, image_path: str, user_query: str) -> str:
        """Baseline interpretation without retrieval context"""
        
        # Encode image
        base64_image = self.encode_image_to_base64(image_path)
        
        # Determine image type
        image_ext = os.path.splitext(image_path)[1].lower()
        if image_ext in ['.jpg', '.jpeg']:
            image_type = 'jpeg'
        elif image_ext == '.png':
            image_type = 'png'
        elif image_ext == '.webp':
            image_type = 'webp'
        else:
            image_type = 'jpeg'  # default
        
        data_url = f"data:image/{image_type};base64,{base64_image}"
        
        # Prepare the request
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"User query: {user_query}\n\nPlease provide a helpful visual interpretation for this blind or low vision user."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": data_url
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 300
        }
        
        try:
            response = requests.post(
                self.base_url,
                headers=self.get_headers(),
                json=payload
            )
            response.raise_for_status()
            
            result = response.json()
            return result['choices'][0]['message']['content']
            
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"API request failed: {str(e)}")
        except KeyError as e:
            raise RuntimeError(f"Unexpected API response format: {str(e)}")
    
    def interpret_with_context(self, image_path: str, user_query: str, retrieved_context: str) -> str:
        """Interpretation using retrieved similar interactions (RAG)"""
        
        # Encode image
        base64_image = self.encode_image_to_base64(image_path)
        
        # Determine image type
        image_ext = os.path.splitext(image_path)[1].lower()
        if image_ext in ['.jpg', '.jpeg']:
            image_type = 'jpeg'
        elif image_ext == '.png':
            image_type = 'png'
        elif image_ext == '.webp':
            image_type = 'webp'
        else:
            image_type = 'jpeg'  # default
        
        data_url = f"data:image/{image_type};base64,{base64_image}"
        
        # Create enhanced prompt with context
        enhanced_prompt = f"""
        User query: {user_query}
        
        Similar past interactions from other BLV users: 
        {retrieved_context}
        
        Please provide a visual interpretation that considers these past interactions to better meet this BLV user's needs. 
        Focus on being concise but comprehensive, keeping the response shorter when possible while maintaining accuracy.
        """
        
        # Prepare the request
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": enhanced_prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": data_url
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 300
        }
        
        try:
            response = requests.post(
                self.base_url,
                headers=self.get_headers(),
                json=payload
            )
            response.raise_for_status()
            
            result = response.json()
            return result['choices'][0]['message']['content']
            
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"API request failed: {str(e)}")
        except KeyError as e:
            raise RuntimeError(f"Unexpected API response format: {str(e)}")
    
    def switch_model(self, new_model: str):
        """Switch to a different vision model"""
        self.model = new_model
        print(f"Switched to model: {new_model}")

if __name__ == "__main__":
    # Quick test - create a dummy image first
    from PIL import Image
    import os
    
    # Create test directories if they don't exist
    os.makedirs("data/images", exist_ok=True)
    
    # Create a simple test image
    test_img = Image.new('RGB', (100, 100), color='red')
    test_img.save("data/images/test.jpg")
    
    try:
        # Test the interpreter
        interpreter = VisualInterpreter()
        print("Visual interpreter initialized!")
        print(f"Current model: {interpreter.model}")
        
        # You can test with: 
        # response = interpreter.interpret_baseline("data/images/test.jpg", "What color is this image?")
        # print(response)
        
    except ValueError as e:
        print(f"Setup error: {e}")
        print("Please create a .env file with your OPENROUTER_API_KEY") 
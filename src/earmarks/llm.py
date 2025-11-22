"""
LLM integration module for earmark classification.

Uses a local LLM (via Ollama) to classify ambiguous amendments.
"""

import json
from pathlib import Path
from sys import stderr
from typing import Any, Optional
import urllib.request
import urllib.error


def load_llm_config() -> dict[str, Any]:
    """
    Load LLM configuration from config file.
    
    Returns:
        Configuration dictionary
    """
    config_path = (
        Path(__file__).parent.parent / "config" / "llm_config.json"
    )
    
    # Default configuration
    default_config = {
        "model": "qwen2.5:3b",
        "host": "localhost",
        "port": 11434,
        "timeout": 30,
        "classification_prompt": (
            "Classify if this is an earmark. "
            "Description: {description}. Amount: ${amount}. "
            "Respond with JSON: {{\"is_earmark\": bool, "
            "\"confidence\": float, \"reasoning\": str}}"
        )
    }
    
    if not config_path.exists():
        return default_config
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            # Merge with defaults
            return {**default_config, **config}
    except Exception as e:
        print(f"[LLM] Error loading config: {e}", file=stderr)
        return default_config


class LocalLLMProcessor:
    """
    Processor for using local LLM to classify earmarks.
    
    Uses Ollama API to communicate with a locally running LLM.
    """
    
    def __init__(self, config: Optional[dict[str, Any]] = None):
        """
        Initialize LLM processor.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or load_llm_config()
        self.model = self.config.get("model", "qwen2.5:3b")
        self.host = self.config.get("host", "localhost")
        self.port = self.config.get("port", 11434)
        self.timeout = self.config.get("timeout", 30)
        self.base_url = f"http://{self.host}:{self.port}"
    
    def _call_ollama(self, prompt: str) -> Optional[str]:
        """
        Call Ollama API to generate a response.
        
        Args:
            prompt: The prompt to send to the LLM
        
        Returns:
            Generated response text or None on error
        """
        url = f"{self.base_url}/api/generate"
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
            }
        }
        
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode('utf-8'),
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "stipend-tracker/1.0"
                }
            )
            
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                return result.get("response", "")
        
        except urllib.error.URLError as e:
            print(
                f"[LLM] Connection error: {e}. Is Ollama running?",
                file=stderr
            )
            return None
        except Exception as e:
            print(f"[LLM] Error calling Ollama: {e}", file=stderr)
            return None
    
    def _parse_llm_response(
        self,
        response: str
    ) -> Optional[dict[str, Any]]:
        """
        Parse LLM response into structured result.
        
        Args:
            response: Raw LLM response text
        
        Returns:
            Parsed classification dictionary or None on error
        """
        if not response:
            return None
        
        try:
            # Find JSON in the response
            start = response.find('{')
            end = response.rfind('}') + 1
            
            if start >= 0 and end > start:
                json_str = response[start:end]
                result = json.loads(json_str)
                
                # Validate required fields
                required = ['is_earmark', 'confidence']
                if all(k in result for k in required):
                    reasoning = result.get(
                        'reasoning',
                        'No reasoning provided'
                    )
                    return {
                        'is_earmark': bool(result['is_earmark']),
                        'confidence': float(result['confidence']),
                        'reasoning': reasoning,
                        'llm_model': self.model
                    }
            
            msg = f"[LLM] Could not parse response: {response[:100]}"
            print(msg, file=stderr)
            return None
            
        except (json.JSONDecodeError, ValueError) as e:
            print(f"[LLM] JSON parse error: {e}", file=stderr)
            return None
    
    def classify_earmark(
        self,
        description: str,
        amount: Optional[float] = None
    ) -> dict[str, Any]:
        """
        Classify an amendment as earmark using LLM.
        
        Args:
            description: Amendment description text
            amount: Dollar amount (optional)
        
        Returns:
            Classification result dictionary
        """
        # Get prompt template from config
        prompt_template = self.config.get("classification_prompt", "")
        
        # Format prompt with amendment details
        amount_str = f"{amount:,.2f}" if amount else "unknown"
        prompt = prompt_template.format(
            description=description[:500],
            amount=amount_str
        )
        
        # Call LLM
        response = self._call_ollama(prompt)
        
        if not response:
            # LLM failed
            return {
                'is_earmark': False,
                'confidence': 0.0,
                'reasoning': 'LLM call failed',
                'llm_model': self.model,
                'llm_used': False
            }
        
        # Parse response
        result = self._parse_llm_response(response)
        
        if result:
            result['llm_used'] = True
            return result
        else:
            # Parse failed
            return {
                'is_earmark': False,
                'confidence': 0.0,
                'reasoning': 'LLM response parse failed',
                'llm_model': self.model,
                'llm_used': False
            }
    
    def test_connection(self) -> bool:
        """
        Test if Ollama is accessible.
        
        Returns:
            True if connection successful
        """
        try:
            # Check if Ollama is running
            url = f"{self.base_url}/api/tags"
            req = urllib.request.Request(url)
            
            with urllib.request.urlopen(req, timeout=5) as resp:
                models = json.loads(resp.read().decode('utf-8'))
                model_list = models.get('models', [])
                model_names = [m.get('name', '') for m in model_list]
                
                if self.model in model_names:
                    msg = (
                        f"[LLM] Connected to Ollama, "
                        f"model '{self.model}' available"
                    )
                    print(msg)
                    return True
                else:
                    msg = (
                        f"[LLM] Model '{self.model}' not found. "
                        f"Available: {', '.join(model_names[:5])}"
                    )
                    print(msg, file=stderr)
                    return False
        
        except Exception as e:
            msg = f"[LLM] Cannot connect to Ollama at {self.base_url}: {e}"
            print(msg, file=stderr)
            return False

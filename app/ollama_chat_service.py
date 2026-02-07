"""
Ollama Chat Service with Langfuse Integration

This service wraps Ollama's chat API for LLM generation with full Langfuse tracing support.
Used as an alternative to OpenAI for RAG answer generation.

Features:
- Compatible interface with OpenAI chat completions
- Automatic Langfuse trace logging
- Token estimation for monitoring
- Response streaming support
- Cost tracking (always $0.00 for local models)
"""

import requests
import time
import logging
from typing import Dict, List, Optional, Any
from functools import wraps

# Langfuse imports (compatible with v3.13.0+)
try:
    from langfuse import observe
    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False
    logging.warning("Langfuse not installed. Ollama chat service observability disabled.")
    # No-op decorator when Langfuse not available
    def observe(*args, **kwargs):
        def decorator(func):
            @wraps(func)
            def wrapper(*f_args, **f_kwargs):
                return func(*f_args, **f_kwargs)
            return wrapper
        return decorator

from app.config import settings

logger = logging.getLogger(__name__)


class OllamaChatService:
    """
    Service for generating chat completions using local Ollama models.
    
    Provides OpenAI-compatible interface for seamless integration with RAG pipeline.
    All generations are traced in Langfuse for monitoring and quality comparison.
    """
    
    def __init__(self):
        """Initialize Ollama chat service."""
        self.base_url = settings.OLLAMA_BASE_URL
        self.model = settings.OLLAMA_CHAT_MODEL
        self.timeout = 300  # 5 minutes for long generations
        
        logger.info(f"Initialized OllamaChatService: model={self.model}, url={self.base_url}")
    
    @observe(as_type="generation", capture_input=True, capture_output=True)
    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate chat completion using Ollama with Langfuse tracing.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0.0 = deterministic, 1.0 = creative)
            max_tokens: Maximum tokens to generate (optional)
            **kwargs: Additional Ollama-specific parameters
            
        Returns:
            Dict with OpenAI-compatible structure:
            {
                "content": str,  # Generated text
                "model": str,    # Model name used
                "usage": {
                    "prompt_tokens": int,
                    "completion_tokens": int,
                    "total_tokens": int
                },
                "finish_reason": str,
                "latency_ms": float
            }
            
        Raises:
            requests.RequestException: If Ollama API call fails
        """
        start_time = time.time()
        
        # Convert messages to Ollama prompt format
        prompt = self._messages_to_prompt(messages)
        
        # Prepare Ollama API request
        payload = {
            "model": self.model,
            "prompt": prompt,
            "temperature": temperature,
            "stream": False,
            "options": {}
        }
        
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens
        
        # Add custom options
        payload["options"].update(kwargs)
        
        logger.info(f"Ollama generation request: model={self.model}, temp={temperature}, prompt_len={len(prompt)}")
        
        try:
            # Call Ollama API
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            result = response.json()
            
            # Extract response
            content = result.get("response", "")
            
            # Estimate token counts (Ollama doesn't always provide exact counts)
            prompt_tokens = self._estimate_tokens(prompt)
            completion_tokens = self._estimate_tokens(content)
            total_tokens = prompt_tokens + completion_tokens
            
            # Calculate latency
            latency_ms = (time.time() - start_time) * 1000
            
            # Log completion (Langfuse @observe decorator handles automatic tracing)
            logger.info(
                f"Ollama generation complete: model={self.model}, "
                f"latency={latency_ms:.0f}ms, tokens={completion_tokens}, "
                f"cost=$0.00 (local)"
            )
            
            return {
                "content": content,
                "model": self.model,
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens
                },
                "finish_reason": "stop",
                "latency_ms": latency_ms,
                "cost": 0.00
            }
            
        except requests.RequestException as e:
            logger.error(f"Ollama API error: {str(e)}")
            # Langfuse @observe decorator automatically tracks errors
            raise
    
    def _messages_to_prompt(self, messages: List[Dict[str, str]]) -> str:
        """
        Convert OpenAI-style messages to Ollama prompt format.
        
        Args:
            messages: List of {"role": "system|user|assistant", "content": "..."}
            
        Returns:
            Formatted prompt string
        """
        prompt_parts = []
        
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                prompt_parts.append(f"System: {content}")
            elif role == "user":
                prompt_parts.append(f"User: {content}")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}")
        
        # Add final prompt for assistant response
        prompt_parts.append("Assistant:")
        
        return "\n\n".join(prompt_parts)
    
    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate token count from text length.
        
        Rough approximation: 1 token ≈ 4 characters (for English text)
        More accurate than character count for monitoring purposes.
        
        Args:
            text: Input text
            
        Returns:
            Estimated token count
        """
        return len(text) // 4
    
    @observe(as_type="generation")
    def stream_generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        **kwargs
    ):
        """
        Generate chat completion with streaming (for future WebUI integration).
        
        Args:
            messages: List of message dicts
            temperature: Sampling temperature
            **kwargs: Additional parameters
            
        Yields:
            Generated text chunks
        """
        prompt = self._messages_to_prompt(messages)
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "temperature": temperature,
            "stream": True,
            "options": kwargs
        }
        
        logger.info(f"Ollama streaming generation: model={self.model}")
        
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                stream=True,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            for line in response.iter_lines():
                if line:
                    import json
                    chunk = json.loads(line)
                    if "response" in chunk:
                        yield chunk["response"]
                        
        except requests.RequestException as e:
            logger.error(f"Ollama streaming error: {str(e)}")
            raise
    
    def test_connection(self) -> bool:
        """
        Test connection to Ollama service.
        
        Returns:
            True if Ollama is accessible and model is available
        """
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            response.raise_for_status()
            
            models = response.json().get("models", [])
            model_names = [m.get("name") for m in models]
            
            if self.model in model_names or f"{self.model}:latest" in model_names:
                logger.info(f"Ollama connection successful: {self.model} available")
                return True
            else:
                logger.warning(f"Ollama model {self.model} not found. Available: {model_names}")
                return False
                
        except requests.RequestException as e:
            logger.error(f"Ollama connection failed: {str(e)}")
            return False


# Global instance
_ollama_chat_service = None


def get_ollama_chat_service() -> OllamaChatService:
    """
    Get or create global OllamaChatService instance.
    
    Returns:
        OllamaChatService singleton
    """
    global _ollama_chat_service
    if _ollama_chat_service is None:
        _ollama_chat_service = OllamaChatService()
    return _ollama_chat_service

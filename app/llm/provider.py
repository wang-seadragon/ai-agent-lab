import os

from langchain_ollama import ChatOllama


def get_chat_model():
    """Local LLM adapter; future providers can be added here."""
    return ChatOllama(
        model=os.getenv("OLLAMA_MODEL", "qwen3:14b"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        temperature=0,
    )

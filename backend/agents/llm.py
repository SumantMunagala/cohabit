import os

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_ollama import ChatOllama

load_dotenv()

LOCAL_MODEL = "llama3.1"
LOCAL_BASE_URL = "http://localhost:11434"
API_MODEL = "claude-sonnet-5"


def get_llm(temperature: float | None = None):
    mode = os.environ.get("LLM_MODE", "api")
    if mode == "local":
        kwargs = {} if temperature is None else {"temperature": temperature}
        return ChatOllama(model=LOCAL_MODEL, base_url=LOCAL_BASE_URL, **kwargs)
    if mode == "api":
        return ChatAnthropic(model=API_MODEL)
    raise ValueError(f"Invalid LLM_MODE: {mode!r} (expected 'local' or 'api')")

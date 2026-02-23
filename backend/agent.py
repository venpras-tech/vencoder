from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent

from config import OLLAMA_BASE_URL
from prompts import CODING_AGENT_SYSTEM_PROMPT
from tools import (
    read_file,
    write_file,
    edit_file,
    delete_file,
    shell_command,
    grep_search,
    glob_search,
    search_context,
)

TOOLS = [
    read_file,
    write_file,
    edit_file,
    delete_file,
    shell_command,
    grep_search,
    glob_search,
    search_context,
]


def build_agent(model: str):
    llm = ChatOllama(
        model=model,
        base_url=OLLAMA_BASE_URL,
        temperature=0.2,
    )
    return create_react_agent(llm, TOOLS, prompt=CODING_AGENT_SYSTEM_PROMPT)

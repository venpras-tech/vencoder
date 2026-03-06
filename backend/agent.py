from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent

from config import NUM_CTX, NUM_PREDICT, OLLAMA_BASE_URL, OLLAMA_KEEP_ALIVE, REPEAT_PENALTY, TEMPERATURE
from prompts import (
    ASK_MODE_PROMPT,
    CODING_AGENT_SYSTEM_PROMPT,
    PLAN_MODE_PROMPT,
)
from tools import (
    read_file,
    write_file,
    edit_file,
    delete_file,
    shell_command,
    grep_search,
    glob_search,
    search_context,
    save_plan,
)

AGENT_TOOLS = [
    read_file,
    write_file,
    edit_file,
    delete_file,
    shell_command,
    grep_search,
    glob_search,
    search_context,
]

ASK_TOOLS = [read_file, grep_search, glob_search, search_context]

PLAN_TOOLS = [read_file, grep_search, glob_search, search_context, save_plan]


def build_agent(model: str, mode: str = "agent"):
    kwargs = {
        "temperature": TEMPERATURE,
        "num_ctx": NUM_CTX,
        "repeat_penalty": REPEAT_PENALTY,
        "keep_alive": OLLAMA_KEEP_ALIVE,
        "reasoning": False,
    }
    num_pred = NUM_PREDICT if NUM_PREDICT > 0 else 4096
    kwargs["num_predict"] = num_pred
    llm = ChatOllama(
        model=model,
        base_url=OLLAMA_BASE_URL,
        **kwargs,
    )
    if mode == "ask":
        return create_react_agent(llm, ASK_TOOLS, prompt=ASK_MODE_PROMPT)
    if mode == "plan":
        return create_react_agent(llm, PLAN_TOOLS, prompt=PLAN_MODE_PROMPT)
    return create_react_agent(llm, AGENT_TOOLS, prompt=CODING_AGENT_SYSTEM_PROMPT)

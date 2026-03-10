from langgraph.prebuilt import create_react_agent

from config import NUM_CTX, NUM_PREDICT, REPEAT_PENALTY, TEMPERATURE
from llm_builder import build_llm
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
    list_directory,
    shell_command,
    run_tests,
    grep_search,
    glob_search,
    web_search,
    search_context,
    git_status,
    git_diff,
    save_plan,
)
from tools.duplicate_wrapper import wrap_tools_with_duplicate_check

AGENT_TOOLS = wrap_tools_with_duplicate_check([
    read_file,
    write_file,
    edit_file,
    delete_file,
    list_directory,
    shell_command,
    run_tests,
    grep_search,
    glob_search,
    web_search,
    search_context,
    git_status,
    git_diff,
])

ASK_TOOLS = wrap_tools_with_duplicate_check([
    read_file,
    list_directory,
    grep_search,
    glob_search,
    web_search,
    search_context,
    git_status,
    git_diff,
])

PLAN_TOOLS = wrap_tools_with_duplicate_check([
    read_file,
    list_directory,
    grep_search,
    glob_search,
    web_search,
    search_context,
    git_status,
    git_diff,
    save_plan,
])


def build_agent(model: str, mode: str = "agent"):
    kwargs = {"reasoning": False}
    llm = build_llm(model, **kwargs)
    if mode == "ask":
        agent = create_react_agent(llm, ASK_TOOLS, prompt=ASK_MODE_PROMPT)
    elif mode == "plan":
        agent = create_react_agent(llm, PLAN_TOOLS, prompt=PLAN_MODE_PROMPT)
    else:
        agent = create_react_agent(llm, AGENT_TOOLS, prompt=CODING_AGENT_SYSTEM_PROMPT)
    return agent.with_retry(
        stop_after_attempt=3,
        wait_exponential_jitter=True,
        retry_if_exception_type=(ConnectionError, TimeoutError, OSError),
    )

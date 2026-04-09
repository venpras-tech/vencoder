from langchain.agents import create_agent

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
    scrape_url,
    search_context,
    git_status,
    git_diff,
    git_branch,
    git_log,
    git_show,
    git_stash,
    git_stash_pop,
    git_create_branch,
    git_switch_branch,
    git_delete_branch,
    git_commit,
    git_commit_all,
    git_add,
    git_reset,
    git_revert,
    git_fetch,
    git_pull,
    git_push,
    git_grep,
    git_diff_staged,
    git_undo_last_commit,
    git_clean,
    git_remote,
    git_current_branch,
    git_short_status,
    git_changed_files,
    save_plan,
    type_check_file,
    type_check_project,
    lint_file,
    lint_and_fix_file,
    security_scan_file,
    security_scan_project,
    code_review_file,
    code_review_project,
    run_all_checks,
    list_available_skills,
    execute_skill,
    create_skill,
    delete_skill,
    list_hooks,
    create_hook,
    delete_hook,
    enable_hook,
    disable_hook,
    get_hook_templates,
)
from tools.duplicate_wrapper import wrap_tools_with_duplicate_check
from mcp_external_tools import get_external_mcp_tools_sync

BASIC_GIT = [git_status, git_diff, git_branch, git_log, git_show]

EXTENDED_GIT = [
    git_stash,
    git_stash_pop,
    git_create_branch,
    git_switch_branch,
    git_delete_branch,
    git_commit,
    git_commit_all,
    git_add,
    git_reset,
    git_revert,
    git_fetch,
    git_pull,
    git_push,
    git_grep,
    git_diff_staged,
    git_undo_last_commit,
    git_clean,
    git_remote,
    git_current_branch,
    git_short_status,
    git_changed_files,
]

CODE_QUALITY_TOOLS = [
    type_check_file,
    type_check_project,
    lint_file,
    lint_and_fix_file,
    security_scan_file,
    security_scan_project,
    code_review_file,
    code_review_project,
    run_all_checks,
]

WORKFLOW_TOOLS = [
    list_available_skills,
    execute_skill,
    create_skill,
    delete_skill,
    list_hooks,
    create_hook,
    delete_hook,
    enable_hook,
    disable_hook,
    get_hook_templates,
]

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
    scrape_url,
    search_context,
    *BASIC_GIT,
    *EXTENDED_GIT,
    *CODE_QUALITY_TOOLS,
    *WORKFLOW_TOOLS,
])

ASK_TOOLS = wrap_tools_with_duplicate_check([
    read_file,
    list_directory,
    grep_search,
    glob_search,
    web_search,
    scrape_url,
    search_context,
    git_status,
    git_diff,
    git_branch,
    git_log,
    git_show,
    git_grep,
    git_remote,
    git_current_branch,
    git_changed_files,
    type_check_file,
    type_check_project,
    lint_file,
    security_scan_file,
    security_scan_project,
    code_review_file,
    code_review_project,
    list_available_skills,
    list_hooks,
])

PLAN_TOOLS = wrap_tools_with_duplicate_check([
    read_file,
    list_directory,
    grep_search,
    glob_search,
    web_search,
    scrape_url,
    search_context,
    git_status,
    git_diff,
    git_branch,
    git_log,
    git_show,
    git_short_status,
    git_changed_files,
    save_plan,
    type_check_file,
    type_check_project,
    code_review_file,
    code_review_project,
    list_available_skills,
    list_hooks,
])


def build_agent(model: str, mode: str = "agent"):
    llm = build_llm(model)
    if mode == "ask":
        agent = create_agent(llm, ASK_TOOLS, system_prompt=ASK_MODE_PROMPT)
    elif mode == "plan":
        agent = create_agent(llm, PLAN_TOOLS, system_prompt=PLAN_MODE_PROMPT)
    else:
        ext = get_external_mcp_tools_sync(mode)
        tools = AGENT_TOOLS + ext if ext else AGENT_TOOLS
        agent = create_agent(llm, tools, system_prompt=CODING_AGENT_SYSTEM_PROMPT)
    return agent.with_retry(
        stop_after_attempt=3,
        wait_exponential_jitter=True,
        retry_if_exception_type=(ConnectionError, TimeoutError, OSError),
    )

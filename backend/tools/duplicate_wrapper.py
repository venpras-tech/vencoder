from typing import Any, List

from langchain_core.tools import BaseTool, StructuredTool

from .agent_context import check_duplicate_tool_call


def _wrap_tool(tool: BaseTool) -> BaseTool:
    if not isinstance(tool, StructuredTool):
        return tool

    def _run(**kwargs: Any) -> str:
        if check_duplicate_tool_call(tool.name, kwargs):
            return "Duplicate: you already called this tool with the same input. Try a different approach."
        return tool.invoke(kwargs)

    return StructuredTool.from_function(
        func=_run,
        name=tool.name,
        description=tool.description,
        args_schema=tool.args_schema,
    )


def wrap_tools_with_duplicate_check(tools: List[BaseTool]) -> List[BaseTool]:
    return [_wrap_tool(t) for t in tools]

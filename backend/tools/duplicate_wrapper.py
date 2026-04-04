from typing import Any, List

from langchain_core.tools import BaseTool, StructuredTool

from .agent_context import check_duplicate_tool_call


def _wrap_tool(tool: BaseTool) -> BaseTool:
    if not isinstance(tool, StructuredTool):
        return tool

    desc = (tool.description or "").strip() or "(tool)"

    if getattr(tool, "coroutine", None) is not None:

        async def _arun(**kwargs: Any) -> str:
            if check_duplicate_tool_call(tool.name, kwargs):
                return "Duplicate: you already called this tool with the same input. Try a different approach."
            return await tool.ainvoke(kwargs)

        return StructuredTool.from_function(
            coroutine=_arun,
            name=tool.name,
            description=desc,
            args_schema=tool.args_schema,
        )

    def _run(**kwargs: Any) -> str:
        if check_duplicate_tool_call(tool.name, kwargs):
            return "Duplicate: you already called this tool with the same input. Try a different approach."
        return tool.invoke(kwargs)

    return StructuredTool.from_function(
        func=_run,
        name=tool.name,
        description=desc,
        args_schema=tool.args_schema,
    )


def wrap_tools_with_duplicate_check(tools: List[BaseTool]) -> List[BaseTool]:
    return [_wrap_tool(t) for t in tools]

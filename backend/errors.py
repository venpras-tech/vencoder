class ToolError(Exception):
    def __init__(self, message: str, path: str = None, tool: str = None):
        self.message = message
        self.path = path
        self.tool = tool
        super().__init__(self._format())

    def _format(self) -> str:
        parts = [self.message]
        if self.path:
            parts.append(f"path={self.path}")
        if self.tool:
            parts.append(f"tool={self.tool}")
        return " | ".join(parts)


class TimeoutError(ToolError):
    pass


class IndexError(ToolError):
    pass

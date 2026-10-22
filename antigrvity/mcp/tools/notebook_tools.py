"""Interactive notebook and code execution bridge tools."""

import ast
import io
import sys
import time
import traceback
from contextlib import redirect_stdout, redirect_stderr
from typing import Any, Dict, List, Optional
from antigrvity.mcp.protocol import MCPTool, MCPToolResult


class NotebookSession:
    """Stateful execution environment simulating a notebook kernel."""

    def __init__(self, session_id: str = "default_notebook"):
        self.session_id = session_id
        self.namespace: Dict[str, Any] = {
            "__name__": "__notebook__",
            "__doc__": "Antigrvity Interactive Notebook Kernel",
        }
        self.cell_history: List[Dict[str, Any]] = []

    def execute_code(self, code: str) -> Dict[str, Any]:
        """Execute a code block within the kernel namespace and capture outputs.
        
        Evaluates the trailing expression if present, replicating Jupyter cell behavior.
        """
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        start = time.time()
        success = True
        return_value = None
        error_msg = None

        with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
            try:
                tree = ast.parse(code)
                cell_name = f"<cell_{len(self.cell_history)+1}>"
                if tree.body and isinstance(tree.body[-1], ast.Expr):
                    last_expr = tree.body.pop()
                    if tree.body:
                        exec_code = compile(ast.Module(body=tree.body, type_ignores=[]), cell_name, "exec")
                        exec(exec_code, self.namespace)
                    eval_code = compile(ast.Expression(body=last_expr.value), cell_name, "eval")
                    return_value = eval(eval_code, self.namespace)
                else:
                    exec_code = compile(tree, cell_name, "exec")
                    exec(exec_code, self.namespace)
            except Exception:
                success = False
                error_msg = traceback.format_exc()

        duration = time.time() - start
        cell_record = {
            "cell_index": len(self.cell_history) + 1,
            "code": code,
            "stdout": stdout_buf.getvalue(),
            "stderr": stderr_buf.getvalue(),
            "return_value": repr(return_value) if return_value is not None else None,
            "success": success,
            "error": error_msg,
            "duration_sec": round(duration, 4),
        }
        self.cell_history.append(cell_record)
        return cell_record


# Default shared notebook kernel
_default_session = NotebookSession()


def get_notebook_tools(session: Optional[NotebookSession] = None) -> List[tuple[MCPTool, Any]]:
    """Return list of (MCPTool, handler) tuples for notebook execution."""
    s = session or _default_session

    tool_run = MCPTool(
        name="antigrvity_notebook_run_code",
        description="Execute a Python code cell inside the stateful ANTIGRVITY notebook kernel, capturing stdout, stderr, and returns.",
        inputSchema={
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python source code to execute"},
            },
            "required": ["code"],
        },
    )

    async def handle_run(args: Dict[str, Any]) -> MCPToolResult:
        code = args.get("code", "")
        res = s.execute_code(code)
        is_error = not res["success"]
        return MCPToolResult.json(res, is_error=is_error)

    tool_inspect = MCPTool(
        name="antigrvity_notebook_inspect_vars",
        description="Inspect variables currently present in the ANTIGRVITY notebook kernel namespace.",
        inputSchema={
            "type": "object",
            "properties": {
                "filter_prefix": {"type": "string", "description": "Optional variable prefix filter"}
            },
        },
    )

    async def handle_inspect(args: Dict[str, Any]) -> MCPToolResult:
        prefix = args.get("filter_prefix", "")
        vars_info = {}
        for k, v in s.namespace.items():
            if k.startswith("__"):
                continue
            if not prefix or k.startswith(prefix):
                vars_info[k] = {
                    "type": type(v).__name__,
                    "repr": repr(v)[:200],
                }
        return MCPToolResult.json({
            "session_id": s.session_id,
            "cells_executed": len(s.cell_history),
            "variables": vars_info,
        })

    return [
        (tool_run, handle_run),
        (tool_inspect, handle_inspect),
    ]


if __name__ == "__main__":
    # Test execution
    res = _default_session.execute_code("x = 42\nprint('Computed x =', x)\nx * 2")
    print(res)

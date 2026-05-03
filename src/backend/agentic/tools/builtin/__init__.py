from backend.agentic.tools.builtin.edit_file import EditTool
from backend.agentic.tools.builtin.glob import GlobTool
from backend.agentic.tools.builtin.grep import GrepTool
from backend.agentic.tools.builtin.list_dir import ListDirTool
from backend.agentic.tools.builtin.memory import MemoryTool
from backend.agentic.tools.builtin.read_file import ReadFileTool
from backend.agentic.tools.builtin.shell import ShellTool
from backend.agentic.tools.builtin.todo import TodosTool
from backend.agentic.tools.builtin.web_fetch import WebFetchTool
from backend.agentic.tools.builtin.web_search import WebSearchTool
from backend.agentic.tools.builtin.write_file import WriteFileTool

__all__ = [
    "ReadFileTool",
    "WriteFileTool",
    "EditTool",
    "ShellTool",
    "ListDirTool",
    "GrepTool",
    "GlobTool",
    "WebSearchTool",
    "WebFetchTool",
    "TodosTool",
    "MemoryTool",
]


def get_all_builtin_tools() -> list[type]:
    """Outils « agent IDE » — conservés dans le code comme modèle ; non branchés au SIEM.

    Réactiver en les listant ici et en décommentant l’enregistrement dans
    ``tools.registry.create_default_registry`` :

    # return [
    #     ReadFileTool,
    #     WriteFileTool,
    #     EditTool,
    #     ShellTool,
    #     ListDirTool,
    #     GrepTool,
    #     GlobTool,
    #     WebSearchTool,
    #     WebFetchTool,
    #     TodosTool,
    #     MemoryTool,
    # ]
    """
    return []

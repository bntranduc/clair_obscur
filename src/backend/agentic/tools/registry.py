from pathlib import Path
from typing import Any
from backend.agentic.config.config import Config
from backend.agentic.hooks.hook_system import HookSystem
from backend.agentic.safety.approval import ApprovalContext, ApprovalDecision, ApprovalManager
from backend.agentic.safety.plan_risk import assess_tool_step, must_prompt_user
from backend.agentic.tools.base import Tool, ToolConfirmation, ToolInvocation, ToolResult
import logging

# Référence — enregistrement bulk « coding agent » :
# from backend.agentic.tools.builtin import get_all_builtin_tools
# from backend.agentic.tools.subagents import SubagentTool, get_default_subagent_definitions

from backend.agentic.tools.clair_log_classifier import ClassifyFirewallLogTool
from backend.agentic.tools.logs_table_sql import BuildSqlForLogsTableTool, RunSqlOnLogsTableTool
from backend.agentic.tools.s3_normalized_logs import FetchNormalizedLogsFromS3Tool
from backend.agentic.tools.subagents import SubagentTool, get_logs_pipeline_subagent_definitions
from backend.agentic.tools.remediation_subagent import get_remediation_subagent_definitions
from backend.agentic.tools.mitre_subagent import get_mitre_subagent_definitions
from backend.agentic.tools.visualization import VisualizationFromPromptTool, get_visualization_subagent_definitions
from backend.agentic.tools.builtin.web_fetch import WebFetchTool
from backend.agentic.tools.builtin.web_search import WebSearchTool

logger = logging.getLogger(__name__)


class ToolRegistry:
    def __init__(self, config: Config):
        self._tools: dict[str, Tool] = {}
        self._mcp_tools: dict[str, Tool] = {}
        self.config = config

    @property
    def connected_mcp_servers(self) -> list[Tool]:
        return self._mcp_tools.values()

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            logger.warning(f"Overwriting existing tool: {tool.name}")

        self._tools[tool.name] = tool
        logger.debug(f"Registered tool: {tool.name}")

    def register_mcp_tool(self, tool: Tool) -> None:
        self._mcp_tools[tool.name] = tool
        logger.debug(f"Registered MCP tool: {tool.name}")

    def unregister(self, name: str) -> bool:
        if name in self._tools:
            del self._tools[name]
            return True

        return False

    def get(self, name: str) -> Tool | None:
        if name in self._tools:
            return self._tools[name]
        elif name in self._mcp_tools:
            return self._mcp_tools[name]

        return None

    def get_tools(self) -> list[Tool]:
        tools: list[Tool] = []

        for tool in self._tools.values():
            tools.append(tool)

        for mcp_tool in self._mcp_tools.values():
            tools.append(mcp_tool)

        if self.config.allowed_tools:
            allowed_set = set(self.config.allowed_tools)
            tools = [t for t in tools if t.name in allowed_set]

        return tools

    def get_schemas(self) -> list[dict[str, Any]]:
        return [tool.to_openai_schema() for tool in self.get_tools()]

    async def invoke(
        self,
        name: str,
        params: dict[str, Any],
        cwd: Path,
        hook_system: HookSystem,
        approval_manager: ApprovalManager | None = None,
        planning_context: str | None = None,
    ) -> ToolResult:
        tool = self.get(name)
        if tool is None:
            result = ToolResult.error_result(
                f"Unknown tool: {name}",
                metadata={"tool_name": name},
            )
            await hook_system.trigger_after_tool(name, params, result)
            return result

        validation_errors = tool.validate_params(params)
        if validation_errors:
            result = ToolResult.error_result(
                f"Invalid parameters: {'; '.join(validation_errors)}",
                metadata={
                    "tool_name": name,
                    "validation_errors": validation_errors,
                },
            )

            await hook_system.trigger_after_tool(name, params, result)

            return result

        await hook_system.trigger_before_tool(name, params)
        invocation = ToolInvocation(
            params=params,
            cwd=cwd,
        )
        if approval_manager:
            confirmation = await tool.get_confirmation(invocation)
            decision = ApprovalDecision.APPROVED

            if confirmation:
                context = ApprovalContext(
                    tool_name=name,
                    params=params,
                    is_mutating=tool.is_mutating(params),
                    affected_paths=confirmation.affected_paths,
                    command=confirmation.command,
                    is_dangerous=confirmation.is_dangerous,
                )

                decision = await approval_manager.check_approval(context)
                if decision == ApprovalDecision.REJECTED:
                    result = ToolResult.error_result(
                        "Operation rejected by safety policy"
                    )
                    await hook_system.trigger_after_tool(name, params, result)
                    return result

            risk = None
            if approval_manager.plan_risk_gate_enabled:
                risk = assess_tool_step(
                    plan_text=planning_context,
                    tool=tool,
                    tool_name=name,
                    params=params,
                    confirmation=confirmation,
                )

            risk_gate = bool(
                approval_manager.plan_risk_gate_enabled
                and risk is not None
                and must_prompt_user(risk)
            )
            policy_gate = bool(
                confirmation is not None
                and decision == ApprovalDecision.NEEDS_CONFIRMATION
            )

            if policy_gate or risk_gate:
                confirm_payload = confirmation
                if confirm_payload is None:
                    confirm_payload = ToolConfirmation(
                        tool_name=name,
                        params=params,
                        description=f"Validation requise pour « {name} ».",
                    )
                approved = await approval_manager.confirm_interactive(
                    confirm_payload,
                    risk=risk,
                )
                if not approved:
                    result = ToolResult.error_result(
                        "L’utilisateur a refusé l’opération."
                    )
                    await hook_system.trigger_after_tool(name, params, result)
                    return result

        try:
            result = await tool.execute(invocation)
        except Exception as e:
            logger.exception(f"Tool {name} raised unexpected error")
            result = ToolResult.error_result(
                f"Internal error: {str(e)}",
                metadata={
                    "tool_name": name,
                },
            )

        await hook_system.trigger_after_tool(name, params, result)
        return result


def create_default_registry(config: Config) -> ToolRegistry:
    """Registre outils pour CLAIR OBSCUR (SIEM / tickets SOC).

    - ``classify_firewall_log`` : classification BUG/ATTACK/NORMAL + sévérité (modèle ESGI).
    - Pipeline logs S3 → SQL : ``fetch_normalized_logs_from_s3``, ``build_sql_for_logs_table``,
      ``run_sql_on_logs_table``, sous-agents ``subagent_s3_normalized_logs`` et ``subagent_logs_table_sql``.
    - Visualisation : ``visualization_from_prompt``, sous-agent ``subagent_visualization_specialist``.
    - Remédiation IR : ``subagent_remediation_soc`` (plan contain/eradicate/recover, outils lecture).
    - Web public : ``web_search`` (DuckDuckGo), ``web_fetch`` (GET HTTP/HTTPS, corps tronqué).
    - MITRE : ``subagent_mitre_simple`` (référence ATT&CK via web uniquement).
    """
    registry = ToolRegistry(config)
    registry.register(WebSearchTool(config))
    registry.register(WebFetchTool(config))
    registry.register(ClassifyFirewallLogTool(config))
    registry.register(FetchNormalizedLogsFromS3Tool(config))
    registry.register(BuildSqlForLogsTableTool(config))
    registry.register(RunSqlOnLogsTableTool(config))
    registry.register(VisualizationFromPromptTool(config))
    for sub_def in get_logs_pipeline_subagent_definitions():
        registry.register(SubagentTool(config, sub_def))
    for sub_def in get_visualization_subagent_definitions():
        registry.register(SubagentTool(config, sub_def))
    for sub_def in get_remediation_subagent_definitions():
        registry.register(SubagentTool(config, sub_def))
    for sub_def in get_mitre_subagent_definitions():
        registry.register(SubagentTool(config, sub_def))
    return registry

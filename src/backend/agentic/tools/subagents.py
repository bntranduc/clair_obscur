import asyncio
import time
from dataclasses import dataclass
from typing import Any, AsyncIterator, Literal

from pydantic import BaseModel, Field

from backend.agentic.agent.events import AgentEvent, AgentEventType
from backend.agentic.config.config import Config
from backend.agentic.tools.base import Tool, ToolInvocation, ToolResult
from backend.agentic.tools.logs_table_sql import LOGS_TABLE_SCHEMA_DOC


def _wrap_subagent_stream_event(
    ev: AgentEvent,
    *,
    definition_name: str,
    parent_tool_call_id: str,
) -> AgentEvent:
    """Ajoute ``subagent`` et ``parent_tool_call_id`` pour le streaming côté UI."""
    data = {
        **ev.data,
        "subagent": definition_name,
        "parent_tool_call_id": parent_tool_call_id,
    }
    return AgentEvent(type=ev.type, data=data)


_SUBAGENT_STREAM_EVENT_TYPES: frozenset[AgentEventType] = frozenset(
    {
        AgentEventType.PLANNING_DELTA,
        AgentEventType.PLANNING_COMPLETE,
        AgentEventType.REASONING_DELTA,
        AgentEventType.REASONING_COMPLETE,
        AgentEventType.TEXT_DELTA,
        AgentEventType.TEXT_COMPLETE,
        AgentEventType.TOOL_CALL_START,
        AgentEventType.TOOL_CALL_COMPLETE,
    }
)

# Réponse finale souvent envoyée en un seul bloc par l’API → synthèse de TEXT_DELTA pour le SSE.
_SUBAGENT_SYNTH_TEXT_CHUNK = 44
_SUBAGENT_SYNTH_MIN_FULL = 72
_SUBAGENT_SYNTH_TAIL_GAP = 48


class SubagentParams(BaseModel):
    goal: str = Field(
        ..., description="The specific task or goal for the subagent to accomplish"
    )


@dataclass
class SubagentDefinition:
    name: str
    description: str
    goal_prompt: str
    allowed_tools: list[str] | None = None
    max_turns: int = 20
    timeout_seconds: float = 600


class SubagentTool(Tool):
    def __init__(self, config: Config, definition: SubagentDefinition):
        super().__init__(config)
        self.definition = definition

    @property
    def name(self) -> str:
        return f"subagent_{self.definition.name}"

    @property
    def description(self) -> str:
        return self.definition.description

    schema = SubagentParams

    def is_mutating(self, params: dict[str, Any]) -> bool:
        # Les outils internes du sous-agent portent leur propre politique ; pas de double blocage ici.
        return False

    def _build_prompt(self, goal: str) -> str:
        return f"""You are a specialized sub-agent with a specific task to complete.

        {self.definition.goal_prompt}

        YOUR TASK:
        {goal}

        IMPORTANT:
        - Focus only on completing the specified task
        - Do not engage in unrelated actions
        - Once you have completed the task or have the answer, provide your final response
        - Be concise and direct in your output
        """

    async def stream_execute(
        self,
        invocation: ToolInvocation,
        parent_tool_call_id: str,
    ) -> AsyncIterator[tuple[Literal["forward", "final"], Any]]:
        """Exécute le sous-agent ; émet ``forward`` + ``AgentEvent`` si ``parent_tool_call_id`` est non vide, puis ``final`` + ``ToolResult``."""
        from backend.agentic.agent.agent import Agent

        params = SubagentParams(**invocation.params)
        if not params.goal:
            yield (
                "final",
                ToolResult.error_result("No goal specified for sub-agent"),
            )
            return

        config_dict = self.config.to_dict()
        config_dict["max_turns"] = self.definition.max_turns
        if self.definition.allowed_tools:
            config_dict["allowed_tools"] = self.definition.allowed_tools

        subagent_config = Config(**config_dict)
        prompt = self._build_prompt(params.goal)

        tool_calls: list[str] = []
        final_response: str | None = None
        error: str | None = None
        terminate_response = "goal"
        stream_ui = bool(parent_tool_call_id.strip())
        chars_from_text_deltas = 0

        try:
            async with Agent(subagent_config) as agent:
                deadline = time.monotonic() + self.definition.timeout_seconds

                async for event in agent.run(prompt):
                    if time.monotonic() > deadline:
                        terminate_response = "timeout"
                        final_response = "Sub-agent timed out"
                        break

                    if stream_ui and event.type == AgentEventType.AGENT_STEP:
                        if event.data.get("phase") == "llm":
                            chars_from_text_deltas = 0

                    if stream_ui and event.type == AgentEventType.TEXT_COMPLETE:
                        content = event.data.get("content")
                        if isinstance(content, str) and content:
                            if (
                                chars_from_text_deltas == 0
                                and len(content) >= _SUBAGENT_SYNTH_MIN_FULL
                            ):
                                for i in range(0, len(content), _SUBAGENT_SYNTH_TEXT_CHUNK):
                                    piece = content[i : i + _SUBAGENT_SYNTH_TEXT_CHUNK]
                                    yield (
                                        "forward",
                                        _wrap_subagent_stream_event(
                                            AgentEvent.text_delta(piece),
                                            definition_name=self.definition.name,
                                            parent_tool_call_id=parent_tool_call_id,
                                        ),
                                    )
                                    await asyncio.sleep(0)
                            elif len(content) > chars_from_text_deltas + _SUBAGENT_SYNTH_TAIL_GAP:
                                tail = content[chars_from_text_deltas:]
                                for i in range(0, len(tail), _SUBAGENT_SYNTH_TEXT_CHUNK):
                                    piece = tail[i : i + _SUBAGENT_SYNTH_TEXT_CHUNK]
                                    yield (
                                        "forward",
                                        _wrap_subagent_stream_event(
                                            AgentEvent.text_delta(piece),
                                            definition_name=self.definition.name,
                                            parent_tool_call_id=parent_tool_call_id,
                                        ),
                                    )
                                    await asyncio.sleep(0)
                        chars_from_text_deltas = 0
                        yield (
                            "forward",
                            _wrap_subagent_stream_event(
                                event,
                                definition_name=self.definition.name,
                                parent_tool_call_id=parent_tool_call_id,
                            ),
                        )
                        await asyncio.sleep(0)
                    elif stream_ui and event.type in _SUBAGENT_STREAM_EVENT_TYPES:
                        if event.type == AgentEventType.TEXT_DELTA:
                            frag = event.data.get("content")
                            if isinstance(frag, str):
                                chars_from_text_deltas += len(frag)
                        yield (
                            "forward",
                            _wrap_subagent_stream_event(
                                event,
                                definition_name=self.definition.name,
                                parent_tool_call_id=parent_tool_call_id,
                            ),
                        )
                        if event.type in (
                            AgentEventType.PLANNING_DELTA,
                            AgentEventType.REASONING_DELTA,
                            AgentEventType.TEXT_DELTA,
                        ):
                            await asyncio.sleep(0)

                    if event.type == AgentEventType.TOOL_CALL_START:
                        n = event.data.get("name")
                        if isinstance(n, str):
                            tool_calls.append(n)
                    elif event.type == AgentEventType.TEXT_COMPLETE:
                        final_response = event.data.get("content")
                    elif event.type == AgentEventType.AGENT_END:
                        if final_response is None:
                            final_response = event.data.get("response")
                    elif event.type == AgentEventType.AGENT_ERROR:
                        terminate_response = "error"
                        error = str(event.data.get("error", "Unknown"))
                        final_response = f"Sub-agent error: {error}"
                        break
        except Exception as e:
            terminate_response = "error"
            error = str(e)
            final_response = f"Sub-agent failed: {e}"

        result = f"""Sub-agent '{self.definition.name}' completed. 
        Termination: {terminate_response}
        Tools called: {', '.join(tool_calls) if tool_calls else 'None'}

        Result:
        {final_response or 'No response'}
        """

        if error:
            yield ("final", ToolResult.error_result(result))
        else:
            yield ("final", ToolResult.success_result(result))

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        final: ToolResult | None = None
        async for kind, payload in self.stream_execute(
            invocation, parent_tool_call_id=""
        ):
            if kind == "final":
                final = payload
        assert final is not None
        return final


CODEBASE_INVESTIGATOR = SubagentDefinition(
    name="codebase_investigator",
    description="Investigates the codebase to answer questions about code structure, patterns, and implementations",
    goal_prompt="""You are a codebase investigation specialist.
Your job is to explore and understand code to answer questions.
Use read_file, grep, glob, and list_dir to investigate.
Do NOT modify any files.""",
    allowed_tools=["read_file", "grep", "glob", "list_dir"],
)


S3_NORMALIZED_LOGS_SUBAGENT = SubagentDefinition(
    name="s3_normalized_logs",
    description=(
        "Sous-agent S3 : récupère des logs normalisés CLAIR OBSCUR depuis le bucket (outil fetch_normalized_logs_from_s3)."
    ),
    goal_prompt="""Tu es le sous-agent **S3 / ingestion**.
Tu n’utilises que l’outil `fetch_normalized_logs_from_s3`.
- Pour « les N derniers logs » ou équivalent : skip=0, limit=N (l’ordre est déjà du plus récent au plus ancien).
- Après l’appel, inclus dans ta réponse finale le **JSON brut** renvoyé par l’outil (pour que l’agent parent le passe à l’extracteur SQL).

Ne pas inventer de lignes : une seule invocation d’outil suffit en général.""",
    allowed_tools=["fetch_normalized_logs_from_s3"],
    max_turns=6,
    timeout_seconds=180,
)

LOGS_TABLE_SQL_SUBAGENT = SubagentDefinition(
    name="logs_table_sql",
    description=(
        "Sous-agent extraction : demande naturelle → SQL DuckDB sur la table logs, puis exécution "
        "(build_sql_for_logs_table puis run_sql_on_logs_table)."
    ),
    goal_prompt=f"""Tu es le sous-agent **extraction SQL** (DuckDB, table `logs`).

{LOGS_TABLE_SCHEMA_DOC}

Étapes :
1. Appelle `build_sql_for_logs_table` avec extraction_request = la demande utilisateur (texte fourni dans LA TÂCHE).
2. Récupère le SELECT (champ sql dans les métadonnées ou bloc ```sql```), puis appelle `run_sql_on_logs_table` avec :
   - sql = ce SELECT,
   - logs_json = **chaîne JSON** représentant uniquement le **tableau** d’objets logs (souvent issu de la clé `events` du fetch S3), fourni dans LA TÂCHE.
3. Réponds en français : résumé court + résultat (tableau ou JSON des lignes).

Si logs_json manque dans la tâche, réponds explicitement ce qu’il manque sans inventer de données.""",
    allowed_tools=["build_sql_for_logs_table", "run_sql_on_logs_table"],
    max_turns=14,
    timeout_seconds=360,
)


def get_logs_pipeline_subagent_definitions() -> list[SubagentDefinition]:
    """Sous-agents pipeline logs S3 → SQL (orchestration multi-étapes)."""
    return [S3_NORMALIZED_LOGS_SUBAGENT, LOGS_TABLE_SQL_SUBAGENT]


CODE_REVIEWER = SubagentDefinition(
    name="code_reviewer",
    description="Reviews code changes and provides feedback on quality, bugs, and improvements",
    goal_prompt="""You are a code review specialist.
Your job is to review code and provide constructive feedback.
Look for bugs, code smells, security issues, and improvement opportunities.
Use read_file, list_dir and grep to examine the code.
Do NOT modify any files.""",
    allowed_tools=["read_file", "grep", "list_dir"],
    max_turns=10,
    timeout_seconds=300,
)


def get_default_subagent_definitions() -> list[SubagentDefinition]:
    """Sub-agents désactivés pour le dashboard CLAIR OBSCUR ; définitions ci-dessus = modèle.

    Pour réactiver : renvoyer la liste commentée et ré-enregistrer dans
    ``create_default_registry``.
    """
    # return [
    #     CODEBASE_INVESTIGATOR,
    #     CODE_REVIEWER,
    # ]
    return []

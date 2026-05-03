"""Outils : demande en langage naturel → SQL DuckDB, puis exécution sur un jeu de logs en mémoire."""

from __future__ import annotations

import json
import os
import re
import tempfile
from typing import Any

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from backend.agentic.tools.base import Tool, ToolInvocation, ToolKind, ToolResult

# Schéma logique aligné sur ``backend.log.normalization.types.NormalizedEvent``
LOGS_TABLE_SCHEMA_DOC = """
Table SQL obligatoire : `logs` (une ligne = un événement normalisé).

Colonnes typiques (types DuckDB déduits du JSON ; certaines valeurs peuvent être NULL) :
- timestamp (VARCHAR, ISO8601 si présent)
- log_source : 'application' | 'authentication' | 'network' | 'system'
- source_ip, destination_ip, hostname, username, session_id, protocol, action, severity, message, uri, http_method, status_code, failure_reason, auth_method, status (success/failure), etc.
- raw_ref : STRUCT ou VARCHAR selon inférence ; peut contenir raw_id, s3_key, line

Les événements renvoyés par fetch_normalized_logs_from_s3 sont déjà dans ce format à plat (JSON).

Règles :
- Produire **un seul** SELECT lecture seule sur `logs`.
- Pour « les N derniers » : ORDER BY timestamp DESC NULLS LAST LIMIT N (adapter si besoin).
- Pas de jointures externes ; pas de fonctions d’écriture.
"""


def _extract_sql_from_llm(text: str) -> str:
    t = (text or "").strip()
    if "```" in t:
        parts = t.split("```")
        for i in range(1, len(parts), 2):
            block = parts[i].lstrip()
            low = block.lower()
            if low.startswith("sql"):
                block = block[3:].lstrip()
            return block.strip().rstrip(";").strip()
    return t.rstrip(";").strip()


_FORBIDDEN_SQL = re.compile(
    r"\b(attach|detach|pragma|copy|export|install|load|secret|checkpoint|vacuum|alter|create|drop|insert|update|delete|truncate|grant|revoke)\b",
    re.IGNORECASE,
)


def _validate_select_only(sql: str) -> tuple[str, list[str]]:
    errors: list[str] = []
    s = sql.strip().rstrip(";").strip()
    if not s.lower().startswith("select"):
        errors.append("La requête doit commencer par SELECT.")
    if ";" in s:
        errors.append("Une seule instruction SQL, sans point-virgule interne.")
    if _FORBIDDEN_SQL.search(s):
        errors.append("Mots-clés interdits (écriture / administration).")
    if not errors:
        return s, []
    return s, errors


async def _chat_plain_text(
    *,
    model: str,
    api_key: str | None,
    base_url: str | None,
    system: str,
    user: str,
    temperature: float = 0.1,
) -> str:
    if not api_key:
        return ""
    client = AsyncOpenAI(
        api_key=api_key,
        base_url=base_url or "https://openrouter.ai/api/v1",
    )
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            stream=False,
        )
        choice = resp.choices[0].message
        return (choice.content or "").strip()
    finally:
        await client.close()


def _run_duckdb_select(sql: str, rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str | None]:
    try:
        import duckdb
    except ImportError:
        return [], "Paquet manquant : installez `duckdb` (voir requirements API)."

    validated, errs = _validate_select_only(sql)
    if errs:
        return [], "; ".join(errs)

    con = duckdb.connect(database=":memory:")
    path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".json",
            delete=False,
        ) as tmp:
            json.dump(rows, tmp, ensure_ascii=False)
            path = tmp.name
        con.execute(
            "CREATE TABLE logs AS SELECT * FROM read_json_auto(?);",
            [path],
        )
        cur = con.execute(validated)
        colnames = [d[0] for d in cur.description]
        out_rows = []
        for tup in cur.fetchall():
            out_rows.append({colnames[i]: tup[i] for i in range(len(colnames))})
        return out_rows, None
    except Exception as e:
        return [], f"DuckDB : {e}"
    finally:
        con.close()
        if path:
            try:
                os.unlink(path)
            except OSError:
                pass


class BuildSqlParams(BaseModel):
    extraction_request: str = Field(
        ...,
        description="Demande utilisateur en langage naturel (ex. « les 10 derniers logs »).",
    )
    extra_context: str | None = Field(
        default=None,
        description="Optionnel : précisions (colonnes à inclure, filtres).",
    )


class RunSqlParams(BaseModel):
    sql: str = Field(..., description="Requête SELECT sur la table `logs` (issue de build_sql_for_logs_table).")
    logs_json: str = Field(
        ...,
        description='Tableau JSON d’objets (liste), même format que la clé « events » renvoyée par fetch_normalized_logs_from_s3.',
    )
    max_result_rows: int = Field(
        200,
        ge=1,
        le=500,
        description="Plafond de lignes renvoyées (sécurité / taille contexte).",
    )


MAX_LOGS_JSON_CHARS = 2_000_000


class BuildSqlForLogsTableTool(Tool):
    """LLM → une requête SELECT DuckDB."""

    name = "build_sql_for_logs_table"
    description = (
        "À partir d’une demande d’extraction en français (ou anglais), produit **une seule** requête SQL DuckDB "
        "de lecture sur la table `logs`. Ne pas exécuter la requête : utiliser run_sql_on_logs_table ensuite."
    )
    kind = ToolKind.NETWORK
    schema = BuildSqlParams

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        p = BuildSqlParams(**invocation.params)
        sys_prompt = (
            "Tu es un générateur SQL pour DuckDB. Réponds uniquement avec le SQL, sans commentaire. "
            + LOGS_TABLE_SCHEMA_DOC
        )
        user_prompt = f"Demande : {p.extraction_request}\n"
        if p.extra_context:
            user_prompt += f"Contexte : {p.extra_context}\n"

        raw = await _chat_plain_text(
            model=self.config.model_name,
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            system=sys_prompt,
            user=user_prompt,
            temperature=0.15,
        )
        if not raw:
            return ToolResult.error_result(
                "Impossible de générer le SQL (clé API ou réseau).",
            )
        sql = _extract_sql_from_llm(raw)
        _, errs = _validate_select_only(sql)
        if errs:
            return ToolResult.success_result(
                f"SQL proposé (à valider / corriger manuellement si besoin) :\n```sql\n{sql}\n```\n"
                f"Avertissement validation : {' ; '.join(errs)}",
                metadata={"sql": sql, "validation_warnings": errs},
            )
        return ToolResult.success_result(
            f"```sql\n{sql}\n```",
            metadata={"sql": sql},
        )


class RunSqlOnLogsTableTool(Tool):
    """Exécute un SELECT DuckDB sur les lignes fournies."""

    name = "run_sql_on_logs_table"
    description = (
        "Charge les lignes JSON en table `logs` en mémoire et exécute le SELECT fourni (DuckDB). "
        "Le paramètre logs_json doit être le tableau « events » (liste d’objets). "
        "**Attention** : pour des graphiques ou stats sur des événements déjà récupérés via "
        "`fetch_normalized_logs_from_s3`, préférer `visualization_from_prompt` avec `data_json` "
        "— évite de dupliquer un gros JSON dans les arguments d’outil (flux LLM très lent ou bloqué)."
    )
    kind = ToolKind.READ
    schema = RunSqlParams

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        p = RunSqlParams(**invocation.params)
        if len(p.logs_json) > MAX_LOGS_JSON_CHARS:
            return ToolResult.error_result(
                f"logs_json trop volumineux (max {MAX_LOGS_JSON_CHARS} caractères).",
            )
        try:
            parsed = json.loads(p.logs_json)
        except json.JSONDecodeError as e:
            return ToolResult.error_result(f"JSON invalide : {e}")

        if not isinstance(parsed, list):
            return ToolResult.error_result("logs_json doit être un tableau JSON [...].")

        rows = [r for r in parsed if isinstance(r, dict)]
        if not rows:
            return ToolResult.error_result("Aucune ligne objet dans logs_json.")

        out_rows, err = _run_duckdb_select(p.sql, rows)
        if err:
            return ToolResult.error_result(err, metadata={"sql": p.sql})

        truncated = False
        if len(out_rows) > p.max_result_rows:
            out_rows = out_rows[: p.max_result_rows]
            truncated = True

        payload = {
            "row_count": len(out_rows),
            "truncated": truncated,
            "rows": out_rows,
        }
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        max_out = 400_000
        if len(text) > max_out:
            text = text[:max_out] + "\n… [sortie tronquée]\n"
            truncated = True

        return ToolResult.success_result(
            text,
            truncated=truncated,
            metadata={"row_count": len(out_rows)},
        )

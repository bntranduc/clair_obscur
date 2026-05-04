"""Visualisations KPI + graphiques ASCII dans le terminal (plotext si dispo, sinon repli unicode)."""

from __future__ import annotations

import json
import math
import shutil
from collections import Counter
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from backend.agentic.tools.base import Tool, ToolInvocation, ToolKind, ToolResult
from backend.agentic.tools.logs_table_sql import _chat_plain_text
from backend.agentic.tools.subagents import SubagentDefinition


class KPIItem(BaseModel):
    label: str = Field(..., description="Libellé court du KPI")
    value: str | float | int = Field(..., description="Valeur affichée")
    trend: Literal["up", "down", "flat"] | None = None


class ChartSpec(BaseModel):
    kind: Literal["none", "bar", "line", "histogram", "pie"] = "none"
    category_key: str | None = Field(
        default=None,
        description="Colonne catégorielle (bar / histogramme sur bins textuels)",
    )
    value_key: str | None = Field(
        default=None,
        description="Colonne numérique (somme par catégorie, axe Y ligne/histogramme)",
    )
    x_key: str | None = Field(default=None, description="Axe X pour ligne temporelle ou ordonnée")
    limit: int = Field(12, ge=2, le=40, description="Nombre max de catégories / points")


class VizPlan(BaseModel):
    title: str = "Vue analytique"
    subtitle: str | None = None
    kpis: list[KPIItem] = Field(default_factory=list)
    chart: ChartSpec = Field(default_factory=ChartSpec)
    markdown_notes: str | None = None


def _extract_json_object(text: str) -> dict[str, Any] | None:
    """Premier objet JSON équilibré trouvé dans ``text``."""
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def _preview_columns(rows: list[dict[str, Any]], max_rows: int = 8) -> str:
    if not rows:
        return "(aucune ligne)"
    keys: list[str] = []
    for r in rows[:max_rows]:
        for k in r:
            if k not in keys:
                keys.append(k)
    lines = [f"Colonnes observées : {', '.join(keys[:40])}"]
    lines.append(f"Extrait ({min(len(rows), max_rows)} lignes) :")
    lines.append(json.dumps(rows[:max_rows], ensure_ascii=False, indent=2)[:6000])
    return "\n".join(lines)


def _safe_float(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return None
        return float(v)
    if isinstance(v, str):
        s = v.strip().replace(",", ".")
        if not s:
            return None
        try:
            return float(s)
        except ValueError:
            return None
    return None


def _aggregate_bar_counts(rows: list[dict[str, Any]], key: str, limit: int) -> tuple[list[str], list[float]]:
    c = Counter()
    for r in rows:
        raw = r.get(key)
        lab = "" if raw is None else str(raw).strip() or "∅"
        c[lab] += 1
    top = c.most_common(limit)
    return [t[0] for t in top], [float(t[1]) for t in top]


def _aggregate_bar_sum(rows: list[dict[str, Any]], cat_key: str, val_key: str, limit: int) -> tuple[list[str], list[float]]:
    sums: dict[str, float] = {}
    for r in rows:
        fv = _safe_float(r.get(val_key))
        if fv is None:
            continue
        raw = r.get(cat_key)
        lab = "" if raw is None else str(raw).strip() or "∅"
        sums[lab] = sums.get(lab, 0.0) + fv
    ordered = sorted(sums.items(), key=lambda x: abs(x[1]), reverse=True)[:limit]
    return [o[0] for o in ordered], [o[1] for o in ordered]


def _sample_keys(rows: list[dict[str, Any]], max_scan: int = 400) -> set[str]:
    keys: set[str] = set()
    for i, r in enumerate(rows):
        if i >= max_scan:
            break
        keys.update(r.keys())
    return keys


def _wants_pie_chart(request_lower: str) -> bool:
    needles = (
        "pie chart",
        "pie-chart",
        "graphique en secteurs",
        "diagramme circulaire",
        "diagramme en camembert",
        "camembert",
        "tarte",
        "donut",
        "secteurs",
        "répartition circulaire",
        "repartition circulaire",
    )
    return any(n in request_lower for n in needles)


def _wants_bar_chart(request_lower: str) -> bool:
    needles = (
        "barplot",
        "bar plot",
        "bar chart",
        "diagramme en barre",
        "diagramme à barres",
        "diagramme a barres",
        "graphique en barres",
        "graph en barres",
        "histogramme",  # souvent demandé à tort pour des effectifs — on traitera en barres si catégoriel
        "répartition",
        "repartition",
        "nombre de logs par",
        "combien de logs par",
        "effectifs par",
        "compte par",
        "count par",
    )
    return any(n in request_lower for n in needles)


def _infer_category_key_for_effectifs(request: str, keys: set[str]) -> str | None:
    """Colonne catégorielle pour effectifs (bar / pie rapides)."""
    req = request.lower()
    category_key: str | None = None
    if any(
        p in req
        for p in (
            "type de log",
            "types de log",
            "type des logs",
            "types des logs",
            "log source",
            "log_source",
        )
    ):
        if "log_source" in keys:
            category_key = "log_source"
    elif "sévérité" in req or "severity" in req:
        if "severity" in keys:
            category_key = "severity"
    elif "protocole" in req or "protocol" in req:
        if "protocol" in keys:
            category_key = "protocol"
    elif "action" in req and "interaction" not in req:
        if "action" in keys:
            category_key = "action"
    elif "hostname" in req or "hôte" in req or "host" in req:
        if "hostname" in keys:
            category_key = "hostname"

    if category_key is None and "log_source" in keys and (
        "par type" in req or "type de" in req or "logs par" in req
    ):
        category_key = "log_source"
    return category_key


def _infer_direct_pie_plan(request: str, rows: list[dict[str, Any]]) -> VizPlan | None:
    """Camembert / pie chart des effectifs par catégorie (sans LLM)."""
    if not rows or not _wants_pie_chart(request.lower()):
        return None
    keys = _sample_keys(rows)
    category_key = _infer_category_key_for_effectifs(request, keys)
    if category_key is None:
        return None
    limit = 25
    labs, vals = _aggregate_bar_counts(rows, category_key, limit)
    if not labs:
        return None

    total = len(rows)
    distinct = len(labs)
    title = (
        "Répartition par type (log_source)"
        if category_key == "log_source"
        else f"Répartition par {category_key}"
    )
    kpis = [
        KPIItem(label="Logs dans l’échantillon", value=total),
        KPIItem(label="Secteurs affichés", value=distinct),
        KPIItem(label="Part dominante", value=f"{labs[0]} ({int(vals[0])})"),
    ]
    chart = ChartSpec(kind="pie", category_key=category_key, value_key=None, limit=limit)
    notes = (
        f"Diagramme circulaire : surface ∝ **nombre de lignes** par `{category_key}`. "
        "Demande détectée comme pie chart d’effectifs (chemin rapide, sans LLM)."
    )
    return VizPlan(
        title=title,
        subtitle="Vue agrégée — terminal",
        kpis=kpis,
        chart=chart,
        markdown_notes=notes,
    )


def _infer_direct_bar_plan(request: str, rows: list[dict[str, Any]]) -> VizPlan | None:
    """Cas fréquent SOC : barplot « nombre de logs par type » sans passer par le LLM."""
    if not rows or not _wants_bar_chart(request.lower()):
        return None

    keys = _sample_keys(rows)
    category_key = _infer_category_key_for_effectifs(request, keys)

    if category_key is None:
        return None

    limit = 25
    labs, vals = _aggregate_bar_counts(rows, category_key, limit)
    if not labs:
        return None

    total = len(rows)
    distinct = len(labs)
    title = "Nombre de logs par type (log_source)" if category_key == "log_source" else f"Nombre de logs par {category_key}"
    kpis = [
        KPIItem(label="Logs dans l’échantillon", value=total),
        KPIItem(label="Catégories affichées", value=distinct),
        KPIItem(label="Catégorie dominante", value=f"{labs[0]} ({int(vals[0])})"),
    ]
    chart = ChartSpec(kind="bar", category_key=category_key, value_key=None, limit=limit)
    notes = (
        f"Diagramme en barres : hauteur = **nombre de lignes** par valeur de `{category_key}`. "
        "Demande détectée comme barplot d’effectifs (chemin rapide, sans LLM)."
    )
    return VizPlan(
        title=title,
        subtitle="Vue agrégée — terminal",
        kpis=kpis,
        chart=chart,
        markdown_notes=notes,
    )


def _ascii_pie_table(labels: list[str], values: list[float], title: str) -> str:
    """Répartition en pourcentages (repli terminal sans plotext.pie)."""
    if not values:
        return "(pas de données pour le camembert)"
    total = sum(values) or 1.0
    lines = [f"## {title}", ""]
    for lb, v in zip(labels, values):
        pct = 100.0 * float(v) / total
        lines.append(f"- **{lb}** — {pct:.1f}% ({v:g})")
    return "\n".join(lines)


def _configure_plotext_style(plt: Any) -> None:
    tw, th = shutil.get_terminal_size(fallback=(120, 30))
    w = max(88, min(tw - 2, 148))
    h = max(22, min(max(th - 3, 22), 36))
    plt.plotsize(w, h)
    for fn_name, args in (
        ("theme", ("dark",)),
        ("canvas_color", ("black",)),
        ("ticks_color", ("bright_white",)),
        ("axes_color", ("dark_gray",)),
    ):
        fn = getattr(plt, fn_name, None)
        if callable(fn):
            try:
                fn(*args)
            except Exception:
                pass


_BAR_COLORS = (
    "cyan",
    "magenta",
    "yellow",
    "green",
    "blue",
    "red",
    "orange",
)


def _ascii_bars(labels: list[str], values: list[float], title: str, width: int = 52) -> str:
    if not values:
        return "(pas de données pour le graphique)"
    mx = max(abs(v) for v in values if not math.isnan(v)) or 1.0
    lines = [f"## {title}", ""]
    label_w = min(22, max(len(str(l)) for l in labels) if labels else 10)
    for lb, v in zip(labels, values):
        bar_len = max(0, int(width * abs(v) / mx))
        bar = "█" * bar_len
        lines.append(f"{str(lb)[:label_w]:<{label_w}} │ {bar} {v:g}")
    return "\n".join(lines)


def _render_chart_plotext(
    plan: VizPlan,
    rows: list[dict[str, Any]],
) -> str:
    try:
        import plotext as plt  # type: ignore[import-untyped]
    except ImportError:
        return ""

    ch = plan.chart
    title = plan.title
    if ch.kind == "none":
        return ""

    plt.clear_data()
    plt.clear_figure()
    _configure_plotext_style(plt)

    try:
        if ch.kind == "bar":
            if not ch.category_key:
                return ""
            if ch.value_key:
                labs, vals = _aggregate_bar_sum(rows, ch.category_key, ch.value_key, ch.limit)
            else:
                labs, vals = _aggregate_bar_counts(rows, ch.category_key, ch.limit)
            if not labs:
                return "(bar vide)"
            colors = [_BAR_COLORS[i % len(_BAR_COLORS)] for i in range(len(labs))]
            try:
                plt.bar(labs, vals, color=colors)
            except TypeError:
                plt.bar(labs, vals, color="cyan")
            plt.title(title)
            plt.xlabel(ch.category_key)
            plt.ylabel(ch.value_key or "nombre de logs")
            try:
                plt.grid(True)
            except Exception:
                pass
            return plt.build()

        if ch.kind == "pie":
            if not ch.category_key:
                return ""
            labs, vals = _aggregate_bar_counts(rows, ch.category_key, ch.limit)
            if not labs:
                return "(pie vide)"
            pie_fn = getattr(plt, "pie", None)
            if not callable(pie_fn):
                return ""
            try:
                pie_fn(vals, labels=labs)
            except TypeError:
                try:
                    pie_fn(labels, vals)
                except Exception:
                    return ""
            except Exception:
                return ""
            plt.title(title)
            return plt.build()

        if ch.kind == "histogram":
            vk = ch.value_key or ch.category_key
            if not vk:
                return ""
            nums = []
            for r in rows:
                fv = _safe_float(r.get(vk))
                if fv is not None:
                    nums.append(fv)
            if len(nums) < 2:
                return "(histogramme : pas assez de valeurs numériques)"
            bins = min(16, max(6, int(math.sqrt(len(nums)))))
            try:
                plt.hist(nums, bins=bins, color="cyan")
            except Exception:
                plt.hist(nums, bins=bins)
            plt.title(title)
            plt.xlabel(vk)
            try:
                plt.grid(True)
            except Exception:
                pass
            return plt.build()

        if ch.kind == "line":
            yk = ch.value_key
            if not yk:
                return ""
            y_plot: list[float] = []
            for r in rows:
                fv = _safe_float(r.get(yk))
                if fv is None:
                    continue
                y_plot.append(fv)
                if len(y_plot) >= ch.limit * 4:
                    break
            if len(y_plot) < 2:
                return "(ligne : pas assez de points)"
            x_plot = list(range(1, len(y_plot) + 1))
            try:
                plt.plot(x_plot, y_plot, color="cyan")
            except Exception:
                plt.plot(x_plot, y_plot)
            plt.title(title)
            plt.xlabel(ch.x_key or "index")
            plt.ylabel(yk)
            try:
                plt.grid(True)
            except Exception:
                pass
            return plt.build()
    except Exception as e:
        return f"(plotext: {e})"

    return ""


def _render_chart_fallback(plan: VizPlan, rows: list[dict[str, Any]]) -> str:
    ch = plan.chart
    if ch.kind == "none":
        return ""
    if ch.kind == "bar":
        if not ch.category_key:
            return ""
        if ch.value_key:
            labs, vals = _aggregate_bar_sum(rows, ch.category_key, ch.value_key, ch.limit)
        else:
            labs, vals = _aggregate_bar_counts(rows, ch.category_key, ch.limit)
        return _ascii_bars(labs, vals, plan.title)
    if ch.kind == "pie":
        if not ch.category_key:
            return ""
        labs, vals = _aggregate_bar_counts(rows, ch.category_key, ch.limit)
        return _ascii_pie_table(labs, vals, plan.title)
    if ch.kind == "histogram":
        vk = ch.value_key or ch.category_key
        if not vk:
            return ""
        nums = [fv for r in rows if (fv := _safe_float(r.get(vk))) is not None]
        if len(nums) < 2:
            return "(histogramme indisponible — données insuffisantes)"
        bins = min(12, max(4, int(math.sqrt(len(nums)))))
        mn, mx = min(nums), max(nums)
        if mx == mn:
            return _ascii_bars(["valeur"], [float(len(nums))], f"{plan.title} (histogramme)")
        step = (mx - mn) / bins
        counts = [0] * bins
        for v in nums:
            bi = min(bins - 1, int((v - mn) / step) if step > 0 else 0)
            counts[bi] += 1
        labels = [f"{mn + i * step:.3g}" for i in range(bins)]
        return _ascii_bars(labels, [float(c) for c in counts], plan.title)
    if ch.kind == "line":
        yk = ch.value_key
        if not yk:
            return ""
        ys = [fv for r in rows if (fv := _safe_float(r.get(yk))) is not None][: ch.limit * 4]
        if len(ys) < 2:
            return "(ligne indisponible)"
        return _ascii_bars([str(i + 1) for i in range(len(ys))], ys, plan.title)
    return ""


_NUMERIC_SERIES_CANDIDATES: tuple[str, ...] = (
    "response_time_ms",
    "duration_ms",
    "bytes_sent",
    "bytes_received",
    "packets",
    "response_size",
    "status_code",
)


def _infer_primary_numeric_series_key(rows: list[dict[str, Any]]) -> str | None:
    """Colonne numérique la plus renseignée (pour line/histogram si le LLM oublie value_key)."""
    best_k: str | None = None
    best_n = 0
    for k in _NUMERIC_SERIES_CANDIDATES:
        n = sum(1 for r in rows if _safe_float(r.get(k)) is not None)
        if n > best_n:
            best_n = n
            best_k = k
    return best_k if best_n > 0 else None


def _build_web_chart_payload(plan: VizPlan, rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Données pour un graphique Recharts dans le dashboard (Assistant IA)."""
    ch = plan.chart
    if ch.kind == "none" or not rows:
        return None

    kpis_web = [{"label": k.label, "value": str(k.value)} for k in plan.kpis[:16]]
    title = plan.title
    subtitle = plan.subtitle

    if ch.kind == "bar":
        if not ch.category_key:
            return None
        if ch.value_key:
            labs, vals = _aggregate_bar_sum(rows, ch.category_key, ch.value_key, ch.limit)
            y_label = f"Σ {ch.value_key}"
        else:
            labs, vals = _aggregate_bar_counts(rows, ch.category_key, ch.limit)
            y_label = "Nombre"
        if not labs:
            return None
        data = [{"name": str(lab)[:120], "value": float(val)} for lab, val in zip(labs, vals)]
        return {
            "kind": "bar",
            "title": title,
            "subtitle": subtitle,
            "xLabel": ch.category_key,
            "yLabel": y_label,
            "data": data,
            "kpis": kpis_web,
        }

    if ch.kind == "pie":
        if not ch.category_key:
            return None
        if ch.value_key:
            labs, vals = _aggregate_bar_sum(rows, ch.category_key, ch.value_key, ch.limit)
            y_label = f"Σ {ch.value_key}"
        else:
            labs, vals = _aggregate_bar_counts(rows, ch.category_key, ch.limit)
            y_label = "Effectif"
        if not labs:
            return None
        data = [{"name": str(lab)[:120], "value": float(val)} for lab, val in zip(labs, vals)]
        return {
            "kind": "pie",
            "title": title,
            "subtitle": subtitle,
            "xLabel": ch.category_key,
            "yLabel": y_label,
            "data": data,
            "kpis": kpis_web,
        }

    if ch.kind == "line":
        yk = (ch.value_key or "").strip() or _infer_primary_numeric_series_key(rows)
        if not yk:
            return None
        cap = min(len(rows), max(ch.limit * 4, 40), 400)
        data: list[dict[str, Any]] = []
        for i, r in enumerate(rows[:cap]):
            fv = _safe_float(r.get(yk))
            data.append({"name": str(i + 1), "value": fv})
        if not any(d["value"] is not None for d in data):
            return None
        return {
            "kind": "line",
            "title": title,
            "subtitle": subtitle,
            "xLabel": ch.x_key or "Index ligne (1 = premier événement)",
            "yLabel": yk,
            "data": data,
            "kpis": kpis_web,
        }

    if ch.kind == "histogram":
        vk = (ch.value_key or ch.category_key or "").strip() or _infer_primary_numeric_series_key(rows)
        if not vk:
            return None
        nums = [fv for r in rows if (fv := _safe_float(r.get(vk))) is not None]
        if len(nums) < 2:
            return None
        bins = min(16, max(4, int(math.sqrt(len(nums)))))
        mn, mx = min(nums), max(nums)
        if mx == mn:
            data = [{"name": str(mn), "value": float(len(nums))}]
        else:
            step = (mx - mn) / bins
            counts = [0] * bins
            for v in nums:
                bi = min(bins - 1, int((v - mn) / step) if step > 0 else 0)
                counts[bi] += 1
            labels = [f"{mn + i * step:.4g}" for i in range(bins)]
            data = [{"name": lab[:120], "value": float(c)} for lab, c in zip(labels, counts)]
        return {
            "kind": "histogram",
            "title": title,
            "subtitle": subtitle,
            "xLabel": vk,
            "yLabel": "Effectif",
            "data": data,
            "kpis": kpis_web,
        }

    return None


def _kpis_markdown(kpis: list[KPIItem]) -> str:
    if not kpis:
        return ""
    lines = ["### Indicateurs", "", "| Indicateur | Valeur |", "|------------|--------|"]
    for k in kpis:
        tv = k.trend or ""
        trend_cell = f" ({tv})" if tv else ""
        val = k.value if isinstance(k.value, str) else str(k.value)
        esc = str(val).replace("|", "\\|")
        lines.append(f"| {k.label.replace('|', '/')} | {esc}{trend_cell} |")
    lines.append("")
    return "\n".join(lines)


class VisualizationParams(BaseModel):
    visualization_request: str = Field(
        ...,
        description=(
            "Intention en langage naturel. Ex. : « affiche un barplot pour le type de logs, nombre de logs » "
            "→ nécessite souvent des lignes dans data_json (ex. tableau `events` après fetch S3)."
        ),
    )
    data_json: str | None = Field(
        default=None,
        description=(
            "JSON : tableau `[{{...}}]` ou objet avec clé `events`. Sans données, le graphique sera vide ou générique."
        ),
    )


_SYS_VIZ = """Tu es un concepteur de tableaux de bord pour analystes SOC (logs normalisés CLAIR OBSCUR).
Réponds avec UN SEUL objet JSON (sans markdown) au schéma :
{
  "title": "string",
  "subtitle": "string ou null",
  "kpis": [ {"label": "...", "value": "nombre ou texte", "trend": "up"|"down"|"flat"|null} ],
  "chart": {
    "kind": "none"|"bar"|"line"|"histogram"|"pie",
    "category_key": "nom de colonne pour barres / camembert (ex. severity, log_source, action)",
    "value_key": "nom de colonne numérique ou null pour compter les lignes",
    "x_key": "pour line si colonne temps/catégorie ordonnée, sinon null",
    "limit": nombre entre 2 et 25 (max catégories / points affichés)
  },
  "markdown_notes": "string ou null — brève interprétation en français"
}

Règles :
- Colonne « type de log » / « type de logs » dans une demande française = **`log_source`** (valeurs application | authentication | network | system).
- « Barplot / diagramme en barres du nombre de logs par type » ⇒ chart.kind = **bar**, category_key = **log_source**, value_key = **null** (compter les lignes).
- « Pie chart / camembert / diagramme circulaire » des effectifs par catégorie ⇒ chart.kind = **pie**, category_key = le champ, value_key = **null** (ou somme si value_key numérique).
- Si aucune donnée tabulaire n’est fournie : kpis génériques et chart.kind = "none" ; invite à charger des événements.
- Répartition par champ catégoriel : **bar** ou **pie** (camembert), category_key = ce champ, value_key null.
- Somme par catégorie : bar, category_key + value_key numérique.
- Distribution d’une métrique continue : histogram sur value_key numérique.
- Titres et labels en français si la demande est en français.

Exemple (demande : « barplot nombre de logs par type ») :
{"title":"Logs par type","subtitle":null,"kpis":[{"label":"Total","value":0,"trend":null}],"chart":{"kind":"bar","category_key":"log_source","value_key":null,"x_key":null,"limit":12},"markdown_notes":"Effectifs par log_source."}
"""


class VisualizationFromPromptTool(Tool):
    """Construit une vue markdown + graphique ASCII depuis une intention et des données."""

    name = "visualization_from_prompt"
    description = (
        "Crée KPIs (markdown) + graphique terminal coloré (plotext : barres/ligne/histogramme/camembert). "
        "Pour « barplot du nombre de logs par type », charge d’abord les événements puis passe leur JSON dans "
        "`data_json` et une phrase du type « barplot par type de logs, nombre de logs » — colonne type = `log_source`."
    )
    kind = ToolKind.NETWORK
    schema = VisualizationParams

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        p = VisualizationParams(**invocation.params)
        rows: list[dict[str, Any]] = []
        if p.data_json and p.data_json.strip():
            try:
                parsed = json.loads(p.data_json)
                if isinstance(parsed, list):
                    rows = [x for x in parsed if isinstance(x, dict)]
                elif isinstance(parsed, dict) and isinstance(parsed.get("events"), list):
                    rows = [x for x in parsed["events"] if isinstance(x, dict)]
            except json.JSONDecodeError as e:
                return ToolResult.error_result(f"data_json invalide : {e}")

        plan = _infer_direct_pie_plan(p.visualization_request, rows)
        if plan is None:
            plan = _infer_direct_bar_plan(p.visualization_request, rows)
        direct_bar = plan is not None
        if plan is None:
            preview = _preview_columns(rows)
            user_prompt = f"""Demande utilisateur :
{p.visualization_request}

Données tabulaires : {len(rows)} ligne(s).

{preview}
"""

            raw = await _chat_plain_text(
                model=self.config.model_name,
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                system=_SYS_VIZ,
                user=user_prompt,
                temperature=0.25,
            )
            if not raw:
                return ToolResult.error_result(
                    "Impossible de générer le plan de visualisation (clé API ou réseau).",
                )

            data = _extract_json_object(raw)
            if data is None:
                return ToolResult.success_result(
                    f"Réponse modèle non JSON ; brut :\n\n{raw[:8000]}",
                    metadata={"parse_error": True},
                )

            try:
                plan = VizPlan.model_validate(data)
            except ValidationError as e:
                return ToolResult.error_result(f"JSON de visualisation invalide : {e}")

        parts: list[str] = []
        parts.append(f"# {plan.title}")
        if plan.subtitle:
            parts.append(f"\n*{plan.subtitle}*\n")

        parts.append(_kpis_markdown(plan.kpis))

        if plan.markdown_notes:
            parts.append("### Notes")
            parts.append(plan.markdown_notes)
            parts.append("")

        chart_block = _render_chart_plotext(plan, rows)
        if not chart_block.strip():
            chart_block = _render_chart_fallback(plan, rows)
        if chart_block.strip():
            parts.append("### Graphique")
            parts.append("")
            parts.append("```")
            parts.append(chart_block.strip())
            parts.append("```")

        out = "\n".join(parts).strip()
        meta: dict[str, Any] = {
            "viz_kind": plan.chart.kind,
            "row_count": len(rows),
            "direct_bar": direct_bar,
        }
        web_chart = _build_web_chart_payload(plan, rows)
        if web_chart:
            meta["chart"] = web_chart
        return ToolResult.success_result(out, metadata=meta)


VISUALIZATION_SPECIALIST_SUBAGENT = SubagentDefinition(
    name="visualization_specialist",
    description=(
        "Sous-agent visualisation : KPIs + graphiques ASCII dans le chat à partir d’une demande et "
        "optionnellement de données JSON (tableau ou objet avec clé events)."
    ),
    goal_prompt="""Tu es le sous-agent **visualisation** pour analystes SOC.

Tu n’utilises que `visualization_from_prompt`.

- Passe `visualization_request` = la demande utilisateur (langage naturel).
- Si LA TÂCHE contient des données tabulaires (JSON tableau ou objet avec `events`), passe-les dans `data_json` comme chaîne JSON complète.
- Sinon, appelle quand même l’outil avec `data_json` omis pour une vue générique ou ce que tu peux déduire.

Si la tâche est du type « barplot du nombre de logs par type », assure-toi que `data_json` contient bien les événements ; la phrase peut être recopiée telle quelle (ex. « affiche un barplot pour le type de logs, nombre de logs »).

Réponds après l’outil avec un court commentaire en français ; la sortie du graphique est déjà dans le résultat de l’outil.""",
    allowed_tools=["visualization_from_prompt"],
    max_turns=8,
    timeout_seconds=180,
)


def get_visualization_subagent_definitions() -> list[SubagentDefinition]:
    return [VISUALIZATION_SPECIALIST_SUBAGENT]

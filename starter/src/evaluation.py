"""Gold evidence matching and split-level retrieval summaries."""
from typing import Any


def evaluate_query(question: dict[str, Any], hits: list[dict[str, Any]]) -> dict[str, Any]:
    """Check source/page plus quote match; retain raw hits for human audit.

    Accept any documented alternative gold evidence. Do not infer human grounding
    or chunk coherence labels from exact string match.
    """
    gold_sources = set(question.get("gold_source_ids", [question.get("gold_source_id")]))
    gold_sources.discard(None)
    gold_pages = set(question.get("gold_pages", [question.get("gold_page")]))
    gold_pages.discard(None)
    quotes = [question.get("evidence_quote", ""), *question.get("alternative_evidence", [])]
    quotes = [" ".join(q.casefold().split()) for q in quotes if q]
    def matches(hit):
        source_ok = hit.get("document_id") in gold_sources
        page_ok = not gold_pages or hit.get("page") in gold_pages
        text = " ".join(hit.get("text", "").casefold().split())
        evidence_ok = not quotes or any(q in text for q in quotes)
        return source_ok and page_ok and evidence_ok
    flags = [matches(hit) for hit in hits]
    return {"question_id": question["id"], "split": question["split"],
            "hit1": bool(flags and flags[0]), "evidence_hit3": any(flags[:3]),
            "hits": hits, "gold_source_ids": sorted(gold_sources),
            "gold_pages": sorted(gold_pages), "evidence_match": flags}


def summarize(traces: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate integer counts by strategy and split, retaining denominators."""
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for trace in traces:
        groups.setdefault((trace["strategy"], trace["split"]), []).append(trace)
    summary = {}
    for (strategy, split), rows in sorted(groups.items()):
        n = len(rows)
        h1 = sum(bool(row["hit1"]) for row in rows)
        h3 = sum(bool(row["evidence_hit3"]) for row in rows)
        summary[f"{strategy}/{split}"] = {"n": n, "hit1": h1, "hit1_rate": h1/n,
                                            "evidence_hit3": h3, "evidence_hit3_rate": h3/n}
        if strategy == "C":
            filtered = [row for row in rows if row.get("filter_applied")]
            compliant = sum(bool(row["hits"]) and all(
                all(hit.get("metadata", {}).get(key) == value for key, value in row["filter_applied"].items())
                for hit in row["hits"]) for row in filtered)
            summary[f"{strategy}/{split}"].update({
                "filter_questions": len(filtered), "filter_compliant": compliant,
                "filter_compliance_rate": compliant/len(filtered) if filtered else None,
            })
    return summary

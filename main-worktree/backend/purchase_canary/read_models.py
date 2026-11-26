def successful_lineage_by_object_no(batch, object_numbers):
    """Map persisted historical chain objects to their authoritative lineage."""
    requested = {str(value) for value in object_numbers if value}
    result = {}
    if not batch or not requested:
        return result
    lineages = batch.lineages.filter(
        scenario_class="pass_through",
        downstream_eligible=True,
    ).order_by("scenario_code")
    for lineage in lineages:
        lineage_numbers = {
            str(value)
            for value in [
                *(lineage.upstream_object_nos or []),
                lineage.current_object_no,
            ]
            if value
        }
        for object_no in requested.intersection(lineage_numbers):
            result[object_no] = lineage
    return result


def historical_lineage_facts(lineage, object_no):
    """Derive read-only progression facts without mutating the active lineage."""
    object_no = str(object_no)
    is_current = object_no == str(lineage.current_object_no)
    is_historical = object_no in {
        str(value) for value in (lineage.upstream_object_nos or [])
    }
    return {
        "canaryLineageId": lineage.canary_lineage_id,
        "scenarioCode": lineage.scenario_code,
        "scenarioClass": lineage.scenario_class,
        "scenarioRole": lineage.scenario_role,
        "downstreamEligible": lineage.downstream_eligible,
        "reservedForNextModule": lineage.reserved_for_next_module,
        "nextStageConsumed": is_historical and not is_current,
        "upstreamObjectNos": lineage.upstream_object_nos,
        "sourceRelationHash": lineage.source_relation_hash,
        "lineagePosition": "current" if is_current else "historical",
    }


__all__ = [
    "historical_lineage_facts",
    "successful_lineage_by_object_no",
]

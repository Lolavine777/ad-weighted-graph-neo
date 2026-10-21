"""Explicit test scenario for a Computer account with usable credentials."""

from scripts.research.final_cpi_profiles import PACKAGE, bind_registry, bind_source_a, read


def identity_source_a(case_id="source-a-projection"):
    query, graph = bind_source_a(case_id)
    if case_id != "source-a-projection":
        return query, graph
    scenario = "test://source-a-explicit-machine-identity"
    query["initial_state"] = {
        **query["initial_state"],
        "usable_identity": [[query["initial_actor"], query["authentication_context"]]],
    }
    query["scenario_reference"] = scenario
    query["rating_resolution"]["scope"]["scenario_id"] = scenario
    for fact in query["runtime_facts"]:
        fact["scope"] = scenario
        fact["provenance_reference"] = scenario
    actions = read(PACKAGE / "source-a-inventory.json")["actions"]
    return bind_registry(query, actions), graph

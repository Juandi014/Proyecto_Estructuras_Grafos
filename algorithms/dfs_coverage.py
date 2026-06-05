import math
from models.graph import Grafo

# Justification: DFS + backtracking applies because the goal is to maximize
# destinations visited — not minimize a single edge weight. Dijkstra finds the
# cheapest/fastest single path; DFS with pruning explores all possible routes
# and keeps the one that reaches the most nodes before hitting a hard constraint.
# The search also enforces that every aircraft type present in the network is
# used at least once, as required by R2.

MAX_DEPTH = 15   # hard cap on path length to keep search tractable


class DFSCoverage:
    # Finds the route that maximizes destinations visited under hard constraints

    def __init__(self, grafo: Grafo):
        self.grafo = grafo
        self._best = None

    # --- Public API ---

    def run_max_by_budget(
        self,
        origin_id: str,
        budget: float,
        time_limit_min: float = math.inf,
        allowed_aircraft: list = None,
        include_secondary: bool = True
    ) -> dict:
        # Returns the path visiting the most destinations without exceeding budget or time
        self._best    = self._empty_result()
        origin        = self.grafo.get_vertice(origin_id)
        if not origin:
            raise ValueError(f"Origin airport '{origin_id}' not found")
        required = self._detect_required_types()
        if allowed_aircraft:
            required = required & set(allowed_aircraft)   # only require types that are allowed

        self._dfs(origin, {origin_id}, [origin_id], [], set(),
                  0.0, 0.0, budget, time_limit_min,
                  allowed_aircraft, required, include_secondary, "costo")
        return self._best

    def run_max_by_time(
        self,
        origin_id: str,
        time_limit_min: float,
        budget: float = math.inf,
        allowed_aircraft: list = None,
        include_secondary: bool = True
    ) -> dict:
        # Returns the path visiting the most destinations without exceeding time or budget
        self._best = self._empty_result()
        origin     = self.grafo.get_vertice(origin_id)
        if not origin:
            raise ValueError(f"Origin airport '{origin_id}' not found")
        required = self._detect_required_types()
        if allowed_aircraft:
            required = required & set(allowed_aircraft)   # only require types that are allowed

        self._dfs(origin, {origin_id}, [origin_id], [], set(),
                  0.0, 0.0, budget, time_limit_min,
                  allowed_aircraft, required, include_secondary, "tiempo")
        return self._best

    # --- Core DFS ---

    def _dfs(self, current, visited, path, path_edges, used_types,
             cost_acc, time_acc, budget, time_limit,
             allowed_ac, required_types, inc_sec, criterion):
        # Recursive DFS with depth cap — updates self._best when a better path is found
        self._try_update_best(path, path_edges, cost_acc, time_acc,
                              used_types, required_types, criterion)

        if len(path) - 1 >= MAX_DEPTH:
            return

        for arista in self.grafo.get_active_routes(current.identificador):
            dest = arista.vertice_destino
            if dest.identificador in visited:
                continue
            if not inc_sec and not dest.is_hub:
                continue

            # Mark dest visited once; try each candidate aircraft as a separate branch
            visited.add(dest.identificador)

            for option in self._get_candidate_options(
                    arista, allowed_ac, used_types, required_types, criterion):

                new_cost = cost_acc + option["cost_usd"]
                new_time = time_acc + option["time_min"]

                # Hard constraint pruning
                if new_cost > budget or new_time > time_limit:
                    continue

                new_used = used_types | {option["aircraft"]}
                path.append(dest.identificador)
                path_edges.append({
                    "origin":      current.identificador,
                    "destination": dest.identificador,
                    "aircraft":    option["aircraft"],
                    "distance_km": arista.distance_km,
                    "cost_usd":    option["cost_usd"],
                    "time_min":    option["time_min"],
                    "subsidized":  arista.is_subsidized()
                })

                self._dfs(dest, visited, path, path_edges, new_used,
                          new_cost, new_time, budget, time_limit,
                          allowed_ac, required_types, inc_sec, criterion)

                path.pop()
                path_edges.pop()

            visited.discard(dest.identificador)

    # --- Best result tracking ---

    def _try_update_best(self, path, path_edges, cost_acc, time_acc,
                         used_types, required_types, criterion):
        # Updates best result respecting type-coverage constraint first, then destinations
        destinations  = len(path) - 1
        best_dest     = len(self._best["path"]) - 1
        current_full  = required_types.issubset(used_types)
        best_full     = required_types.issubset(self._best.get("used_types", []))

        # A path covering all required types beats one that does not
        if not current_full and best_full:
            return
        if current_full and not best_full:
            if destinations < 1:
                return
        else:
            # Same coverage status: maximize destinations, then criterion
            if destinations < best_dest:
                return
            if destinations == best_dest:
                if criterion == "costo"  and cost_acc >= self._best["total_cost"]:
                    return
                if criterion == "tiempo" and time_acc >= self._best["total_time"]:
                    return

        self._best = {
            "path":             list(path),
            "edges":            list(path_edges),
            "total_cost":       round(cost_acc, 2),
            "total_time":       round(time_acc, 2),
            "destinations":     destinations,
            "used_types":       list(used_types),
            "covers_all_types": current_full,
        }

    # --- Aircraft candidate selection ---

    def _get_candidate_options(self, arista, allowed_ac,
                               used_types, required_types, criterion) -> list:
        # Returns: best option by criterion + one option per uncovered required type
        options = arista.get_options()
        if allowed_ac:
            options = [o for o in options if o["aircraft"] in allowed_ac]
        if not options:
            return []

        if criterion == "costo":
            best = min(options, key=lambda o: o["cost_usd"])
        elif criterion == "tiempo":
            best = min(options, key=lambda o: o["time_min"])
        else:
            best = min(options, key=lambda o: o["cost_usd"])

        candidates = [best]
        seen       = {best["aircraft"]}
        uncovered  = required_types - used_types

        # Add one option per uncovered type to ensure we can reach full coverage
        for opt in options:
            if opt["aircraft"] in uncovered and opt["aircraft"] not in seen:
                candidates.append(opt)
                seen.add(opt["aircraft"])

        return candidates

    def _detect_required_types(self) -> set:
        # Returns all aircraft types present in active routes of the graph
        types = set()
        for _, arista in self.grafo.get_all_aristas():   # get_all_aristas returns (iata, Arista)
            types.update(arista.aircraft_types)
        return types

    def _empty_result(self) -> dict:
        # Returns an empty baseline result
        return {
            "path": [], "edges": [], "total_cost": 0.0, "total_time": 0.0,
            "destinations": -1, "used_types": [], "covers_all_types": False
        }
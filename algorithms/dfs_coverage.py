import math
from models.graph import Grafo

# Justification: DFS + backtracking applies here because the goal is to maximize
# destinations visited — not minimize a single edge weight. Dijkstra finds the
# cheapest/fastest single path; DFS with pruning explores all possible routes
# and keeps the one that reaches the most nodes before hitting a hard constraint.


class DFSCoverage:
    # Finds the route that maximizes destinations visited under hard constraints

    def __init__(self, grafo: Grafo):
        self.grafo = grafo
        self._best = None   # stores best result found during current search

    # --- Public API ---

    def run_max_by_budget(
        self,
        origin_id: str,
        budget: float,
        allowed_aircraft: list = None,
        include_secondary: bool = True
    ) -> dict:
        # Returns the path visiting the most destinations without exceeding budget
        self._best = self._empty_result()
        origin = self.grafo.get_vertice(origin_id)
        if not origin:
            raise ValueError(f"Origin airport '{origin_id}' not found")

        self._dfs(
            current    = origin,
            visited    = {origin_id},
            path       = [origin_id],
            path_edges = [],
            cost_acc   = 0.0,
            time_acc   = 0.0,
            budget     = budget,
            time_limit = math.inf,
            allowed_ac = allowed_aircraft,
            inc_sec    = include_secondary,
            criterion  = "costo"
        )
        return self._best

    def run_max_by_time(
        self,
        origin_id: str,
        time_limit_min: float,
        allowed_aircraft: list = None,
        include_secondary: bool = True
    ) -> dict:
        # Returns the path visiting the most destinations without exceeding time limit
        self._best = self._empty_result()
        origin = self.grafo.get_vertice(origin_id)
        if not origin:
            raise ValueError(f"Origin airport '{origin_id}' not found")

        self._dfs(
            current    = origin,
            visited    = {origin_id},
            path       = [origin_id],
            path_edges = [],
            cost_acc   = 0.0,
            time_acc   = 0.0,
            budget     = math.inf,
            time_limit = time_limit_min,
            allowed_ac = allowed_aircraft,
            inc_sec    = include_secondary,
            criterion  = "tiempo"
        )
        return self._best

    # --- Core DFS ---

    def _dfs(
        self,
        current,
        visited: set,
        path: list,
        path_edges: list,
        cost_acc: float,
        time_acc: float,
        budget: float,
        time_limit: float,
        allowed_ac: list,
        inc_sec: bool,
        criterion: str
    ):
        # Recursive DFS — updates self._best when a better path is found
        self._try_update_best(path, path_edges, cost_acc, time_acc, criterion)

        for arista in self.grafo.get_active_routes(current.identificador):
            dest = arista.vertice_destino

            # Skip repeated airports (hard constraint)
            if dest.identificador in visited:
                continue

            # Skip secondary airports if not included
            if not inc_sec and not dest.is_hub:
                continue

            # Skip edges that don't have any allowed aircraft type
            option = self._pick_option(arista, allowed_ac, criterion)
            if option is None:
                continue

            new_cost = cost_acc + option["cost_usd"]
            new_time = time_acc + option["time_min"]

            # Hard constraint pruning — both limits are enforced
            if new_cost > budget or new_time > time_limit:
                continue

            # Recurse
            visited.add(dest.identificador)
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

            self._dfs(dest, visited, path, path_edges,
                      new_cost, new_time,
                      budget, time_limit,
                      allowed_ac, inc_sec, criterion)

            # Backtrack
            path.pop()
            path_edges.pop()
            visited.discard(dest.identificador)

    # --- Best result tracking ---

    def _try_update_best(
        self,
        path: list,
        path_edges: list,
        cost_acc: float,
        time_acc: float,
        criterion: str
    ):
        # Updates best result if current path visits more destinations (or ties better)
        destinations = len(path) - 1   # exclude origin
        best_dest    = len(self._best["path"]) - 1

        if destinations < best_dest:
            return

        if destinations == best_dest:
            # Tiebreak: prefer lower cost when criterion=costo, lower time otherwise
            if criterion == "costo" and cost_acc >= self._best["total_cost"]:
                return
            if criterion == "tiempo" and time_acc >= self._best["total_time"]:
                return

        self._best = {
            "path":        list(path),
            "edges":       list(path_edges),
            "total_cost":  round(cost_acc, 2),
            "total_time":  round(time_acc, 2),
            "destinations": destinations
        }

    # --- Aircraft option selection ---

    def _pick_option(self, arista, allowed_ac: list, criterion: str) -> dict | None:
        # Returns the best valid option for this edge respecting allowed aircraft
        options = arista.get_options()

        if allowed_ac:
            options = [o for o in options if o["aircraft"] in allowed_ac]
        if not options:
            return None

        if criterion == "costo":
            return min(options, key=lambda o: o["cost_usd"])
        if criterion == "tiempo":
            return min(options, key=lambda o: o["time_min"])
        # "distancia" — minimize cost as tiebreak
        return min(options, key=lambda o: o["cost_usd"])

    # --- Helpers ---

    def _empty_result(self) -> dict:
        # Returns an empty baseline result to compare against
        return {"path": [], "edges": [], "total_cost": 0.0,
                "total_time": 0.0, "destinations": -1}
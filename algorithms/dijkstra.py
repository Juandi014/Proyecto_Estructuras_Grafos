import math
from models.graph import Grafo

# Justification: Dijkstra applies here because all edge weights (distance, cost,
# time) are strictly non-negative. It guarantees the optimal single-source path
# under one criterion while enforcing hard budget/time constraints via pruning.

CRITERIA = ("distancia", "costo", "tiempo")


class Dijkstra:
    # Finds shortest path in a weighted directed graph by one optimization criterion

    def __init__(self, grafo: Grafo):
        self.grafo = grafo

    def run(
        self,
        origin_id: str,
        destination_id: str,
        criterion: str = "distancia",
        budget: float = math.inf,
        time_limit_min: float = math.inf,
        include_secondary: bool = True
    ) -> dict:
        # Runs Dijkstra from origin to destination; returns result dict
        self._validate_inputs(origin_id, destination_id, criterion)

        ids        = self._get_active_ids(include_secondary)
        dist       = {v: math.inf for v in ids}
        cost_acc   = {v: math.inf for v in ids}   # accumulated USD cost
        time_acc   = {v: math.inf for v in ids}   # accumulated time in minutes
        pred       = {v: None     for v in ids}
        aircraft   = {v: None     for v in ids}   # aircraft chosen on edge into v
        no_visited = set(ids)

        dist[origin_id]      = 0
        cost_acc[origin_id]  = 0
        time_acc[origin_id]  = 0

        while no_visited:
            u = self._pick_min(no_visited, dist)
            if dist[u] == math.inf:
                break

            no_visited.remove(u)

            if u == destination_id:
                break

            for arista in self.grafo.get_active_routes(u):
                v = arista.vertice_destino.identificador
                if v not in no_visited:
                    continue
                if not include_secondary and not arista.vertice_destino.is_hub:
                    continue

                option         = self._best_option(arista, criterion)
                edge_weight    = option["weight"]
                edge_cost      = option["cost_usd"]
                edge_time      = option["time_min"]

                new_dist  = dist[u]     + edge_weight
                new_cost  = cost_acc[u] + edge_cost
                new_time  = time_acc[u] + edge_time

                # Hard constraints: prune if either budget or time is exceeded
                if new_cost > budget or new_time > time_limit_min:
                    continue

                if new_dist < dist[v]:
                    dist[v]     = new_dist
                    cost_acc[v] = new_cost
                    time_acc[v] = new_time
                    pred[v]     = u
                    aircraft[v] = option["aircraft"]

        path = self._reconstruct_path(pred, origin_id, destination_id)
        return {
            "path":         path,
            "dist":         dist,
            "cost_acc":     cost_acc,
            "time_acc":     time_acc,
            "pred":         pred,
            "aircraft":     aircraft,
            "total_weight": dist[destination_id],
            "total_cost":   cost_acc[destination_id],
            "total_time":   time_acc[destination_id],
            "reachable":    dist[destination_id] < math.inf
        }

    # --- Weight selection per criterion ---

    def _best_option(self, arista, criterion: str) -> dict:
        # Returns the aircraft option that minimizes the given criterion
        options = arista.get_options()
        if criterion == "costo":
            best = min(options, key=lambda o: o["cost_usd"])
            return {**best, "weight": best["cost_usd"]}
        if criterion == "tiempo":
            best = min(options, key=lambda o: o["time_min"])
            return {**best, "weight": best["time_min"]}
        # "distancia" — weight is km, aircraft with lowest cost is preferred as tiebreak
        best = min(options, key=lambda o: o["cost_usd"])
        return {**best, "weight": arista.getPeso()}

    # --- Graph helpers ---

    def _get_active_ids(self, include_secondary: bool) -> list:
        # Returns list of airport IDs eligible for this search
        return [
            v.identificador for v in self.grafo.vertices
            if include_secondary or v.is_hub
        ]

    def _pick_min(self, no_visited: set, dist: dict) -> str:
        # Returns the unvisited node with the smallest tentative distance
        return min(no_visited, key=lambda v: dist[v])

    def _reconstruct_path(self, pred: dict, origin: str, destination: str) -> list:
        # Walks predecessor map backwards to build the ordered path
        path   = []
        actual = destination
        while actual is not None:
            path.insert(0, actual)
            actual = pred[actual]
        if not path or path[0] != origin:
            return []
        return path

    # --- Input validation ---

    def _validate_inputs(self, origin: str, destination: str, criterion: str):
        # Raises ValueError if any input is invalid
        if not self.grafo.vertice_existe(origin):
            raise ValueError(f"Origin airport '{origin}' not found in graph")
        if not self.grafo.vertice_existe(destination):
            raise ValueError(f"Destination airport '{destination}' not found in graph")
        if criterion not in CRITERIA:
            raise ValueError(f"Criterion must be one of {CRITERIA}, got '{criterion}'")

    # --- Multi-criteria runner ---

    def run_all_criteria(
        self,
        origin_id: str,
        destination_id: str,
        budget: float = math.inf,
        time_limit_min: float = math.inf,
        include_secondary: bool = True
    ) -> dict:
        # Runs Dijkstra once per criterion; returns dict keyed by criterion name
        return {
            c: self.run(origin_id, destination_id, c, budget, time_limit_min, include_secondary)
            for c in CRITERIA
        }
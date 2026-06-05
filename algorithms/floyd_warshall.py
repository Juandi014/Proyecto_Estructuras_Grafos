import math
from models.graph import Grafo

# Justification: Floyd-Warshall computes minimum-cost paths between ALL pairs of
# airports in O(V³). Used by DynamicPlanner._suggest_next (R3): rather than
# counting only direct neighbors one hop away, the planner evaluates true
# multi-hop reachability from each candidate destination within the remaining
# budget, producing a globally accurate suggestion instead of a greedy local one.
# With ≤30 airports, O(V³) = ~27 000 operations — negligible overhead.


class FloydWarshall:
    # Computes all-pairs minimum-cost distances for a directed weighted graph

    def __init__(self, grafo: Grafo):
        self.grafo = grafo
        self._ids  = []    # sorted list of airport IATA codes
        self._idx  = {}    # IATA → matrix index
        self._dist = []    # dist[i][j] = min cost from airport i to airport j
        self._next = []    # next[i][j] = index of first hop from i toward j
        self.run()

    # --- Core algorithm ---

    def run(self):
        # Initializes matrices from active edges and relaxes all pairs
        self._ids = sorted(v.identificador for v in self.grafo.vertices)
        n         = len(self._ids)
        self._idx = {iata: i for i, iata in enumerate(self._ids)}
        INF       = math.inf

        self._dist = [[INF] * n for _ in range(n)]
        self._next = [[None] * n for _ in range(n)]

        # Distance from every node to itself is 0
        for i in range(n):
            self._dist[i][i] = 0.0

        # Seed direct edges with the cheapest aircraft option cost
        for v in self.grafo.vertices:
            i = self._idx[v.identificador]
            for arista in self.grafo.get_active_routes(v.identificador):
                j = self._idx.get(arista.vertice_destino.identificador)
                if j is None:
                    continue
                if not arista.aircraft_types:   # guard: skip routes with no aircraft defined
                    continue
                opt = arista.get_cheapest_option()
                if opt["cost_usd"] < self._dist[i][j]:
                    self._dist[i][j] = opt["cost_usd"]
                    self._next[i][j] = j

        # Relax all pairs through every intermediate node k
        for k in range(n):
            for i in range(n):
                if self._dist[i][k] == INF:
                    continue
                for j in range(n):
                    if self._dist[k][j] == INF:
                        continue
                    via_k = self._dist[i][k] + self._dist[k][j]
                    if via_k < self._dist[i][j]:
                        self._dist[i][j] = via_k
                        self._next[i][j] = self._next[i][k]

    # --- Public queries ---

    def shortest_cost(self, origin: str, dest: str) -> float:
        # Returns minimum cost from origin to dest; math.inf if unreachable
        i = self._idx.get(origin)
        j = self._idx.get(dest)
        if i is None or j is None:
            return math.inf
        return self._dist[i][j]

    def reachable(self, origin: str, dest: str) -> bool:
        # Returns True if dest can be reached from origin
        return self.shortest_cost(origin, dest) < math.inf

    def shortest_path(self, origin: str, dest: str) -> list:
        # Reconstructs the cheapest-cost path as an ordered list of IATA codes
        i = self._idx.get(origin)
        j = self._idx.get(dest)
        if i is None or j is None or self._dist[i][j] == math.inf:
            return []
        path = [origin]
        curr = i
        while curr != j:
            nxt = self._next[curr][j]
            if nxt is None:
                return []
            curr = nxt
            path.append(self._ids[curr])
        return path

    def reachable_from(self, origin: str, max_cost: float = math.inf) -> list:
        # Returns all airports reachable from origin within max_cost
        i = self._idx.get(origin)
        if i is None:
            return []
        return [
            self._ids[j]
            for j in range(len(self._ids))
            if j != i and self._dist[i][j] <= max_cost
        ]
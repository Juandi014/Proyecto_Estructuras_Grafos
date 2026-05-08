import math
from models.airport import Vertice
from models.route import Arista


class Grafo:
    # Directed weighted graph using adjacency list — implemented from scratch
    def __init__(self):
        self.vertices = []                          # list[Vertice] — all airport nodes
        self._index: dict[str, Vertice] = {}        # iata -> Vertice for O(1) lookup
        self.aircraft_rates: dict = {}              # global overridable aircraft rates
        self.budget_threshold_pct: float = 0.35     # triggers job offers below this %
        self.lodging_interval_h: int = 20           # hours between mandatory lodgings
        self.food_interval_h: int = 8               # hours between mandatory meals

    # --- Node operations ---

    def agregar_vertice(self, vertice: Vertice):
        # Adds airport node and registers it in the lookup index
        self.vertices.append(vertice)
        self._index[vertice.identificador] = vertice

    def get_vertice(self, iata: str) -> Vertice | None:
        # Returns airport by IATA code or None
        return self._index.get(iata)

    def vertice_existe(self, iata: str) -> bool:
        # Checks if airport is registered in the graph
        return iata in self._index

    def get_hubs(self) -> list:
        # Returns only hub airports
        return [v for v in self.vertices if v.is_hub]

    def get_secondary_airports(self) -> list:
        # Returns only secondary airports
        return [v for v in self.vertices if not v.is_hub]

    # --- Edge operations ---

    def get_active_routes(self, iata: str) -> list:
        # Returns non-blocked outgoing routes from the given airport
        vertice = self.get_vertice(iata)
        if not vertice:
            return []
        return [a for a in vertice.adyacencias if not a.is_blocked]

    def get_arista(self, origin: str, destination: str) -> Arista | None:
        # Returns the route between two airports or None
        vertice = self.get_vertice(origin)
        if not vertice:
            return None
        for arista in vertice.adyacencias:
            if arista.vertice_destino.identificador == destination:
                return arista
        return None

    def bloquear_ruta(self, origin: str, destination: str) -> bool:
        # Blocks a specific route; returns True if found and blocked
        arista = self.get_arista(origin, destination)
        if arista:
            arista.block()
            return True
        return False

    def desbloquear_ruta(self, origin: str, destination: str) -> bool:
        # Unblocks a specific route; returns True if found and unblocked
        arista = self.get_arista(origin, destination)
        if arista:
            arista.unblock()
            return True
        return False

    def get_all_aristas(self, include_blocked: bool = False) -> list:
        # Returns all routes across the entire graph
        result = []
        for v in self.vertices:
            for a in v.adyacencias:
                if include_blocked or not a.is_blocked:
                    result.append((v.identificador, a))
        return result

    def get_vecinos(self, iata: str, include_secondary: bool = True) -> list:
        # Returns reachable airport IATA codes from given airport
        vecinos = []
        for arista in self.get_active_routes(iata):
            dest = arista.vertice_destino
            if include_secondary or dest.is_hub:
                vecinos.append(dest.identificador)
        return vecinos

    # --- Global config ---

    def apply_aircraft_rates(self, rates: dict):
        # Overwrites aircraft rates globally on all existing routes
        self.aircraft_rates = rates
        for v in self.vertices:
            for arista in v.adyacencias:
                arista.aircraft_rates = rates

    # --- Display ---

    def imprimir_grafo(self):
        # Prints adjacency list with distance weight per route
        for v in self.vertices:
            print("***************************")
            print(v.identificador)
            for a in v.adyacencias:
                status = "[BLOCKED]" if a.is_blocked else ""
                print(
                    f"  → {a.vertice_destino.identificador} "
                    f"| {a.getPeso()} km "
                    f"| {', '.join(a.aircraft_types)} "
                    f"{status}"
                )
        print("-------------------------------------")
        print(f"Total: {len(self.vertices)} airports | "
              f"{len(self.get_all_aristas())} active routes")

    def __repr__(self) -> str:
        active = len(self.get_all_aristas())
        total = len(self.get_all_aristas(include_blocked=True))
        return (
            f"Grafo({len(self.vertices)} airports | "
            f"{active} active routes | "
            f"{total - active} blocked)"
        )
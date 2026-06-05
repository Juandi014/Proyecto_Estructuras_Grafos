# Default aircraft cost and time rates (overridable via JSON)
AIRCRAFT_DEFAULTS = {
    "Avión Comercial": {"cost_per_km": 0.18, "time_per_km": 0.7},
    "Avión Regional":  {"cost_per_km": 0.25, "time_per_km": 1.1},
    "Hélice":          {"cost_per_km": 0.12, "time_per_km": 2.5},
}


class Arista:
    # Directed graph edge — represents a route between two airports
    def __init__(
        self,
        vertice_destino,
        distance_km: float,
        aircraft_types: list,
        base_cost: float,
        min_stay_min: int,
        aircraft_rates: dict = None
    ):
        self.vertice_destino = vertice_destino   # Vertice — destination airport node
        self.distance_km = distance_km
        self.aircraft_types = aircraft_types     # e.g. ["Avión Comercial", "Hélice"]
        self.base_cost = base_cost               # 0 if subsidized route
        self.min_stay_min = min_stay_min         # minimum stay at destination in minutes
        self.aircraft_rates = aircraft_rates if aircraft_rates is not None else AIRCRAFT_DEFAULTS
        self.is_blocked = False                  # True when route is interrupted (R4)

    def getPeso(self) -> float:
        # Returns distance_km as default weight (used by graph traversal algorithms)
        return self.distance_km

    def is_subsidized(self) -> bool:
        # Checks if this route has zero base cost
        return self.base_cost == 0

    def get_cost(self, aircraft_type: str) -> float:
        # Returns total flight cost in USD for the given aircraft type
        if self.is_subsidized():
            return 0.0
        rate = self.aircraft_rates.get(aircraft_type, AIRCRAFT_DEFAULTS.get(aircraft_type, {}))
        cost_per_km = rate.get("cost_per_km", 0)
        return round(self.distance_km * cost_per_km, 2)

    def get_time(self, aircraft_type: str) -> float:
        # Returns total flight time in minutes for the given aircraft type
        rate = self.aircraft_rates.get(aircraft_type, AIRCRAFT_DEFAULTS.get(aircraft_type, {}))
        time_per_km = rate.get("time_per_km", 0)
        return round(self.distance_km * time_per_km, 2)

    def get_options(self) -> list:
        # Returns all aircraft options with computed cost and time for this route
        options = []
        for aircraft in self.aircraft_types:
            options.append({
                "aircraft": aircraft,
                "cost_usd": self.get_cost(aircraft),
                "time_min": self.get_time(aircraft),
                "distance_km": self.distance_km,
                "subsidized": self.is_subsidized()
            })
        return options

    def get_cheapest_option(self) -> dict:
        # Returns the aircraft option with the lowest cost for this route
        options = self.get_options()
        return min(options, key=lambda o: o["cost_usd"])

    def get_fastest_option(self) -> dict:
        # Returns the aircraft option with the shortest flight time
        options = self.get_options()
        return min(options, key=lambda o: o["time_min"])

    def block(self):
        # Marks route as blocked due to interruption (R4)
        self.is_blocked = True

    def unblock(self):
        # Restores route to active state
        self.is_blocked = False

    def to_dict(self) -> dict:
        # Returns route as serializable dict
        return {
            "destino": self.vertice_destino.identificador,
            "distanciaKm": self.distance_km,
            "aeronaves": self.aircraft_types,
            "costoBase": self.base_cost,
            "estanciaMinima": self.min_stay_min,
            "bloqueada": self.is_blocked
        }

    def __repr__(self) -> str:
        status = "BLOCKED" if self.is_blocked else "OK"
        return (
            f"Arista(→{self.vertice_destino.identificador} | "
            f"{self.distance_km}km | {status})"
        )
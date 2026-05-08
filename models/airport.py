class Activity:
    # Represents an optional or mandatory activity at an airport
    def __init__(self, name: str, activity_type: str, duration_min: int, cost_usd: float):
        self.name = name
        self.activity_type = activity_type   # "obligatoria" | "opcional"
        self.duration_min = duration_min
        self.cost_usd = cost_usd

    def to_dict(self) -> dict:
        # Returns activity as serializable dict
        return {
            "nombre": self.name,
            "tipo": self.activity_type,
            "duracionMin": self.duration_min,
            "costoUSD": self.cost_usd
        }


class Job:
    # Represents a temporary job available at an airport
    def __init__(self, name: str, hourly_rate: float, max_hours: int):
        self.name = name
        self.hourly_rate = hourly_rate
        self.max_hours = max_hours

    def calculate_earnings(self, hours_worked: int) -> float:
        # Returns total earnings capped at max_hours
        capped = min(hours_worked, self.max_hours)
        return round(capped * self.hourly_rate, 2)

    def to_dict(self) -> dict:
        # Returns job as serializable dict
        return {
            "nombre": self.name,
            "tarifaHora": self.hourly_rate,
            "maxHoras": self.max_hours
        }


class Vertice:
    # Graph node — represents an airport identified by its IATA code
    def __init__(
        self,
        identificador: str,
        name: str,
        city: str,
        country: str,
        timezone: str,
        is_hub: bool,
        lodging_cost: float,
        food_cost: float,
        airlines: list,
        activities: list,
        jobs: list
    ):
        self.identificador = identificador   # IATA code — used as node key
        self.adyacencias = []                # list[Arista] — outgoing routes
        self.name = name
        self.city = city
        self.country = country
        self.timezone = timezone
        self.is_hub = is_hub
        self.lodging_cost = lodging_cost     # USD per night
        self.food_cost = food_cost           # USD per meal
        self.airlines = airlines
        self.activities = activities         # list[Activity]
        self.jobs = jobs                     # list[Job]

    def agregar_adyacencia(self, arista):
        # Adds an outgoing route (Arista) to this airport
        self.adyacencias.append(arista)

    def get_optional_activities(self) -> list:
        # Returns only optional activities
        return [a for a in self.activities if a.activity_type == "opcional"]

    def get_mandatory_activities(self) -> list:
        # Returns only mandatory activities
        return [a for a in self.activities if a.activity_type == "obligatoria"]

    def to_dict(self) -> dict:
        # Returns airport node as serializable dict
        return {
            "id": self.identificador,
            "nombre": self.name,
            "ciudad": self.city,
            "pais": self.country,
            "zonaHoraria": self.timezone,
            "esHub": self.is_hub,
            "costoAlojamiento": self.lodging_cost,
            "costoAlimentacion": self.food_cost,
            "aerolineas": self.airlines,
            "actividades": [a.to_dict() for a in self.activities],
            "trabajos": [j.to_dict() for j in self.jobs]
        }

    def __repr__(self) -> str:
        hub_label = "HUB" if self.is_hub else "SEC"
        return f"Vertice({self.identificador} | {self.city}, {self.country} | {hub_label})"
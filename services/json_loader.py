import json
from models.airport import Vertice, Activity, Job
from models.route import Arista, AIRCRAFT_DEFAULTS
from models.graph import Grafo


class JSONLoader:
    # Loads network.json and builds a fully populated Grafo

    def __init__(self, filepath: str):
        self.filepath = filepath

    def load(self) -> Grafo:
        # Reads JSON file and returns a constructed Grafo
        raw = self._read_file()
        grafo = Grafo()
        self._apply_global_config(grafo, raw.get("configuracion", {}))
        self._load_airports(grafo, raw.get("aeropuertos", []))
        self._load_routes(grafo, raw.get("rutas", []))
        return grafo

    def _read_file(self) -> dict:
        # Reads and parses the JSON file; raises on missing file or invalid JSON
        with open(self.filepath, "r", encoding="utf-8") as f:
            return json.load(f)

    def _apply_global_config(self, grafo: Grafo, config: dict):
        # Applies global settings to the graph; falls back to defaults if absent
        grafo.budget_threshold_pct = config.get("presupuestoMinimoPorc", 0.35)
        grafo.lodging_interval_h   = config.get("intervaloAlojamiento", 20)
        grafo.food_interval_h      = config.get("intervaloAlimentacion", 8)
        raw_rates = config.get("aeronaves", {})
        grafo.aircraft_rates = self._parse_aircraft_rates(raw_rates)

    def _parse_aircraft_rates(self, raw: dict) -> dict:
        # Merges JSON aircraft rates over defaults; missing keys keep default values
        rates = {k: dict(v) for k, v in AIRCRAFT_DEFAULTS.items()}
        for aircraft, values in raw.items():
            if aircraft not in rates:
                rates[aircraft] = {}
            if "costoKm" in values:
                rates[aircraft]["cost_per_km"] = values["costoKm"]
            if "tiempoKm" in values:
                rates[aircraft]["time_per_km"] = values["tiempoKm"]
        return rates

    def _load_airports(self, grafo: Grafo, raw_airports: list):
        # Builds Vertice objects and registers them in the graph
        for raw in raw_airports:
            vertice = self._build_vertice(raw)
            grafo.agregar_vertice(vertice)

    def _build_vertice(self, raw: dict) -> Vertice:
        # Constructs a single Vertice from its raw JSON dict
        activities = [self._build_activity(a) for a in raw.get("actividades", [])]
        jobs       = [self._build_job(j)      for j in raw.get("trabajos", [])]
        return Vertice(
            identificador = raw["id"],
            name          = raw["nombre"],
            city          = raw["ciudad"],
            country       = raw["pais"],
            timezone      = raw["zonaHoraria"],
            is_hub        = raw["esHub"],
            lodging_cost  = raw["costoAlojamiento"],
            food_cost     = raw["costoAlimentacion"],
            airlines      = raw.get("aerolineas", []),
            activities    = activities,
            jobs          = jobs
        )

    def _build_activity(self, raw: dict) -> Activity:
        # Constructs an Activity from its raw JSON dict
        return Activity(
            name          = raw["nombre"],
            activity_type = raw["tipo"],
            duration_min  = raw["duracionMin"],
            cost_usd      = raw["costoUSD"]
        )

    def _build_job(self, raw: dict) -> Job:
        # Constructs a Job from its raw JSON dict
        return Job(
            name        = raw["nombre"],
            hourly_rate = raw["tarifaHora"],
            max_hours   = raw["maxHoras"]
        )

    def _load_routes(self, grafo: Grafo, raw_routes: list):
        # Builds Arista objects and attaches them to their origin Vertice
        for raw in raw_routes:
            origin_id = raw["origen"]
            origin    = grafo.get_vertice(origin_id)
            dest      = grafo.get_vertice(raw["destino"])
            if origin is None:
                raise ValueError(f"Route origin '{origin_id}' not found in airports")
            if dest is None:
                raise ValueError(f"Route destination '{raw['destino']}' not found in airports")
            arista = self._build_arista(dest, raw, grafo.aircraft_rates)
            origin.agregar_adyacencia(arista)

    def _build_arista(self, dest: Vertice, raw: dict, rates: dict) -> Arista:
        # Constructs an Arista with the global aircraft rates already applied
        return Arista(
            vertice_destino = dest,
            distance_km     = raw["distanciaKm"],
            aircraft_types  = raw["aeronaves"],
            base_cost       = raw["costoBase"],
            min_stay_min    = raw["estanciaMinima"],
            aircraft_rates  = rates
        )

    def save(self, grafo: Grafo, filepath: str = None):
        # Serializes the current graph state back to JSON (for UI overwrites)
        output_path = filepath or self.filepath
        rutas = []
        for v in grafo.vertices:
            for arista in v.adyacencias:
                entry = arista.to_dict()
                entry["origen"] = v.identificador
                rutas.append(entry)
        data = {
            "configuracion": {
                "aeronaves": {
                    name: {"costoKm": vals["cost_per_km"], "tiempoKm": vals["time_per_km"]}
                    for name, vals in grafo.aircraft_rates.items()
                },
                "presupuestoMinimoPorc": grafo.budget_threshold_pct,
                "intervaloAlojamiento":  grafo.lodging_interval_h,
                "intervaloAlimentacion": grafo.food_interval_h
            },
            "aeropuertos": [v.to_dict() for v in grafo.vertices],
            "rutas": rutas
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
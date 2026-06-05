import math
from models.graph import Grafo
from models.airport import Vertice
from models.route import Arista
from algorithms.travel_state import TravelState, Phase
from algorithms.floyd_warshall import FloydWarshall


class DynamicPlanner:
    # Manages step-by-step trip planning with dynamic budget (R3).
    # Each public method advances the state by one decision and returns
    # the new situation dict so any UI can render it without coupling.

    def __init__(self, grafo: Grafo, origin_id: str, initial_budget: float,
                 time_limit_min: float = float("inf")):
        self.grafo   = grafo
        self._fw     = FloydWarshall(grafo)   # precomputed all-pairs costs for suggestion
        self.state   = TravelState(
            origin_id,
            initial_budget,
            time_limit_min        = time_limit_min,
            budget_threshold_pct  = grafo.budget_threshold_pct   # configurable from JSON
        )
        self._enter_airport(origin_id)   # set up first mandatory checks

    # --- Situation query (UI calls this after every action) ---

    def get_situation(self) -> dict:
        # Returns full description of current state and available actions
        airport = self.grafo.get_vertice(self.state.current_id)
        base = {
            "phase":   self.state.phase.value,
            "airport": airport.to_dict() if airport else {},
            "state":   self.state.summary()
        }

        if self.state.phase == Phase.MANDATORY_LODGING:
            return {**base, "lodging_cost": airport.lodging_cost}

        if self.state.phase == Phase.MANDATORY_FOOD:
            return {**base, "food_cost": airport.food_cost}

        if self.state.phase == Phase.OPTIONAL_ACTIVITIES:
            acts = [a for a in airport.get_optional_activities()
                    if a.name not in self.state.done_activities_here]
            return {**base, "activities": [a.to_dict() for a in acts]}

        if self.state.phase == Phase.JOBS:
            jobs = airport.jobs
            return {**base,
                    "jobs":           [j.to_dict() for j in jobs],
                    "jobs_available": self.state.jobs_available()}

        if self.state.phase == Phase.CHOOSE_DESTINATION:
            options    = self._build_destination_options()
            suggestion = self._suggest_next(options)
            return {**base, "destinations": options, "suggestion": suggestion}

        if self.state.phase == Phase.CHOOSE_AIRCRAFT:
            arista  = self.state.pending_arista
            options = self._filter_aircraft_options(arista)
            return {**base,
                    "destination":      self.state.pending_destination.identificador,
                    "aircraft_options": options}

        if self.state.phase == Phase.IN_TRANSIT:
            return {**base,
                    "destination": self.state.pending_destination.identificador,
                    "aircraft":    self.state.pending_aircraft,
                    "time_min":    self.state.pending_arista.get_time(
                                       self.state.pending_aircraft)}

        if self.state.phase == Phase.TRIP_ENDED:
            return {**base, "log": self.state.log}

        return base

    # --- Action handlers ---

    def confirm_lodging(self):
        # Pays for lodging at current airport and resets lodging timer
        airport = self.grafo.get_vertice(self.state.current_id)
        cost    = airport.lodging_cost
        self.state.spend(cost, f"Lodging at {self.state.current_id}")
        self.state.log_activity("Alojamiento", "obligatoria", 480, cost)
        self.state.advance_time(480)   # 8h sleep counted as time
        self.state.reset_lodging_timer()
        self.state.phase = self._next_mandatory_or(Phase.OPTIONAL_ACTIVITIES)

    def confirm_meal(self):
        # Pays for a meal at current (or last visited) airport and resets meal timer
        airport = self.grafo.get_vertice(self.state.current_id)
        cost    = airport.food_cost
        self.state.spend(cost, f"Meal at {self.state.current_id}")
        self.state.log_activity("Alimentación", "obligatoria", 30, cost)
        self.state.advance_time(30)
        self.state.reset_meal_timer()
        self.state.phase = self._next_mandatory_or(Phase.OPTIONAL_ACTIVITIES)

    def do_activity(self, activity_name: str):
        # Performs an optional activity at the current airport
        if activity_name in self.state.done_activities_here:
            raise ValueError(f"Activity '{activity_name}' already completed at this stop")
        airport  = self.grafo.get_vertice(self.state.current_id)
        activity = next((a for a in airport.get_optional_activities()
                         if a.name == activity_name), None)
        if activity is None:
            raise ValueError(f"Activity '{activity_name}' not found at {self.state.current_id}")
        if self.state.budget < activity.cost_usd:
            raise ValueError("Insufficient budget for this activity")

        self.state.spend(activity.cost_usd, f"Activity: {activity_name}")
        self.state.log_activity(activity.name, "opcional",
                                activity.duration_min, activity.cost_usd)
        self.state.advance_time(activity.duration_min)
        self.state.done_activities_here.add(activity_name)

    def skip_activities(self):
        # Skips optional activities and moves to jobs phase
        self.state.phase = Phase.JOBS

    def do_job(self, job_name: str, hours: float):
        # Works a job at the current airport and earns income
        if not self.state.jobs_available():
            raise ValueError("Jobs are only available when budget < threshold of initial")
        airport = self.grafo.get_vertice(self.state.current_id)
        job     = next((j for j in airport.jobs if j.name == job_name), None)
        if job is None:
            raise ValueError(f"Job '{job_name}' not found at {self.state.current_id}")

        hours  = min(hours, job.max_hours)
        earned = job.calculate_earnings(hours)
        self.state.earn(earned, f"Job: {job_name} ({hours}h)")
        self.state.log_job(job_name, hours, earned)
        self.state.advance_time(hours * 60)

    def skip_jobs(self):
        # Skips job offer and moves to destination selection
        self.state.phase = Phase.CHOOSE_DESTINATION

    def choose_destination(self, airport_id: str):
        # Selects next destination airport; moves to aircraft selection
        arista = self.grafo.get_arista(self.state.current_id, airport_id)
        if arista is None or arista.is_blocked:
            raise ValueError(f"No active route from {self.state.current_id} to {airport_id}")
        if airport_id in self.state.visited:
            raise ValueError(f"Airport {airport_id} already visited")

        self.state.pending_destination = arista.vertice_destino
        self.state.pending_arista      = arista
        self.state.phase               = Phase.CHOOSE_AIRCRAFT

    def choose_aircraft(self, aircraft_type: str):
        # Confirms aircraft choice and starts the in-transit phase
        arista = self.state.pending_arista
        if aircraft_type not in arista.aircraft_types:
            raise ValueError(f"Aircraft '{aircraft_type}' not available on this route")
        cost     = arista.get_cost(aircraft_type)
        time_min = arista.get_time(aircraft_type)
        if cost > self.state.budget:
            raise ValueError("Insufficient budget for this flight")
        if self.state.elapsed_min + time_min > self.state.time_limit_min:
            raise ValueError("This flight would exceed the available time limit")
        if arista.is_subsidized() and not self.state.can_use_subsidized(arista.distance_km):
            raise ValueError("Cannot use this subsidized route: 20% distance limit reached")
        self.state.pending_aircraft = aircraft_type
        self.state.phase            = Phase.IN_TRANSIT

    def complete_flight(self):
        # Completes in-transit leg, arrives at destination, triggers mandatory checks
        arista     = self.state.pending_arista
        aircraft   = self.state.pending_aircraft
        dest       = self.state.pending_destination
        cost       = arista.get_cost(aircraft)
        time_min   = arista.get_time(aircraft)
        subsidized = arista.is_subsidized()

        # Check if a meal is needed mid-flight — cost billed to last airport
        meals_during = int((self.state.since_meal_min + time_min) //
                           (self.grafo.food_interval_h * 60))
        if meals_during > 0:
            last_airport = self.grafo.get_vertice(self.state.current_id)
            for _ in range(meals_during):
                meal_cost = last_airport.food_cost
                self.state.spend(meal_cost, f"In-flight meal (billed to {self.state.current_id})")
                self.state.log_activity("Alimentación en vuelo", "obligatoria", 0, meal_cost)

        # Save meal accumulator before advance_time modifies it
        original_since_meal = self.state.since_meal_min

        self.state.spend(cost, f"Flight {self.state.current_id} -> {dest.identificador} ({aircraft})")
        self.state.log_flight(self.state.current_id, dest.identificador,
                              aircraft, arista.distance_km, cost, time_min, subsidized)
        self.state.advance_time(time_min)
        self.state.record_leg(arista.distance_km, subsidized)

        # Correct since_meal_min: remaining partial time after all mid-flight meals
        self.state.since_meal_min = round(
            (original_since_meal + time_min) % (self.grafo.food_interval_h * 60), 2)

        # Arrive
        self.state.visited.add(dest.identificador)
        self.state.current_id          = dest.identificador
        self.state.pending_destination = None
        self.state.pending_arista      = None
        self.state.pending_aircraft    = None

        self._enter_airport(dest.identificador)

    def cancel_flight(self):
        # Cancels an in-transit leg and returns the traveler to the departure airport
        if self.state.phase != Phase.IN_TRANSIT:
            raise ValueError("No active flight to cancel")
        self.state.pending_destination = None
        self.state.pending_arista      = None
        self.state.pending_aircraft    = None
        self._enter_airport(self.state.current_id)

    def end_trip(self):
        # Ends the trip and transitions to TRIP_ENDED phase
        self.state.phase = Phase.TRIP_ENDED

    # --- Internal helpers ---

    def _enter_airport(self, airport_id: str):
        # Sets the correct phase when arriving at or starting at an airport
        self.state.done_activities_here = set()
        self.state.phase = self._next_mandatory_or(Phase.OPTIONAL_ACTIVITIES)

    def _next_mandatory_or(self, fallback: Phase) -> Phase:
        # Returns the next mandatory phase if triggered, otherwise fallback
        if self.state.needs_lodging(self.grafo.lodging_interval_h):
            return Phase.MANDATORY_LODGING
        if self.state.needs_meal(self.grafo.food_interval_h):
            return Phase.MANDATORY_FOOD
        return fallback

    def _build_destination_options(self) -> list:
        # Returns reachable, unvisited destinations with cost/time per aircraft
        options = []
        for arista in self.grafo.get_active_routes(self.state.current_id):
            dest_id = arista.vertice_destino.identificador
            if dest_id in self.state.visited:
                continue
            aircraft_opts = self._filter_aircraft_options(arista)
            if not aircraft_opts:
                continue
            options.append({
                "airport_id":       dest_id,
                "distance_km":      arista.distance_km,
                "subsidized":       arista.is_subsidized(),
                "min_stay_min":     arista.min_stay_min,
                "aircraft_options": aircraft_opts
            })
        return options

    def _filter_aircraft_options(self, arista: Arista) -> list:
        # Returns aircraft options that fit within current budget, time and distance rules
        result        = []
        remaining_min = self.state.time_limit_min - self.state.elapsed_min
        for opt in arista.get_options():
            if opt["cost_usd"] > self.state.budget:
                continue
            if opt["time_min"] > remaining_min:                          # hard time constraint
                continue
            if arista.is_subsidized() and not self.state.can_use_subsidized(arista.distance_km):
                continue
            result.append(opt)
        return result

    def _suggest_next(self, destination_options: list) -> str | None:
        # Uses Floyd-Warshall to score each candidate by truly reachable unvisited airports
        best_id    = None
        best_score = -1
        for opt in destination_options:
            dest_id  = opt["airport_id"]
            cheapest = min(opt["aircraft_options"], key=lambda o: o["cost_usd"], default=None)
            if cheapest is None:
                continue
            remaining = self.state.budget - cheapest["cost_usd"]
            # Count unvisited airports reachable from dest within remaining budget (multi-hop)
            score = sum(
                1 for iata in self._fw.reachable_from(dest_id, remaining)
                if iata not in self.state.visited
            )
            if score > best_score:
                best_score = score
                best_id    = dest_id
        return best_id
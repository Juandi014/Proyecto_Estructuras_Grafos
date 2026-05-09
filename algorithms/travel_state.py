from enum import Enum


class Phase(Enum):
    # Represents the current decision phase the traveler is in
    MANDATORY_LODGING    = "mandatory_lodging"
    MANDATORY_FOOD       = "mandatory_food"
    OPTIONAL_ACTIVITIES  = "optional_activities"
    JOBS                 = "jobs"
    CHOOSE_DESTINATION   = "choose_destination"
    CHOOSE_AIRCRAFT      = "choose_aircraft"
    IN_TRANSIT           = "in_transit"
    ARRIVED              = "arrived"
    TRIP_ENDED           = "trip_ended"


class TravelState:
    # Holds all mutable state for the traveler's dynamic trip

    def __init__(self, origin_id: str, initial_budget: float):
        self.origin_id        = origin_id
        self.current_id       = origin_id
        self.initial_budget   = initial_budget
        self.budget           = initial_budget

        # Time trackers (minutes)
        self.elapsed_min          = 0.0
        self.since_lodging_min    = 0.0   # resets on each lodging
        self.since_meal_min       = 0.0   # resets on each meal

        # Route tracking
        self.visited              = {origin_id}
        self.total_km             = 0.0
        self.subsidized_km        = 0.0

        # Current leg (set when choosing destination/aircraft)
        self.pending_destination  = None   # Vertice — chosen next airport
        self.pending_arista       = None   # Arista — chosen route
        self.pending_aircraft     = None   # str — chosen aircraft type

        # Phase
        self.phase = Phase.OPTIONAL_ACTIVITIES

        # Log — all decisions recorded here for the final report
        self.log: list[dict] = []

    # --- Budget helpers ---

    def jobs_available(self) -> bool:
        # Returns True when budget has dropped below the threshold
        return self.budget < self.initial_budget * 0.35

    def spend(self, amount: float, reason: str):
        # Deducts amount from budget and logs the expense
        self.budget = round(self.budget - amount, 2)
        self.log.append({"type": "expense", "reason": reason, "amount": round(amount, 2),
                         "budget_after": self.budget})

    def earn(self, amount: float, reason: str):
        # Adds amount to budget and logs the income
        self.budget = round(self.budget + amount, 2)
        self.log.append({"type": "income", "reason": reason, "amount": round(amount, 2),
                         "budget_after": self.budget})

    # --- Time helpers ---

    def advance_time(self, minutes: float):
        # Advances all time counters by the given minutes
        self.elapsed_min       = round(self.elapsed_min       + minutes, 2)
        self.since_lodging_min = round(self.since_lodging_min + minutes, 2)
        self.since_meal_min    = round(self.since_meal_min    + minutes, 2)

    def needs_lodging(self, lodging_interval_h: int) -> bool:
        # Checks if 20h (or configured interval) have elapsed since last lodging
        return self.since_lodging_min >= lodging_interval_h * 60

    def needs_meal(self, food_interval_h: int) -> bool:
        # Checks if 8h (or configured interval) have elapsed since last meal
        return self.since_meal_min >= food_interval_h * 60

    def reset_lodging_timer(self):
        # Resets lodging timer after a stay
        self.since_lodging_min = 0.0

    def reset_meal_timer(self):
        # Resets meal timer after eating
        self.since_meal_min = 0.0

    # --- Subsidized route constraint ---

    def can_use_subsidized(self, route_km: float) -> bool:
        # Enforces: subsidized distance <= 20% of total trip distance
        future_total      = self.total_km + route_km
        future_subsidized = self.subsidized_km + route_km
        if future_total == 0:
            return True
        return future_subsidized / future_total <= 0.20

    def record_leg(self, km: float, subsidized: bool):
        # Updates distance counters after completing a flight leg
        self.total_km      = round(self.total_km + km, 2)
        if subsidized:
            self.subsidized_km = round(self.subsidized_km + km, 2)

    # --- Log helpers ---

    def log_flight(self, origin: str, destination: str, aircraft: str,
                   km: float, cost: float, time_min: float, subsidized: bool):
        # Records a completed flight leg in the trip log
        self.log.append({
            "type":        "flight",
            "origin":      origin,
            "destination": destination,
            "aircraft":    aircraft,
            "distance_km": km,
            "cost_usd":    cost,
            "time_min":    time_min,
            "subsidized":  subsidized
        })

    def log_activity(self, name: str, activity_type: str,
                     duration_min: int, cost_usd: float):
        # Records an activity (mandatory or optional) in the trip log
        self.log.append({
            "type":          "activity",
            "name":          name,
            "activity_type": activity_type,
            "duration_min":  duration_min,
            "cost_usd":      cost_usd,
            "airport":       self.current_id
        })

    def log_job(self, name: str, hours: float, earnings: float):
        # Records a job worked in the trip log
        self.log.append({
            "type":     "job",
            "name":     name,
            "hours":    hours,
            "earnings": earnings,
            "airport":  self.current_id
        })

    def log_free_time(self, minutes: float):
        # Records idle free time at the current airport
        self.log.append({
            "type":     "free_time",
            "minutes":  minutes,
            "airport":  self.current_id
        })

    def summary(self) -> dict:
        # Returns a summary snapshot of the current travel state
        return {
            "current_airport":  self.current_id,
            "budget":           self.budget,
            "initial_budget":   self.initial_budget,
            "elapsed_h":        round(self.elapsed_min / 60, 2),
            "since_lodging_h":  round(self.since_lodging_min / 60, 2),
            "since_meal_h":     round(self.since_meal_min / 60, 2),
            "visited":          list(self.visited),
            "total_km":         self.total_km,
            "subsidized_km":    self.subsidized_km,
            "phase":            self.phase.value
        }
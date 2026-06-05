from models.graph import Grafo
from algorithms.dijkstra import Dijkstra
from algorithms.travel_state import TravelState, Phase


class InterruptionService:
    # Handles route blocking, rerouting and itinerary recalculation (R4)

    def __init__(self, grafo: Grafo):
        self.grafo    = grafo
        self.blocked  = []   # list of (origin, destination) tuples currently blocked

    # --- Route blocking ---

    def block_route(self, origin_id: str, destination_id: str) -> dict:
        # Blocks a route and returns the event descriptor
        success = self.grafo.bloquear_ruta(origin_id, destination_id)
        if not success:
            raise ValueError(f"Route {origin_id} -> {destination_id} not found")
        self.blocked.append((origin_id, destination_id))
        return {"event": "blocked", "origin": origin_id, "destination": destination_id}

    def unblock_route(self, origin_id: str, destination_id: str) -> dict:
        # Restores a previously blocked route
        success = self.grafo.desbloquear_ruta(origin_id, destination_id)
        if not success:
            raise ValueError(f"Route {origin_id} -> {destination_id} not found")
        if (origin_id, destination_id) in self.blocked:
            self.blocked.remove((origin_id, destination_id))
        return {"event": "unblocked", "origin": origin_id, "destination": destination_id}

    def get_blocked_routes(self) -> list:
        # Returns all currently blocked (origin, destination) pairs
        return list(self.blocked)

    # --- In-transit interruption ---

    def interrupt_in_transit(self, state: TravelState) -> dict:
        # Called when a route is blocked while the traveler is flying it.
        # Returns traveler to the origin of the interrupted leg.
        if state.phase != Phase.IN_TRANSIT:
            raise ValueError("Traveler is not currently in transit")

        origin_id = state.current_id
        dest      = state.pending_destination

        # Block the active route
        self.block_route(origin_id, dest.identificador)

        # Reset pending leg — traveler returns to origin
        state.pending_destination = None
        state.pending_arista      = None
        state.pending_aircraft    = None
        state.phase               = Phase.CHOOSE_DESTINATION

        state.log.append({
            "type":        "interruption",
            "origin":      origin_id,
            "destination": dest.identificador,
            "note":        "Route blocked mid-flight — returned to origin"
        })

        return {
            "event":        "in_transit_interrupted",
            "returned_to":  origin_id,
            "blocked_leg":  f"{origin_id} -> {dest.identificador}"
        }

    # --- Itinerary recalculation ---

    def recalculate(
        self,
        state: TravelState,
        destination_id: str,
        criterion: str = "costo",
        include_secondary: bool = True
    ) -> dict:
        # Finds the best alternative route after a blocking event.
        # Returns the new path or signals no alternative exists.
        remaining_min = state.time_limit_min - state.elapsed_min   # hard time constraint (spec)
        dijkstra = Dijkstra(self.grafo)
        result   = dijkstra.run(
            origin_id         = state.current_id,
            destination_id    = destination_id,
            criterion         = criterion,
            budget            = state.budget,
            time_limit_min    = remaining_min,
            include_secondary = include_secondary
        )

        if not result["reachable"]:
            return {
                "event": "no_alternative",
                "from":  state.current_id,
                "to":    destination_id,
                "note":  "No viable alternative route within current budget and time"
            }

        return {
            "event":        "recalculated",
            "from":         state.current_id,
            "to":           destination_id,
            "criterion":    criterion,
            "path":         result["path"],
            "total_cost":   result["total_cost"],
            "total_time":   result["total_time"],
            "aircraft":     result["aircraft"]
        }

    # --- Planned itinerary impact check ---

    def check_planned_path(self, path: list, origin_id: str, destination_id: str) -> dict:
        # Checks whether any edge in a planned path is currently blocked.
        # Returns the first blocked leg found, or signals the path is still valid.
        for i in range(len(path) - 1):
            seg_origin = path[i]
            seg_dest   = path[i + 1]
            arista     = self.grafo.get_arista(seg_origin, seg_dest)
            if arista is None or arista.is_blocked:
                return {
                    "valid":       False,
                    "blocked_leg": f"{seg_origin} -> {seg_dest}",
                    "leg_index":   i
                }
        return {"valid": True, "blocked_leg": None, "leg_index": None}
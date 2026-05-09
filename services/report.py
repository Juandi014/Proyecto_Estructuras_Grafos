from models.graph import Grafo
from algorithms.travel_state import TravelState


class ReportService:
    # Builds the final trip report from TravelState log (R5)

    def __init__(self, grafo: Grafo):
        self.grafo = grafo

    def build(self, state: TravelState) -> dict:
        # Assembles the complete report from the travel log
        flights    = self._extract_flights(state)
        activities = self._extract_activities(state)
        jobs       = self._extract_jobs(state)
        visited    = self._build_visited(state, flights, activities)
        totals     = self._build_totals(state, flights, activities, jobs)
        return {
            "visited":    visited,
            "flights":    flights,
            "activities": activities,
            "jobs":       jobs,
            "totals":     totals
        }

    # --- Section builders ---

    def _extract_flights(self, state: TravelState) -> list:
        # Returns list of all flown legs from the log
        result = []
        for entry in state.log:
            if entry["type"] != "flight":
                continue
            origin  = self.grafo.get_vertice(entry["origin"])
            dest    = self.grafo.get_vertice(entry["destination"])
            result.append({
                "origin_iata":      entry["origin"],
                "origin_city":      origin.city    if origin else "—",
                "destination_iata": entry["destination"],
                "destination_city": dest.city      if dest   else "—",
                "aircraft":         entry["aircraft"],
                "distance_km":      entry["distance_km"],
                "time_min":         entry["time_min"],
                "cost_usd":         entry["cost_usd"],
                "subsidized":       entry["subsidized"]
            })
        return result

    def _extract_activities(self, state: TravelState) -> list:
        # Returns all activities (mandatory and optional) from the log
        result = []
        for entry in state.log:
            if entry["type"] != "activity":
                continue
            airport = self.grafo.get_vertice(entry["airport"])
            result.append({
                "name":          entry["name"],
                "activity_type": entry["activity_type"],
                "airport_iata":  entry["airport"],
                "airport_city":  airport.city if airport else "—",
                "duration_min":  entry["duration_min"],
                "cost_usd":      entry["cost_usd"]
            })
        return result

    def _extract_jobs(self, state: TravelState) -> list:
        # Returns all jobs worked from the log
        result = []
        for entry in state.log:
            if entry["type"] != "job":
                continue
            airport = self.grafo.get_vertice(entry["airport"])
            result.append({
                "name":         entry["name"],
                "airport_iata": entry["airport"],
                "airport_city": airport.city if airport else "—",
                "hours":        entry["hours"],
                "earnings_usd": entry["earnings"]
            })
        return result

    def _build_visited(
        self,
        state: TravelState,
        flights: list,
        activities: list
    ) -> list:
        # Groups cost and time per visited airport from flights and activities
        stay_cost  = {iata: 0.0 for iata in state.visited}
        stay_time  = {iata: 0.0 for iata in state.visited}

        # Accumulate flight costs to destination airport
        for f in flights:
            dest = f["destination_iata"]
            if dest in stay_cost:
                stay_cost[dest] = round(stay_cost[dest] + f["cost_usd"], 2)
                stay_time[dest] = round(stay_time[dest] + f["time_min"], 2)

        # Accumulate activity costs and durations to their airport
        for a in activities:
            iata = a["airport_iata"]
            if iata in stay_cost:
                stay_cost[iata] = round(stay_cost[iata] + a["cost_usd"], 2)
                stay_time[iata] = round(stay_time[iata] + a["duration_min"], 2)

        result = []
        for iata in state.visited:
            airport = self.grafo.get_vertice(iata)
            result.append({
                "iata":       iata,
                "name":       airport.name    if airport else "—",
                "city":       airport.city    if airport else "—",
                "country":    airport.country if airport else "—",
                "is_hub":     airport.is_hub  if airport else False,
                "stay_min":   stay_time[iata],
                "total_cost": stay_cost[iata]
            })
        return result

    def _build_totals(
        self,
        state: TravelState,
        flights: list,
        activities: list,
        jobs: list
    ) -> dict:
        # Computes trip-level financial and time totals
        total_spent  = round(sum(f["cost_usd"]      for f in flights)    +
                             sum(a["cost_usd"]      for a in activities), 2)
        total_earned = round(sum(j["earnings_usd"]  for j in jobs),       2)
        return {
            "initial_budget":    state.initial_budget,
            "total_spent":       total_spent,
            "total_earned":      total_earned,
            "final_balance":     round(state.budget, 2),
            "total_time_min":    round(state.elapsed_min, 2),
            "total_time_h":      round(state.elapsed_min / 60, 2),
            "total_km":          state.total_km,
            "subsidized_km":     state.subsidized_km,
            "destinations_count": len(state.visited) - 1,   # exclude origin
            "flights_count":     len(flights),
            "jobs_count":        len(jobs)
        }

    # --- Text renderer (UI-agnostic plain text summary) ---

    def render_text(self, report: dict) -> str:
        # Returns a formatted plain-text version of the full report
        lines = []
        t = report["totals"]

        lines.append("=" * 60)
        lines.append("           SKYROUTE PLANNER — TRIP REPORT")
        lines.append("=" * 60)

        lines.append("\n[ VISITED AIRPORTS ]")
        for v in report["visited"]:
            hub = "HUB" if v["is_hub"] else "SEC"
            lines.append(f"  {v['iata']} ({hub}) — {v['city']}, {v['country']}")
            lines.append(f"    Stay: {v['stay_min']:.0f} min | Cost: ${v['total_cost']:.2f}")

        lines.append("\n[ FLIGHTS ]")
        for f in report["flights"]:
            sub = " [SUBSIDIZED]" if f["subsidized"] else ""
            lines.append(
                f"  {f['origin_iata']} -> {f['destination_iata']}"
                f"  |  {f['aircraft']}"
                f"  |  {f['distance_km']} km"
                f"  |  {f['time_min']:.0f} min"
                f"  |  ${f['cost_usd']:.2f}{sub}"
            )

        lines.append("\n[ ACTIVITIES ]")
        for a in report["activities"]:
            lines.append(
                f"  [{a['activity_type']:10}] {a['name']}"
                f"  @{a['airport_iata']}"
                f"  |  {a['duration_min']} min"
                f"  |  ${a['cost_usd']:.2f}"
            )

        if report["jobs"]:
            lines.append("\n[ JOBS WORKED ]")
            for j in report["jobs"]:
                lines.append(
                    f"  {j['name']}  @{j['airport_iata']}"
                    f"  |  {j['hours']}h"
                    f"  |  +${j['earnings_usd']:.2f}"
                )

        lines.append("\n[ TOTALS ]")
        lines.append(f"  Initial budget   : ${t['initial_budget']:.2f}")
        lines.append(f"  Total spent      : ${t['total_spent']:.2f}")
        lines.append(f"  Total earned     : ${t['total_earned']:.2f}")
        lines.append(f"  Final balance    : ${t['final_balance']:.2f}")
        lines.append(f"  Total time       : {t['total_time_h']:.1f}h  ({t['total_time_min']:.0f} min)")
        lines.append(f"  Total distance   : {t['total_km']} km  (subsidized: {t['subsidized_km']} km)")
        lines.append(f"  Destinations     : {t['destinations_count']}")
        lines.append(f"  Flights          : {t['flights_count']}")
        lines.append(f"  Jobs worked      : {t['jobs_count']}")
        lines.append("=" * 60)

        return "\n".join(lines)
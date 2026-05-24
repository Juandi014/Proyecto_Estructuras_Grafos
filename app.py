import uuid
import math
import json
from flask import Flask, jsonify, request, render_template, session
from flask.json.provider import DefaultJSONProvider


class SafeJSONProvider(DefaultJSONProvider):
    # Replaces math.inf with null so the browser receives valid JSON
    def dumps(self, obj, **kwargs):
        def _clean(o):
            if isinstance(o, float) and (math.isinf(o) or math.isnan(o)):
                return None
            if isinstance(o, dict):
                return {k: _clean(v) for k, v in o.items()}
            if isinstance(o, list):
                return [_clean(i) for i in o]
            return o
        return json.dumps(_clean(obj), **kwargs)
from services.json_loader import JSONLoader
from services.interruption import InterruptionService
from services.report import ReportService
from algorithms.dijkstra import Dijkstra
from algorithms.dfs_coverage import DFSCoverage
from algorithms.dynamic_planner import DynamicPlanner
from algorithms.travel_state import Phase

app = Flask(__name__, template_folder="ui/templates", static_folder="ui/static")
app.json_provider_class = SafeJSONProvider
app.json = SafeJSONProvider(app)
app.secret_key = "skyroute-dev-key"

# ── Global graph (loaded once at startup) ─────────────────────────────────────
GRAPH_PATH      = "data/network.json"
grafo           = JSONLoader(GRAPH_PATH).load()
interruption_svc = InterruptionService(grafo)

# ── In-memory session store for dynamic planner instances (R3) ────────────────
_planner_sessions: dict[str, DynamicPlanner] = {}

# ─────────────────────────────────────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    # Serves the single-page application
    return render_template("index.html")

# ─────────────────────────────────────────────────────────────────────────────
# R1 — Graph data
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/graph")
def get_graph():
    # Returns full graph in Cytoscape.js format
    nodes = []
    edges = []
    blocked = [(o, d) for o, d in interruption_svc.get_blocked_routes()]

    for v in grafo.vertices:
        nodes.append({"data": {
            "id":       v.identificador,
            "label":    v.identificador,
            "name":     v.name,
            "city":     v.city,
            "country":  v.country,
            "is_hub":   v.is_hub,
            "timezone": v.timezone,
            "airlines": v.airlines
        }})
        for a in v.adyacencias:
            dest = a.vertice_destino.identificador
            edge_id = f"{v.identificador}-{dest}"
            edges.append({"data": {
                "id":          edge_id,
                "source":      v.identificador,
                "target":      dest,
                "distance_km": a.distance_km,
                "aircraft":    a.aircraft_types,
                "subsidized":  a.is_subsidized(),
                "blocked":     a.is_blocked,
                "min_stay":    a.min_stay_min
            }})

    return jsonify({"nodes": nodes, "edges": edges,
                    "blocked_routes": blocked})

@app.route("/api/airport/<iata>")
def get_airport(iata):
    # Returns full airport detail for the info panel
    v = grafo.get_vertice(iata.upper())
    if not v:
        return jsonify({"error": f"Airport '{iata}' not found"}), 404
    return jsonify(v.to_dict())

@app.route("/api/aircraft-rates", methods=["GET", "PUT"])
def aircraft_rates():
    # GET returns current rates; PUT overwrites them globally
    if request.method == "GET":
        return jsonify(grafo.aircraft_rates)
    data = request.get_json()
    grafo.apply_aircraft_rates(data)
    return jsonify({"ok": True, "rates": grafo.aircraft_rates})

# ─────────────────────────────────────────────────────────────────────────────
# R2 — Basic planning
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/plan/route", methods=["POST"])
def plan_route():
    # Dijkstra: best route from origin to destination by one or more criteria
    # Body: { origin, destination, criteria[], budget?, time_limit_min?,
    #         include_secondary, allowed_aircraft[] }
    body       = request.get_json()
    origin     = body.get("origin", "").upper()
    destination = body.get("destination", "").upper()
    criteria   = body.get("criteria", ["distancia"])
    budget     = float(body.get("budget", float("inf")))
    time_limit = float(body.get("time_limit_min", float("inf")))
    inc_sec    = body.get("include_secondary", True)

    dk      = Dijkstra(grafo)
    results = {}
    for c in criteria:
        try:
            results[c] = dk.run(origin, destination, c, budget, time_limit, inc_sec)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
    return jsonify(results)

@app.route("/api/plan/coverage", methods=["POST"])
def plan_coverage():
    # DFS: max destinations by budget (R2a) and by time (R2b)
    # Body: { origin, budget, time_limit_min, allowed_aircraft[], include_secondary }
    body       = request.get_json()
    origin     = body.get("origin", "").upper()
    budget     = float(body.get("budget", 0))
    time_limit = float(body.get("time_limit_min", float("inf")))
    allowed_ac = body.get("allowed_aircraft") or None
    inc_sec    = body.get("include_secondary", True)

    dfs = DFSCoverage(grafo)
    try:
        by_budget = dfs.run_max_by_budget(origin, budget, allowed_ac, inc_sec)
        by_time   = dfs.run_max_by_time(origin, time_limit, allowed_ac, inc_sec)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"by_budget": by_budget, "by_time": by_time})

# ─────────────────────────────────────────────────────────────────────────────
# R3 — Advanced dynamic planning
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/plan/advanced/start", methods=["POST"])
def advanced_start():
    # Creates a new dynamic planner session
    # Body: { origin, initial_budget }
    body    = request.get_json()
    origin  = body.get("origin", "").upper()
    budget  = float(body.get("initial_budget", 0))

    try:
        planner = DynamicPlanner(grafo, origin, budget)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    sid = str(uuid.uuid4())
    _planner_sessions[sid] = planner
    return jsonify({"session_id": sid,
                    "situation": planner.get_situation()})

@app.route("/api/plan/advanced/<sid>/situation")
def advanced_situation(sid):
    # Returns the current situation for an active session
    planner = _get_session(sid)
    if not planner:
        return jsonify({"error": "Session not found"}), 404
    return jsonify(planner.get_situation())

@app.route("/api/plan/advanced/<sid>/action", methods=["POST"])
def advanced_action(sid):
    # Dispatches a traveler action within the session
    # Body: { action, ...params }
    # Actions: confirm_lodging | confirm_meal | do_activity | skip_activities |
    #          do_job | skip_jobs | choose_destination | choose_aircraft |
    #          complete_flight | end_trip
    planner = _get_session(sid)
    if not planner:
        return jsonify({"error": "Session not found"}), 404

    body   = request.get_json()
    action = body.get("action")

    try:
        _dispatch_action(planner, action, body)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    situation = planner.get_situation()

    # Auto-attach report when trip ends
    if planner.state.phase == Phase.TRIP_ENDED:
        report_svc = ReportService(grafo)
        report     = report_svc.build(planner.state)
        situation["report"] = report

    return jsonify(situation)

@app.route("/api/plan/advanced/<sid>/report")
def advanced_report(sid):
    # Generates the full trip report for a session
    planner = _get_session(sid)
    if not planner:
        return jsonify({"error": "Session not found"}), 404
    svc    = ReportService(grafo)
    report = svc.build(planner.state)
    return jsonify(report)

# ─────────────────────────────────────────────────────────────────────────────
# R4 — Interruptions
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/interrupt", methods=["POST"])
def interrupt_route():
    # Blocks a route and optionally recalculates for an active session
    # Body: { origin, destination, session_id?, destination_goal?, criterion? }
    body   = request.get_json()
    origin = body.get("origin", "").upper()
    dest   = body.get("destination", "").upper()

    try:
        event = interruption_svc.block_route(origin, dest)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    result = {"event": event}

    # If traveler is in-transit on this exact leg, redirect to origin
    sid = body.get("session_id")
    if sid:
        planner = _get_session(sid)
        if planner and planner.state.phase == Phase.IN_TRANSIT:
            pend_dest = planner.state.pending_destination
            if pend_dest and pend_dest.identificador == dest and planner.state.current_id == origin:
                interrupt_event = interruption_svc.interrupt_in_transit(planner.state)
                result["in_transit_interrupt"] = interrupt_event
                result["situation"] = planner.get_situation()

    return jsonify(result)

@app.route("/api/interrupt/unblock", methods=["POST"])
def unblock_route():
    # Restores a blocked route
    # Body: { origin, destination }
    body = request.get_json()
    try:
        event = interruption_svc.unblock_route(
            body.get("origin", "").upper(),
            body.get("destination", "").upper()
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(event)

@app.route("/api/interrupt/recalculate", methods=["POST"])
def recalculate_route():
    # Recalculates best path after a blocking event for an active session
    # Body: { session_id, destination_goal, criterion? }
    body      = request.get_json()
    sid       = body.get("session_id")
    dest_goal = body.get("destination_goal", "").upper()
    criterion = body.get("criterion", "costo")

    planner = _get_session(sid)
    if not planner:
        return jsonify({"error": "Session not found"}), 404

    result = interruption_svc.recalculate(planner.state, dest_goal, criterion)
    return jsonify(result)

@app.route("/api/interrupt/blocked")
def get_blocked():
    # Returns all currently blocked routes
    return jsonify({"blocked": interruption_svc.get_blocked_routes()})

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_session(sid: str) -> DynamicPlanner | None:
    # Returns the planner session by ID or None
    return _planner_sessions.get(sid)

def _dispatch_action(planner: DynamicPlanner, action: str, body: dict):
    # Routes action string to the correct planner method
    if action == "confirm_lodging":
        planner.confirm_lodging()
    elif action == "confirm_meal":
        planner.confirm_meal()
    elif action == "do_activity":
        planner.do_activity(body["activity_name"])
    elif action == "skip_activities":
        planner.skip_activities()
    elif action == "do_job":
        planner.do_job(body["job_name"], float(body["hours"]))
    elif action == "skip_jobs":
        planner.skip_jobs()
    elif action == "choose_destination":
        planner.choose_destination(body["airport_id"])
    elif action == "choose_aircraft":
        planner.choose_aircraft(body["aircraft_type"])
    elif action == "complete_flight":
        planner.complete_flight()
    elif action == "end_trip":
        planner.end_trip()
    else:
        raise ValueError(f"Unknown action '{action}'")

if __name__ == "__main__":
    app.run(debug=True, port=5000)
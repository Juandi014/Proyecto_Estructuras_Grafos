// Thin wrapper around fetch() for all backend endpoints

const API = (() => {
  const BASE = '';

  async function _req(method, path, body) {
    const opts = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) opts.body = JSON.stringify(body);
    const res  = await fetch(BASE + path, opts);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Request failed');
    return data;
  }

  return {
    // R1 — graph
    getGraph:         ()           => _req('GET',  '/api/graph'),
    getAirport:       (iata)       => _req('GET',  `/api/airport/${iata}`),
    getAircraftRates: ()           => _req('GET',  '/api/aircraft-rates'),
    putAircraftRates: (rates)      => _req('PUT',  '/api/aircraft-rates', rates),

    // R2 — basic planning
    planRoute:    (body) => _req('POST', '/api/plan/route',    body),
    planCoverage: (body) => _req('POST', '/api/plan/coverage', body),

    // R3 — advanced dynamic planning
    advancedStart:     (body)        => _req('POST', '/api/plan/advanced/start',              body),
    advancedSituation: (sid)         => _req('GET',  `/api/plan/advanced/${sid}/situation`),
    advancedAction:    (sid, body)   => _req('POST', `/api/plan/advanced/${sid}/action`,      body),
    advancedReport:    (sid)         => _req('GET',  `/api/plan/advanced/${sid}/report`),

    // R4 — interruptions
    blockRoute:        (origin, destination) => _req('POST', '/api/interrupt',         { origin, destination }),
    unblockRoute:      (origin, destination) => _req('POST', '/api/interrupt/unblock', { origin, destination }),
    recalculate:       (body)                => _req('POST', '/api/interrupt/recalculate', body),
    getBlocked:        ()                    => _req('GET',  '/api/interrupt/blocked'),

    // R4 — in-transit interrupt
    blockRouteSession: (origin, destination, session_id) =>
      _req('POST', '/api/interrupt', { origin, destination, session_id }),

    // Graph upload
    loadGraph: async (file) => {
      const fd  = new FormData();
      fd.append('file', file);
      const res  = await fetch('/api/load-graph', { method: 'POST', body: fd });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Upload failed');
      return data;
    },
  };
})();
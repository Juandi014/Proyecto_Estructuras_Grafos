// All UI logic: tabs, forms, dynamic planner state machine, report renderer

window.App = (() => {
  // ── State ──────────────────────────────────────────────────────────────────
  let graphData        = null;
  let sessionId        = null;
  let selectedDest     = null;
  let selectedAircraft = null;
  let _phaseHistory    = [];

  // ── Init / upload screen ───────────────────────────────────────────────────

  let _booted = false;

  function init() {
    const overlay    = document.getElementById('upload-overlay');
    const fileInput  = document.getElementById('json-file-input');
    const dropZone   = document.getElementById('drop-zone');
    const loadBtn    = document.getElementById('upload-load-btn');
    const defaultBtn = document.getElementById('use-default-btn');
    const statusEl   = document.getElementById('upload-status');

    // Drag-and-drop support
    dropZone.addEventListener('dragover', e => {
      e.preventDefault();
      dropZone.classList.add('drag-over');
    });
    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
    dropZone.addEventListener('drop', e => {
      e.preventDefault();
      dropZone.classList.remove('drag-over');
      const file = e.dataTransfer.files[0];
      if (file) {
        fileInput.files = e.dataTransfer.files;
        _activateLoadBtn(file.name);
      }
    });

    fileInput.addEventListener('change', () => {
      if (fileInput.files[0]) _activateLoadBtn(fileInput.files[0].name);
    });

    loadBtn.addEventListener('click', () => _doLoad(fileInput.files[0], statusEl));
    defaultBtn.addEventListener('click', () => _doLoad(null, statusEl));

    function _activateLoadBtn(name) {
      loadBtn.textContent = `Load "${name}"`;
      loadBtn.disabled    = false;
    }
  }

  async function _doLoad(file, statusEl) {
    statusEl.style.color = 'var(--text-dim)';
    statusEl.textContent  = file ? 'Uploading…' : 'Loading default graph…';
    try {
      if (file) await API.loadGraph(file);
      document.getElementById('upload-overlay').classList.add('hidden');
      if (_booted) {
        await _reloadGraph();
      } else {
        _booted = true;
        await boot();
      }
    } catch (e) {
      statusEl.style.color = 'var(--blocked-color)';
      statusEl.textContent  = e.message;
    }
  }

  function showUpload() {
    const fileInput = document.getElementById('json-file-input');
    const loadBtn   = document.getElementById('upload-load-btn');
    const statusEl  = document.getElementById('upload-status');
    fileInput.value       = '';
    statusEl.textContent  = '';
    loadBtn.textContent   = 'Load File';
    loadBtn.disabled      = true;
    document.getElementById('upload-overlay').classList.remove('hidden');
  }

  // ── Boot ───────────────────────────────────────────────────────────────────

  async function boot() {
    _setupTabs();
    _setupInterruptPanel();
    Graph.init('cy', _onNodeClick);
    graphData = await API.getGraph();
    Graph.load(graphData);
    _updateStats();
    _populateAirportSelects();
    await _loadAircraftRates();
  }

  async function _reloadGraph() {
    graphData = await API.getGraph();
    Graph.load(graphData);
    _updateStats();
    _populateAirportSelects();
    // Reset active session state
    sessionId        = null;
    selectedDest     = null;
    selectedAircraft = null;
    _phaseHistory    = [];
    document.getElementById('adv-log').innerHTML = '';
    document.getElementById('adv-session').style.display   = 'none';
    document.getElementById('adv-start-form').style.display = '';
    document.getElementById('report-content').innerHTML =
      '<p style="font-size:11px;color:var(--text-faint);text-align:center;padding:24px">Complete a trip to see the report</p>';
    _toast('Graph reloaded successfully', 'success');
  }

  // ── Stats bar ──────────────────────────────────────────────────────────────

  function _updateStats() {
    const blocked = graphData.blocked_routes.length;
    document.getElementById('stat-airports').textContent = graphData.nodes.length;
    document.getElementById('stat-routes').textContent   = graphData.edges.length;
    document.getElementById('stat-blocked').textContent  = blocked;
  }

  // ── Tabs ───────────────────────────────────────────────────────────────────

  function _setupTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const panel = btn.closest('.tab-panel-root');
        panel.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        panel.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById(btn.dataset.tab).classList.add('active');
      });
    });
  }

  // ── Airport selects ────────────────────────────────────────────────────────

  function _populateAirportSelects() {
    const selects = document.querySelectorAll('.airport-select');
    const options = graphData.nodes
      .sort((a, b) => a.data.id.localeCompare(b.data.id))
      .map(n => `<option value="${n.data.id}">${n.data.id} — ${n.data.city}</option>`)
      .join('');
    selects.forEach(s => s.innerHTML = `<option value="">Select airport…</option>${options}`);
  }

  // ── Node click → airport info ──────────────────────────────────────────────

  async function _onNodeClick(iata) {
    Graph.focusNode(iata);
    try {
      const data = await API.getAirport(iata);
      _renderAirportInfo(data);
      // Switch to info tab on left panel
      document.querySelector('[data-tab="tab-info"]').click();
    } catch(e) { _toast(e.message, 'error'); }
  }

  function _renderAirportInfo(d) {
    const hub = d.esHub
      ? `<span class="badge badge-hub">HUB</span>`
      : `<span class="badge badge-sec">Secondary</span>`;

    const acts = d.actividades.map(a =>
      `<div class="info-row"><span class="key">${a.nombre}</span>
       <span class="val">${a.duracionMin}min / $${a.costoUSD}</span></div>`).join('');

    const airlines = d.aerolineas.map(a => `<span>${a}</span>`).join(', ');

    document.getElementById('airport-info').innerHTML = `
      <div class="info-card">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
          <h3>${d.id}</h3>${hub}
        </div>
        <div class="info-row"><span class="key">City</span><span class="val">${d.ciudad}, ${d.pais}</span></div>
        <div class="info-row"><span class="key">Timezone</span><span class="val">${d.zonaHoraria}</span></div>
        <div class="info-row"><span class="key">Lodging</span><span class="val">$${d.costoAlojamiento}/night</span></div>
        <div class="info-row"><span class="key">Food</span><span class="val">$${d.costoAlimentacion}/meal</span></div>
        <div class="info-row"><span class="key">Airlines</span><span class="val" style="font-size:10px">${airlines}</span></div>
      </div>
      ${d.actividades.length ? `<div class="section-label">Activities</div><div class="info-card">${acts}</div>` : ''}`;
  }

  // ── R2 — Route planning ────────────────────────────────────────────────────

  window.runRoute = async function() {
    const origin  = document.getElementById('r2-origin').value;
    const dest    = document.getElementById('r2-dest').value;
    const budget  = parseFloat(document.getElementById('r2-budget').value) || Infinity;
    const timeLim = parseFloat(document.getElementById('r2-time').value) * 60 || Infinity;
    const incSec  = document.getElementById('r2-secondary').checked;
    const criteria = [...document.querySelectorAll('.r2-criterion:checked')].map(c => c.value);

    const allowedAc = [...document.querySelectorAll('.r2-aircraft:checked')].map(c => c.value);

    if (!origin || !dest)     return _toast('Select origin and destination', 'error');
    if (!criteria.length)     return _toast('Select at least one criterion', 'error');
    if (!allowedAc.length)    return _toast('Select at least one transport type', 'error');

    const routeBtn = document.querySelector('#tab-r2 .btn-primary');
    routeBtn.disabled = true;
    routeBtn.textContent = 'Calculating…';
    try {
      const body = { origin, destination: dest, criteria, include_secondary: incSec,
                     allowed_aircraft: allowedAc };
      if (isFinite(budget))  body.budget         = budget;
      if (isFinite(timeLim)) body.time_limit_min  = timeLim;
      const res = await API.planRoute(body);
      _renderRouteResults(res);
    } catch(e) {
      _toast(e.message, 'error');
    } finally {
      routeBtn.disabled = false;
      routeBtn.textContent = 'Calculate Route';
    }
  };

  function _renderRouteResults(res) {
    const el = document.getElementById('r2-results');
    el.innerHTML = Object.entries(res).map(([c, r]) => {
      if (!r.reachable) return `<div class="route-result"><div class="section-label">${c}</div><p style="color:var(--blocked-color);font-size:11px">No reachable path within constraints</p></div>`;
      const pathHtml = r.path.map((n,i) =>
        `<span class="path-node" data-path='${JSON.stringify(r.path)}' onclick="App.focusPath(this.dataset.path)">${n}</span>${i < r.path.length-1 ? '<span class="path-arrow">→</span>' : ''}`
      ).join('');
      return `<div class="route-result">
        <div class="section-label" style="margin-bottom:6px">${c}</div>
        <div class="route-path">${pathHtml}</div>
        <div class="route-meta">
          <div class="meta-item"><div class="val">${r.total_dist_km?.toFixed(0)} km</div><div class="key">Distance</div></div>
          <div class="meta-item"><div class="val">$${r.total_cost?.toFixed(2)}</div><div class="key">Cost</div></div>
          <div class="meta-item"><div class="val">${(r.total_time/60).toFixed(1)}h</div><div class="key">Time</div></div>
        </div>
      </div>`;
    }).join('');
    // Highlight first result path on graph
    const first = Object.values(res).find(r => r.reachable);
    if (first) Graph.highlightPath(first.path);
  }

  // ── R2 — Coverage ─────────────────────────────────────────────────────────

  window.runCoverage = async function() {
    const origin  = document.getElementById('cov-origin').value;
    const budget  = parseFloat(document.getElementById('cov-budget').value) || 0;
    const timeLim = parseFloat(document.getElementById('cov-time').value) * 60 || Infinity;
    const incSec  = document.getElementById('cov-secondary').checked;
    const allowedAcCov = [...document.querySelectorAll('.cov-aircraft:checked')].map(c => c.value);

    if (!origin)              return _toast('Select origin airport', 'error');
    if (!allowedAcCov.length) return _toast('Select at least one transport type', 'error');
    if (!budget && !isFinite(timeLim)) return _toast('Enter a budget or time limit', 'error');

    const btn = document.querySelector('#tab-coverage .btn-primary');
    btn.disabled = true;
    btn.textContent = 'Searching…';

    try {
      const covBody = { origin, include_secondary: incSec, allowed_aircraft: allowedAcCov };
      if (isFinite(budget))  covBody.budget         = budget;
      if (isFinite(timeLim)) covBody.time_limit_min  = timeLim;
      const res = await API.planCoverage(covBody);
      _renderCoverageResults(res);
    } catch(e) {
      _toast(e.message, 'error');
    } finally {
      btn.disabled = false;
      btn.textContent = 'Find Coverage';
    }
  };

  function _renderCoverageResults(res) {
    const el = document.getElementById('cov-results');
    const render = (label, r) => {
      const pathHtml = r.path.map((n,i) =>
        `<span class="path-node">${n}</span>${i<r.path.length-1?'<span class="path-arrow">→</span>':''}`
      ).join('');
      return `<div class="route-result">
        <div class="section-label">${label} — ${r.destinations} destinations</div>
        <div class="route-path">${pathHtml}</div>
        <div class="route-meta">
          <div class="meta-item"><div class="val">${r.destinations}</div><div class="key">Stops</div></div>
          <div class="meta-item"><div class="val">$${r.total_cost?.toFixed(2)}</div><div class="key">Cost</div></div>
          <div class="meta-item"><div class="val">${(r.total_time/60).toFixed(1)}h</div><div class="key">Time</div></div>
        </div>
      </div>`;
    };
    el.innerHTML = render('Max by Budget', res.by_budget) + render('Max by Time', res.by_time);
    if (res.by_budget.path.length) Graph.highlightPath(res.by_budget.path);
  }

  // ── R3 — Advanced planner ─────────────────────────────────────────────────

  window.startAdvanced = async function() {
    const origin = document.getElementById('adv-origin').value;
    const budget = parseFloat(document.getElementById('adv-budget').value);
    if (!origin || !budget) return _toast('Fill origin and budget', 'error');

    try {
      const advTimeLim = parseFloat(document.getElementById('adv-time')?.value) * 60;
      const advBody = { origin, initial_budget: budget };
      if (isFinite(advTimeLim)) advBody.time_limit_min = advTimeLim;
      const res = await API.advancedStart(advBody);
      sessionId = res.session_id;
      _phaseHistory = [];
      document.getElementById('adv-log').innerHTML = '';
      _renderSituation(res.situation);
      document.getElementById('adv-start-form').style.display = 'none';
      document.getElementById('adv-session').style.display = 'block';
      Graph.focusNode(origin);
      _toast('Trip started!', 'success');
    } catch(e) { _toast(e.message, 'error'); }
  };

  async function _action(body) {
    if (!sessionId) return;
    try {
      const sit = await API.advancedAction(sessionId, body);
      _renderSituation(sit);
      if (sit.report) _renderReport(sit.report);
      const toasts = {
        'do_activity':    `Activity completed!`,
        'confirm_lodging':'Lodging paid',
        'confirm_meal':   'Meal paid',
        'do_job':         'Job worked — earnings added',
        'complete_flight':'Landed!',
      };
      if (toasts[body.action]) _toast(toasts[body.action], 'success');
    } catch(e) { _toast(e.message, 'error'); }
  }

  function _renderSituation(sit) {
    const el     = document.getElementById('adv-situation');
    const s      = sit.state;
    const phase  = sit.phase;
    const ap     = sit.airport;

    // Update graph focus — flight animation handles in-transit visual
    if (s) Graph.focusNode(s.current_airport);

    // Budget bar
    const pct = s ? Math.max(0, (s.budget / s.initial_budget) * 100) : 100;
    const barClass = pct < 35 ? 'warn' : '';
    const budgetBar = s ? `
      <div class="budget-bar-wrap">
        <div class="budget-bar-label">
          <span>$${s.budget?.toFixed(2)} remaining</span>
          <span class="pct">${pct.toFixed(0)}%</span>
        </div>
        <div class="budget-bar-track">
          <div class="budget-bar-fill ${barClass}" style="width:${pct}%"></div>
        </div>
      </div>` : '';

    // Phase banner
    const phaseLabel = {
      'optional_activities': 'Choose Activities',
      'jobs': 'Jobs Available',
      'choose_destination': 'Choose Next Destination',
      'choose_aircraft': 'Choose Aircraft',
      'in_transit': 'In Transit…',
      'mandatory_lodging': '⚠ Lodging Required',
      'mandatory_food': '⚠ Meal Required',
      'arrived': 'Arrived',
      'trip_ended': 'Trip Ended'
    }[phase] || phase;

    const bannerClass = {
      'in_transit': 'flight', 'choose_aircraft': 'flight',
      'optional_activities': 'activity', 'jobs': 'job',
      'mandatory_lodging': 'mandatory', 'mandatory_food': 'mandatory'
    }[phase] || 'activity';

    let content = `${budgetBar}
      <div class="phase-banner ${bannerClass}">${phaseLabel}</div>`;

    if (ap?.id) content += `<div class="info-row" style="padding:6px 0"><span class="key">At</span><span class="val">${ap.id} — ${ap.ciudad}</span></div>`;
    if (s)      content += `<div class="info-row"><span class="key">Elapsed</span><span class="val">${s.elapsed_h?.toFixed(1)}h</span></div>`;

    // Phase-specific controls
    if (phase === 'mandatory_lodging') {
      content += `<button class="btn btn-warn btn-block" onclick="App.action({action:'confirm_lodging'})">Pay Lodging ($${ap?.costoAlojamiento})</button>`;
    }
    else if (phase === 'mandatory_food') {
      content += `<button class="btn btn-warn btn-block" onclick="App.action({action:'confirm_meal'})">Pay Meal ($${ap?.costoAlimentacion})</button>`;
    }
    else if (phase === 'optional_activities') {
      const acts = (sit.activities || []).map(a => `
        <div class="list-item">
          <div>
            <div class="name">${a.nombre}</div>
            <div class="duration">${a.duracionMin}min</div>
          </div>
          <span class="cost">$${a.costoUSD}</span>
          <button class="btn btn-ghost btn-sm" onclick="App.action({action:'do_activity',activity_name:'${a.nombre}'})">Do</button>
        </div>`).join('');
      content += acts || '<p style="font-size:11px;color:var(--text-dim)">No optional activities here.</p>';
      content += `<button class="btn btn-ghost btn-block" onclick="App.action({action:'skip_activities'})">Skip →</button>`;
    }
    else if (phase === 'jobs') {
      if (sit.jobs_available) {
        const jobs = (sit.jobs || []).map(j => `
          <div class="list-item">
            <div>
              <div class="name">${j.nombre}</div>
              <div class="duration">max ${j.maxHoras}h @ $${j.tarifaHora}/h</div>
            </div>
            <button class="btn btn-ghost btn-sm" onclick="App.promptJob('${j.nombre}',${j.maxHoras})">Work</button>
          </div>`).join('');
        content += `<div class="section-label">Jobs (budget &lt; 35%)</div>${jobs}`;
      } else {
        content += `<p style="font-size:11px;color:var(--text-dim)">Jobs unavailable (budget &gt; 35%).</p>`;
      }
      content += `<button class="btn btn-ghost btn-block" onclick="App.action({action:'skip_jobs'})">Continue →</button>`;
    }
    else if (phase === 'choose_destination') {
      const suggestion = sit.suggestion;
      if (suggestion) content += `<div class="suggestion-chip">💡 Suggested: <b>${suggestion}</b></div>`;
      const dests = (sit.destinations || []).map(d => {
        const opts = d.aircraft_options.map(o =>
          `<div class="ac-option" id="ac-${d.airport_id}-${o.aircraft.replace(/\s/g,'_')}"
            onclick="App.selectAircraft('${d.airport_id}','${o.aircraft}')">
            <span>${o.aircraft}</span>
            <span>$${o.cost_usd?.toFixed(2)} / ${(o.time_min/60).toFixed(1)}h</span>
          </div>`).join('');
        return `<div class="dest-card" id="dest-${d.airport_id}" onclick="App.selectDest('${d.airport_id}')">
          <div class="dest-id">${d.airport_id}</div>
          <div class="dest-city">${_cityOf(d.airport_id)} — ${d.distance_km}km${d.subsidized?' ✦ subsidized':''}</div>
          <div class="aircraft-opts">${opts}</div>
        </div>`;
      }).join('');
      content += dests || '<p style="font-size:11px;color:var(--text-dim)">No reachable destinations.</p>';
      content += `<button class="btn btn-primary btn-block" id="btn-fly" style="display:none" onclick="App.fly()">✈ Fly</button>`;
      content += `<button class="btn btn-ghost btn-block" onclick="App.action({action:'end_trip'})">End Trip</button>`;
    }
    else if (phase === 'in_transit') {
      const etaH = ((sit.time_min || 0) / 60).toFixed(1);
      content += `<p style="font-size:11px;color:var(--text-dim)">
        Flying to <b>${sit.destination}</b> on <b>${sit.aircraft}</b>…<br>
        ETA: ${etaH}h — watch the map ✈
      </p>`;
    }
    else if (phase === 'trip_ended') {
      content += `<button class="btn btn-primary btn-block" onclick="document.querySelector('[data-tab=tab-report]').click()">View Report →</button>`;
    }

    el.innerHTML = content;
    _appendLog(sit);
  }

  function _cityOf(iata) {
    return graphData?.nodes.find(n => n.data.id === iata)?.data.city || '';
  }

  // ── Dest / aircraft selection ──────────────────────────────────────────────

  function _selectDest(iata) {
    selectedDest = iata;
    document.querySelectorAll('.dest-card').forEach(c => c.classList.remove('selected'));
    document.getElementById(`dest-${iata}`)?.classList.add('selected');
    if (selectedAircraft) document.getElementById('btn-fly').style.display = 'block';
  }

  function _selectAircraft(destId, aircraft) {
    selectedDest     = destId;
    selectedAircraft = aircraft;
    document.querySelectorAll('.ac-option').forEach(o => o.classList.remove('selected'));
    document.getElementById(`ac-${destId}-${aircraft.replace(/\s/g,'_')}`)?.classList.add('selected');
    document.querySelectorAll('.dest-card').forEach(c => c.classList.remove('selected'));
    document.getElementById(`dest-${destId}`)?.classList.add('selected');
    document.getElementById('btn-fly').style.display = 'block';
  }

  async function _fly() {
    if (!selectedDest || !selectedAircraft) return _toast('Select destination and aircraft', 'error');
    await _action({ action: 'choose_destination', airport_id: selectedDest });

    // Send choose_aircraft and read response directly to get flight data
    const sit = await API.advancedAction(sessionId, { action: 'choose_aircraft', aircraft_type: selectedAircraft });
    _renderSituation(sit);

    if (sit.phase === 'in_transit') {
      const origin     = sit.state.current_airport;
      const dest       = sit.destination;
      // Scale flight time to UI duration: 50ms per minute, clamped between 1.5s and 6s
      const durationMs = Math.min(6000, Math.max(1500, (sit.time_min || 60) * 50));

      Graph.startFlightAnimation(
        origin, dest, durationMs,
        // onArrived — auto-complete the flight when animation finishes
        () => _action({ action: 'complete_flight' }),
        // onReturned — fired after plane animates back to origin on interrupt
        (o) => {
          _toast(`Flight interrupted — returned to ${o}`, 'error');
          // Re-fetch backend state (already reset by cancel_flight) and re-render
          if (sessionId) {
            API.advancedSituation(sessionId)
              .then(sit => { _renderSituation(sit); Graph.focusNode(o); })
              .catch(() => {});
          }
        }
      );
    }
    selectedDest = selectedAircraft = null;
  }

  function _promptJob(jobName, maxHours) {
    const hours = parseFloat(prompt(`Hours to work (max ${maxHours}):`, maxHours));
    if (!isNaN(hours) && hours > 0) _action({ action: 'do_job', job_name: jobName, hours });
  }

  function _focusPath(pathJson) {
    const path = JSON.parse(pathJson);
    Graph.highlightPath(path);
  }

  // ── Interrupt panel ────────────────────────────────────────────────────────

  function _setupInterruptPanel() {
    window.blockRoute = async function() {
      const origin = document.getElementById('int-origin').value;
      const dest   = document.getElementById('int-dest').value;
      if (!origin || !dest) return _toast('Select both airports', 'error');
      try {
        const res = await API.blockRouteSession(origin, dest, sessionId);
        Graph.setEdgeBlocked(origin, dest, true);

        // If the blocked route is the one currently being flown, return plane to origin
        const flying = Graph.getFlightRoute();
        if (flying && flying.origin === origin && flying.dest === dest) {
          Graph.interruptFlight();
          // onReturned in _fly() re-fetches situation after the 700 ms animation
        } else if (res.in_transit_interrupt) {
          // Interrupted but animation not active — update UI directly from response
          if (res.situation) _renderSituation(res.situation);
          const to = res.in_transit_interrupt.redirected_to;
          if (to) { Graph.focusNode(to); _toast(`Redirected back to ${to}`, 'error'); }
        }

        const gd = await API.getGraph();
        graphData = gd;
        _updateStats();
        _toast(`Route ${origin}→${dest} blocked`, 'error');
      } catch(e) { _toast(e.message, 'error'); }
    };

    window.unblockRoute = async function() {
      const origin = document.getElementById('int-origin').value;
      const dest   = document.getElementById('int-dest').value;
      if (!origin || !dest) return _toast('Select both airports', 'error');
      try {
        await API.unblockRoute(origin, dest);
        Graph.setEdgeBlocked(origin, dest, false);
        _toast(`Route ${origin}→${dest} restored`, 'success');
      } catch(e) { _toast(e.message, 'error'); }
    };

    window.recalculate = async function() {
      if (!sessionId) return _toast('No active session', 'error');
      const dest = document.getElementById('int-goal').value;
      if (!dest) return _toast('Select destination goal', 'error');
      try {
        const res = await API.recalculate({ session_id: sessionId, destination_goal: dest, criterion: 'costo' });
        if (res.event === 'recalculated') {
          Graph.highlightPath(res.path);
          _toast(`New path: ${res.path.join('→')}`, 'success');
        } else {
          _toast('No alternative route found', 'error');
        }
      } catch(e) { _toast(e.message, 'error'); }
    };
  }

  // ── Log ────────────────────────────────────────────────────────────────────

  function _appendLog(sit) {
    if (!sit || !sit.phase) return;
    const el = document.getElementById('adv-log');
    if (!el) return;

    const phase = sit.phase;
    const ap    = sit.airport;
    const state = sit.state;
    const loc   = ap?.id || state?.current_airport || '';

    const typeMap = {
      'mandatory_lodging':   'expense',
      'mandatory_food':      'expense',
      'in_transit':          'flight',
      'choose_aircraft':     'flight',
      'choose_destination':  'flight',
      'optional_activities': 'activity',
      'arrived':             'activity',
      'jobs':                'job',
      'trip_ended':          'income',
    };

    const textMap = {
      'mandatory_lodging':   `Lodging paid at ${loc}`,
      'mandatory_food':      `Meal paid at ${loc}`,
      'in_transit':          `Flying to ${sit.destination || '?'} on ${sit.aircraft || '?'}`,
      'choose_aircraft':     `Choosing aircraft to ${sit.destination || '?'}`,
      'choose_destination':  `Choosing next destination from ${loc}`,
      'optional_activities': `At ${loc} — pick activities`,
      'arrived':             `Arrived at ${loc}`,
      'jobs':                `Jobs available at ${loc}`,
      'trip_ended':          'Trip ended',
    };

    const text = textMap[phase];
    if (!text) return;

    _phaseHistory.unshift({ text, type: typeMap[phase] || '' });
    if (_phaseHistory.length > 6) _phaseHistory.pop();

    el.innerHTML = _phaseHistory
      .map(e => `<div class="log-entry ${e.type}">${e.text}</div>`)
      .join('');
  }

  // ── Report ─────────────────────────────────────────────────────────────────

  async function loadReport() {
    if (!sessionId) return;
    try {
      const report = await API.advancedReport(sessionId);
      _renderReport(report);
    } catch(e) { _toast(e.message, 'error'); }
  }

  window.loadReport = loadReport;

  function _renderReport(r) {
    const t = r.totals;
    document.getElementById('report-content').innerHTML = `
      <div class="report-section">
        <h4>Totals</h4>
        ${[
          ['Initial Budget',  `$${t.initial_budget?.toFixed(2)}`],
          ['Total Spent',     `$${t.total_spent?.toFixed(2)}`],
          ['Total Earned',    `+$${t.total_earned?.toFixed(2)}`],
          ['Final Balance',   `$${t.final_balance?.toFixed(2)}`],
          ['Total Time',      `${t.total_time_h?.toFixed(1)}h`],
          ['Distance',        `${t.total_km} km`],
          ['Subsidized km',   `${t.subsidized_km} km`],
          ['Destinations',    t.destinations_count],
          ['Flights',         t.flights_count],
          ['Jobs Worked',     t.jobs_count],
        ].map(([k,v]) => `<div class="total-row"><span class="tkey">${k}</span><span class="tval">${v}</span></div>`).join('')}
      </div>

      <div class="report-section">
        <h4>Visited Airports</h4>
        <table class="report-table">
          <tr><th>IATA</th><th>City</th><th>Country</th><th>Type</th><th>Stay</th><th>Cost</th></tr>
          ${r.visited.map(v => `<tr>
            <td><b>${v.iata}</b></td><td>${v.city}</td><td>${v.country}</td>
            <td>${v.is_hub ? 'HUB':'SEC'}</td>
            <td>${(v.stay_min/60).toFixed(1)}h</td>
            <td>$${v.total_cost?.toFixed(2)}</td>
          </tr>`).join('')}
        </table>
      </div>

      <div class="report-section">
        <h4>Flights</h4>
        <table class="report-table">
          <tr><th>From</th><th>To</th><th>Aircraft</th><th>km</th><th>Time</th><th>Cost</th></tr>
          ${r.flights.map(f => `<tr>
            <td>${f.origin_iata}</td><td>${f.destination_iata}</td>
            <td style="font-size:10px">${f.aircraft}</td>
            <td>${f.distance_km}</td>
            <td>${(f.time_min/60).toFixed(1)}h</td>
            <td>${f.subsidized?'<span style="color:var(--success)">FREE</span>':`$${f.cost_usd?.toFixed(2)}`}</td>
          </tr>`).join('')}
        </table>
      </div>

      <div class="report-section">
        <h4>Activities</h4>
        <table class="report-table">
          <tr><th>Name</th><th>Type</th><th>Airport</th><th>Duration</th><th>Cost</th></tr>
          ${r.activities.map(a => `<tr>
            <td>${a.name}</td><td>${a.activity_type}</td>
            <td>${a.airport_iata}</td><td>${a.duration_min}min</td>
            <td>$${a.cost_usd?.toFixed(2)}</td>
          </tr>`).join('')}
        </table>
      </div>

      ${r.jobs.length ? `<div class="report-section">
        <h4>Jobs Worked</h4>
        <table class="report-table">
          <tr><th>Job</th><th>Airport</th><th>Hours</th><th>Earned</th></tr>
          ${r.jobs.map(j => `<tr>
            <td>${j.name}</td><td>${j.airport_iata}</td>
            <td>${j.hours}h</td><td style="color:var(--success)">+$${j.earnings_usd?.toFixed(2)}</td>
          </tr>`).join('')}
        </table>
      </div>` : ''}
    `;
    document.querySelector('[data-tab="tab-report"]').click();
  }

  // ── Aircraft rates ─────────────────────────────────────────────────────────

  async function _loadAircraftRates() {
    try {
      const rates = await API.getAircraftRates();
      _renderAircraftRatesForm(rates);
    } catch(e) { /* silent on load failure */ }
  }

  function _renderAircraftRatesForm(rates) {
    const el = document.getElementById('aircraft-rates-form');
    if (!el) return;
    el.innerHTML = Object.entries(rates).map(([name, r]) => {
      const key = name.replace(/\s/g, '_');
      return `<div style="margin-bottom:10px">
        <div style="font-size:10px;font-weight:600;color:var(--text-dim);margin-bottom:4px">${name}</div>
        <div style="display:flex;gap:8px">
          <div class="field" style="margin:0;flex:1">
            <label style="font-size:10px">$/km</label>
            <input type="number" id="acr-${key}-cost" class="ac-rate-input"
              step="0.001" min="0" value="${r.cost_per_km}"
              data-aircraft="${name}" data-field="cost_per_km">
          </div>
          <div class="field" style="margin:0;flex:1">
            <label style="font-size:10px">min/km</label>
            <input type="number" id="acr-${key}-time" class="ac-rate-input"
              step="0.01" min="0" value="${r.time_per_km}"
              data-aircraft="${name}" data-field="time_per_km">
          </div>
        </div>
      </div>`;
    }).join('');
  }

  window.saveAircraftRates = async function() {
    const rates = {};
    document.querySelectorAll('.ac-rate-input').forEach(inp => {
      const name  = inp.dataset.aircraft;
      const field = inp.dataset.field;
      if (!rates[name]) rates[name] = {};
      rates[name][field] = parseFloat(inp.value);
    });
    try {
      await API.putAircraftRates(rates);
      _toast('Aircraft rates updated', 'success');
    } catch(e) { _toast(e.message, 'error'); }
  };

  // ── Toast ──────────────────────────────────────────────────────────────────

  function _toast(msg, type = '') {
    const el = document.getElementById('toast');
    el.textContent = msg;
    el.className = `show ${type}`;
    clearTimeout(el._t);
    el._t = setTimeout(() => el.className = '', 3000);
  }

  return {
    boot,
    init,
    showUpload,
    action:         _action,
    selectDest:     _selectDest,
    selectAircraft: _selectAircraft,
    fly:            _fly,
    promptJob:      _promptJob,
    focusPath:      _focusPath,
  };
})();

document.addEventListener('DOMContentLoaded', App.init);
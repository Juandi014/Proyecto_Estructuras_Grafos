// Cytoscape.js initialization and all graph visual operations

const Graph = (() => {
  let cy       = null;
  let onSelect = null;

  // Tracks the active flight animation state
  let _flight = {
    active: false, origin: null, dest: null,
    node: null, anim: null, onArrived: null, onReturned: null,
  };

  // ── Init ────────────────────────────────────────────────────────────────────

  function init(containerId, selectCallback) {
    onSelect = selectCallback;
    cy = cytoscape({
      container: document.getElementById(containerId),
      style:     _buildStyle(),
      layout:    { name: 'preset' },
      minZoom:   0.3,
      maxZoom:   3,
      wheelSensitivity: 0.3,
    });
    cy.on('tap', 'node', e => onSelect && onSelect(e.target.id()));
    cy.on('tap', e => { if (e.target === cy) _clearHighlight(); });
  }

  // ── Load data ────────────────────────────────────────────────────────────────

  function load(graphData) {
    cy.elements().remove();
    const positions = _circleLayout(graphData.nodes);
    const nodes = graphData.nodes.map(n => ({
      data: n.data,
      position: positions[n.data.id],
      classes: n.data.is_hub ? 'hub' : 'secondary'
    }));
    const edges = graphData.edges.map(e => ({
      data: e.data,
      classes: _edgeClass(e.data)
    }));
    cy.add(nodes);
    cy.add(edges);
    cy.fit(cy.nodes(), 40);
  }

  // ── Layout ───────────────────────────────────────────────────────────────────

  function _circleLayout(nodes) {
    // Hubs in outer ring, secondary in inner cluster
    const hubs = nodes.filter(n => n.data.is_hub);
    const secs = nodes.filter(n => !n.data.is_hub);
    const pos  = {};
    const cx   = 600, cy_ = 400;

    hubs.forEach((n, i) => {
      const angle = (i / hubs.length) * 2 * Math.PI - Math.PI / 2;
      pos[n.data.id] = { x: cx + Math.cos(angle) * 320, y: cy_ + Math.sin(angle) * 260 };
    });
    secs.forEach((n, i) => {
      const angle = (i / secs.length) * 2 * Math.PI - Math.PI / 2;
      const r = 140 + (i % 3) * 40;
      pos[n.data.id] = { x: cx + Math.cos(angle) * r, y: cy_ + Math.sin(angle) * r };
    });
    return pos;
  }

  // ── Highlight path ───────────────────────────────────────────────────────────

  function highlightPath(path, color = '#00d4ff') {
    _clearHighlight();
    if (!path || path.length < 2) return;
    for (let i = 0; i < path.length; i++) {
      cy.$(`#${path[i]}`).addClass('on-path');
    }
    for (let i = 0; i < path.length - 1; i++) {
      const edge = cy.edges(`[source="${path[i]}"][target="${path[i+1]}"]`);
      edge.addClass('path-edge');
    }
    cy.nodes().not('.on-path').addClass('dimmed');
    cy.edges().not('.path-edge').addClass('dimmed');
  }

  function _clearHighlight() {
    cy.elements().removeClass('on-path path-edge dimmed in-transit-pulse');
  }

  // ── Block / unblock visual ───────────────────────────────────────────────────

  function setEdgeBlocked(origin, dest, blocked) {
    const edge = cy.edges(`[source="${origin}"][target="${dest}"]`);
    if (blocked) edge.addClass('blocked').removeClass('subsidized');
    else         edge.removeClass('blocked');
  }

  // ── Legacy pulse (kept for backward compat) ──────────────────────────────────

  function pulseNode(iata) {
    cy.$(`#${iata}`).addClass('in-transit-pulse');
  }

  function stopPulse(iata) {
    cy.$(`#${iata}`).removeClass('in-transit-pulse');
  }

  // ── In-flight animation ──────────────────────────────────────────────────────

  function startFlightAnimation(origin, dest, durationMs, onArrived, onReturned) {
    // Creates a plane node at origin and animates it to dest over durationMs
    if (_flight.active) _cleanFlight();

    const oPos = cy.$(`#${origin}`).position();
    const dPos = cy.$(`#${dest}`).position();

    cy.add({
      data: { id: '__plane__', label: '✈' },
      position: { x: oPos.x, y: oPos.y },
      classes: 'flight-node',
    });

    cy.edges(`[source="${origin}"][target="${dest}"]`).addClass('in-transit');

    _flight = {
      active: true, origin, dest,
      node: cy.$('#__plane__'),
      anim: null, onArrived, onReturned,
    };

    // Animate plane node position from origin to destination
    _flight.anim = _flight.node.animation(
      { position: { x: dPos.x, y: dPos.y } },
      { duration: durationMs, complete: () => _finishFlight(false) }
    );
    _flight.anim.play();
  }

  function interruptFlight() {
    // Stops active animation and returns plane to origin
    if (!_flight.active) return;
    if (_flight.anim) _flight.anim.stop();

    const oPos = cy.$(`#${_flight.origin}`).position();
    // Animate return to origin then fire onReturned
    _flight.node.animate(
      { position: { x: oPos.x, y: oPos.y } },
      { duration: 700, complete: () => _finishFlight(true) }
    );
  }

  function isFlightActive() {
    // Returns true while a flight animation is running
    return _flight.active;
  }

  function getFlightRoute() {
    // Returns { origin, dest } of the active flight, or null
    return _flight.active ? { origin: _flight.origin, dest: _flight.dest } : null;
  }

  function _finishFlight(interrupted) {
    // Removes plane node, clears edge class, and fires the correct callback
    cy.edges(`[source="${_flight.origin}"][target="${_flight.dest}"]`).removeClass('in-transit');
    if (_flight.node && _flight.node.length) cy.remove(_flight.node);

    const { origin, onArrived, onReturned } = _flight;
    _cleanFlight();

    if (interrupted && onReturned) onReturned(origin);
    else if (!interrupted && onArrived) onArrived();
  }

  function _cleanFlight() {
    // Resets flight state to idle
    _flight = {
      active: false, origin: null, dest: null,
      node: null, anim: null, onArrived: null, onReturned: null,
    };
  }

  // ── Focus ────────────────────────────────────────────────────────────────────

  function focusNode(iata) {
    _clearHighlight();
    const node = cy.$(`#${iata}`);
    node.addClass('on-path');
    cy.animate({ fit: { eles: node.closedNeighborhood(), padding: 80 } }, { duration: 500 });
  }

  // ── Helpers ──────────────────────────────────────────────────────────────────

  function _edgeClass(data) {
    if (data.blocked)    return 'blocked';
    if (data.subsidized) return 'subsidized';
    return '';
  }

  function _buildStyle() {
    return [
      { selector: 'node',
        style: { 'label': 'data(label)', 'width': 36, 'height': 36,
          'background-color': '#1e2d45', 'border-width': 2, 'border-color': '#2a3f5f',
          'color': '#7b9fc4', 'font-size': 10, 'font-family': "'Space Mono', monospace",
          'text-valign': 'bottom', 'text-margin-y': 4, 'text-halign': 'center' } },
      { selector: 'node.hub',
        style: { 'width': 48, 'height': 48, 'background-color': '#0d1f35',
          'border-color': '#00d4ff', 'border-width': 2.5, 'color': '#00d4ff', 'font-size': 11 } },
      { selector: 'node.secondary',
        style: { 'background-color': '#0d1a28', 'border-color': '#2a3f5f' } },
      { selector: 'node.on-path',
        style: { 'background-color': '#002233', 'border-color': '#00d4ff',
          'border-width': 3, 'color': '#00d4ff' } },
      { selector: 'node.dimmed',
        style: { 'opacity': 0.2 } },
      // Plane node that flies between airports
      { selector: 'node.flight-node',
        style: { 'label': '✈', 'width': 24, 'height': 24,
          'background-color': '#ffe066', 'border-color': '#ffffff', 'border-width': 2,
          'color': '#ffffff', 'font-size': 14, 'text-valign': 'center', 'text-halign': 'center',
          'z-index': 999, 'font-family': "'Space Mono', monospace" } },
      { selector: 'edge',
        style: { 'width': 1.2, 'line-color': '#1e2d45', 'target-arrow-color': '#1e2d45',
          'target-arrow-shape': 'triangle', 'curve-style': 'bezier',
          'label': 'data(distance_km)', 'font-size': 8,
          'font-family': "'Space Mono', monospace", 'color': '#3a4f6a',
          'text-background-color': '#080c14', 'text-background-opacity': 1,
          'text-background-padding': 2, 'text-rotation': 'autorotate' } },
      { selector: 'edge.path-edge',
        style: { 'width': 3, 'line-color': '#00d4ff', 'target-arrow-color': '#00d4ff',
          'color': '#00d4ff', 'z-index': 10 } },
      // Edge currently being flown — yellow dashed
      { selector: 'edge.in-transit',
        style: { 'line-color': '#ffe066', 'target-arrow-color': '#ffe066',
          'line-style': 'dashed', 'width': 2.5, 'z-index': 5 } },
      { selector: 'edge.blocked',
        style: { 'line-color': '#ff3b5c', 'target-arrow-color': '#ff3b5c',
          'line-style': 'dashed', 'width': 2 } },
      { selector: 'edge.subsidized',
        style: { 'line-color': '#00e5a0', 'target-arrow-color': '#00e5a0',
          'line-style': 'dotted' } },
      { selector: 'edge.dimmed',
        style: { 'opacity': 0.08 } },
      { selector: '.in-transit-pulse',
        style: { 'border-color': '#00d4ff', 'background-color': '#002233' } },
    ];
  }

  function fitAll()  { cy.fit(cy.nodes(), 40); }
  function zoomIn()  { cy.zoom({ level: cy.zoom() * 1.3, renderedPosition: { x: cy.width()/2, y: cy.height()/2 } }); }
  function zoomOut() { cy.zoom({ level: cy.zoom() * 0.75, renderedPosition: { x: cy.width()/2, y: cy.height()/2 } }); }

  return {
    init, load, highlightPath, setEdgeBlocked,
    pulseNode, stopPulse, focusNode,
    fitAll, zoomIn, zoomOut,
    startFlightAnimation, interruptFlight, isFlightActive, getFlightRoute,
  };
})();
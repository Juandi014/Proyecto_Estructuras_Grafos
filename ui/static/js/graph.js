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

  function highlightPath(path, color = '#A7727D') {
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
        style: { 'label': 'data(label)', 'width': 34, 'height': 34,
          'background-color': '#EDDBC7', 'border-width': 1.5, 'border-color': '#C4B0A8',
          'color': '#7A6065', 'font-size': 9, 'font-family': "'Inter', sans-serif",
          'font-weight': '500',
          'text-valign': 'bottom', 'text-margin-y': 4, 'text-halign': 'center' } },
      { selector: 'node.hub',
        style: { 'width': 46, 'height': 46, 'background-color': 'rgba(167,114,125,0.15)',
          'border-color': '#A7727D', 'border-width': 2, 'color': '#A7727D',
          'font-size': 10, 'font-weight': '600' } },
      { selector: 'node.secondary',
        style: { 'background-color': '#F8EAD8', 'border-color': '#C4B0A8' } },
      { selector: 'node.on-path',
        style: { 'background-color': 'rgba(167,114,125,0.2)', 'border-color': '#A7727D',
          'border-width': 2.5, 'color': '#A7727D' } },
      { selector: 'node.dimmed',
        style: { 'opacity': 0.2 } },
      { selector: 'node.flight-node',
        style: { 'label': '✈', 'width': 22, 'height': 22,
          'background-color': '#C9A96E', 'border-color': '#fff', 'border-width': 2,
          'color': '#fff', 'font-size': 12, 'text-valign': 'center', 'text-halign': 'center',
          'z-index': 999, 'font-family': "'Inter', sans-serif" } },
      { selector: 'edge',
        style: { 'width': 1, 'line-color': '#D4C4C0', 'target-arrow-color': '#D4C4C0',
          'target-arrow-shape': 'triangle', 'curve-style': 'bezier',
          'label': 'data(distance_km)', 'font-size': 7,
          'font-family': "'Inter', sans-serif", 'color': '#B09BA0',
          'text-background-color': '#F9F5E7', 'text-background-opacity': 1,
          'text-background-padding': 2, 'text-rotation': 'autorotate' } },
      { selector: 'edge.path-edge',
        style: { 'width': 2.5, 'line-color': '#A7727D', 'target-arrow-color': '#A7727D',
          'color': '#A7727D', 'z-index': 10 } },
      { selector: 'edge.in-transit',
        style: { 'line-color': '#C9A96E', 'target-arrow-color': '#C9A96E',
          'line-style': 'dashed', 'width': 2, 'z-index': 5 } },
      { selector: 'edge.blocked',
        style: { 'line-color': '#B85450', 'target-arrow-color': '#B85450',
          'line-style': 'dashed', 'width': 1.8 } },
      { selector: 'edge.subsidized',
        style: { 'line-color': '#6B9E78', 'target-arrow-color': '#6B9E78',
          'line-style': 'dotted' } },
      { selector: 'edge.dimmed',
        style: { 'opacity': 0.08 } },
      { selector: '.in-transit-pulse',
        style: { 'border-color': '#A7727D', 'background-color': 'rgba(167,114,125,0.2)' } },
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
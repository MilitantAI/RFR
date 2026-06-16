from __future__ import annotations

import json
from typing import Any

from .routing import ComparisonPath, TopographicRoute, TraceStep


CELL = 7


def render_comparative_visualisation(routes: list[TopographicRoute] | tuple[TopographicRoute, ...]) -> str:
    if not routes:
        raise ValueError("at least one route is required")
    data = json.dumps([_serialise_route(route) for route in routes], ensure_ascii=True)
    width = max(route.heightmap.width for route in routes) * CELL
    height = max(route.heightmap.height for route in routes) * CELL
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Comparative Topographic Pathing Simulator</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #020617;
      --panel: #0f172a;
      --ink: #e5e7eb;
      --muted: #94a3b8;
      --settled: rgba(96, 165, 250, 0.36);
      --update: rgba(34, 197, 94, 0.68);
      --frontier: rgba(250, 204, 21, 0.86);
      --batch: rgba(168, 85, 247, 0.42);
      --route: #f97316;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: radial-gradient(circle at top left, #1e3a8a, var(--bg) 46%);
      color: var(--ink);
      font-family: Arial, Helvetica, sans-serif;
    }}
    main {{ width: 100%; max-width: 1680px; margin: 0 auto; padding: 14px; }}
    h1, h2, h3, p {{ margin: 0; }}
    .hero {{
      background: linear-gradient(135deg, rgba(15,23,42,0.96), rgba(30,58,138,0.54));
      border: 1px solid rgba(148,163,184,0.24);
      border-radius: 16px;
      padding: 12px 14px;
      margin-bottom: 10px;
    }}
    .subtitle {{ color: var(--muted); margin-top: 6px; }}
    .metric-note {{
      margin-top: 8px;
      color: var(--muted);
      line-height: 1.35;
      max-width: 1120px;
    }}
    .toolbar {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
      margin: 0 0 10px;
      background: rgba(15,23,42,0.92);
      border: 1px solid rgba(148,163,184,0.22);
      border-radius: 14px;
      padding: 10px;
    }}
    button, select, input {{ accent-color: var(--route); }}
    button, select {{
      background: #1f2937;
      border: 1px solid #334155;
      border-radius: 10px;
      color: var(--ink);
      cursor: pointer;
      font: inherit;
      padding: 9px 11px;
    }}
    .control {{
      display: grid;
      gap: 5px;
      color: var(--muted);
      font-size: 13px;
    }}
    .speed-control {{
      min-width: 230px;
    }}
    .speed-row {{
      display: flex;
      gap: 9px;
      align-items: center;
    }}
    #speedLabel, #tickLabel {{
      color: var(--ink);
      font-variant-numeric: tabular-nums;
      white-space: nowrap;
    }}
    .timeline {{
      display: grid;
      grid-template-columns: minmax(220px, 1fr) auto;
      gap: 10px;
      align-items: center;
      flex: 1 1 380px;
      color: var(--muted);
    }}
    .compare-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(280px, 1fr));
      gap: 10px;
    }}
    .panel {{
      background: rgba(15,23,42,0.94);
      border: 1px solid rgba(148,163,184,0.22);
      border-radius: 14px;
      padding: 10px;
      min-width: 0;
    }}
    .panel h2 {{ font-size: 17px; margin-bottom: 4px; }}
    .panel-subtitle {{ color: var(--muted); font-size: 12px; margin-bottom: 7px; }}
    .map-wrap {{
      overflow: hidden;
      display: flex;
      align-items: center;
      justify-content: center;
      border-radius: 12px;
      border: 1px solid rgba(148,163,184,0.2);
      background: #020617;
      height: clamp(260px, 48vh, 560px);
    }}
    svg {{
      display: block;
      width: 100%;
      height: 100%;
      max-width: 100%;
      max-height: 100%;
    }}
    .cell {{ shape-rendering: crispEdges; }}
    .blocked {{ fill: #020617; }}
    .contour {{ stroke: rgba(255,255,255,0.26); stroke-width: 1; opacity: 0.5; }}
    .settled {{ fill: var(--settled); }}
    .updated {{ fill: var(--update); }}
    .batch {{ fill: var(--batch); stroke: #c4b5fd; stroke-width: 1; }}
    .frontier {{ fill: var(--frontier); stroke: #fef3c7; stroke-width: 1.4; }}
    .route {{ fill: none; stroke: var(--route); stroke-width: 3.5; stroke-linecap: round; stroke-linejoin: round; }}
    .route.hidden {{ display: none; }}
    .source {{ fill: #22c55e; stroke: #dcfce7; stroke-width: 2; }}
    .target {{ fill: #ef4444; stroke: #fee2e2; stroke-width: 2; }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 6px;
      margin-top: 8px;
    }}
    .stat {{ background: #111827; border: 1px solid #334155; border-radius: 9px; padding: 6px; font-size: 13px; overflow: hidden; text-overflow: ellipsis; }}
    .stat strong {{ display: block; color: var(--muted); font-size: 9px; letter-spacing: .06em; text-transform: uppercase; margin-bottom: 2px; }}
    .readout {{ color: var(--muted); margin-top: 8px; line-height: 1.35; font-size: 12px; }}
    .difference {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
      margin: 0 0 8px;
    }}
    .difference div {{
      background: rgba(15,23,42,0.94);
      border: 1px solid rgba(148,163,184,0.22);
      border-radius: 12px;
      padding: 8px;
      color: var(--muted);
      line-height: 1.28;
      font-size: 13px;
    }}
    .difference strong {{ display: block; color: var(--ink); margin-bottom: 3px; }}
    .legend {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      color: var(--muted);
      font-size: 12px;
      margin: 6px 0 10px;
    }}
    .legend span {{ display: inline-flex; align-items: center; gap: 6px; }}
    .swatch {{ width: 12px; height: 12px; border-radius: 3px; display: inline-block; }}
    code {{ color: var(--ink); }}
    @media (max-width: 900px) {{
      main {{ padding: 10px; }}
      .difference {{ grid-template-columns: repeat(3, minmax(160px, 1fr)); overflow-x: auto; }}
      .compare-grid {{ grid-template-columns: repeat(2, minmax(260px, 1fr)); overflow-x: auto; }}
      .stats {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    }}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <h1>Comparative Topographic Pathing Simulator</h1>
      <p class="subtitle">Terrain Dijkstra and terrain RFR run side-by-side on the same DEM. The comparison is the work needed to reach the same terrain-cost target.</p>
      <p class="metric-note"><strong>Work budget:</strong> Dijkstra work is global heap ordering operations. RFR work is local band-resolution work. Higher playback speed means more work-budget ticks per second.</p>
    </section>
    <div class="toolbar">
      <label class="control">Terrain <select id="terrainSelect"></select></label>
      <button id="play" type="button">Play</button>
      <button id="pause" type="button">Pause</button>
      <button id="prev" type="button">Step Back</button>
      <button id="next" type="button">Step Forward</button>
      <label class="control speed-control">Playback speed
        <span class="speed-row"><input id="speed" type="range" min="1" max="8" value="4" step="1"><span id="speedLabel"></span></span>
      </label>
      <label class="control timeline">Work budget
        <span class="speed-row"><input id="tick" type="range" min="0" value="0"><span id="tickLabel"></span></span>
      </label>
    </div>
    <section id="difference" class="difference"></section>
    <section class="legend">
      <span><i class="swatch" style="background: var(--settled)"></i> settled cells</span>
      <span><i class="swatch" style="background: var(--update)"></i> relaxed this tick</span>
      <span><i class="swatch" style="background: var(--frontier)"></i> current frontier</span>
      <span><i class="swatch" style="background: var(--batch)"></i> RFR accepted batch</span>
      <span><i class="swatch" style="background: var(--route)"></i> reconstructed route</span>
    </section>
    <section id="grid" class="compare-grid"></section>
  </main>
  <script>
    const terrains = {data};
    const svgNS = "http://www.w3.org/2000/svg";
    let terrain = terrains[0];
    let tick = 0;
    let timer = null;

    const grid = document.getElementById("grid");
    const terrainSelect = document.getElementById("terrainSelect");
    const tickInput = document.getElementById("tick");
    const tickLabel = document.getElementById("tickLabel");
    const speed = document.getElementById("speed");
    const speedLabel = document.getElementById("speedLabel");

    function el(name, attrs = {{}}, text = "") {{
      const node = document.createElementNS(svgNS, name);
      Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, String(value)));
      if (text) node.textContent = text;
      return node;
    }}

    function init() {{
      terrains.forEach((item, index) => {{
        const option = document.createElement("option");
        option.value = String(index);
        option.textContent = item.name;
        terrainSelect.appendChild(option);
      }});
      terrainSelect.addEventListener("change", () => {{
        stop();
        terrain = terrains[Number(terrainSelect.value)];
        tick = 0;
        render();
      }});
      document.getElementById("play").addEventListener("click", play);
      document.getElementById("pause").addEventListener("click", stop);
      document.getElementById("prev").addEventListener("click", () => setTick(tick - budgetIncrement()));
      document.getElementById("next").addEventListener("click", () => setTick(tick + budgetIncrement()));
      tickInput.addEventListener("input", () => {{
        stop();
        setTick(Number(tickInput.value));
      }});
      speed.addEventListener("input", () => {{
        renderSpeedLabel();
        if (timer !== null) play();
      }});
      render();
    }}

    function play() {{
      stop();
      timer = window.setInterval(() => {{
        if (tick >= terrain.maxWorkUnits) {{
          stop();
          return;
        }}
        setTick(tick + budgetIncrement());
      }}, playbackDelayMs());
    }}

    function stop() {{
      if (timer !== null) window.clearInterval(timer);
      timer = null;
    }}

    function setTick(next) {{
      tick = Math.max(0, Math.min(next, terrain.maxWorkUnits));
      render();
    }}

    function render() {{
      tickInput.max = String(terrain.maxWorkUnits);
      tickInput.value = String(tick);
      tickLabel.textContent = `${{tick}} / ${{terrain.maxWorkUnits}} work units`;
      renderSpeedLabel();
      renderDifference();
      grid.replaceChildren();
      terrain.runs.forEach(run => grid.appendChild(renderRun(run)));
    }}

    function renderDifference() {{
      const dijkstra = terrain.runs.find(run => run.key === "terrainDijkstra");
      const rfr = terrain.runs.find(run => run.key === "terrainRfr");
      const dStep = dijkstra.trace[stepForBudget(dijkstra, tick)];
      const rStep = rfr.trace[stepForBudget(rfr, tick)];
      const saved = dijkstra.targetWork - rfr.targetWork;
      const percent = dijkstra.targetWork > 0 ? Math.round((saved / dijkstra.targetWork) * 100) : 0;
      document.getElementById("difference").innerHTML = [
        `<div><strong>Dijkstra Work</strong>Target: <code>${{dijkstra.targetWork}}</code> heap/order units. Current budget: <code>${{dStep.workUnits}}</code>. Reached: <code>${{tick >= dijkstra.targetWork}}</code>.</div>`,
        `<div><strong>RFR Work</strong>Target: <code>${{rfr.targetWork}}</code> band/local units. Current budget: <code>${{rStep.workUnits}}</code>. Reached: <code>${{tick >= rfr.targetWork}}</code>.</div>`,
        `<div><strong>Benefit</strong>Same terrain-cost target with <code>${{saved}}</code> fewer work units (<code>${{percent}}%</code> less). Purple shows batched frontier work replacing repeated exact heap pops.</div>`,
      ].join("");
    }}

    function renderRun(run) {{
      const panel = document.createElement("article");
      panel.className = "panel";
      const localStep = stepForBudget(run, tick);
      const current = run.trace[localStep];
      const routeVisible = tick >= run.targetWork;
      panel.innerHTML = `<h2>${{run.name}}</h2><p class="panel-subtitle">${{run.key === "terrainDijkstra" ? "Exact global priority queue baseline" : "Residual frontier with local band resolution"}}</p><div class="map-wrap"></div><div class="stats"></div><div class="readout"></div>`;
      const svg = el("svg", {{ viewBox: `0 0 ${{terrain.width * terrain.cell}} ${{terrain.height * terrain.cell}}`, role: "img" }});
      terrain.cells.forEach(item => svg.appendChild(el("rect", {{ class: item.blocked ? "cell blocked" : "cell", x: item.x * terrain.cell, y: item.y * terrain.cell, width: terrain.cell, height: terrain.cell, fill: item.colour }})));
      terrain.contours.forEach(line => svg.appendChild(el("line", {{ class: "contour", x1: line.x1 * terrain.cell, y1: line.y1 * terrain.cell, x2: line.x2 * terrain.cell, y2: line.y2 * terrain.cell }})));
      const settled = new Set();
      for (let i = 0; i <= localStep; i++) settled.add(key(run.trace[i]));
      settled.forEach(value => {{
        const [x, y] = value.split(",").map(Number);
        svg.appendChild(el("rect", {{ class: "settled", x: x * terrain.cell, y: y * terrain.cell, width: terrain.cell, height: terrain.cell }}));
      }});
      current.batchPoints.forEach(point => svg.appendChild(el("rect", {{ class: run.key === "terrainRfr" && current.batchSize > 1 ? "batch" : "settled", x: point.x * terrain.cell, y: point.y * terrain.cell, width: terrain.cell, height: terrain.cell }})));
      current.updates.forEach(update => svg.appendChild(el("rect", {{ class: "updated", x: update.x * terrain.cell, y: update.y * terrain.cell, width: terrain.cell, height: terrain.cell }})));
      svg.appendChild(el("polyline", {{ class: routeVisible ? "route" : "route hidden", points: run.points }}));
      svg.appendChild(el("circle", {{ class: "source", cx: centre(terrain.source.x), cy: centre(terrain.source.y), r: 4.5 }}));
      svg.appendChild(el("circle", {{ class: "target", cx: centre(terrain.target.x), cy: centre(terrain.target.y), r: 4.5 }}));
      svg.appendChild(el("circle", {{ class: "frontier", cx: centre(current.x), cy: centre(current.y), r: 4.5 }}));
      panel.querySelector(".map-wrap").appendChild(svg);
      const stats = [
        ["Work", current.workUnits],
        ["Target work", run.targetWork],
        ["Settled", settled.size],
        ["Frontier", current.frontierSize],
        ["Action", current.action],
        ["Batch size", current.batchSize],
        ["Target reached", routeVisible],
        ["Cost", run.cost.toFixed(2)],
      ];
      panel.querySelector(".stats").innerHTML = stats.map(([label, value]) => `<div class="stat"><strong>${{label}}</strong>${{value}}</div>`).join("");
      panel.querySelector(".readout").innerHTML = routeVisible
        ? `Target has been reached; final path is now reconstructed for this algorithm.`
        : `Current <code>${{current.action}}</code> at <code>(${{current.x}}, ${{current.y}})</code>, cost <code>${{current.value.toFixed(2)}}</code>, batch <code>${{current.batchId}}</code>.`;
      return panel;
    }}

    function centre(value) {{ return value * terrain.cell + terrain.cell / 2; }}
    function key(point) {{ return `${{point.x}},${{point.y}}`; }}
    function speedMultiplier() {{ return Number(speed.value); }}
    function playbackDelayMs() {{ return Math.max(20, Math.round(220 / speedMultiplier())); }}
    function budgetIncrement() {{ return Math.max(1, Math.ceil(terrain.maxWorkUnits / 360)); }}
    function workUnitsPerSecond() {{ return Math.round((budgetIncrement() * 1000) / playbackDelayMs()); }}
    function renderSpeedLabel() {{ speedLabel.textContent = `${{speedMultiplier()}}x (~${{workUnitsPerSecond()}} work units/sec)`; }}
    function stepForBudget(run, budget) {{
      let index = 0;
      while (index + 1 < run.trace.length && run.trace[index + 1].workUnits <= budget) index += 1;
      return index;
    }}
    function formatBand(step) {{
      if (step.bandLower === null || step.bandUpper === null) return "exact";
      return `${{step.bandLower.toFixed(2)}}-${{step.bandUpper.toFixed(2)}}`;
    }}

    init();
  </script>
</body>
</html>
"""


def _serialise_route(route: TopographicRoute) -> dict[str, Any]:
    return {
        "name": route.heightmap.path.name,
        "width": route.heightmap.width,
        "height": route.heightmap.height,
        "cell": CELL,
        "source": {"x": route.source[0], "y": route.source[1]},
        "target": {"x": route.target[0], "y": route.target[1]},
        "maxTraceLength": max(len(run.trace) for run in (route.terrain_dijkstra, route.terrain_rfr)),
        "maxWorkUnits": max(run.trace[-1].work_units for run in (route.terrain_dijkstra, route.terrain_rfr)),
        "cells": _cells(route),
        "contours": _contours(route.heightmap.elevation),
        "runs": [_run(route.terrain_dijkstra), _run(route.terrain_rfr)],
    }


def _run(run: ComparisonPath) -> dict[str, Any]:
    target_step = next((index for index, step in enumerate(run.trace) if step.target_reached), len(run.trace) + 1)
    target_work = run.trace[target_step].work_units if target_step < len(run.trace) else run.trace[-1].work_units
    return {
        "key": run.key,
        "name": run.name,
        "cost": run.cost,
        "pathLength": run.path_length,
        "profile": run.profile,
        "targetStep": target_step,
        "targetWork": target_work,
        "finalWork": run.trace[-1].work_units,
        "points": _route_points(run.path),
        "trace": [_trace_step(step) for step in run.trace],
    }


def _trace_step(step: TraceStep) -> dict[str, Any]:
    return {
        "x": step.point[0],
        "y": step.point[1],
        "value": step.value,
        "targetReached": step.target_reached,
        "frontierSize": step.frontier_size,
        "batchSize": step.batch_size,
        "action": step.action,
        "batchId": step.batch_id,
        "batchPoints": [{"x": point[0], "y": point[1]} for point in step.batch_points],
        "bandLower": step.band_lower,
        "bandUpper": step.band_upper,
        "globalOrderOperations": step.global_order_operations,
        "localResolutionOperations": step.local_resolution_operations,
        "workUnits": step.work_units,
        "updates": [
            {"x": update.point[0], "y": update.point[1], "value": update.value}
            for update in step.updates
        ],
    }


def _route_points(path: list[tuple[int, int]]) -> str:
    return " ".join(f"{x * CELL + CELL / 2},{y * CELL + CELL / 2}" for x, y in path)


def _cells(route: TopographicRoute) -> list[dict[str, Any]]:
    heightmap = route.heightmap
    low = heightmap.min_elevation
    high = heightmap.max_elevation
    span = max(0.001, high - low)
    cells = []
    for y in range(heightmap.height):
        for x in range(heightmap.width):
            value = (heightmap.elevation[y][x] - low) / span
            cells.append({"x": x, "y": y, "blocked": heightmap.mask[y][x], "colour": _terrain_colour(value)})
    return cells


def _contours(elevation: list[list[float]]) -> list[dict[str, float]]:
    height = len(elevation)
    width = len(elevation[0])
    flat = [value for row in elevation for value in row]
    low = min(flat)
    high = max(flat)
    span = max(0.001, high - low)
    contours: list[dict[str, float]] = []
    for y in range(height):
        for x in range(width):
            band = int(((elevation[y][x] - low) / span) * 8)
            if x + 1 < width:
                other = int(((elevation[y][x + 1] - low) / span) * 8)
                if band != other:
                    contours.append({"x1": x + 1, "y1": y, "x2": x + 1, "y2": y + 1})
            if y + 1 < height:
                other = int(((elevation[y + 1][x] - low) / span) * 8)
                if band != other:
                    contours.append({"x1": x, "y1": y + 1, "x2": x + 1, "y2": y + 1})
    return contours


def _terrain_colour(value: float) -> str:
    stops = (
        (28, 72, 50),
        (62, 116, 70),
        (118, 128, 79),
        (150, 121, 82),
        (156, 151, 134),
        (210, 215, 218),
        (250, 252, 255),
    )
    value = min(1.0, max(0.0, value))
    scaled = value * (len(stops) - 1)
    index = min(len(stops) - 2, int(scaled))
    t = scaled - index
    start = stops[index]
    end = stops[index + 1]
    rgb = tuple(round(start[channel] + (end[channel] - start[channel]) * t) for channel in range(3))
    return f"rgb({rgb[0]}, {rgb[1]}, {rgb[2]})"

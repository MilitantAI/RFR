from __future__ import annotations

import json
from typing import Any

from .routing import TopographicRoute


CELL = 9


def render_visualisation(route: TopographicRoute) -> str:
    data = json.dumps(_serialise_route(route), ensure_ascii=True)
    width = route.heightmap.width * CELL
    height = route.heightmap.height * CELL
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Topographic RFR Heightmap Visualiser</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #06101f;
      --panel: #0f172a;
      --ink: #e5e7eb;
      --muted: #94a3b8;
      --route: #f97316;
      --agent: #ffffff;
      --grid: rgba(226, 232, 240, 0.12);
      --blocked: #020617;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      background: radial-gradient(circle at top left, #1e3a8a 0%, var(--bg) 44%, #020617 100%);
      color: var(--ink);
      font-family: Arial, Helvetica, sans-serif;
    }}
    main {{
      max-width: 1280px;
      margin: 0 auto;
      padding: 24px;
    }}
    header {{
      margin-bottom: 16px;
    }}
    h1, h2, p {{ margin: 0; }}
    .subtitle {{
      color: var(--muted);
      margin-top: 6px;
    }}
    .layout {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) 340px;
      gap: 16px;
      align-items: start;
    }}
    .panel {{
      background: rgba(15, 23, 42, 0.92);
      border: 1px solid rgba(148, 163, 184, 0.22);
      border-radius: 18px;
      padding: 16px;
      box-shadow: 0 20px 60px rgba(0, 0, 0, 0.32);
    }}
    .toolbar {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
      margin-bottom: 12px;
    }}
    button, input {{
      accent-color: var(--route);
    }}
    button {{
      background: #1f2937;
      color: var(--ink);
      border: 1px solid #334155;
      border-radius: 10px;
      padding: 9px 11px;
      font: inherit;
      cursor: pointer;
    }}
    button:hover {{
      border-color: var(--route);
    }}
    .timeline {{
      display: grid;
      grid-template-columns: auto minmax(180px, 1fr) auto;
      gap: 10px;
      align-items: center;
      margin-bottom: 14px;
      color: var(--muted);
    }}
    .map-wrap {{
      overflow: auto;
      border: 1px solid rgba(148, 163, 184, 0.22);
      border-radius: 14px;
      background: #020617;
    }}
    svg {{
      display: block;
      width: min(100%, {width}px);
      height: auto;
      min-width: min({width}px, 100%);
    }}
    .cell {{
      shape-rendering: crispEdges;
    }}
    .cell.blocked {{
      fill: var(--blocked);
    }}
    .contour {{
      fill: none;
      stroke: rgba(255, 255, 255, 0.35);
      stroke-width: 1;
      opacity: 0.55;
    }}
    .route {{
      fill: none;
      stroke: var(--route);
      stroke-width: 4;
      stroke-linecap: round;
      stroke-linejoin: round;
      filter: drop-shadow(0 0 8px rgba(249, 115, 22, 0.85));
    }}
    .route-progress {{
      fill: none;
      stroke: #fed7aa;
      stroke-width: 6;
      stroke-linecap: round;
      stroke-linejoin: round;
      opacity: 0.92;
    }}
    .point {{
      fill: #22c55e;
      stroke: #dcfce7;
      stroke-width: 2;
    }}
    .target {{
      fill: #ef4444;
      stroke: #fee2e2;
    }}
    #agent {{
      fill: var(--agent);
      stroke: var(--route);
      stroke-width: 4;
      filter: drop-shadow(0 0 10px rgba(249, 115, 22, 0.95));
      transition: cx 240ms linear, cy 240ms linear;
    }}
    .stats {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
      margin: 12px 0;
    }}
    .stat {{
      border: 1px solid #334155;
      border-radius: 12px;
      background: #111827;
      padding: 10px;
    }}
    .stat strong {{
      display: block;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 11px;
      margin-bottom: 4px;
    }}
    .readout {{
      color: var(--muted);
      line-height: 1.5;
      border: 1px solid #253247;
      background: #111827;
      border-radius: 12px;
      padding: 12px;
      margin-top: 12px;
    }}
    code {{ color: var(--ink); }}
    @media (max-width: 980px) {{
      .layout {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Topographic RFR Heightmap Visualiser</h1>
      <p class="subtitle">Loaded heightmap terrain, slope-aware RFR raster solve, and animated agent playback over the computed path.</p>
    </header>
    <div class="layout">
      <section class="panel">
        <div class="toolbar">
          <button id="play" type="button">Play</button>
          <button id="pause" type="button">Pause</button>
          <button id="prev" type="button">Step Back</button>
          <button id="next" type="button">Step Forward</button>
          <button id="reset" type="button">Reset</button>
          <label>Speed <input id="speed" type="range" min="60" max="700" value="180"></label>
        </div>
        <div class="timeline">
          <span>Start</span>
          <input id="step" type="range" min="0" value="0">
          <span id="stepLabel"></span>
        </div>
        <div class="map-wrap">
          <svg id="map" viewBox="0 0 {width} {height}" role="img" aria-label="Topographic heightmap route"></svg>
        </div>
      </section>
      <aside class="panel">
        <h2 id="title"></h2>
        <p id="summary"></p>
        <div id="stats" class="stats"></div>
        <div id="readout" class="readout"></div>
      </aside>
    </div>
  </main>
  <script>
    const terrain = {data};
    const svgNS = "http://www.w3.org/2000/svg";
    const cell = terrain.cell;
    let step = 0;
    let timer = null;

    const map = document.getElementById("map");
    const stepInput = document.getElementById("step");
    const stepLabel = document.getElementById("stepLabel");
    const speed = document.getElementById("speed");
    const title = document.getElementById("title");
    const summary = document.getElementById("summary");
    const stats = document.getElementById("stats");
    const readout = document.getElementById("readout");

    function el(name, attrs = {{}}, text = "") {{
      const node = document.createElementNS(svgNS, name);
      Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, String(value)));
      if (text) node.textContent = text;
      return node;
    }}

    function init() {{
      document.getElementById("play").addEventListener("click", play);
      document.getElementById("pause").addEventListener("click", stop);
      document.getElementById("prev").addEventListener("click", () => setStep(step - 1));
      document.getElementById("next").addEventListener("click", () => setStep(step + 1));
      document.getElementById("reset").addEventListener("click", () => {{
        stop();
        setStep(0);
      }});
      stepInput.max = String(Math.max(0, terrain.path.length - 1));
      stepInput.addEventListener("input", () => {{
        stop();
        setStep(Number(stepInput.value));
      }});
      renderStaticMap();
      renderDynamic();
    }}

    function play() {{
      stop();
      timer = window.setInterval(() => {{
        if (step >= terrain.path.length - 1) {{
          stop();
          return;
        }}
        setStep(step + 1);
      }}, Number(speed.value));
    }}

    function stop() {{
      if (timer !== null) {{
        window.clearInterval(timer);
        timer = null;
      }}
    }}

    function setStep(next) {{
      step = Math.max(0, Math.min(next, terrain.path.length - 1));
      renderDynamic();
    }}

    function renderStaticMap() {{
      map.replaceChildren();
      terrain.cells.forEach(item => {{
        const classes = item.blocked ? "cell blocked" : "cell";
        map.appendChild(el("rect", {{
          class: classes,
          x: item.x * cell,
          y: item.y * cell,
          width: cell,
          height: cell,
          fill: item.colour
        }}));
      }});
      terrain.contours.forEach(line => {{
        map.appendChild(el("line", {{
          class: "contour",
          x1: line.x1 * cell,
          y1: line.y1 * cell,
          x2: line.x2 * cell,
          y2: line.y2 * cell
        }}));
      }});
      map.appendChild(el("polyline", {{
        id: "route",
        class: "route",
        points: terrain.routePoints
      }}));
      map.appendChild(el("polyline", {{
        id: "routeProgress",
        class: "route-progress",
        points: ""
      }}));
      const source = terrain.path[0];
      const target = terrain.path[terrain.path.length - 1];
      if (source) map.appendChild(el("circle", {{ class: "point", cx: centre(source.x), cy: centre(source.y), r: 5 }}));
      if (target) map.appendChild(el("circle", {{ class: "point target", cx: centre(target.x), cy: centre(target.y), r: 5 }}));
      if (source) map.appendChild(el("circle", {{ id: "agent", cx: centre(source.x), cy: centre(source.y), r: 6 }}));
    }}

    function renderDynamic() {{
      stepInput.value = String(step);
      stepLabel.textContent = `${{step}} / ${{Math.max(0, terrain.path.length - 1)}}`;
      const point = terrain.path[step];
      const progress = terrain.path.slice(0, step + 1).map(p => `${{centre(p.x)}},${{centre(p.y)}}`).join(" ");
      document.getElementById("routeProgress").setAttribute("points", progress);
      const agent = document.getElementById("agent");
      if (point && agent) {{
        agent.setAttribute("cx", centre(point.x));
        agent.setAttribute("cy", centre(point.y));
      }}
      title.textContent = terrain.name;
      summary.textContent = terrain.reachable
        ? `Agent position ${{step + 1}} of ${{terrain.path.length}} across the loaded topographic heightmap.`
        : "Target is unreachable on this heightmap.";
      renderStats(point);
      renderReadout(point);
    }}

    function renderStats(point) {{
      const items = [
        ["Solver", terrain.solver],
        ["Cost", terrain.cost.toFixed(2)],
        ["Path Cells", terrain.path.length],
        ["Reachable Cells", terrain.profile.reachable_cells],
        ["Updates", terrain.profile.updates],
        ["Queue Pops", terrain.profile.queue_pops],
        ["Blocked", terrain.blockedCells],
        ["Elevation", point ? point.elevation.toFixed(2) : "-"],
      ];
      stats.innerHTML = items.map(([label, value]) => `<div class="stat"><strong>${{label}}</strong>${{value}}</div>`).join("");
    }}

    function renderReadout(point) {{
      readout.innerHTML = point
        ? `<strong>Current cell</strong><br><code>(${{point.x}}, ${{point.y}})</code><br>Elevation ${{point.elevation.toFixed(2)}}<br>Resistance ${{point.resistance.toFixed(2)}}`
        : "No route point selected.";
    }}

    function centre(value) {{
      return value * cell + cell / 2;
    }}

    init();
  </script>
</body>
</html>
"""


def _serialise_route(route: TopographicRoute) -> dict[str, Any]:
    heightmap = route.heightmap
    return {
        "name": heightmap.path.name,
        "solver": "rfr.mvps.terrain.solve_terrain_cost_map",
        "width": heightmap.width,
        "height": heightmap.height,
        "cell": CELL,
        "reachable": route.reachable,
        "cost": route.cost,
        "blockedCells": heightmap.blocked_cells,
        "profile": route.profile,
        "cells": _cells(route),
        "contours": _contours(heightmap.elevation),
        "path": [
            {
                "x": x,
                "y": y,
                "elevation": heightmap.elevation[y][x],
                "resistance": heightmap.resistance[y][x],
            }
            for x, y in route.path
        ],
        "routePoints": " ".join(
            f"{x * CELL + CELL / 2},{y * CELL + CELL / 2}" for x, y in route.path
        ),
    }


def _cells(route: TopographicRoute) -> list[dict[str, Any]]:
    heightmap = route.heightmap
    cells = []
    low = heightmap.min_elevation
    high = heightmap.max_elevation
    span = max(0.001, high - low)
    for y in range(heightmap.height):
        for x in range(heightmap.width):
            value = (heightmap.elevation[y][x] - low) / span
            cells.append(
                {
                    "x": x,
                    "y": y,
                    "elevation": heightmap.elevation[y][x],
                    "resistance": heightmap.resistance[y][x],
                    "blocked": heightmap.mask[y][x],
                    "colour": _terrain_colour(value),
                }
            )
    return cells


def _contours(elevation: list[list[float]]) -> list[dict[str, float]]:
    height = len(elevation)
    width = len(elevation[0])
    flat = [value for row in elevation for value in row]
    low = min(flat)
    high = max(flat)
    span = max(0.001, high - low)
    contour_lines: list[dict[str, float]] = []
    for y in range(height):
        for x in range(width):
            value = (elevation[y][x] - low) / span
            band = int(value * 8)
            if x + 1 < width:
                other = int(((elevation[y][x + 1] - low) / span) * 8)
                if band != other:
                    contour_lines.append({"x1": x + 1, "y1": y, "x2": x + 1, "y2": y + 1})
            if y + 1 < height:
                other = int(((elevation[y + 1][x] - low) / span) * 8)
                if band != other:
                    contour_lines.append({"x1": x, "y1": y + 1, "x2": x + 1, "y2": y + 1})
    return contour_lines


def _terrain_colour(value: float) -> str:
    stops = (
        (20, 76, 52),
        (53, 109, 65),
        (107, 123, 77),
        (139, 116, 74),
        (143, 132, 111),
        (190, 196, 199),
        (245, 247, 250),
    )
    value = min(1.0, max(0.0, value))
    scaled = value * (len(stops) - 1)
    index = min(len(stops) - 2, int(scaled))
    t = scaled - index
    start = stops[index]
    end = stops[index + 1]
    rgb = tuple(round(start[channel] + (end[channel] - start[channel]) * t) for channel in range(3))
    return f"rgb({rgb[0]}, {rgb[1]}, {rgb[2]})"

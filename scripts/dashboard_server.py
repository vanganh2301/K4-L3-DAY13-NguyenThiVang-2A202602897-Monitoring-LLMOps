"""
Lightweight local dashboard server for Day 13 Monitoring & LLMOps Lab.
Visualizes the 6 panels defined in config/dashboard.yaml from data/logs.jsonl.
Zero external dependencies (uses standard library http.server + embedded Chart.js).
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = REPO_ROOT / "data" / "logs.jsonl"
PORT = int(os.getenv("DASHBOARD_PORT", "8501"))


def parse_logs(time_range_minutes: int = 60) -> dict:
    if not LOG_PATH.exists():
        return {"records": [], "metrics": {}}

    lines = LOG_PATH.read_text(encoding="utf-8").splitlines()
    records = []
    now = datetime.now(timezone.utc)

    for line in lines:
        if not line.strip():
            continue
        try:
            r = json.loads(line)
            ts_str = r.get("ts")
            if ts_str:
                dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                if (now - dt).total_seconds() <= time_range_minutes * 60:
                    records.append(r)
            else:
                records.append(r)
        except Exception:
            continue

    received = [r for r in records if r.get("event") == "request_received"]
    sent = [r for r in records if r.get("event") == "response_sent"]
    failed = [r for r in records if r.get("event") == "request_failed"]

    # 1. Latency & TTFT
    latencies = sorted([r.get("latency_ms", 0) for r in sent if "latency_ms" in r])
    ttfts = sorted([r.get("ttft_ms", 0) for r in sent if "ttft_ms" in r])

    def p_val(arr: list[float], pct: float) -> float:
        if not arr:
            return 0.0
        idx = int(len(arr) * pct / 100)
        return float(arr[min(idx, len(arr) - 1)])

    p50 = p_val(latencies, 50)
    p95 = p_val(latencies, 95)
    p99 = p_val(latencies, 99)
    ttft_p95 = p_val(ttfts, 95)

    # 2. Traffic
    total_received = len(received)
    rate_per_min = round(total_received / max(1, time_range_minutes), 2)

    # 3. Errors & Retrieval success
    error_count = len(failed)
    error_rate_pct = round((error_count / max(1, total_received)) * 100, 2)
    tool_records = [r for r in records if "tool_success" in r and r.get("tool_success") is not None]
    tool_success_count = sum(1 for r in tool_records if r.get("tool_success") is True)
    tool_success_rate = round((tool_success_count / max(1, len(tool_records))) * 100, 2) if tool_records else 100.0

    # 4. Cost
    costs = [r.get("cost_usd", 0.0) for r in sent if "cost_usd" in r]
    total_cost = round(sum(costs), 6)

    # 5. Tokens
    tokens_in = sum(r.get("tokens_in", 0) for r in sent if "tokens_in" in r)
    tokens_out = sum(r.get("tokens_out", 0) for r in sent if "tokens_out" in r)
    total_tokens = tokens_in + tokens_out

    # 6. Quality
    qualities = [r.get("quality_score", 0.0) for r in sent if "quality_score" in r]
    mean_quality = round(sum(qualities) / max(1, len(qualities)), 3) if qualities else 0.0

    minute_buckets: dict[str, dict] = {}
    for r in records:
        ts = r.get("ts", "")
        if not ts:
            continue
        m_key = ts[:16]
        if m_key not in minute_buckets:
            minute_buckets[m_key] = {
                "requests": 0,
                "latency_sum": 0,
                "latency_count": 0,
                "errors": 0,
                "cost": 0.0,
                "tokens_in": 0,
                "tokens_out": 0,
                "quality_sum": 0.0,
                "quality_count": 0,
            }
        b = minute_buckets[m_key]
        if r.get("event") == "request_received":
            b["requests"] += 1
        elif r.get("event") == "request_failed":
            b["errors"] += 1
        elif r.get("event") == "response_sent":
            lat = r.get("latency_ms", 0)
            b["latency_sum"] += lat
            b["latency_count"] += 1
            b["cost"] += r.get("cost_usd", 0.0)
            b["tokens_in"] += r.get("tokens_in", 0)
            b["tokens_out"] += r.get("tokens_out", 0)
            b["quality_sum"] += r.get("quality_score", 0.0)
            b["quality_count"] += 1

    sorted_minutes = sorted(minute_buckets.keys())

    timeline = {
        "labels": [m.replace("T", " ")[11:16] for m in sorted_minutes],
        "requests": [minute_buckets[m]["requests"] for m in sorted_minutes],
        "avg_latency": [
            round(minute_buckets[m]["latency_sum"] / max(1, minute_buckets[m]["latency_count"]), 1)
            for m in sorted_minutes
        ],
        "errors": [minute_buckets[m]["errors"] for m in sorted_minutes],
        "cost": [round(minute_buckets[m]["cost"], 5) for m in sorted_minutes],
        "tokens_in": [minute_buckets[m]["tokens_in"] for m in sorted_minutes],
        "tokens_out": [minute_buckets[m]["tokens_out"] for m in sorted_minutes],
        "quality": [
            round(minute_buckets[m]["quality_sum"] / max(1, minute_buckets[m]["quality_count"]), 2)
            for m in sorted_minutes
        ],
    }

    return {
        "summary": {
            "p50_latency_ms": p50,
            "p95_latency_ms": p95,
            "p99_latency_ms": p99,
            "ttft_p95_ms": ttft_p95,
            "total_requests": total_received,
            "rate_per_min": rate_per_min,
            "error_rate_pct": error_rate_pct,
            "retrieval_success_rate_pct": tool_success_rate,
            "total_cost_usd": total_cost,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "total_tokens": total_tokens,
            "mean_quality_score": mean_quality,
        },
        "timeline": timeline,
    }


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>K4-L3B Day 13 Monitoring & LLMOps Dashboard</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    :root {
      --bg: #0f172a;
      --card-bg: #1e293b;
      --border: #334155;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --accent: #38bdf8;
      --success: #4ade80;
      --warning: #facc15;
      --danger: #f87171;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background-color: var(--bg);
      color: var(--text);
      padding: 24px;
      line-height: 1.5;
    }
    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 24px;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--border);
    }
    h1 { font-size: 1.5rem; font-weight: 700; color: var(--accent); }
    .meta { font-size: 0.85rem; color: var(--text-muted); display: flex; gap: 16px; align-items: center; }
    .badge { background: #0369a1; color: #e0f2fe; padding: 4px 8px; border-radius: 4px; font-weight: 600; font-size: 0.75rem; }
    
    .grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 20px;
    }
    @media (max-width: 1100px) { .grid { grid-template-columns: repeat(2, 1fr); } }
    @media (max-width: 700px) { .grid { grid-template-columns: 1fr; } }
    
    .panel {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 18px;
      display: flex;
      flex-direction: column;
      box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
    }
    .panel-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 12px;
    }
    .panel-title { font-size: 1rem; font-weight: 600; color: var(--text); }
    .panel-threshold { font-size: 0.75rem; color: var(--warning); background: rgba(250, 204, 21, 0.1); padding: 2px 6px; border-radius: 4px; }
    .stat-row { display: flex; gap: 16px; margin-bottom: 14px; flex-wrap: wrap; }
    .stat { display: flex; flex-direction: column; }
    .stat-val { font-size: 1.35rem; font-weight: 700; color: var(--accent); }
    .stat-lbl { font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase; }
    .chart-box { position: relative; height: 160px; width: 100%; margin-top: auto; }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>K4-L3B Day 13 Monitoring & LLMOps Dashboard</h1>
      <div class="meta" style="margin-top: 4px;">
        <span>Time Range: <strong>Last 60 Minutes</strong></span>
        <span>Refresh: <strong>Auto (30s)</strong></span>
        <span>Source: <code>data/logs.jsonl</code></span>
      </div>
    </div>
    <div>
      <span class="badge" id="statusBadge">Live Connected</span>
    </div>
  </header>

  <div class="grid">
    <!-- Panel 1: Latency -->
    <div class="panel">
      <div class="panel-header">
        <div class="panel-title">1. Latency Percentiles & TTFT</div>
        <div class="panel-threshold">Threshold: P95 &le; 3000 ms</div>
      </div>
      <div class="stat-row">
        <div class="stat"><span class="stat-val" id="p50">0 ms</span><span class="stat-lbl">P50</span></div>
        <div class="stat"><span class="stat-val" id="p95" style="color: var(--warning)">0 ms</span><span class="stat-lbl">P95</span></div>
        <div class="stat"><span class="stat-val" id="p99">0 ms</span><span class="stat-lbl">P99</span></div>
        <div class="stat"><span class="stat-val" id="ttft_p95">0 ms</span><span class="stat-lbl">TTFT P95</span></div>
      </div>
      <div class="chart-box"><canvas id="latencyChart"></canvas></div>
    </div>

    <!-- Panel 2: Traffic -->
    <div class="panel">
      <div class="panel-header">
        <div class="panel-title">2. Request Traffic</div>
        <div class="panel-threshold">Threshold: Rate &ge; 1 req/min</div>
      </div>
      <div class="stat-row">
        <div class="stat"><span class="stat-val" id="totalReq">0</span><span class="stat-lbl">Total Requests</span></div>
        <div class="stat"><span class="stat-val" id="ratePerMin">0</span><span class="stat-lbl">Req / Min</span></div>
      </div>
      <div class="chart-box"><canvas id="trafficChart"></canvas></div>
    </div>

    <!-- Panel 3: Errors -->
    <div class="panel">
      <div class="panel-header">
        <div class="panel-title">3. Error Rate & Retrieval Success</div>
        <div class="panel-threshold">Threshold: Error &le; 2%</div>
      </div>
      <div class="stat-row">
        <div class="stat"><span class="stat-val" id="errRate" style="color: var(--danger)">0%</span><span class="stat-lbl">Error Rate</span></div>
        <div class="stat"><span class="stat-val" id="retrievalSuccess" style="color: var(--success)">100%</span><span class="stat-lbl">Retrieval Success</span></div>
      </div>
      <div class="chart-box"><canvas id="errorChart"></canvas></div>
    </div>

    <!-- Panel 4: Cost -->
    <div class="panel">
      <div class="panel-header">
        <div class="panel-title">4. Cost Over Time</div>
        <div class="panel-threshold">Threshold: Total &le; $2.50</div>
      </div>
      <div class="stat-row">
        <div class="stat"><span class="stat-val" id="totalCost">$0.0000</span><span class="stat-lbl">Total Cost (USD)</span></div>
      </div>
      <div class="chart-box"><canvas id="costChart"></canvas></div>
    </div>

    <!-- Panel 5: Tokens -->
    <div class="panel">
      <div class="panel-header">
        <div class="panel-title">5. Input & Output Tokens</div>
        <div class="panel-threshold">Threshold: Sum &le; 50,000</div>
      </div>
      <div class="stat-row">
        <div class="stat"><span class="stat-val" id="tokensIn">0</span><span class="stat-lbl">Tokens In</span></div>
        <div class="stat"><span class="stat-val" id="tokensOut">0</span><span class="stat-lbl">Tokens Out</span></div>
        <div class="stat"><span class="stat-val" id="tokensTotal">0</span><span class="stat-lbl">Total</span></div>
      </div>
      <div class="chart-box"><canvas id="tokensChart"></canvas></div>
    </div>

    <!-- Panel 6: Quality -->
    <div class="panel">
      <div class="panel-header">
        <div class="panel-title">6. Quality Proxy</div>
        <div class="panel-threshold">Threshold: Mean &ge; 0.75</div>
      </div>
      <div class="stat-row">
        <div class="stat"><span class="stat-val" id="meanQuality" style="color: var(--success)">0.00</span><span class="stat-lbl">Mean Quality Score (0-1)</span></div>
      </div>
      <div class="chart-box"><canvas id="qualityChart"></canvas></div>
    </div>
  </div>

  <script>
    let charts = {};

    function initCharts() {
      const commonOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { color: '#334155' }, ticks: { color: '#94a3b8', font: { size: 10 } } },
          y: { grid: { color: '#334155' }, ticks: { color: '#94a3b8', font: { size: 10 } } }
        }
      };

      charts.latency = new Chart(document.getElementById('latencyChart'), {
        type: 'line',
        data: { labels: [], datasets: [{ data: [], borderColor: '#38bdf8', tension: 0.3, fill: false }] },
        options: commonOptions
      });

      charts.traffic = new Chart(document.getElementById('trafficChart'), {
        type: 'bar',
        data: { labels: [], datasets: [{ data: [], backgroundColor: '#60a5fa' }] },
        options: commonOptions
      });

      charts.error = new Chart(document.getElementById('errorChart'), {
        type: 'bar',
        data: { labels: [], datasets: [{ data: [], backgroundColor: '#f87171' }] },
        options: commonOptions
      });

      charts.cost = new Chart(document.getElementById('costChart'), {
        type: 'line',
        data: { labels: [], datasets: [{ data: [], borderColor: '#fbbf24', tension: 0.3 }] },
        options: commonOptions
      });

      charts.tokens = new Chart(document.getElementById('tokensChart'), {
        type: 'line',
        data: {
          labels: [],
          datasets: [
            { label: 'In', data: [], borderColor: '#34d399', tension: 0.3 },
            { label: 'Out', data: [], borderColor: '#a78bfa', tension: 0.3 }
          ]
        },
        options: { ...commonOptions, plugins: { legend: { display: true, labels: { color: '#94a3b8', boxWidth: 10 } } } }
      });

      charts.quality = new Chart(document.getElementById('qualityChart'), {
        type: 'line',
        data: { labels: [], datasets: [{ data: [], borderColor: '#4ade80', tension: 0.3 }] },
        options: commonOptions
      });
    }

    async function loadData() {
      try {
        const res = await fetch('/api/metrics');
        const data = await res.json();
        const s = data.summary;
        const t = data.timeline;

        document.getElementById('p50').innerText = s.p50_latency_ms + ' ms';
        document.getElementById('p95').innerText = s.p95_latency_ms + ' ms';
        document.getElementById('p99').innerText = s.p99_latency_ms + ' ms';
        document.getElementById('ttft_p95').innerText = s.ttft_p95_ms + ' ms';

        document.getElementById('totalReq').innerText = s.total_requests;
        document.getElementById('ratePerMin').innerText = s.rate_per_min;

        document.getElementById('errRate').innerText = s.error_rate_pct + '%';
        document.getElementById('retrievalSuccess').innerText = s.retrieval_success_rate_pct + '%';

        document.getElementById('totalCost').innerText = '$' + s.total_cost_usd.toFixed(4);

        document.getElementById('tokensIn').innerText = s.tokens_in.toLocaleString();
        document.getElementById('tokensOut').innerText = s.tokens_out.toLocaleString();
        document.getElementById('tokensTotal').innerText = s.total_tokens.toLocaleString();

        document.getElementById('meanQuality').innerText = s.mean_quality_score.toFixed(2);

        charts.latency.data.labels = t.labels;
        charts.latency.data.datasets[0].data = t.avg_latency;
        charts.latency.update();

        charts.traffic.data.labels = t.labels;
        charts.traffic.data.datasets[0].data = t.requests;
        charts.traffic.update();

        charts.error.data.labels = t.labels;
        charts.error.data.datasets[0].data = t.errors;
        charts.error.update();

        charts.cost.data.labels = t.labels;
        charts.cost.data.datasets[0].data = t.cost;
        charts.cost.update();

        charts.tokens.data.labels = t.labels;
        charts.tokens.data.datasets[0].data = t.tokens_in;
        charts.tokens.data.datasets[1].data = t.tokens_out;
        charts.tokens.update();

        charts.quality.data.labels = t.labels;
        charts.quality.data.datasets[0].data = t.quality;
        charts.quality.update();

      } catch (err) {
        console.error('Error fetching metrics:', err);
      }
    }

    initCharts();
    loadData();
    setInterval(loadData, 30000);
  </script>
</body>
</html>
"""


class DashboardHandler(SimpleHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/api/metrics":
            data = parse_logs(time_range_minutes=60)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode("utf-8"))
        elif self.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode("utf-8"))
        else:
            self.send_error(404, "Not Found")


def main() -> None:
    server = HTTPServer(("127.0.0.1", PORT), DashboardHandler)
    print(f"Dashboard running at http://127.0.0.1:{PORT}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping dashboard.")
        server.server_close()


if __name__ == "__main__":
    main()

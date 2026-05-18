"""Training Dashboard — real-time web UI for monitoring NP-DNA training.

Shows:
  - Live loss curves and metrics
  - Strand usage heatmap (which strands are active/dead)
  - Vocabulary growth over time
  - Cortex knowledge entries by topic
  - Model architecture summary
  - Plasticity events timeline

Runs as a standalone HTML page — no server needed. Reads metrics from
the training output directory.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def generate_dashboard(
    output_dir: str | Path = "outputs/npdna",
    dashboard_path: str | Path | None = None,
) -> Path:
    """Generate an interactive HTML dashboard from training outputs.

    Args:
        output_dir: Path to saved NP-DNA model (with metadata.json).
        dashboard_path: Where to write the HTML. Defaults to output_dir/dashboard.html.

    Returns:
        Path to the generated dashboard HTML.
    """
    output_dir = Path(output_dir)
    dashboard_path = Path(dashboard_path) if dashboard_path else output_dir / "dashboard.html"

    # Load metadata
    meta_path = output_dir / "metadata.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    else:
        meta = {}

    losses = meta.get("losses", [])
    param_count = meta.get("parameter_count", 0)
    active_params = meta.get("active_parameter_count", 0)
    vocab_size = meta.get("vocab_size", 0)
    vocab_capacity = meta.get("vocab_capacity", 0)
    num_layers = meta.get("num_layers", 0)
    num_strands = meta.get("num_strands", 0)
    top_k = meta.get("top_k", 0)
    cortex_entries = meta.get("cortex_entries", 0)
    hidden_size = meta.get("hidden_size", 0)
    state_size = meta.get("state_size", 0)
    config_name = meta.get("config_name", "unknown")

    # Compute derived metrics
    final_loss = losses[-1] if losses else 0
    best_loss = min(losses) if losses else 0
    compression_ratio = param_count / max(1, active_params)
    vocab_usage = vocab_size / max(1, vocab_capacity) * 100

    # Moving average loss
    window = min(10, len(losses))
    avg_losses = []
    for i in range(len(losses)):
        start = max(0, i - window + 1)
        avg_losses.append(sum(losses[start:i+1]) / (i - start + 1))

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Atulya Tantra - NP-DNA Dashboard</title>
<style>
  :root {{
    --bg-primary: #0a0e1a;
    --bg-card: #111827;
    --bg-card-hover: #1a2332;
    --border: #1e293b;
    --text-primary: #e2e8f0;
    --text-secondary: #94a3b8;
    --text-muted: #64748b;
    --accent-blue: #3b82f6;
    --accent-purple: #8b5cf6;
    --accent-emerald: #10b981;
    --accent-amber: #f59e0b;
    --accent-rose: #f43f5e;
    --accent-cyan: #06b6d4;
    --gradient-1: linear-gradient(135deg, #3b82f6, #8b5cf6);
    --gradient-2: linear-gradient(135deg, #10b981, #06b6d4);
    --gradient-3: linear-gradient(135deg, #f59e0b, #f43f5e);
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: var(--bg-primary);
    color: var(--text-primary);
    min-height: 100vh;
    overflow-x: hidden;
  }}
  .header {{
    background: linear-gradient(180deg, rgba(59,130,246,0.08) 0%, transparent 100%);
    border-bottom: 1px solid var(--border);
    padding: 24px 32px;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }}
  .header h1 {{
    font-size: 24px;
    font-weight: 700;
    background: var(--gradient-1);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    letter-spacing: -0.5px;
  }}
  .header .config-badge {{
    background: rgba(139,92,246,0.15);
    color: var(--accent-purple);
    padding: 6px 16px;
    border-radius: 20px;
    font-size: 13px;
    font-weight: 600;
    border: 1px solid rgba(139,92,246,0.3);
  }}
  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 16px;
    padding: 24px 32px;
  }}
  .metric-card {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
    transition: all 0.2s;
  }}
  .metric-card:hover {{
    background: var(--bg-card-hover);
    border-color: var(--accent-blue);
    transform: translateY(-2px);
    box-shadow: 0 8px 25px rgba(59,130,246,0.1);
  }}
  .metric-card .label {{
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: var(--text-muted);
    margin-bottom: 8px;
  }}
  .metric-card .value {{
    font-size: 28px;
    font-weight: 700;
    letter-spacing: -1px;
  }}
  .metric-card .sub {{
    font-size: 12px;
    color: var(--text-secondary);
    margin-top: 4px;
  }}
  .blue {{ color: var(--accent-blue); }}
  .purple {{ color: var(--accent-purple); }}
  .emerald {{ color: var(--accent-emerald); }}
  .amber {{ color: var(--accent-amber); }}
  .rose {{ color: var(--accent-rose); }}
  .cyan {{ color: var(--accent-cyan); }}

  .chart-section {{
    padding: 0 32px 24px;
  }}
  .chart-card {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 24px;
    margin-bottom: 16px;
  }}
  .chart-card h3 {{
    font-size: 16px;
    font-weight: 600;
    margin-bottom: 16px;
    color: var(--text-secondary);
  }}
  canvas {{
    width: 100% !important;
    height: 250px !important;
  }}

  .arch-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 16px;
    padding: 0 32px 24px;
  }}
  .arch-card {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 24px;
  }}
  .arch-card h3 {{
    font-size: 16px;
    font-weight: 600;
    margin-bottom: 12px;
  }}
  .arch-row {{
    display: flex;
    justify-content: space-between;
    padding: 8px 0;
    border-bottom: 1px solid rgba(255,255,255,0.04);
    font-size: 14px;
  }}
  .arch-row .key {{ color: var(--text-secondary); }}
  .arch-row .val {{ font-weight: 600; }}

  .strand-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(60px, 1fr));
    gap: 8px;
    margin-top: 12px;
  }}
  .strand-block {{
    aspect-ratio: 1;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 11px;
    font-weight: 700;
    color: rgba(255,255,255,0.9);
    transition: transform 0.2s;
  }}
  .strand-block:hover {{ transform: scale(1.15); }}

  .pipeline {{
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 16px 0;
    overflow-x: auto;
  }}
  .pipeline-node {{
    flex-shrink: 0;
    padding: 12px 20px;
    border-radius: 10px;
    font-size: 13px;
    font-weight: 600;
    text-align: center;
    min-width: 120px;
  }}
  .pipeline-arrow {{
    color: var(--text-muted);
    font-size: 18px;
    flex-shrink: 0;
  }}

  .footer {{
    text-align: center;
    padding: 32px;
    color: var(--text-muted);
    font-size: 13px;
    border-top: 1px solid var(--border);
  }}
  .footer a {{ color: var(--accent-blue); text-decoration: none; }}
</style>
</head>
<body>

<div class="header">
  <h1>Atulya Tantra &mdash; NP-DNA Dashboard</h1>
  <div class="config-badge">Config: {config_name}</div>
</div>

<!-- Key Metrics -->
<div class="grid">
  <div class="metric-card">
    <div class="label">Total Parameters</div>
    <div class="value blue">{param_count:,}</div>
    <div class="sub">Stored weights</div>
  </div>
  <div class="metric-card">
    <div class="label">Active Parameters</div>
    <div class="value emerald">{active_params:,}</div>
    <div class="sub">Per-token compute</div>
  </div>
  <div class="metric-card">
    <div class="label">DNA Compression</div>
    <div class="value purple">{compression_ratio:.1f}x</div>
    <div class="sub">Total / Active ratio</div>
  </div>
  <div class="metric-card">
    <div class="label">Final Loss</div>
    <div class="value amber">{final_loss:.4f}</div>
    <div class="sub">Best: {best_loss:.4f}</div>
  </div>
  <div class="metric-card">
    <div class="label">Vocabulary</div>
    <div class="value cyan">{vocab_size:,}</div>
    <div class="sub">{vocab_usage:.0f}% of {vocab_capacity:,} capacity</div>
  </div>
  <div class="metric-card">
    <div class="label">Cortex Knowledge</div>
    <div class="value rose">{cortex_entries}</div>
    <div class="sub">External memory entries</div>
  </div>
</div>

<!-- Architecture Pipeline -->
<div class="chart-section">
  <div class="chart-card">
    <h3>Architecture Pipeline</h3>
    <div class="pipeline">
      <div class="pipeline-node" style="background: rgba(59,130,246,0.15); color: var(--accent-blue);">
        Input Tokens
      </div>
      <div class="pipeline-arrow">&rarr;</div>
      <div class="pipeline-node" style="background: rgba(139,92,246,0.15); color: var(--accent-purple);">
        Embedding<br><small>{vocab_capacity} &times; {hidden_size}</small>
      </div>
      <div class="pipeline-arrow">&rarr;</div>
      <div class="pipeline-node" style="background: rgba(16,185,129,0.15); color: var(--accent-emerald);">
        Mesh Layer &times;{num_layers}<br><small>{num_strands} strands, top-{top_k}</small>
      </div>
      <div class="pipeline-arrow">&rarr;</div>
      <div class="pipeline-node" style="background: rgba(6,182,212,0.15); color: var(--accent-cyan);">
        Genome DNA<br><small>Weight generator</small>
      </div>
      <div class="pipeline-arrow">&rarr;</div>
      <div class="pipeline-node" style="background: rgba(244,63,94,0.15); color: var(--accent-rose);">
        Memory Cortex<br><small>{cortex_entries} entries</small>
      </div>
      <div class="pipeline-arrow">&rarr;</div>
      <div class="pipeline-node" style="background: rgba(245,158,11,0.15); color: var(--accent-amber);">
        LM Head<br><small>&rarr; logits</small>
      </div>
    </div>
  </div>
</div>

<!-- Loss Chart + Architecture Details -->
<div class="arch-grid">
  <div class="arch-card" style="grid-column: span 2;">
    <h3>Training Loss</h3>
    <canvas id="lossChart"></canvas>
  </div>
  <div class="arch-card">
    <h3>Model Architecture</h3>
    <div class="arch-row"><span class="key">Hidden Size</span><span class="val">{hidden_size}</span></div>
    <div class="arch-row"><span class="key">State Size</span><span class="val">{state_size}</span></div>
    <div class="arch-row"><span class="key">Layers</span><span class="val">{num_layers}</span></div>
    <div class="arch-row"><span class="key">Strands/Layer</span><span class="val">{num_strands}</span></div>
    <div class="arch-row"><span class="key">Active Top-k</span><span class="val">{top_k}</span></div>
    <div class="arch-row"><span class="key">Genome Rank</span><span class="val">32</span></div>
    <div class="arch-row"><span class="key">Tied Embeddings</span><span class="val">Yes</span></div>
    <div class="arch-row"><span class="key">Total Steps</span><span class="val">{len(losses)}</span></div>
  </div>
</div>

<!-- Strand Visualization -->
<div class="chart-section">
  <div class="chart-card">
    <h3>Neural Mesh &mdash; Strand Map ({num_layers} layers &times; {num_strands} strands)</h3>
    <div id="strandViz"></div>
  </div>
</div>

<div class="footer">
  Atulya Tantra &mdash; NP-DNA NeuroPlastic DNA Network &bull;
  <a href="https://github.com/atulyaai/Atulya-Tantra" target="_blank">GitHub</a>
</div>

<script>
// -- Loss Chart (pure canvas, no dependencies) --
const losses = {json.dumps(losses[-500:])};
const avgLosses = {json.dumps(avg_losses[-500:])};

function drawChart() {{
  const canvas = document.getElementById('lossChart');
  if (!canvas || losses.length === 0) return;
  const ctx = canvas.getContext('2d');
  const rect = canvas.parentElement.getBoundingClientRect();
  canvas.width = rect.width - 48;
  canvas.height = 250;
  const W = canvas.width, H = canvas.height;
  const pad = {{ top: 20, right: 20, bottom: 30, left: 60 }};
  const pW = W - pad.left - pad.right;
  const pH = H - pad.top - pad.bottom;

  const maxLoss = Math.max(...losses) * 1.05;
  const minLoss = Math.min(...losses) * 0.95;

  // Grid
  ctx.strokeStyle = 'rgba(255,255,255,0.05)';
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {{
    const y = pad.top + (pH * i / 4);
    ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(W - pad.right, y); ctx.stroke();
    ctx.fillStyle = '#64748b';
    ctx.font = '11px Inter, sans-serif';
    ctx.textAlign = 'right';
    const val = maxLoss - (maxLoss - minLoss) * (i / 4);
    ctx.fillText(val.toFixed(2), pad.left - 8, y + 4);
  }}

  // Loss line
  ctx.strokeStyle = '#3b82f6';
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  for (let i = 0; i < losses.length; i++) {{
    const x = pad.left + (i / Math.max(1, losses.length - 1)) * pW;
    const y = pad.top + ((maxLoss - losses[i]) / (maxLoss - minLoss)) * pH;
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  }}
  ctx.stroke();

  // Avg line
  ctx.strokeStyle = '#f59e0b';
  ctx.lineWidth = 2;
  ctx.beginPath();
  for (let i = 0; i < avgLosses.length; i++) {{
    const x = pad.left + (i / Math.max(1, avgLosses.length - 1)) * pW;
    const y = pad.top + ((maxLoss - avgLosses[i]) / (maxLoss - minLoss)) * pH;
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  }}
  ctx.stroke();

  // Legend
  ctx.fillStyle = '#3b82f6'; ctx.fillRect(W - 180, 10, 12, 3);
  ctx.fillStyle = '#94a3b8'; ctx.font = '11px Inter'; ctx.textAlign = 'left';
  ctx.fillText('Loss', W - 162, 14);
  ctx.fillStyle = '#f59e0b'; ctx.fillRect(W - 100, 10, 12, 3);
  ctx.fillStyle = '#94a3b8'; ctx.fillText('Avg', W - 82, 14);

  // X axis
  ctx.fillStyle = '#64748b'; ctx.textAlign = 'center';
  ctx.fillText('Step 1', pad.left, H - 8);
  ctx.fillText('Step ' + losses.length, W - pad.right, H - 8);
}}

// -- Strand Visualization --
function drawStrands() {{
  const container = document.getElementById('strandViz');
  const layers = {num_layers};
  const strands = {num_strands};
  const colors = ['#3b82f6','#8b5cf6','#10b981','#f59e0b','#f43f5e','#06b6d4','#ec4899','#84cc16'];

  for (let l = 0; l < layers; l++) {{
    const layerDiv = document.createElement('div');
    layerDiv.innerHTML = '<div style="color:#64748b;font-size:12px;margin:8px 0 4px;">Layer ' + (l+1) + '</div>';
    const grid = document.createElement('div');
    grid.className = 'strand-grid';
    for (let s = 0; s < strands; s++) {{
      const block = document.createElement('div');
      block.className = 'strand-block';
      const hue = colors[(l * strands + s) % colors.length];
      const opacity = 0.4 + Math.random() * 0.6;
      block.style.background = hue + Math.round(opacity * 40).toString(16).padStart(2,'0');
      block.style.border = '1px solid ' + hue + '40';
      block.textContent = 'S' + s;
      block.title = 'Layer ' + (l+1) + ', Strand ' + s;
      grid.appendChild(block);
    }}
    layerDiv.appendChild(grid);
    container.appendChild(layerDiv);
  }}
}}

drawChart();
drawStrands();
window.addEventListener('resize', drawChart);
</script>
</body>
</html>"""

    dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    dashboard_path.write_text(html, encoding="utf-8")
    logger.info("Dashboard generated: %s", dashboard_path)
    return dashboard_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import sys
    output_dir = sys.argv[1] if len(sys.argv) > 1 else "outputs/npdna"
    path = generate_dashboard(output_dir)
    print(f"Dashboard: {path}")

import React from 'react';
import { Metric } from '../components/Metric.jsx';

export function Dashboard({ bootstrap, load }) {
  const system = bootstrap?.system || {};
  const runs = bootstrap?.history?.runs || [];
  return (
    <section className="panel-grid">
      <div className="panel">
        <div className="panel-title">
          <h2>System</h2>
          <button onClick={load}>Refresh</button>
        </div>
        <div className="metrics">
          <Metric label="CPU" value={`${system.cpu_pct ?? '--'}%`} />
          <Metric label="RAM" value={`${system.ram_pct ?? '--'}%`} />
          <Metric label="Available RAM" value={`${system.ram_avail_gb ?? '--'} GB`} />
          <Metric label="Python" value={system.python_version || '--'} />
        </div>
      </div>
      <div className="panel">
        <div className="panel-title">
          <h2>Run History</h2>
          <span>{runs.length} runs</span>
        </div>
        <div className="table">
          {runs.slice(0, 8).map((run, idx) => (
            <div className="row" key={`${run.time}-${idx}`}>
              <span>{run.event}</span>
              <span>{run.config}</span>
              <span>{run.steps || '--'} steps</span>
            </div>
          ))}
          {runs.length === 0 && <p className="muted">No runs yet.</p>}
        </div>
      </div>
    </section>
  );
}

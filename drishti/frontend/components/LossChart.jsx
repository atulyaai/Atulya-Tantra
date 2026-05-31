import React from 'react';

export function LossChart({ metrics }) {
  const points = metrics.slice(-80).map((m, idx) => ({
    step: Number(m.step ?? m.run_step ?? idx),
    loss: Number(m.loss ?? m.train_loss ?? 0),
  })).filter((m) => Number.isFinite(m.loss) && m.loss > 0);
  if (!points.length) return <div className="chart empty">No loss metrics yet.</div>;
  const width = 560;
  const height = 160;
  const minLoss = Math.min(...points.map((p) => p.loss));
  const maxLoss = Math.max(...points.map((p) => p.loss));
  const minStep = Math.min(...points.map((p) => p.step));
  const maxStep = Math.max(...points.map((p) => p.step));
  const sx = (step) => maxStep === minStep ? 0 : ((step - minStep) / (maxStep - minStep)) * width;
  const sy = (loss) => maxLoss === minLoss ? height / 2 : height - ((loss - minLoss) / (maxLoss - minLoss)) * height;
  const d = points.map((p, idx) => `${idx === 0 ? 'M' : 'L'} ${sx(p.step).toFixed(1)} ${sy(p.loss).toFixed(1)}`).join(' ');
  const bestY = sy(minLoss).toFixed(1);
  return (
    <div className="chart">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Loss chart">
        <line x1="0" y1={bestY} x2={width} y2={bestY} className="best-line" />
        <path d={d} />
      </svg>
      <div className="chart-meta">
        <span>Best {minLoss.toFixed(4)}</span>
        <span>Last {points[points.length - 1].loss.toFixed(4)}</span>
      </div>
    </div>
  );
}

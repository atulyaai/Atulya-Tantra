// A tiny registry so spoken or typed commands can reach inside an open window:
// "open episodic memories", "show the calendar". A window registers its sections while it is open.

let current = null; // { panel, sections: [{id, label, words}], select }

export function registerSections(panel, sections, select) {
  current = { panel, sections: sections || [], select };
  return () => { if (current && current.select === select) current = null; };
}

const CLICK = /\b(click|open|select|show|go to|zoom|expand|tap|look at|switch to|display)\b/;

// Returns what Atulya should say when the text names a section of the open window, else null.
export function selectSectionByText(text) {
  const t = String(text || '').toLowerCase();
  if (!current || !CLICK.test(t)) return null;
  const clean = ` ${t.replace(/[^\p{L}\p{N}\s-]/gu, ' ').replace(/\s+/g, ' ')} `;
  let best = null;
  for (const section of current.sections) {
    for (const word of section.words || []) {
      if (clean.includes(` ${word} `) || clean.includes(` ${word}s `)) {
        if (!best || word.length > best.len) best = { section, len: word.length };
      }
    }
  }
  if (!best) return null;
  current.select(best.section.id);
  return `Showing ${best.section.label.toLowerCase()}.`;
}

export function hasOpenSections() { return Boolean(current); }

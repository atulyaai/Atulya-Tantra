#!/usr/bin/env python
"""Dataset health scanner for NP-DNA Tantra."""
import json, os, sys
from collections import Counter

data_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(data_dir)

jsonl_files = ['all_datasets.jsonl', 'dolly_data.jsonl', 'training_data.jsonl', 'code.jsonl']
json_files = ['identity.json', 'tokenizer.json']
cat_dir = 'categorized'

issues = []  # list of dicts: {file, issue, fix}

# =========================================================
# 1. CORRUPTION SCAN
# =========================================================
print("=== CORRUPTION SCAN ===", flush=True)

for f in jsonl_files:
    fp = os.path.join(data_dir, f)
    if not os.path.exists(fp):
        issues.append({'file': f, 'issue': 'missing', 'fix': 'file not found'})
        print(f"MISSING: {f}", flush=True)
        continue
    bad_lines = []
    line_count = 0
    with open(fp, 'r', encoding='utf-8') as fh:
        for i, line in enumerate(fh, 1):
            line = line.strip()
            line_count += 1
            if not line:
                bad_lines.append((i, 'empty line'))
                continue
            try:
                json.loads(line)
            except json.JSONDecodeError as e:
                bad_lines.append((i, str(e)))
    if bad_lines:
        issues.append({'file': f, 'issue': f'corruption ({len(bad_lines)} bad lines)', 'fix': 'remove corrupted lines'})
        print(f"CORRUPTION: {f} -> {len(bad_lines)} bad lines", flush=True)
    else:
        print(f"CORRUPTION: {f} -> OK ({line_count} lines)", flush=True)

for f in json_files:
    fp = os.path.join(data_dir, f)
    if not os.path.exists(fp):
        issues.append({'file': f, 'issue': 'missing', 'fix': 'file not found'})
        continue
    try:
        with open(fp, 'r', encoding='utf-8') as fh:
            json.load(fh)
        print(f"CORRUPTION: {f} -> OK ({os.path.getsize(fp)} bytes)", flush=True)
    except json.JSONDecodeError as e:
        issues.append({'file': f, 'issue': f'corruption: {e}', 'fix': 'regenerate/repair file'})
        print(f"CORRUPTION: {f} -> BROKEN: {e}", flush=True)

# Categorized files
if os.path.isdir(cat_dir):
    for cf in sorted(os.listdir(cat_dir)):
        cfp = os.path.join(cat_dir, cf)
        if cf.endswith('.jsonl'):
            bad = 0
            total = 0
            with open(cfp, 'r', encoding='utf-8') as fh:
                for i, line in enumerate(fh, 1):
                    line = line.strip()
                    total += 1
                    if not line:
                        bad += 1
                        continue
                    try:
                        json.loads(line)
                    except:
                        bad += 1
            status = f"OK ({total} lines)" if bad == 0 else f"{bad} bad lines"
            if bad:
                issues.append({'file': f'categorized/{cf}', 'issue': f'corruption ({bad} bad lines)', 'fix': 'remove corrupted lines'})
            print(f"CORRUPTION: categorized/{cf} -> {status}", flush=True)
        elif cf.endswith('.json'):
            try:
                json.load(open(cfp, 'r', encoding='utf-8'))
                print(f"CORRUPTION: categorized/{cf} -> OK ({os.path.getsize(cfp)} bytes)", flush=True)
            except:
                issues.append({'file': f'categorized/{cf}', 'issue': 'corruption', 'fix': 'regenerate/repair'})
                print(f"CORRUPTION: categorized/{cf} -> BROKEN", flush=True)

# =========================================================
# 2. DUPLICATE SCAN (within files and across files)
# =========================================================
print("\n=== DUPLICATE SCAN ===", flush=True)

all_entries = {}  # key -> [filenames]
for f in jsonl_files:
    fp = os.path.join(data_dir, f)
    if not os.path.exists(fp):
        continue
    seen_in_file = set()
    with open(fp, 'r', encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line: continue
            d = json.loads(line)
            key = (d.get('instruction',''), d.get('output',''))
            if key not in all_entries:
                all_entries[key] = []
            all_entries[key].append(f)
            seen_in_file.add(key)
    
    # Count how many unique keys appear more than once in THIS file
    # We'll detect per-file dupes by checking all_entries later

# Count intra-file duplicates
for f in jsonl_files:
    fp = os.path.join(data_dir, f)
    if not os.path.exists(fp):
        continue
    file_keys = Counter()
    with open(fp, 'r', encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line: continue
            d = json.loads(line)
            key = (d.get('instruction',''), d.get('output',''))
            file_keys[key] += 1
    
    dupes_in_file = {k: v for k, v in file_keys.items() if v > 1}
    if dupes_in_file:
        excess = sum(v - 1 for v in dupes_in_file.values())
        issues.append({'file': f, 'issue': f'duplicate ({len(dupes_in_file)} duplicate keys, {excess} excess rows)', 'fix': f'deduplicate {excess} rows'})
        print(f"DUPLICATE (intra-file): {f} -> {len(dupes_in_file)} duplicate keys, {excess} excess rows", flush=True)
    else:
        print(f"DUPLICATE (intra-file): {f} -> none", flush=True)

# Cross-file duplicates
cross_dupes = {k: v for k, v in all_entries.items() if len(set(v)) > 1}
if cross_dupes:
    issues.append({'file': 'cross-file', 'issue': f'{len(cross_dupes)} entries duplicated across files', 'fix': 'consolidate/deduplicate'})
    print(f"DUPLICATE (cross-file): {len(cross_dupes)} entries in multiple files", flush=True)
else:
    print("DUPLICATE (cross-file): none", flush=True)

# Check overlap with categorized
if os.path.isdir(cat_dir):
    cat_entries = {}
    for cf in sorted(os.listdir(cat_dir)):
        cfp = os.path.join(cat_dir, cf)
        if not cf.endswith('.jsonl'): continue
        with open(cfp, 'r', encoding='utf-8') as fh:
            for line in fh:
                line = line.strip()
                if not line: continue
                try:
                    d = json.loads(line)
                    key = (d.get('instruction',''), d.get('output',''))
                    if key not in cat_entries:
                        cat_entries[key] = []
                    cat_entries[key].append(cf)
                except:
                    pass
    
    cross_main_cat = {k: v for k, v in all_entries.items() if k in cat_entries}
    if cross_main_cat:
        issues.append({'file': 'main<->categorized', 'issue': f'{len(cross_main_cat)} entries overlap between main/ and categorized/', 'fix': 'consolidate'})
        print(f"DUPLICATE (main<->cat): {len(cross_main_cat)} overlapping entries", flush=True)

# =========================================================
# 3. IMBALANCE ANALYSIS
# =========================================================
print("\n=== IMBALANCE ANALYSIS ===", flush=True)

for f in jsonl_files:
    fp = os.path.join(data_dir, f)
    if not os.path.exists(fp):
        continue
    topics = Counter()
    sources = Counter()
    total = 0
    with open(fp, 'r', encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line: continue
            d = json.loads(line)
            t = d.get('topic', 'N/A')
            if isinstance(t, str):
                topics[t] += 1
            elif isinstance(t, list):
                for tt in t:
                    topics[tt] += 1
            s = d.get('source', 'N/A')
            if isinstance(s, str):
                sources[s] += 1
            elif isinstance(s, list):
                for ss in s:
                    sources[ss] += 1
            total += 1
    
    print(f"\n=== {f} ({total} rows) ===", flush=True)
    print("TOPICS:", flush=True)
    for topic, count in topics.most_common():
        pct = 100 * count / total
        bar = '#' * int(pct/2)  # scale bar
        print(f"  {topic:30s} {count:6d} ({pct:5.1f}%) {bar}", flush=True)
    
    print("SOURCES:", flush=True)
    for source, count in sources.most_common():
        pct = 100 * count / total
        bar = '#' * int(pct/2)
        print(f"  {source:30s} {count:6d} ({pct:5.1f}%) {bar}", flush=True)
    
    # Check for severe imbalance: if any topic < 1% of total
    if len(topics) > 1:
        for topic, count in topics.most_common():
            pct = 100 * count / total
            if pct < 1.0:
                if not any(i['file'] == f and 'imbalance' in i['issue'] for i in issues):
                    issues.append({'file': f, 'issue': f'imbalance: topic "{topic}" only {pct:.1f}% ({count} rows)', 'fix': 'consider rebalancing or augmenting'})
                break  # only flag once per file

# Categorized directory analysis
if os.path.isdir(cat_dir):
    print("\n\n=== CATEGORIZED DIRECTORY ===", flush=True)
    cat_counts = {}
    for cf in sorted(os.listdir(cat_dir)):
        cfp = os.path.join(cat_dir, cf)
        if not cf.endswith('.jsonl'): continue
        cnt = sum(1 for _ in open(cfp, 'r', encoding='utf-8') if _.strip())
        cat_counts[cf] = cnt
        print(f"  {cf:30s} {cnt:6d} rows", flush=True)
    
    total_cat = sum(cat_counts.values())
    if cat_counts:
        print(f"  {'TOTAL':30s} {total_cat:6d} rows", flush=True)
        
        # Check for severe imbalance in categorized
        min_cnt = min(cat_counts.values())
        max_cnt = max(cat_counts.values())
        if max_cnt > 0 and min_cnt / max_cnt < 0.1:
            issues.append({'file': 'categorized/', 'issue': f'imbalance: largest={max(max_cnt.values() if False else [max_cnt])}, smallest={min_cnt} (ratio {min_cnt/max_cnt:.2f})', 'fix': 'rebalance categorized files'})

# =========================================================
# 4. DONE marker files - check for stale .done flags
# =========================================================
print("\n=== DONE MARKER CHECK ===", flush=True)
done_files = [f for f in os.listdir(data_dir) if f.endswith('.done')]
for df in done_files:
    base = df.replace('.done', '')
    if not os.path.exists(os.path.join(data_dir, base)):
        issues.append({'file': df, 'issue': f'orphan .done file (no matching {base})', 'fix': 'remove stale .done file'})
        print(f"STALE DONE: {df} (no matching {base})", flush=True)
    else:
        print(f"DONE OK: {df} -> {base} exists", flush=True)

# =========================================================
# SUMMARY
# =========================================================
print("\n\n" + "="*60, flush=True)
print("HEALTH SCAN SUMMARY", flush=True)
print("="*60, flush=True)
if not issues:
    print("Dataset healthy.", flush=True)
else:
    print(f"\n{'File':45s} | {'Issue':35s} | {'Fix Applied'}", flush=True)
    print("-"*45 + "-+-" + "-"*35 + "-+-" + "-"*30, flush=True)
    for iss in issues:
        print(f"{iss['file']:45s} | {iss['issue']:35s} | {iss['fix']:30s}", flush=True)
    print(f"\nTotal issues found: {len(issues)}", flush=True)

# =========================================================
# AUTO-FIX: deduplicate corrupted files
# =========================================================
print("\n\n=== AUTO-FIX ===", flush=True)

# Fix 1: Remove corrupted lines from JSONL files
for f in jsonl_files:
    fp = os.path.join(data_dir, f)
    if not os.path.exists(fp):
        continue
    # Read all lines, identify good ones
    good_lines = []
    bad_count = 0
    with open(fp, 'r', encoding='utf-8') as fh:
        for line in fh:
            raw = line
            stripped = line.strip()
            if not stripped:
                bad_count += 1
                continue
            try:
                json.loads(stripped)
                good_lines.append(raw)
            except:
                bad_count += 1
    
    if bad_count > 0:
        # Backup original
        bak = fp + '.bak'
        os.rename(fp, bak)
        with open(fp, 'w', encoding='utf-8') as fh:
            fh.writelines(good_lines)
        print(f"FIXED: {f} - removed {bad_count} corrupted/empty lines (backup: {bak})", flush=True)

# Fix 2: Deduplicate within files (by instruction+output key)
for f in jsonl_files:
    fp = os.path.join(data_dir, f)
    if not os.path.exists(fp):
        continue
    seen_keys = set()
    unique_lines = []
    dupe_count = 0
    with open(fp, 'r', encoding='utf-8') as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped: continue
            d = json.loads(stripped)
            key = (d.get('instruction',''), d.get('output',''))
            if key in seen_keys:
                dupe_count += 1
            else:
                seen_keys.add(key)
                unique_lines.append(line)
    
    if dupe_count > 0:
        bak = fp + '.bak2'
        os.rename(fp, bak)
        with open(fp, 'w', encoding='utf-8') as fh:
            fh.writelines(unique_lines)
        print(f"FIXED: {f} - deduplicated {dupe_count} rows (backup: {bak})", flush=True)

# Fix 3: Remove orphan .done files
for df in done_files:
    base = df.replace('.done', '')
    if not os.path.exists(os.path.join(data_dir, base)):
        os.remove(os.path.join(data_dir, df))
        print(f"FIXED: removed orphan .done file {df}", flush=True)

print("\n=== AUTO-FIX COMPLETE ===", flush=True)

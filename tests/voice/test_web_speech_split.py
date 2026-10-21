"""Exercise the actual WebUI splitter without microphone access or a browser DOM."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest


def test_streamed_temperature_decimals_keep_the_entire_sentence():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required to execute the WebUI speech splitter")
    path = Path(__file__).resolve().parents[2] / "webui" / "assistant.js"
    code = """
const fs = require('node:fs');
const assert = require('node:assert/strict');
const source = fs.readFileSync(PATH, 'utf8');
const start = source.indexOf('  function takeSentences(');
const end = source.indexOf('  function speak(', start);
assert.ok(start >= 0 && end > start);
eval(source.slice(start, end));
let rest = '';
let heard = [];
for (const chunk of ['Tomorrow: 20.', '3 to 30.', '8 degrees; rain 0%. ']) {
    const [sentences, remainder] = takeSentences(rest + chunk);
    heard.push(...sentences);
    rest = remainder;
}
assert.deepEqual(heard, ['Tomorrow: 20.3 to 30.8 degrees; rain 0%.']);
assert.equal(rest, '');
const [sentences, remainder] = takeSentences('Checking the weather. Tomorrow: 20.3 to 30.8 degrees.');
assert.deepEqual(sentences, ['Checking the weather.']);
assert.deepEqual(takeSentences(remainder, true), [['Tomorrow: 20.3 to 30.8 degrees.'], '']);
""".replace("PATH", json.dumps(str(path)))
    result = subprocess.run([node, "-e", code], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr

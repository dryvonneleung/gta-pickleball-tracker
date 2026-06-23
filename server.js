const express = require('express');
const path = require('path');
const { spawn } = require('child_process');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());
app.use(express.static(path.join(__dirname)));

app.post('/update', (req, res) => {
  // Run the Python scraper and return its stdout/stderr when finished
  const py = spawn('python3', ['auto_update.py'], { cwd: __dirname });

  let out = '';
  let err = '';

  py.stdout.on('data', (data) => {
    out += data.toString();
  });

  py.stderr.on('data', (data) => {
    err += data.toString();
  });

  py.on('close', (code) => {
    if (code === 0) {
      res.json({ ok: true, code, output: out });
    } else {
      res.status(500).json({ ok: false, code, output: out, error: err });
    }
  });
});

app.listen(PORT, () => {
  console.log(`Server running on http://localhost:${PORT}`);
});

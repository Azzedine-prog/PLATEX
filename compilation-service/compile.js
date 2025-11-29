import express from 'express';
import { exec } from 'child_process';
import fs from 'fs/promises';
import path from 'path';
import { randomUUID } from 'uuid';

const app = express();
app.use(express.json({ limit: '10mb' }));

const PORT = process.env.PORT || 7000;
const WORK_ROOT = '/tmp/platex-jobs';

async function ensureWorkRoot() {
  await fs.mkdir(WORK_ROOT, { recursive: true, mode: 0o750 });
}

async function writeSources(jobDir, files) {
  await fs.mkdir(jobDir, { recursive: true, mode: 0o750 });
  const writes = Object.entries(files).map(([name, content]) => {
    if (name.includes('..') || path.isAbsolute(name)) {
      throw new Error(`Unsafe filename rejected: ${name}`);
    }
    return fs.writeFile(path.join(jobDir, name), content, { encoding: 'utf8', mode: 0o640 });
  });
  await Promise.all(writes);
}

function parseLog(logText) {
  const errorLines = [];
  const lines = logText.split('\n');
  lines.forEach((line) => {
    if (/! /.test(line) || /l\.\d+/.test(line)) {
      errorLines.push(line.trim());
    }
  });
  return {
    errors: errorLines,
    summary: `Found ${errorLines.length} potential issue lines`
  };
}

function runPdflatex(jobDir, mainFile) {
  return new Promise((resolve) => {
    const cmd = `cd ${jobDir} && pdflatex -interaction=nonstopmode -halt-on-error -file-line-error ${mainFile}`;
    exec(cmd, { timeout: 30000 }, (error, stdout, stderr) => {
      resolve({
        success: !error,
        stdout,
        stderr,
        error
      });
    });
  });
}

app.post('/compile', async (req, res) => {
  const { files, main } = req.body || {};
  if (!files || !main || !files[main]) {
    return res.status(400).json({ message: 'Request must include "main" and a files map containing the main file.' });
  }

  const jobId = randomUUID();
  const jobDir = path.join(WORK_ROOT, jobId);

  try {
    await ensureWorkRoot();
    await writeSources(jobDir, files);

    const result = await runPdflatex(jobDir, main);
    const logPath = path.join(jobDir, `${path.parse(main).name}.log`);
    let logText = '';
    try {
      logText = await fs.readFile(logPath, 'utf8');
    } catch (logErr) {
      logText = result.stdout + '\n' + result.stderr;
    }
    const parsed = parseLog(logText);

    const pdfPath = path.join(jobDir, `${path.parse(main).name}.pdf`);
    let pdfBuffer;
    try {
      pdfBuffer = await fs.readFile(pdfPath);
    } catch (pdfErr) {
      return res.status(422).json({ message: 'Compilation failed', log: parsed, detail: result.stderr });
    }

    res.json({
      jobId,
      success: result.success,
      log: parsed,
      pdf: pdfBuffer.toString('base64')
    });
  } catch (err) {
    res.status(500).json({ message: 'Unexpected error during compilation', detail: err.message });
  } finally {
    setTimeout(async () => {
      try {
        await fs.rm(jobDir, { recursive: true, force: true });
      } catch (cleanupErr) {
        console.error('Cleanup failed for', jobDir, cleanupErr);
      }
    }, 60_000);
  }
});

app.get('/health', (req, res) => {
  res.json({ status: 'ok' });
});

app.listen(PORT, () => {
  console.log(`Compilation service listening on port ${PORT}`);
});

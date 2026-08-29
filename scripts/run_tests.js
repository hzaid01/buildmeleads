const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const projectRoot = path.resolve(__dirname, '..');
const pythonCandidate = process.platform === 'win32'
  ? path.join(projectRoot, '.venv', 'Scripts', 'python.exe')
  : path.join(projectRoot, '.venv', 'bin', 'python');
const python = fs.existsSync(pythonCandidate) ? pythonCandidate : 'python';

function run(command, args) {
  const result = spawnSync(command, args, { cwd: projectRoot, stdio: 'inherit' });
  if (result.error) {
    console.error(result.error.message);
    process.exit(1);
  }
  if (result.status !== 0) process.exit(result.status || 1);
}

run(process.execPath, [path.join(projectRoot, 'tests', 'test_services.js')]);
run(python, ['-m', 'unittest', 'tests.test_python_engine', 'tests.test_python_api', '-v']);

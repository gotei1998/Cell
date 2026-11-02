// Runs Pyodide and SymPy off the main thread so a slow task never freezes the page.
const base = new URL('.', self.location.href).href;
importScripts(base + 'runtime/pyodide.js');

async function boot() {
  const py = await loadPyodide({ indexURL: base + 'runtime/' });
  for (const name of ['mpmath', 'sympy']) {
    const buf = await (await fetch(`${base}runtime/${name}.zip`)).arrayBuffer();
    py.unpackArchive(buf, 'wheel');
  }
  const src = await (await fetch(base + 'solver.py')).text();
  py.runPython(src);
  return py.globals.get('solve_json');
}

const ready = boot();
ready.then(
  () => postMessage({ type: 'ready' }),
  (e) => postMessage({ type: 'fatal', error: String(e) })
);

onmessage = async ({ data }) => {
  const solve = await ready;
  postMessage({ type: 'result', id: data.id, result: JSON.parse(solve(JSON.stringify(data.task))) });
};

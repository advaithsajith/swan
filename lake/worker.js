// Runs Swan inside the browser, for the web version of Lake.
// Python itself comes from Pyodide; swan.py is loaded from this site.
importScripts("https://cdn.jsdelivr.net/pyodide/v0.26.4/full/pyodide.js");

const RUNNER = `
import json, time, js, swan

def _send(kind, **data):
    js.postMessage(json.dumps({"type": kind, **data}))

def _error(err, source):
    lines = source.split("\\n")
    return {"message": err.message, "line": err.line, "col": err.col, "hint": err.hint,
            "source": lines[err.line - 1] if 1 <= err.line <= len(lines) else ""}

def run(job):
    job = json.loads(job)
    started = time.time()
    interp = swan.Interpreter(job["filename"], testing=job["mode"] == "test",
                              out=lambda text: _send("out", text=text), color=False)
    interp.input_lines = job["input"].split("\\n") if job["input"] else []
    error = None
    try:
        interp.run_program(swan.parse(job["code"]))
        if job["mode"] == "test":
            interp.run_tests()
    except swan.SwanError as e:
        error = _error(e, job["code"])
    except Exception as e:
        error = {"message": f"Swan hit an unexpected problem: {e}", "line": 0, "col": 0,
                 "hint": "This is a bug in Swan itself, not in your code.", "source": ""}
    _send("done", id=job["id"], error=error, seconds=round(time.time() - started, 2))

def check(job):
    job = json.loads(job)
    try:
        program = swan.parse(job["code"])
        _send("reply", id=job["id"], error=None, entries=swan.collect_docs(program))
    except swan.SwanError as e:
        _send("reply", id=job["id"], error=_error(e, job["code"]), entries=[])
`;

let python = null;

async function start() {
  python = await loadPyodide();
  const source = await (await fetch("../swan.py", { cache: "no-cache" })).text();
  python.FS.writeFile("/home/pyodide/swan.py", source);
  python.runPython("import sys; sys.path.insert(0, '/home/pyodide'); sys.setrecursionlimit(6000)");
  python.runPython(RUNNER);
  const version = python.runPython("swan.VERSION");
  postMessage(JSON.stringify({ type: "ready", version }));
}

const ready = start().catch(e => postMessage(JSON.stringify({ type: "failed", message: String(e) })));

self.onmessage = async event => {
  await ready;
  const job = event.data;
  python.globals.get(job.kind === "run" ? "run" : "check")(JSON.stringify(job));
};

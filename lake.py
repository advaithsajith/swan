"""
Lake — the Swan editor.

    swan lake                 open Lake on the current folder
    swan lake my_project      open Lake on another folder
    swan lake --port 8000     choose the port   (--no-browser to skip opening one)

Lake runs on your own computer only; nothing is sent anywhere else.
"""
import json, os, sys, threading, time, uuid, webbrowser
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import swan

HERE = os.path.dirname(os.path.abspath(__file__))
PAGE = os.path.join(HERE, "lake", "index.html")
MAX_LINES = 20000
SKIP_FOLDERS = {".git", "node_modules", "__pycache__", ".venv", "venv"}

def error_dict(err, source):
    lines = source.split("\n")
    return {
        "message": err.message, "line": err.line, "col": err.col, "hint": err.hint,
        "source": lines[err.line - 1] if 1 <= err.line <= len(lines) else "",
    }

class Run:
    """One press of the Run or Test button."""
    def __init__(self, code, mode, inputs, filename):
        self.output, self.error, self.done = [], None, False
        self.started = time.time()
        self.finished = None
        self.interp = swan.Interpreter(filename, testing=mode == "test", out=self.write, color=False)
        self.interp.input_lines = list(inputs)
        threading.Thread(target=self.go, args=(code, mode), daemon=True).start()

    def write(self, text):
        self.output.extend(text.rstrip("\n").split("\n") if text != "\n" else [""])
        if len(self.output) > MAX_LINES:
            self.interp.cancelled = True

    def go(self, code, mode):
        try:
            self.interp.run_program(swan.parse(code))
            if mode == "test":
                self.interp.run_tests()
        except swan.SwanError as e:
            if len(self.output) > MAX_LINES:
                e = swan.SwanError(f"Stopped after {MAX_LINES} lines of output.", hint="Is there a loop that never ends?")
            self.error = error_dict(e, code)
        except Exception as e:
            self.error = {"message": f"Swan hit an unexpected problem: {e}", "line": 0, "col": 0,
                          "hint": "This is a bug in Swan itself, not in your code.", "source": ""}
        finally:
            self.finished = time.time()
            self.done = True

RUNS = {}

class Lake(BaseHTTPRequestHandler):
    root = os.getcwd()

    def log_message(self, *args):
        pass

    def send(self, status, body, kind="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", kind + ("; charset=utf-8" if "json" in kind or "html" in kind else ""))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length) or b"{}")

    def safe_path(self, rel):
        full = os.path.realpath(os.path.join(self.root, rel))
        if not full.startswith(os.path.realpath(self.root) + os.sep) or not full.endswith(".swan"):
            return None
        return full

    # ── reading ──
    def do_GET(self):
        url = urlparse(self.path)
        query = {k: v[0] for k, v in parse_qs(url.query).items()}
        if url.path in ("/", "/index.html"):
            with open(PAGE, "rb") as f:
                return self.send(200, f.read(), "text/html")
        if url.path == "/api/files":
            return self.send(200, {"root": os.path.basename(os.path.abspath(self.root)) or self.root,
                                   "files": self.list_files(), "version": swan.VERSION})
        if url.path == "/api/file":
            path = self.safe_path(query.get("path", ""))
            if not path or not os.path.exists(path):
                return self.send(404, {"error": "No such file."})
            with open(path, encoding="utf-8") as f:
                return self.send(200, {"path": query["path"], "content": f.read()})
        if url.path == "/api/poll":
            run = RUNS.get(query.get("id"))
            if run is None:
                return self.send(404, {"error": "No such run."})
            start = int(query.get("from", 0))
            end = run.finished or time.time()
            return self.send(200, {"output": run.output[start:], "done": run.done, "error": run.error,
                                   "seconds": round(end - run.started, 2)})
        self.send(404, {"error": "Not found."})

    def list_files(self):
        found = []
        for folder, dirs, files in os.walk(self.root):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_FOLDERS and not d.startswith("."))
            for name in sorted(files):
                if name.endswith(".swan"):
                    found.append(os.path.relpath(os.path.join(folder, name), self.root).replace(os.sep, "/"))
            if len(found) > 500:
                break
        return found

    # ── doing ──
    def do_POST(self):
        url = urlparse(self.path)
        try:
            data = self.body()
        except ValueError:
            return self.send(400, {"error": "Bad request."})
        code = data.get("code", "")
        if url.path == "/api/run":
            run_id = uuid.uuid4().hex
            inputs = [line for line in data.get("input", "").split("\n")] if data.get("input") else []
            RUNS[run_id] = Run(code, data.get("mode", "run"), inputs, data.get("filename") or "untitled.swan")
            for old in [k for k, r in RUNS.items() if r.done and time.time() - (r.finished or 0) > 300]:
                RUNS.pop(old, None)
            return self.send(200, {"id": run_id})
        if url.path == "/api/stop":
            run = RUNS.get(data.get("id"))
            if run:
                run.interp.cancelled = True
            return self.send(200, {"ok": True})
        if url.path == "/api/check":
            try:
                swan.parse(code)
                return self.send(200, {"error": None})
            except swan.SwanError as e:
                return self.send(200, {"error": error_dict(e, code)})
        if url.path == "/api/docs":
            try:
                return self.send(200, {"entries": swan.collect_docs(swan.parse(code)), "error": None})
            except swan.SwanError as e:
                return self.send(200, {"entries": [], "error": error_dict(e, code)})
        if url.path == "/api/save":
            path = self.safe_path(data.get("path", ""))
            if not path:
                return self.send(400, {"error": "Files must end in .swan and live inside this folder."})
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(code)
            return self.send(200, {"ok": True})
        self.send(404, {"error": "Not found."})

def serve(argv):
    port, open_browser, folder = 7777, True, os.getcwd()
    args = list(argv)
    while args:
        a = args.pop(0)
        if a == "--port" and args:
            port = int(args.pop(0))
        elif a == "--no-browser":
            open_browser = False
        else:
            folder = os.path.abspath(a)
    if not os.path.isdir(folder):
        print(f"I couldn't find the folder '{folder}'.")
        return 1
    Lake.root = folder
    swan.prepare_threads()
    server = None
    for attempt in range(20):
        try:
            server = ThreadingHTTPServer(("127.0.0.1", port + attempt), Lake)
            break
        except OSError:
            continue
    if server is None:
        print("I couldn't find a free port for Lake.")
        return 1
    address = f"http://localhost:{server.server_address[1]}"
    print(f"Lake is open at {address}   (editing {folder})")
    print("Press Ctrl+C here to close it.")
    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(address)).start()
    server.serve_forever()
    return 0

if __name__ == "__main__":
    sys.exit(serve(sys.argv[1:]))

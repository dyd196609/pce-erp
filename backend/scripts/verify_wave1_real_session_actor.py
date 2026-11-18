"""Real HTTP/JWT acceptance for the Wave 1 formal-import actor chain."""

from __future__ import annotations

from hashlib import sha256
import io
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from http.cookiejar import CookieJar
from urllib.error import HTTPError, URLError
from urllib.request import build_opener, HTTPCookieProcessor, Request
import uuid

from openpyxl import load_workbook


class HttpResponse:
    def __init__(self, status_code, content, headers=None):
        self.status_code = status_code
        self.content = content
        self.headers = headers or {}

    def json(self):
        return json.loads(self.content.decode("utf-8"))

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}: {self.content.decode('utf-8', errors='replace')}")


class HttpSession:
    def __init__(self):
        self.opener = build_opener(HTTPCookieProcessor(CookieJar()))

    def request(self, method, url, *, headers=None, json_body=None, data=None, files=None, timeout=10):
        request_headers = dict(headers or {})
        body = None
        if json_body is not None:
            body = json.dumps(json_body).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
        elif files:
            boundary = f"----PCE{uuid.uuid4().hex}"
            chunks = []
            for key, value in (data or {}).items():
                chunks.extend([f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n\r\n{value}\r\n".encode("utf-8")])
            for key, (filename, content, content_type) in files.items():
                chunks.extend([
                    f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"; filename=\"{filename}\"\r\nContent-Type: {content_type}\r\n\r\n".encode("utf-8"),
                    content, b"\r\n",
                ])
            chunks.append(f"--{boundary}--\r\n".encode("ascii"))
            body = b"".join(chunks)
            request_headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        request = Request(url, data=body, headers=request_headers, method=method)
        try:
            with self.opener.open(request, timeout=timeout) as response:
                return HttpResponse(response.status, response.read(), dict(response.headers))
        except HTTPError as exc:
            return HttpResponse(exc.code, exc.read(), dict(exc.headers))

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url, *, json=None, **kwargs):
        return self.request("POST", url, json_body=json, **kwargs)


SOURCE_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = SOURCE_ROOT / "backend"
# The gate copies its input into disposable databases; it never writes here.
# Honor the explicitly selected acceptance database instead of silently testing
# another source tree's default database in an isolated integration package.
PRODUCTION_DB = Path(os.environ.get("PCE_DATABASE_PATH") or BACKEND_ROOT / "db.sqlite3").resolve()


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def copy_database(source, target):
    with sqlite3.connect(source) as source_connection, sqlite3.connect(target) as target_connection:
        source_connection.backup(target_connection)


def free_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def wait_ready(base_url, process):
    for _ in range(120):
        if process.poll() is not None:
            raise RuntimeError(f"backend exited early with {process.returncode}")
        try:
            response = HttpSession().get(f"{base_url}/api/auth/login/", timeout=0.5)
            if response.status_code in (400, 405):
                return
        except (URLError, TimeoutError):
            pass
        time.sleep(0.25)
    raise RuntimeError("backend did not become ready")


def login(session, base_url, username, password):
    response = session.post(f"{base_url}/api/auth/login/", json={"username": username, "password": password}, timeout=10)
    response.raise_for_status()
    return response.json()["token"]


def customer_xlsx(template_bytes, code):
    workbook = load_workbook(io.BytesIO(template_bytes))
    sheet = workbook.active
    sheet.cell(2, 1, code)
    sheet.cell(2, 2, "A4真实HTTP会话客户")
    sheet.cell(2, 3, "是")
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


def multipart(content, name="A4-客户人工导入样例.xlsx"):
    return {"file": (name, content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}


def main():
    before_hash = digest(PRODUCTION_DB)
    password = secrets.token_urlsafe(24)
    readonly_password = secrets.token_urlsafe(24)
    run_id = "W1FI-REAL-SESSION-ACTOR-GATE"
    work_root = SOURCE_ROOT / "work"
    work_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pce-wave1-real-session-", dir=str(work_root), ignore_cleanup_errors=True) as folder:
        isolated_db = Path(folder) / "final-isolated.sqlite3"
        drift_db = Path(folder) / "different-runtime.sqlite3"
        trace_path = Path(folder) / "actual-http-trace.jsonl"
        copy_database(PRODUCTION_DB, isolated_db)
        env = os.environ.copy()
        env.update({
            "PCE_DATABASE_PATH": str(isolated_db),
            "PCE_ISOLATED_RUNSERVER_TEST": "1",
            "PCE_REHEARSAL_MAINTENANCE_PASSWORD": password,
            "PCE_REHEARSAL_READONLY_PASSWORD": readonly_password,
            "PCE_FORMAL_IMPORT_ACTOR_TRACE_PATH": str(trace_path),
            "PYTHONDONTWRITEBYTECODE": "1",
        })
        subprocess.run([sys.executable, str(BACKEND_ROOT / "manage.py"), "check"], cwd=SOURCE_ROOT, env=env, check=True, capture_output=True, text=True)
        bootstrap = subprocess.run(
            [sys.executable, str(BACKEND_ROOT / "scripts" / "bootstrap_wave1_formal_import_actor.py"), "--run-id", run_id, "--acceptance-label", "A4"],
            cwd=SOURCE_ROOT, env=env, check=True, capture_output=True, text=True,
        )
        bootstrap_result = json.loads(bootstrap.stdout)
        port = free_port()
        base_url = f"http://127.0.0.1:{port}"
        server = subprocess.Popen(
            [sys.executable, str(BACKEND_ROOT / "manage.py"), "runserver", f"127.0.0.1:{port}", "--noreload"],
            cwd=SOURCE_ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        try:
            wait_ready(base_url, server)
            session = HttpSession()
            token = login(session, base_url, "wave1_import_maintenance_a4", password)
            headers = {"Authorization": f"Bearer {token}"}
            context = session.get(f"{base_url}/api/pde/formal-import/current-context/", headers=headers, timeout=10)
            context.raise_for_status()
            context_data = context.json()
            assert context_data["status"] == "AUTHENTICATED"
            assert context_data["requestActorTrace"]["resolvedEmployeeId"]
            template = session.get(f"{base_url}/api/pde/formal-import/customers/template/", headers=headers, timeout=10)
            template.raise_for_status()
            content = customer_xlsx(template.content, "A4-HTTP-GATE-CUSTOMER")
            preview = session.post(f"{base_url}/api/pde/formal-import/customers/preview/", headers=headers, files=multipart(content), timeout=20)
            preview.raise_for_status()
            preview_data = preview.json()
            assert preview_data["counts"]["create"] == 1 and preview_data["canCommit"]
            commit_fields = {
                "previewFingerprint": preview_data["previewFingerprint"],
                "previewActorBinding": json.dumps(preview_data["previewActorBinding"], ensure_ascii=False),
                "idempotencyKey": "W1FI-REAL-SESSION-A4-CUSTOMER", "confirmed": "true",
            }
            commit = session.post(f"{base_url}/api/pde/formal-import/customers/commit/", headers=headers, data=commit_fields, files=multipart(content), timeout=20)
            commit.raise_for_status()
            assert commit.json()["created"] == 1
            readback = session.get(f"{base_url}/api/pde/a1-foundation/customers/", headers=headers, timeout=10)
            readback.raise_for_status()
            assert "A4-HTTP-GATE-CUSTOMER" in json.dumps(readback.json(), ensure_ascii=False)
            replay_preview = session.post(f"{base_url}/api/pde/formal-import/customers/preview/", headers=headers, files=multipart(content), timeout=20)
            replay_preview.raise_for_status()
            replay_data = replay_preview.json()
            assert replay_data["counts"]["match"] == 1
            replay = session.post(
                f"{base_url}/api/pde/formal-import/customers/commit/", headers=headers,
                data={"previewFingerprint": replay_data["previewFingerprint"], "previewActorBinding": json.dumps(replay_data["previewActorBinding"], ensure_ascii=False), "idempotencyKey": "W1FI-REAL-SESSION-A4-CUSTOMER-REPLAY", "confirmed": "true"},
                files=multipart(content), timeout=20,
            )
            replay.raise_for_status()
            assert replay.json()["created"] == 0 and replay.json()["matched"] == 1
            readonly_session = HttpSession()
            readonly_token = login(readonly_session, base_url, "wave1_import_readonly_a4", readonly_password)
            readonly_headers = {"Authorization": f"Bearer {readonly_token}"}
            denied_preview = readonly_session.post(f"{base_url}/api/pde/formal-import/customers/preview/", headers=readonly_headers, files=multipart(content), timeout=20)
            denied_preview.raise_for_status()
            denied_data = denied_preview.json()
            denied = readonly_session.post(
                f"{base_url}/api/pde/formal-import/customers/commit/", headers=readonly_headers,
                data={"previewFingerprint": denied_data["previewFingerprint"], "previewActorBinding": json.dumps(denied_data["previewActorBinding"], ensure_ascii=False), "idempotencyKey": "W1FI-READONLY-DENIED", "confirmed": "true"},
                files=multipart(content), timeout=20,
            )
            assert denied.status_code == 403
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
        copy_database(isolated_db, drift_db)
        drift_env = {**env, "PCE_DATABASE_PATH": str(drift_db)}
        drift_port = free_port()
        drift_url = f"http://127.0.0.1:{drift_port}"
        drift_server = subprocess.Popen(
            [sys.executable, str(BACKEND_ROOT / "manage.py"), "runserver", f"127.0.0.1:{drift_port}", "--noreload"],
            cwd=SOURCE_ROOT, env=drift_env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        try:
            wait_ready(drift_url, drift_server)
            stale = HttpSession().get(f"{drift_url}/api/pde/formal-import/current-context/", headers={"Authorization": f"Bearer {token}"}, timeout=10)
            assert stale.status_code == 401
            assert "数据库运行上下文已变化" in json.dumps(stale.json(), ensure_ascii=False)
        finally:
            drift_server.terminate()
            try:
                drift_server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                drift_server.kill()
        traces = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert any(item["outcome"] == "PASS" and item["source"] == "ACTUAL_HTTP_REQUEST" for item in traces)
        assert digest(PRODUCTION_DB) == before_hash
        print(json.dumps({
            "gate": "verify:pce-formal-import-real-session-actor", "status": "PASS",
            "chain": ["final isolated DB", "shared bootstrap", "start backend", "login HTTP", "current context", "preview HTTP", "commit HTTP", "readback HTTP"],
            "maintenanceCommit": "PASS", "customerReplay": "PASS",
            "readOnlyPreview": "ALLOW", "readOnlyCommit": "403",
            "databaseSwitchInvalidatesJWT": True, "actualHttpTraceCount": len(traces),
            "bootstrapContext": bootstrap_result["result"]["actorContext"],
            "productionDatabaseSha256": before_hash, "productionWrites": 0,
            "readOnlySourceDatabase": str(PRODUCTION_DB),
        }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"gate": "verify:pce-formal-import-real-session-actor", "status": "FAIL", "error": str(exc)}, ensure_ascii=False, indent=2))
        raise

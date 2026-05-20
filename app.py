import json
import os
import queue
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

from flask import Flask, Response, abort, jsonify, render_template, request, stream_with_context

from parse import claim_pending, get_default_model, get_model_options, start_parse_job
from storage import append_csv_row, build_invoice_filename, get_next_ref

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024
UPLOAD_DIR = Path(__file__).resolve().parent / ".folio_uploads"

_jobs: dict[str, queue.Queue] = {}
_staged_files: dict[str, tuple[str, str]] = {}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/models")
def models():
    return jsonify(get_model_options())


@app.route("/pick-folder")
def pick_folder():
    result = subprocess.run(
        ["osascript", "-e", "POSIX path of (choose folder)"],
        capture_output=True, text=True,
    )
    path = result.stdout.strip() if result.returncode == 0 else None
    return jsonify({"path": path})


@app.route("/parse", methods=["POST"])
def parse():
    model = request.form.get("model", "").strip()
    if not model:
        model = get_default_model()
        if not model:
            return jsonify({"error": "No models available from opencode"}), 500

    temp_files = []
    file_keys = request.form.getlist("file_keys")
    source_ids = request.form.getlist("source_ids")
    UPLOAD_DIR.mkdir(exist_ok=True)
    for i, f in enumerate(request.files.getlist("files")):
        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", dir=UPLOAD_DIR, delete=False)
        f.save(tmp.name)
        tmp.close()
        file_key = file_keys[i] if i < len(file_keys) and file_keys[i] else f.filename
        source_id = source_ids[i] if i < len(source_ids) and source_ids[i] else str(uuid.uuid4())
        _staged_files[source_id] = (f.filename, tmp.name)
        temp_files.append((f.filename, tmp.name, file_key, source_id))

    job_id = str(uuid.uuid4())
    _jobs[job_id] = start_parse_job(temp_files, model)
    return jsonify({"job_id": job_id, "total": len(temp_files)})


@app.route("/retry", methods=["POST"])
def retry():
    body = request.get_json() or {}
    model = body.get("model", "").strip()
    if not model:
        model = get_default_model()
        if not model:
            return jsonify({"error": "No models available from opencode"}), 500

    temp_files = []
    for row in body.get("rows", []):
        source_id = row.get("source_id", "")
        staged = _staged_files.get(source_id)
        if not staged:
            continue
        orig_name, path = staged
        if not os.path.exists(path):
            continue
        file_key = row.get("file_key") or source_id
        temp_files.append((row.get("filename_original") or orig_name, path, file_key, source_id))

    if not temp_files:
        return jsonify({"error": "No retryable staged files found"}), 400

    job_id = str(uuid.uuid4())
    _jobs[job_id] = start_parse_job(temp_files, model)
    return jsonify({"job_id": job_id, "total": len(temp_files)})


@app.route("/stream/<job_id>")
def stream(job_id):
    q = _jobs.get(job_id)
    if q is None:
        abort(404)

    def generate():
        try:
            while True:
                try:
                    event = q.get(timeout=130)
                except queue.Empty:
                    yield 'data: {"type": "error", "error": "timeout"}\n\n'
                    break
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("type") == "done":
                    break
        finally:
            _jobs.pop(job_id, None)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/save", methods=["POST"])
def save():
    body = request.get_json()
    if isinstance(body, list):
        rows, dest_dir = body, None
    else:
        rows = body.get("rows", [])
        dest_dir = body.get("dest_dir") or None

    if not dest_dir:
        abort(400, "dest_dir is required")

    results = []
    for row in rows:
        orig = row.get("filename_original", "")
        file_key = row.get("file_key", "")
        source_id = row.get("source_id", "")
        try:
            result = claim_pending(row["file_id"])
            if result is None:
                raise ValueError("Unknown file_id — already saved or session expired")
            path, is_temp = result

            os.makedirs(dest_dir, exist_ok=True)
            csv_path = os.path.join(dest_dir, "payments.csv")
            ref_num = get_next_ref(csv_path)
            filename = build_invoice_filename(row)
            dest = os.path.join(dest_dir, filename)
            if is_temp:
                shutil.move(path, dest)
            else:
                shutil.copy2(path, dest)
            if source_id:
                _staged_files.pop(source_id, None)
            append_csv_row(csv_path, row["targetCurrency"], row["amount"], row["paymentReference"], ref_num)
            results.append({
                "filename_original": orig,
                "file_key": file_key,
                "source_id": source_id,
                "filename": filename,
                "success": True,
            })
        except Exception as e:
            results.append({
                "filename_original": orig,
                "file_key": file_key,
                "source_id": source_id,
                "success": False,
                "error": str(e),
            })
    return jsonify(results)


if __name__ == "__main__":
    app.run(debug=True, port=5001, host="127.0.0.1")

"""
Thrive Africa - Cloud Engineering Internship
Task tracker: the application you will deploy, learn, and improve.

It is deliberately small. Read the whole thing - it is about 200 lines and
you will be asked in week 3 what each part does.

Four things in here exist for the four projects:

  /health          a load balancer checks this        -> Scale it
  /metrics         numbers worth graphing             -> Watch it
  a real database  data you can lose and restore      -> Recover it
  DATABASE_URL     a password that must not be in code -> Secure it

Plus /admin/break, which staff use to break your app on demo day.
"""

import os
import time
import socket
import json
import logging
import random
from datetime import datetime, timezone

from flask import Flask, request, render_template, redirect, url_for, jsonify, Response
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, text
from sqlalchemy.orm import declarative_base, sessionmaker

# ---------------------------------------------------------------- config
# Everything configurable comes from the environment. Nothing is hardcoded
# here, which is what lets the same image run on your laptop and on AWS.

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:////data/tasks.db")
APP_VERSION  = os.environ.get("APP_VERSION", "dev")
BREAK_TOKEN  = os.environ.get("BREAK_TOKEN", "")
PORT         = int(os.environ.get("PORT", "8080"))

INSTANCE  = socket.gethostname()[:12]
STARTED   = time.time()

# Structured logs. One JSON object per line, which is what CloudWatch
# Logs Insights can query. Printing free-form text makes that much harder.
logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("tasks")


def emit(event, **fields):
    log.info(json.dumps({
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "instance": INSTANCE,
        "version": APP_VERSION,
        **fields,
    }))


# ---------------------------------------------------------------- database
# SQLAlchemy talks to SQLite and Postgres through the same code. In week 2
# DATABASE_URL points at a file inside the container - restart it and your
# data is gone. In week 3 it points at a real database and the data survives.

engine_args = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    # check_same_thread lets several threads share the connection.
    # timeout makes a thread wait for a lock instead of failing instantly.
    engine_args["connect_args"] = {"check_same_thread": False, "timeout": 15}

engine = create_engine(DATABASE_URL, **engine_args)
Session = sessionmaker(bind=engine)
Base = declarative_base()


class Task(Base):
    __tablename__ = "tasks"
    id         = Column(Integer, primary_key=True)
    title      = Column(String(200), nullable=False)
    done       = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


def init_db():
    """Create the table if it is missing, and put something in it the first
    time so the page is not empty.

    This has to tolerate starting twice at once. Several web workers boot in
    parallel, and they all run this. Two of them can both look, both see no
    table, and both try to create it - one wins and the other gets an error.
    That is a race condition, and it is the kind of thing that only shows up
    under concurrency. So: try, and treat failure as "somebody else got there
    first" rather than as fatal.

    If the database really is unreachable, we still let the app start. It will
    report itself unhealthy on /health, which is far more useful than a
    container that crashes on boot and tells you nothing."""
    if DATABASE_URL.startswith("sqlite"):
        path = DATABASE_URL.replace("sqlite:///", "")
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    try:
        Base.metadata.create_all(engine, checkfirst=True)
    except Exception as e:
        emit("db.create.skipped", reason=str(e)[:160])

    try:
        s = Session()
        try:
            if s.query(Task).count() == 0:
                for title in [
                    "Deploy this app in the AWS console",
                    "Write down every step you took",
                    "Rebuild the same thing with Terraform",
                ]:
                    s.add(Task(title=title))
                s.commit()
                emit("db.seeded")
        finally:
            s.close()
    except Exception as e:
        emit("db.seed.skipped", reason=str(e)[:160])


# ---------------------------------------------------------------- metrics
# Counters live in memory, so each running copy has its own. That is a real
# property of the system, not a bug: when you scale to four tasks in week 5,
# refreshing this page will show four different sets of numbers.

METRICS = {
    "requests_total": 0,
    "errors_total": 0,
    "tasks_created_total": 0,
    "duration_sum": 0.0,
    "duration_count": 0,
}

# Break mode is how staff make your app fail on demo day.
BREAK = {"mode": "off"}

app = Flask(__name__)


@app.before_request
def _start_timer():
    request._t0 = time.perf_counter()

    if BREAK["mode"] == "slow":
        time.sleep(random.uniform(1.5, 3.0))
    elif BREAK["mode"] == "errors" and request.path not in ("/admin/break",):
        if random.random() < 0.4:
            METRICS["errors_total"] += 1
            emit("request.failed", path=request.path, reason="injected")
            return Response("Internal Server Error", status=500)


@app.after_request
def _record(response):
    elapsed = time.perf_counter() - getattr(request, "_t0", time.perf_counter())
    METRICS["requests_total"] += 1
    METRICS["duration_sum"] += elapsed
    METRICS["duration_count"] += 1
    if response.status_code >= 500:
        METRICS["errors_total"] += 1

    emit("request",
         path=request.path,
         method=request.method,
         status=response.status_code,
         ms=round(elapsed * 1000, 1))
    return response


# ---------------------------------------------------------------- pages

def uptime_text():
    s = int(time.time() - STARTED)
    if s < 60:
        return "%ds" % s
    if s < 3600:
        return "%dm %ds" % (s // 60, s % 60)
    return "%dh %dm" % (s // 3600, (s % 3600) // 60)


@app.route("/")
def index():
    s = Session()
    try:
        tasks = s.query(Task).order_by(Task.done, Task.created_at.desc()).all()
        open_count = sum(1 for t in tasks if not t.done)
        return render_template(
            "index.html",
            tasks=tasks,
            open_count=open_count,
            done_count=len(tasks) - open_count,
            instance=INSTANCE,
            version=APP_VERSION,
            uptime=uptime_text(),
            requests=METRICS["requests_total"],
            db_kind="postgres" if DATABASE_URL.startswith("postgres") else "sqlite",
            # Only a genuinely failing health check shows in the UI.
            # "slow" and "errors" stay silent - a real system does not
            # announce that it is broken, you find that out from metrics.
            broken=BREAK["mode"] == "db",
        )
    finally:
        s.close()


@app.route("/tasks", methods=["POST"])
def add_task():
    title = (request.form.get("title") or "").strip()
    if title:
        s = Session()
        try:
            s.add(Task(title=title[:200]))
            s.commit()
            METRICS["tasks_created_total"] += 1
            emit("task.created", title=title[:200])
        finally:
            s.close()
    return redirect(url_for("index"))


@app.route("/tasks/<int:task_id>/toggle", methods=["POST"])
def toggle_task(task_id):
    s = Session()
    try:
        t = s.get(Task, task_id)
        if t:
            t.done = not t.done
            s.commit()
            emit("task.toggled", task_id=task_id, done=t.done)
    finally:
        s.close()
    return redirect(url_for("index"))


@app.route("/tasks/<int:task_id>/delete", methods=["POST"])
def delete_task(task_id):
    s = Session()
    try:
        t = s.get(Task, task_id)
        if t:
            s.delete(t)
            s.commit()
            emit("task.deleted", task_id=task_id)
    finally:
        s.close()
    return redirect(url_for("index"))


# ---------------------------------------------------------------- machine endpoints

@app.route("/health")
def health():
    """The load balancer calls this every few seconds. If it returns anything
    other than 200, the load balancer stops sending traffic to this copy."""
    if BREAK["mode"] == "db":
        return jsonify(status="unhealthy", database="unreachable"), 503
    try:
        s = Session()
        s.execute(text("SELECT 1"))
        s.close()
    except Exception as e:
        emit("health.failed", error=str(e)[:200])
        return jsonify(status="unhealthy", database="error"), 503

    return jsonify(
        status="ok",
        database="connected",
        instance=INSTANCE,
        version=APP_VERSION,
        uptime_seconds=int(time.time() - STARTED),
    )


@app.route("/metrics")
def metrics():
    """Prometheus text format. Point a scraper at it, or just read it."""
    avg_ms = 0.0
    if METRICS["duration_count"]:
        avg_ms = (METRICS["duration_sum"] / METRICS["duration_count"]) * 1000

    s = Session()
    try:
        open_tasks = s.query(Task).filter(Task.done.is_(False)).count()
    except Exception:
        open_tasks = -1
    finally:
        s.close()

    body = "\n".join([
        "# HELP tasks_requests_total Requests served by this instance",
        "# TYPE tasks_requests_total counter",
        'tasks_requests_total{instance="%s"} %d' % (INSTANCE, METRICS["requests_total"]),
        "# HELP tasks_errors_total Requests that returned 5xx",
        "# TYPE tasks_errors_total counter",
        'tasks_errors_total{instance="%s"} %d' % (INSTANCE, METRICS["errors_total"]),
        "# HELP tasks_created_total Tasks added",
        "# TYPE tasks_created_total counter",
        'tasks_created_total{instance="%s"} %d' % (INSTANCE, METRICS["tasks_created_total"]),
        "# HELP tasks_request_duration_ms Mean request duration",
        "# TYPE tasks_request_duration_ms gauge",
        'tasks_request_duration_ms{instance="%s"} %.2f' % (INSTANCE, avg_ms),
        "# HELP tasks_open Tasks not yet done",
        "# TYPE tasks_open gauge",
        'tasks_open{instance="%s"} %d' % (INSTANCE, open_tasks),
        "",
    ])
    return Response(body, mimetype="text/plain; version=0.0.4")


@app.route("/api/tasks")
def api_tasks():
    """JSON, for load tests and scripts."""
    s = Session()
    try:
        return jsonify([
            {"id": t.id, "title": t.title, "done": t.done,
             "created_at": t.created_at.isoformat() if t.created_at else None}
            for t in s.query(Task).order_by(Task.id).all()
        ])
    finally:
        s.close()


@app.route("/admin/break", methods=["GET", "POST"])
def admin_break():
    """Staff use this to break your app without telling you how.

    Modes:  off | slow | errors | db
    Send the token as ?token=... or the X-Break-Token header.
    """
    token = request.args.get("token") or request.headers.get("X-Break-Token", "")
    if not BREAK_TOKEN or token != BREAK_TOKEN:
        return jsonify(error="unauthorised"), 401

    mode = (request.args.get("mode") or "off").lower()
    if mode not in ("off", "slow", "errors", "db"):
        return jsonify(error="mode must be one of: off, slow, errors, db"), 400

    BREAK["mode"] = mode
    emit("break.set", mode=mode)
    return jsonify(mode=mode, instance=INSTANCE)


@app.errorhandler(500)
def on_error(e):
    emit("error.unhandled", error=str(e)[:200])
    return render_template("error.html"), 500


init_db()
emit("app.started", database=DATABASE_URL.split("@")[-1], port=PORT)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=False)

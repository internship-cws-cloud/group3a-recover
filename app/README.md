# Task tracker

The application you will deploy, learn, and improve over the next six weeks.

It is a to-do list. That is deliberate — the application is not the interesting
part, and it should not be. What matters is that it is a **real running system**:
it has a health check, it emits metrics, it keeps data in a database, and it
needs a password it must not carry in its own source code.

Those four things are the four projects.

---

## Run it on your laptop

You need Docker. Nothing else.

```bash
docker compose up --build
```

Open <http://localhost:8080>.

To stop it:

```bash
docker compose down
```

To stop it **and throw the data away**, which is worth doing once so you see
what happens:

```bash
docker compose down -v
```

## Run it the way week 3 will

Week 2 uses SQLite — a file inside the container. Restart the container and
your tasks are gone. Week 3 moves to a real database. You can try that now:

```bash
docker compose --profile pg up --build -d
DATABASE_URL=postgresql://tasks:changeme@db:5432/tasks docker compose up web
```

Same image, same code, one environment variable. That is the whole point of
keeping configuration out of the source.

---

## What the page shows you

The left column is **the machine**. The right column is **the application**.

The left column is the one to pay attention to:

| Field | Why it matters |
|---|---|
| `served by` | The ID of the container serving this page. When you scale to four copies in week 5, refresh and watch this change. |
| `uptime` | How long *this copy* has been running. A deploy resets it. So does a crash. |
| `requests` | Counted in memory, so each copy has its own number. |
| `storage` | `sqlite` or `postgres`. It changes on its own when you change `DATABASE_URL`. |

Nothing here is decoration. Every value is something you will need to explain
at some point.

---

## The endpoints

| Path | What it does |
|---|---|
| `/` | The task list |
| `/health` | Returns 200 and checks the database. **The load balancer calls this.** Returns 503 if the database is unreachable. |
| `/metrics` | Request count, error count, mean duration, open tasks. Prometheus text format. |
| `/api/tasks` | The tasks as JSON. Useful for load tests and scripts. |
| `/admin/break` | Staff only. See below. |

Try them now:

```bash
curl localhost:8080/health
curl localhost:8080/metrics
curl localhost:8080/api/tasks
```

### `/health` is not decoration

When you put a load balancer in front of this app, it calls `/health` every
few seconds. If it gets anything other than a 200, it **stops sending traffic
to that copy**. Get the health check wrong and your app will look broken when
it is fine, or look fine when it is broken.

### `/metrics` is per copy

The counters live in memory. Four running copies means four different sets of
numbers. That is not a bug — it is why you aggregate metrics somewhere central
instead of reading them off one machine.

---

## How staff will break your app

`/admin/break` takes a token that staff hold and you do not.

```
/admin/break?mode=slow&token=...      every request takes 1.5-3 seconds
/admin/break?mode=errors&token=...    40% of requests return 500
/admin/break?mode=db&token=...        the health check starts failing
/admin/break?mode=off&token=...       back to normal
```

Two of those modes are silent. The page will not tell you something is wrong —
you have to notice from your dashboard, your alarms, or your logs. That is the
entire point of the demo in week 7.

---

## The logs

Every request writes one line of JSON:

```json
{"ts":"2026-09-14T10:22:01Z","event":"request","instance":"7f3a2b1c",
 "path":"/","method":"GET","status":200,"ms":4.2}
```

One object per line, not free-form text. That is what makes it queryable in
CloudWatch Logs Insights later. Printing `print("something happened")` would
make week 5 much harder for the group doing **Watch it**.

---

## Configuration

Nothing is hardcoded. Everything comes from the environment, which is what
lets the same image run on your laptop and on AWS.

| Variable | Default | Notes |
|---|---|---|
| `DATABASE_URL` | `sqlite:////data/tasks.db` | Week 3 changes this to a real database |
| `APP_VERSION` | `dev` | Set it to the git SHA in your pipeline |
| `BREAK_TOKEN` | empty | Staff set this. Empty means `/admin/break` refuses everything. |
| `PORT` | `8080` | |

Copy `.env.example` to `.env` for local work. **Never commit `.env`.** The
database password in `DATABASE_URL` is exactly the kind of thing that ends up
in a public repository and then in somebody's crypto mining bill.

---

## The code

One file, about 200 lines, commented throughout. Read it.

```
app.py              everything
templates/          the two pages
static/style.css    the styling
Dockerfile          how it becomes a container
requirements.txt    four dependencies
docker-compose.yml  local development only. AWS never sees this file.
```

You will be asked in week 3 what each part does, and in week 7 why your system
behaves the way it does under failure. The honest route to both answers is to
have read this.

## Things worth trying before week 2

1. Start it, add a task, then `docker compose down` and `up` again. Is the task
   still there? Now try `down -v` first. Why is that different?
2. Run `curl localhost:8080/health` while the app is running. Now stop the
   database (`docker compose stop db`, on the pg profile) and run it again.
3. Watch the logs with `docker compose logs -f web` while you click around.
4. Look at `/metrics`, refresh the page ten times, and look again.

If you can explain all four, week 2 will go well.

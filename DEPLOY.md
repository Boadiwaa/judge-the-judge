# Deploying to fly.io

**Don't deploy until the clinical content has been reviewed** (cases, answer key, About page). See
`REVIEW_QUEUE.md`.

The deployed app serves precomputed results only. It never runs a model and needs no API key or GPU.

## 0. Before you deploy

1. Re-run the pipeline if any case or prompt changed (see "Updating results" below), and commit
   `data/results/`. Only notes that changed are re-judged; the rest come from the cache.
2. Test the image locally:

   ```bash
   docker build -t jtj .
   docker run --rm -p 8080:8080 -e RATER_CODE=local-test -e OWNER_CODE=local-owner jtj
   ```

   Open http://localhost:8080.

If `fly deploy` fails with a registry `401 Unauthorized` from the remote builder, build locally instead
(Docker Desktop must be running; flyctl needs its socket):

```bash
DOCKER_HOST=unix://$HOME/.docker/run/docker.sock fly deploy --ha=false --local-only
```

## 1. Create the app (once)

```bash
fly auth login
fly launch --no-deploy --copy-config --name <your-app-name> --region lhr
```

`--copy-config` keeps this repo's `fly.toml`. Say **no** to any offer to add a database.

## 2. Secrets

```bash
fly secrets set RATER_CODE='<code you give clinicians>' OWNER_CODE='<code only you know>'
```

- `RATER_CODE` turns on "Rate notes". Without it, rater mode shows as disabled.
- `OWNER_CODE` turns on the ratings export at `/export/ratings.zip`. Your browser asks for a username
  (anything) and a password (this code).

## 3. Volume for clinician ratings (before inviting raters)

```bash
fly volumes create jtj_data --size 1 --region lhr
```

Then uncomment the `[mounts]` block at the end of `fly.toml` (done for judge-the-judge on 2026-10-29). Without a volume, ratings are lost
whenever the machine restarts.

## 4. Deploy

```bash
fly deploy
fly scale count 1
```

Run **exactly one machine**. Flet keeps each visitor's session in memory over a WebSocket, and the
ratings database is a single SQLite file on the volume.

## 5. Anonymous usage counts

The app logs anonymous usage (visits, pages viewed, phone vs desktop, challenge scores, protocol downloads)
to `/data/usage.sqlite` on the same volume. No cookies, IP addresses or personal data (`src/jtj/app/usage.py`).
Download `https://<your-app>.fly.dev/export/usage.zip` (password: `OWNER_CODE`): it holds `events.csv` and a
plain-text `summary.txt`.

## 6. Get the ratings back

Either download the CSVs in the browser, from `https://<your-app>.fly.dev/export/ratings.zip`
(password: `OWNER_CODE`), or copy the raw database:

```bash
fly ssh sftp get /data/ratings.sqlite ./data/ratings.sqlite
```

Then regenerate the agreement results locally, commit, and redeploy:

```bash
.venv/bin/python scripts/compute_agreement.py
```

## Updating results after a change

```bash
llama-server -m <path>/gemma-4-E2B-it-Q4_0.gguf --alias gemma-4-E2B-it-Q4_0 --jinja -c 16384 -ngl 99 --port 8081
.venv/bin/python scripts/validate_cases.py
.venv/bin/python scripts/run_judges.py --judge all
.venv/bin/python scripts/compute_metrics.py
.venv/bin/python scripts/compute_metrics.py --strict-spec
git add data/results && git commit -m "Regenerate results" && fly deploy
```

## Costs and behaviour

- `auto_stop_machines = "stop"` and `min_machines_running = 0`: the machine sleeps when idle and wakes
  on the next visit. The first visit after a sleep is slower.
- The Flet web client is about 3.5 MB gzipped. A cold first load takes a few seconds while the browser
  starts it.

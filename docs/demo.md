# Demo

Recording: `docs/demo.gif` (added after the local run below is captured).

## Recording script

1. Start the stack (`docker compose up --build`, or API + worker in two
   terminals) with an empty database and open http://localhost:8000 —
   the dashboard shows the empty state.
2. Run `python scripts/run_demo_seed.py`. It registers three monitors and
   checks each once:
   - **GitHub** (https://github.com) — comes up UP
   - **TU Dortmund** (https://www.tu-dortmund.de) — comes up UP
   - **Dead example** (http://127.0.0.1:9) — connection refused, DOWN
3. Back on the dashboard: two green cards and one red card, the header
   stats read 3 monitors / 2 up / 1 down, and each card shows its first
   latency and uptime values.
4. Click **Check now** on the dead example — it stays red and the error
   text appears on the card.
5. Add a new monitor from the form (e.g. your own site), watch it appear
   as PENDING and flip to UP on the worker's next pass.
6. Leave it running for a minute so the latency sparklines build up on
   the UP cards; end on the full dashboard.

Target length: ~40 seconds.

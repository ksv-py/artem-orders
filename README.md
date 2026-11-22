# Artem Orders — furniture / interior order tracking (v1)

A mobile-first web app for Artem Interiors & Constructions (Delhi) that
replaces diary/notebook order tracking in the furniture workshop. When a
customer asks "Meri almaari kab tak banegi?", the app answers with the
order's measurements, design photo, wood, karigar, delivery date and
progress photos.

## What it does

- **Dashboard** — counts (in progress, overdue, due this week,
  delivered), orders due soon, and karigar workload (jobs per karigar).
- **Orders** — customer name, item (wardrobe/almari, modular kitchen,
  bed, dining table, TV unit, door, other), size/measurements,
  wood/material (teak, sheesham, plywood, MDF, laminate, other),
  status (New / Cutting / Assembly / Polish / Ready / Delivered),
  delivery date, notes, design photo. Status and karigar can be
  updated as work progresses.
- **Delivery dates on top** — the order list is sorted by delivery
  date (soonest first). Overdue orders are highlighted red, due-today
  is flagged, and the dashboard lists orders due this week.
- **Karigars** — craftsmen with a skill (carpenter, polisher, painter,
  helper). Each order is assigned to one karigar; the Karigars page
  shows which jobs each karigar currently has.
- **Work photos** — attach multiple progress photos to an order, each
  with a stage and caption. Each order page has a "Send update to
  customer on WhatsApp" button that opens a `wa.me` link with the
  order update text prefilled (no WhatsApp API, just a share link).
- **Roles** — none in v1: a single workshop-manager view.

## Run it locally

```bash
pip install -r requirements.txt
python app.py
```

Then open http://127.0.0.1:5000 in a browser (or on a phone on the
same network via the machine's IP). The database file
`artem_orders.db` is created on first boot with demo seed data. (On
Debian/Ubuntu systems where pip refuses system-wide installs, use a
virtual environment: `python3 -m venv .venv && .venv/bin/pip install
-r requirements.txt` then `.venv/bin/python app.py`.)

## Deploy on Render

The repo includes `render.yaml` (free plan). Render runs
`pip install -r requirements.txt` then `python app.py`. The app reads
the `PORT` environment variable. Note: on Render's free plan the
SQLite file and uploaded photos live on the instance disk, so data
resets on redeploy. Use a Render persistent disk or a hosted
database before using this for real orders.

## Demo seed data

On first boot the app seeds 4 karigars (Raju and Sunil, carpenters;
Imran, polisher; Gopal, helper) and 5 demo orders so the dashboard
is not empty. These are demo names from the reference Reel's world,
not real clients or projects. One order (Gupta ji's bed, due
20 Nov 2026, in Polish) is already overdue so the overdue highlight
is visible. Delete `artem_orders.db` and restart to re-seed, or add
real orders/karigars from the app.

## v1 limitations (deliberate)

- **No login/passwords.** Anyone with the link can open it. Add real
  auth (per-manager accounts) before giving it to a team.
- **No WhatsApp Business API.** The update button opens a `wa.me`
  share link with the text prefilled; the manager taps it, picks the
  customer chat, and sends. A `wa.me` text link cannot attach a
  photo, so work photos are shared from the phone gallery alongside
  the message, not from inside the link.
- **SQLite + local files.** Fine for a small workshop on one server;
  move to a hosted database and object storage for real use.
- **No push notifications.** Overdue orders show on the dashboard
  and in the order list; nothing pings the manager.
- **No customer-facing view.** Customers do not get a login or a
  tracking link in v1; updates go to them over WhatsApp.

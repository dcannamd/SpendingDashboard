# North America Spending Explorer

A dashboard showing what households spend money on, by US state and Canadian
province, with 10 to 15 years of history. Built to help spot product
opportunities: where a region over-indexes on a category, and which categories
are growing.

It ships with **synthetic demo data** (clearly bannered) so you can see it
working. Follow "Load real data" to replace it.

## How it works

```
pipeline/   Python (standard library only) - fetches, normalizes, derives
data/       history.csv (growing time series) + cpi.json (inflation cache)
web/        static dashboard (HTML/CSS/JS, no build step)
render.yaml Render Blueprint: static site + weekly cron job
```

1. **Fetchers** pull BEA (US, per person) and Statistics Canada (per household),
   map each source's categories onto 8 common categories, and append to
   `data/history.csv`. First run backfills ~15 years; later runs add new
   releases and overwrite revised figures.
2. **build.py** turns that into `web/data/spending.json`: budget share,
   nominal spend and inflation-adjusted spend (BLS and StatCan CPI).
3. **The dashboard** reads that one JSON file. Index vs average, growth and
   trends are computed in the browser, so filters are instant.

Regions are compared by **share of budget**, never by raw dollars across
countries, because BEA is per person and Statistics Canada is per household.

## Run locally

```bash
python -m pipeline.make_demo_data      # synthetic data, no internet needed
python -m http.server -d web 8000      # open http://localhost:8000
```

## Load real data

1. Get a free BEA key: https://apps.bea.gov/API/signup/
   (BLS key is optional: https://data.bls.gov/registrationEngine/)
2. Run the source check first. It was written without access to the live APIs,
   so this confirms the table IDs and category matching on your machine:
   ```bash
   export BEA_API_KEY=your_key
   python -m pipeline.check_sources
   ```
   Fix anything marked `FAIL` or `!! UNMAPPED` (mappings are plain dicts at the
   top of `fetch_statcan.py` and `fetch_bea.py`).
3. Build: `python -m pipeline.build`, then reload the dashboard.

## Deploy: GitHub + Render

1. Push this folder to a GitHub repo.
2. In Render: **New > Blueprint**, pick the repo. It creates the static site
   (`web/`) and the weekly cron job.
3. In the cron job's environment set `GITHUB_REPO` (`owner/repo`), `GITHUB_TOKEN`
   (fine-grained token, Contents: read & write on that repo only), `BEA_API_KEY`
   and optionally `BLS_API_KEY`.
4. Each run refreshes data, commits it, and the push redeploys the site.
   Run `data/history.csv` and `web/data/spending.json` through git so history
   is preserved.

Cron jobs are a paid Render service; check current pricing. The static site is
free.

## Things to know

- **Not live.** Official spending data is annual and lags 1 to 2 years. Weekly
  refreshes pick up new releases as they are published.
- **Categories are coarse** because BEA's state data is. Pets, hobbies, baby
  gear and the like are not separable here.
- **Cross-agency matching is approximate** (US food includes restaurants and
  hotels; Canadian food does not split them).
- **Averages weight every region equally**, not by population.
- `BREAK_YEARS` in `pipeline/common.py` is empty. Add years where an agency
  changed methodology and they appear as dashed lines on trend charts.
- COVID years (2020 to 2021) are shaded on trend charts.

## Next steps

- Add Mexico (INEGI ENIGH) as a third tile grid.
- Add Google Trends by state/province as a product-demand signal for
  specific items.
- Population-weighted benchmarks.

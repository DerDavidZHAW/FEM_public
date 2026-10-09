# Historical data for the CH-only back-cast

Downloads and prepares observed hourly data for Switzerland and its four neighbours, so that a
`CH_only` run can be fed real neighbour prices and border limits, and its CH price can be
compared with the real one. Nothing here changes the model; feeding the data into a run is the
next step.

## Run

From the repo root, for any period of local (Europe/Zurich) days, both ends inclusive:

```bash
python -m data_prep.historical.download --start 2023-10-01 --end 2026-09-30
python -m data_prep.historical.process --start 2023-10-01 --end 2026-09-30
python -m data_prep.historical.plot_overview --start 2023-10-01 --end 2026-09-30
python -m data_prep.historical.plot_trade_ntc --start 2025-10-01 --end 2026-09-30 --processed 2023-10-01 2026-09-30
```

- **download** writes raw files to `input/historical/raw/` (gitignored, about 140 MB for three
  years). Files on disk are kept; `--force` fetches them again. Use it for files of the
  running year, which the publishers keep extending (Swissgrid `*-<this year>.*`, BFE).
  Energy-Charts allows 2 requests per minute, so three years take about 13 minutes.
  - **Download manifest:** every file is recorded in `input/historical/raw_manifest.json`, which can be
    committed. Each entry holds the source URL (the ENTSO-E token is redacted), retrieval time, HTTP
    Last-Modified, ETag, size and SHA-256.
  - **Reuse rule:** a file on disk is reused only if it still matches its checksum and came from the
    URL the code now uses. Otherwise download stops and asks for `--force`.
  - **Files from before 2026-10-09 16:40 local:** their entries carry the checksum and the file write
    time, but no HTTP metadata until they are fetched again with `--force`.
- **process** writes hourly UTC tables to `input/historical/processed/<start>_<end>/`, plus
  `provenance.json`. It records:
  - the period;
  - the git commit, whether `data_prep/historical` had uncommitted changes, and a checksum of every code
    file;
  - every setting in `config.py` (e.g. `CAPACITY_HOURLY_RULE`, `ONSITE_SOLAR_SHARE`);
  - each raw file with its checksum and manifest source; hand-copied files are marked as not in the
    manifest;
  - the checksum of every output table.

  Processing stops if a raw file no longer matches its manifest checksum.
- **plot_overview** writes `plots/historical_overview_<start>_<end>.html`.
- **plot_trade_ntc** writes `trade_vs_ntc_<start>_<end>` as `.html`, `.png` and `_limit_stats.csv`, to
  `plots/` or to `--out-dir`.
  - Content: per border, the combined day-ahead NTC, the scheduled commercial exchange and the
    physical flow, daily or hourly. A table counts the hours at and above each limit, and how many of
    the hours above it the Swissgrid intraday NTC covers.
  - `--processed` names the processed folder when it spans more than the plotted days. The script
    raises if that folder lacks any plotted hour.

ENTSO-E day-ahead NTC needs a personal token in the environment variable `ENTSOE_API_KEY`.
To request one, register on transparency.entsoe.eu, then email transparency@entsoe.eu with the
subject "Restful API access". With the token set, run:

```bash
python -m data_prep.historical.download --start 2023-10-01 --end 2026-09-30 --sources entsoe_ntc
```

Then rerun `process`. Without the token, that step stops with an error.

## Sources

| Data | Source | Coverage |
|---|---|---|
| Day-ahead prices CH, DE-LU, FR, IT-North, AT | Energy-Charts `/v2/price` (CC BY 4.0, Bundesnetzagentur / SMARD.de) | full period; neighbours quarter-hourly from 2025-10-01, averaged to hours |
| CH generation by type, load, net trade | Energy-Charts `/v2/public_power?country=ch` | full period, hourly |
| CH scheduled exchanges per border | Energy-Charts `/v2/cbet` | full period, quarter-hourly |
| CH physical flows per border | **Swissgrid metered** (energy overview workbook); Energy-Charts `/v2/cbpf` kept for reference only | Swissgrid: to its latest published month; Energy-Charts: full period |
| CH installed capacity per type (yearly) | Energy-Charts `/v2/installed_power` | to 2025 |
| CH consumption, production, metered exchanges per direction | Swissgrid `EnergieUebersichtCH-<year>.xlsx` | full period; the running year lags about one month |
| Day-ahead NTC, 8 directions | Swissgrid D-2 NTC XML, one file per day | **current year only** (from 2026-01-01) |
| Intraday NTC, net commercial flows, spot spreads | Swissgrid `Grenzfluesse-<year>.csv` | **current year only** |
| Day-ahead NTC, 8 directions | ENTSO-E A61 | needs a token; not yet run against the live API |
| Day-ahead NTC, 8 directions, Oct-Dec 2025 | ENTSO-E Transparency Platform web table (TR 11.1), copied by hand into `raw/entsoe_web/` | 92 days; stopgap until the token arrives |
| Storage-lake content, weekly | BFE open data ogd17, from `bfe-ogd.ch`. Until 2026-10-09 the `uvek-gis.admin.ch` mirror was used; it lagged by one weekly reading. | full period, including the first reading after the period end |
| National electricity balance, monthly (end use, losses, pumping, production by type) | BFE open data ogd35 | to the latest published month; the running year is provisional |

## Processed tables

All tables share the index column `time_utc`, the UTC start of each hour. Exchanges are
positive for imports into CH. Columns are named after the FEM nodes (`CH00`, `DE00`, `FR00`,
`IT00`, `AT00`), and directions read `<from>_to_<to>` (e.g. `DE_to_CH`).

| File | Content |
|---|---|
| `prices_day_ahead_hourly.csv` | EUR/MWh per node |
| `ch_public_power_hourly.csv` | MW per generation type, plus `load` and `cross_border_electricity_trading` |
| `ch_exchanges_scheduled_hourly.csv` | Scheduled commercial exchange (Energy-Charts), MW per neighbour, plus `sum` |
| `ch_exchanges_physical_hourly.csv` | Physical flow, **Swissgrid metered**, MW per neighbour, plus `sum`. Ends with Swissgrid's latest published month.<br>**Why not Energy-Charts:** on the FR border it shows about 15% more flow than Swissgrid, in both directions and in every month since Oct 2023. BFE monthly imports agree with Swissgrid. |
| `ch_exchanges_physical_energy_charts_hourly.csv` | Energy-Charts physical flow (cbpf), **reference only**; compared with Swissgrid in `validation_report.csv` |
| `swissgrid_overview_hourly.csv` | MW: consumption, production, metered flow per direction, net import per neighbour |
| `swissgrid_cross_border_hourly.csv` | intraday NTC (`ntc_id_*`), net commercial flows, spot spreads |
| `ntc_swissgrid_d2_hourly.csv` | day-ahead NTC per direction, MW |
| `ntc_entsoe_a61_hourly.csv` | same, from ENTSO-E (only after the token step) |
| `ntc_entsoe_web_hourly.csv` | same, from the hand copy of the ENTSO-E web table (Oct-Dec 2025) |
| `ntc_dayahead_combined_hourly.csv` | Swissgrid D-2 where available, else the ENTSO-E web copy; `source_<direction>` names the source of each value |
| `nuclear_availability_hourly.csv` | generation, net capacity, outage = capacity - generation, availability |
| `reservoir_weekly_bfe.csv` | GWh per region and maximum content; starts with the last reading before the period |
| `ch_demand_option_a_hourly.csv` | Swiss demand without storage pumping, MW (`demand.py`). **Use `demand_MW`**, built as follows:<br>- Swissgrid end-user consumption;<br>- plus grid losses: BFE monthly, in proportion to end-user consumption;<br>- plus on-site consumption: BFE end use minus Swissgrid end-user, a monthly total.<br>**Assumption:** half of the on-site consumption is placed like PV output and half flat (`ONSITE_SOLAR_SHARE = 0.5` in `config.py`). The real split is not published. The extremes stay as columns: `demand_solar_shaped_MW` (all like PV) and `demand_flat_MW` (all flat).<br>Monthly demand equals BFE Landesverbrauch. Months without complete data or without BFE publication stay NaN. |
| `coverage_report.csv` | missing hours and the longest gap for each column |
| `validation_report.csv` | cross-checks between sources (see `checks.py`) |

### ENTSO-E web copy (Oct-Dec 2025)

Swissgrid publishes D-2 NTC files only for the current year, and none of its 2025 files are archived publicly.

**Source.** The same values were read from the ENTSO-E Transparency Platform table "Forecast Transfer
Capacities, day-ahead, BZN|CH" in a browser, one page per day, after accepting the platform terms.
- Each day is stored as one line of `raw/entsoe_web/*.txt`, with an hour count and a checksum computed on
  the page.
- `entsoe_web.py` re-checks both and raises on any mismatch.

**Validation.** On 2026 check days (`raw/entsoe_web/validation_2026/`) the ENTSO-E values equal the
Swissgrid D-2 files in every value (192/192 on 15 Jan, 184/184 on the 23-hour 29 Mar).

**24 Sep 2026.** Swissgrid's public file for that day is the early version 1 with "n.y.d.", while ENTSO-E
holds a later revision.
- The user chose ENTSO-E for that day: `NTC_ENTSOE_WEB_PREFERRED_DAYS` in `config.py` makes the combined
  table use `raw/entsoe_web/part_2026-09-24.txt` in all eight directions.
- `validation_report.csv` keeps the difference on record: Italy values differ by up to 1,395 MW.
- The combined day-ahead NTC is complete for Oct 2025 - Sep 2026.

**Replacement.** Once the API token arrives, `entsoe_ntc.py` replaces this hand copy, which should then be
compared with the API values.

## Analyses

Checks of the processed data. Their outputs go to `input/historical/analysis/<name>/`, which is not
versioned; each can be regenerated with the command shown.

| Analysis | Command | Period | Main findings |
|---|---|---|---|
| Trade versus day-ahead NTC | `python -m data_prep.historical.plot_trade_ntc --start 2025-10-01 --end 2026-09-30 --processed 2023-10-01 2026-09-30 --out-dir input/historical/analysis/trade_vs_ntc` | Oct 2025 - Sep 2026 | **Most binding limits.** FR to CH imports are at the limit in 69% of hours, CH to IT exports in 34%.<br>**Hours above the day-ahead NTC** are intraday trades within the intraday NTC.<br>**No step** where the NTC source switches from ENTSO-E to Swissgrid.<br>**Only 24 Sep 2026** has an early D-2 file version. |

## Rules

- **Missing data stays NaN.** Nothing is interpolated or filled. A gap shows up in
  `coverage_report.csv`, and the step that builds model inputs must raise on it.
- **Quarter-hours become hourly values only when all four quarters exist.** Prices and power use
  the mean. Transfer limits (D-2, intraday and ENTSO-E NTC) use `CAPACITY_HOURLY_RULE` in
  `config.py`, which defaults to `"min"`: FEM has one constant flow per hour, so that flow must
  respect every quarter-hour limit. This is the counterpart of the mean price, which gives the exact
  cost of a constant hourly flow. Set it to `"mean"` only if the hourly value should stand for an
  energy total whose flow may vary between quarters.
- **Publisher "no value" markers become NaN and are counted.** These are Swissgrid's `n.y.d.`
  in D-2 NTC, plus `99999` and wrong-signed values in the intraday NTC.
- **Nuclear outages are estimated from hourly generation.** Outage = net capacity
  (`NUCLEAR_UNITS_NET_MW` in `config.py`) minus generation. ENTSO-E unavailability data is
  not used. The capacity is checked against Energy-Charts for every year it publishes.

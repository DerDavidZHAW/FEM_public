"""
Scrape the list of Swiss storage lakes from Wikipedia into a CSV.

Reads https://de.wikipedia.org/wiki/Liste_der_Speicherseen_in_der_Schweiz
(main table: lake name, canton, total volume [Mio m3], lake surface level
[m a.s.l.], dam name/height/completion year) and writes
"wiki_speicherseen.csv" into this folder.

Dependency-free HTML table parsing (html.parser), so no lxml/bs4 needed.

Run from anywhere:  python input/hydro_WATSA/scrape_wiki_speicherseen.py
"""

from html.parser import HTMLParser
from pathlib import Path
import urllib.request

import pandas as pd

FOLDER = Path(__file__).parent
URL = "https://de.wikipedia.org/wiki/Liste_der_Speicherseen_in_der_Schweiz"
CSV_FILE = FOLDER / "wiki_speicherseen.csv"


class TableParser(HTMLParser):
    """Collect all <table> elements as lists of rows of cell texts."""

    def __init__(self):
        super().__init__()
        self.tables = []
        self._table_stack = []
        self._row = None
        self._cell = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._table_stack.append([])
        elif tag == "tr" and self._table_stack:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []
        elif tag == "br" and self._cell is not None:
            # stacked values in one cell (e.g. old + new dam of the same lake)
            self._cell.append(" | ")

    def handle_endtag(self, tag):
        if tag == "table" and self._table_stack:
            self.tables.append(self._table_stack.pop())
        elif tag == "tr" and self._row is not None:
            if self._table_stack:
                self._table_stack[-1].append(self._row)
            self._row = None
        elif tag in ("td", "th") and self._cell is not None:
            if self._row is not None:
                self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def de_num(text):
    """Parse a German-formatted number ('1 131', '0,4'); NaN on failure.

    Cells with several '|'-separated values (lakes raised by a newer, higher
    dam, e.g. Lac des Dix) yield the maximum, i.e. today's state.
    """
    values = []
    for part in str(text).split("|"):
        t = (
            part.replace("\xa0", "")
            .replace("’", "")
            .replace("'", "")
            .replace(" ", "")
            .replace(",", ".")
        )
        try:
            values.append(float(t))
        except ValueError:
            pass
    return max(values) if values else float("nan")


def main():
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    html = urllib.request.urlopen(req).read().decode("utf-8")

    tables = TableParser()
    tables.feed(html)
    # the lake table is by far the largest one on the page
    table = max(tables.tables, key=len)

    # header row: Bild, Name, Kanton/Land, Gesamtinhalt, Seespiegelhöhe,
    # Fläche, max. Tiefe, Bild, Name der Talsperre, Stau­mauertyp,
    # Fertigstellung, Höhe, Kronenlänge
    rows = []
    for r in table:
        # natural lakes used as reservoirs have 9 cells (no dam columns),
        # dammed lakes have 13
        if len(r) < 9 or r[1] in ("", "Name"):
            continue
        rows.append(
            {
                "lake_name": r[1],
                "canton": r[2].replace("Kanton", " ").split("|")[0].strip(),
                "volume_Mm3": de_num(r[3]),
                "lake_level_masl": de_num(r[4]),
                "area_km2": de_num(r[5]),
                "max_depth_m": de_num(r[6]),
                "dam_name": r[8] if len(r) >= 13 else "Natursee",
                "dam_type": r[9] if len(r) >= 13 else "Natursee",
                "dam_completed": r[10] if len(r) >= 13 else "",
                "dam_height_m": de_num(r[11]) if len(r) >= 13 else float("nan"),
            }
        )

    df = pd.DataFrame(rows)
    df = df[df["volume_Mm3"].notna()]
    df = df.sort_values("volume_Mm3", ascending=False)
    df.to_csv(CSV_FILE, index=False, encoding="utf-8")
    print(f"Wrote {len(df)} lakes to {CSV_FILE.name}")
    print(f"Total volume: {df['volume_Mm3'].sum():,.0f} Mio m3")
    print(df.head(10)[["lake_name", "canton", "volume_Mm3", "lake_level_masl"]].to_string())


if __name__ == "__main__":
    main()

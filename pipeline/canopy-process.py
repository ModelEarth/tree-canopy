"""
Forest canopy timeseries and target for every US county, from Google Data Commons.

Writes the two files the RealityStream Forest Canopy parameters use:

    input/targets/forest-canopy-timeseries-<first>-<last>.csv   Fips, Name, <year>, <year>, ...  (percent forest cover)
    input/targets/forest-canopy-target.csv                      Fips, Target  (1 = growth >= threshold over the window)

Definition, unchanged from the original Forest Canopy colab: variable LandCoverFraction_Forest
("Percent of Forest Covered Area"), relative growth between the first and last year of the window,
counties at or above the threshold labelled 1, all others 0.

    python pipeline/canopy-process.py                    # last 5 available years, 5 percent
    python pipeline/canopy-process.py --years 4 --threshold 5 --out input/targets
    python pipeline/canopy-process.py --check            # offline self-check of the growth logic

Needs DATACOMMONS_API_KEY: in the environment, in the OS credential store (service "modelearth",
see realitystream/api/keystore.md), or in the .env named by automation/paths.yaml in the webroot.
Request a key at https://apikeys.datacommons.org/.
"""
import argparse
import os
import re
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
VARIABLE = "LandCoverFraction_Forest"


def get_setting(name):
    """One value by name: environment, then OS credential store, then the webroot's env file. Never the whole file."""
    value = os.environ.get(name)
    if value:
        return value
    try:
        import keyring
        value = keyring.get_password("modelearth", name)
        if value:
            return value
    except Exception:
        pass
    for automation in (os.path.join(REPO, "..", "automation"), os.path.join(REPO, "..", "..", "automation")):
        paths_yaml = os.path.join(automation, "paths.yaml")
        if not os.path.exists(paths_yaml):
            continue
        match = re.search(r"^\s*env_file:\s*(.+)$", open(paths_yaml, encoding="utf-8").read(), re.MULTILINE)
        if not match:
            continue
        env_file = os.path.join(automation, re.sub(r"\s+#.*$", "", match.group(1)).strip().strip("\"'"))
        if os.path.exists(env_file):
            with open(env_file, encoding="utf-8") as fh:
                for line in fh:
                    if line.startswith(name + "="):
                        return line.split("=", 1)[1].strip().strip("\"'")
    return None


def fetch_county_forest_cover(api_key):
    """Long table: Fips, Name, year, value for every US county and every year Data Commons has."""
    from datacommons_client import DataCommonsClient  # pip install datacommons-client

    client = DataCommonsClient(api_key=api_key)
    obs = client.observations_dataframe(
        variable_dcids=[VARIABLE], date="all", parent_entity="country/USA", entity_type="County"
    )
    if obs is None or obs.empty:
        raise RuntimeError(f"Data Commons returned no {VARIABLE} observations for US counties.")
    obs = obs.rename(columns={"entity": "Fips", "entity_name": "Name"})
    obs["Fips"] = obs["Fips"].astype(str).str.replace("geoId/", "", regex=False).str.zfill(5)
    obs["year"] = obs["date"].astype(str).str[:4].astype(int)
    if "Name" not in obs.columns:
        obs["Name"] = ""
    obs["Name"] = obs["Name"].astype(str).str.replace(" County", "", regex=False)
    return obs[["Fips", "Name", "year", "value"]]


def build_outputs(obs, years, threshold):
    """(timeseries wide table, target table, first_year, last_year) from the long observations."""
    available = sorted(obs["year"].unique())
    window = available[-years:] if years else available
    first, last = window[0], window[-1]
    wide = obs[obs["year"].isin(window)].pivot_table(index=["Fips", "Name"], columns="year", values="value",
                                                     aggfunc="median").reset_index()
    wide.columns = [str(c) for c in wide.columns]
    start, recent = wide[str(first)], wide[str(last)]
    growth = (recent - start) / start.replace(0, pd.NA) * 100
    target = pd.DataFrame({"Fips": wide["Fips"], "Target": (growth >= threshold).fillna(False).astype(int)})
    return wide, target, first, last


def check():
    """Offline self-check: window selection and threshold labelling."""
    rows = []
    for fips, name, cover in (("01001", "Autauga", [40, 41, 42, 43]), ("01003", "Baldwin", [50, 50, 50, 50]),
                               ("01005", "Barbour", [20, 20, 20, 19])):
        for year, value in zip((2016, 2017, 2018, 2019), cover):
            rows.append({"Fips": fips, "Name": name, "year": year, "value": value})
    wide, target, first, last = build_outputs(pd.DataFrame(rows), years=3, threshold=4.0)
    assert (first, last) == (2017, 2019)
    assert list(wide.columns) == ["Fips", "Name", "2017", "2018", "2019"]
    assert dict(zip(target["Fips"], target["Target"])) == {"01001": 1, "01003": 0, "01005": 0}  # 41 -> 43 is 4.9%
    print("check passed")


def main():
    parser = argparse.ArgumentParser(description="Forest canopy timeseries and target from Data Commons")
    parser.add_argument("--years", type=int, default=5, help="how many of the most recent years to keep (default 5)")
    parser.add_argument("--threshold", type=float, default=5.0, help="percent growth labelled 1 (default 5)")
    parser.add_argument("--out", default=os.path.join(REPO, "input", "targets"), help="output folder")
    parser.add_argument("--check", action="store_true", help="run the offline self-check and exit")
    args = parser.parse_args()
    if args.check:
        return check()

    api_key = get_setting("DATACOMMONS_API_KEY")
    if not api_key:
        sys.exit("DATACOMMONS_API_KEY is not set. Request one at https://apikeys.datacommons.org/ and store it "
                 "with `python api/keystore.py set DATACOMMONS_API_KEY` in realitystream, or in your env file.")
    obs = fetch_county_forest_cover(api_key)
    wide, target, first, last = build_outputs(obs, args.years, args.threshold)

    os.makedirs(args.out, exist_ok=True)
    ts_path = os.path.join(args.out, f"forest-canopy-timeseries-{first}-{last}.csv")
    target_path = os.path.join(args.out, "forest-canopy-target.csv")
    wide.to_csv(ts_path, index=False)
    target.to_csv(target_path, index=False)
    print(f"{len(wide)} counties, years {first} to {last}")
    print(f"{int(target['Target'].sum())} counties at or above {args.threshold:g} percent growth")
    print(f"wrote {ts_path}\nwrote {target_path}")


if __name__ == "__main__":
    main()

"""Bounded optional dependency worker. Keep stdout machine-readable."""

import contextlib
import json
import sys


def main():
    config = json.load(sys.stdin)
    with contextlib.redirect_stdout(sys.stderr):
        from jobspy import scrape_jobs

        frame = scrape_jobs(
            site_name=["indeed"],
            search_term=config["query"],
            location=config["location"],
            results_wanted=config["limit"],
            hours_old=config["hours"],
            country_indeed="USA",
        )
    print(frame.to_json(orient="records", date_format="iso"))


if __name__ == "__main__":
    main()

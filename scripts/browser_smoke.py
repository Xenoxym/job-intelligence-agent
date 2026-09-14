"""Exercise the real UI and review-only autofill against a local fixture."""

import argparse
import json
import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

from backend.browser_assist import fill_verified
from backend.schemas import Profile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    Path("artifacts").mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1100}, device_scale_factor=1)
        token = os.getenv("API_TOKEN", "")
        if token:
            page.add_init_script('sessionStorage.setItem("scout-token", ' + json.dumps(token) + ")")
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(args.base_url)
        expect(page.get_by_role("heading", name="Your next move.")).to_be_visible()
        expect(page.locator(".job-card").first).to_be_visible()
        page.screenshot(path="artifacts/dashboard-desktop.png", full_page=True)
        page.get_by_label("Search jobs", exact=True).fill("Vector Works")
        expect(page.locator(".job-card")).to_have_count(1)
        page.locator(".job-card").click()
        dialog = page.get_by_role("dialog")
        expect(
            dialog.get_by_role("heading", name="Senior ML Infrastructure Engineer", exact=True)
        ).to_be_visible()
        if dialog.get_by_role("button", name="Save", exact=True).is_enabled():
            dialog.get_by_role("button", name="Save", exact=True).click()
            expect(dialog.get_by_text("Current stage:", exact=False)).to_contain_text("saved")
        dialog.get_by_role("button", name="Prepare application", exact=True).click()
        expect(dialog.get_by_role("heading", name="Application preparation", exact=True)).to_be_visible()
        expect(dialog.locator(".answer").filter(has_text="sponsorship")).to_contain_text("Unknown")
        for status in ["applied", "interview"]:
            dialog.get_by_label("Next application status").select_option(status)
            dialog.get_by_label("Application note", exact=True).fill("Browser smoke outcome")
            dialog.get_by_role("button", name="Update stage", exact=True).click()
            expect(dialog.get_by_text("Current stage:", exact=False)).to_contain_text(status)
        page.screenshot(path="artifacts/job-detail.png", full_page=True)
        dialog.get_by_role("button", name="Close job details").click()
        page.get_by_label("Search jobs", exact=True).fill("")
        page.get_by_role("button", name="Application pipeline").click()
        expect(page.get_by_role("heading", name="Keep things moving.")).to_be_visible()
        expect(page.locator(".job-card").first).to_be_visible()
        page.get_by_role("button", name="Preferences", exact=False).first.click()
        expect(page.get_by_label("Candidate JSON")).to_have_value(__import__("re").compile("Chengqian"))
        page.get_by_role("button", name="Save preferences", exact=True).click()
        expect(page.get_by_role("status")).to_contain_text("Preferences saved")
        page.get_by_role("button", name="Opportunities", exact=False).click()
        page.set_viewport_size({"width": 390, "height": 844})
        expect(page.locator(".job-card").first).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        page.screenshot(path="artifacts/dashboard-mobile.png", full_page=True)
        # The autofill helper must not select legal answers or submit a form.
        page.set_content(
            '<form><label>Full name<input name="name" required></label><label>Email<input name="email" required></label><label>Sponsorship<select name="sponsorship" required><option value="">Choose</option><option>No</option></select></label><label><input type="checkbox" name="attestation" required>I attest</label><button type="submit">Submit</button></form>'
        )
        profile = Profile.model_validate_json(Path("config/candidate.json").read_text())
        result = fill_verified(page, profile)
        assert page.locator("input[name=name]").input_value() == "Chengqian Luo"
        assert page.locator("select").input_value() == ""
        assert not page.locator("input[type=checkbox]").is_checked()
        assert result["submitted"] is False
        assert {"email", "sponsorship", "attestation"} <= set(result["unresolved"])
        assert not errors, errors
        browser.close()
        print(
            "PASS: desktop/mobile UI, filters, preparation, tracking, preferences, fact-only autofill; no browser errors"
        )


if __name__ == "__main__":
    main()

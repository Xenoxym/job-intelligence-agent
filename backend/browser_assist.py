"""Local, visible Playwright assistance. There is deliberately no submit capability."""

import argparse
import ipaddress
import json
import re
import socket
from pathlib import Path
from urllib.parse import urlsplit

from backend.schemas import Profile

SAFE_FIELDS = {
    "name": r"^(full name|name)$",
    "email": r"^(email|email address)$",
    "phone": r"^(phone|phone number|mobile phone)$",
}


def public_url(url):
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        return False
    try:
        addresses = socket.getaddrinfo(parts.hostname, parts.port or 443)
        return bool(addresses) and all(ipaddress.ip_address(a[4][0]).is_global for a in addresses)
    except (OSError, ValueError):
        return False


def fill_verified(page, profile):
    filled, unresolved = [], []
    for field, pattern in SAFE_FIELDS.items():
        value = getattr(profile, field)
        locator = page.get_by_label(re.compile(pattern, re.I))
        if value and locator.count() == 1 and locator.is_visible() and locator.is_editable():
            locator.fill(value)
            filled.append(field)
    for element in page.locator(
        "input[required], textarea[required], select[required], [aria-required=true]"
    ).all():
        try:
            missing = not element.input_value()
            if element.get_attribute("type") in {"checkbox", "radio"}:
                missing = not element.is_checked()
            if missing:
                unresolved.append(
                    element.get_attribute("aria-label")
                    or element.get_attribute("name")
                    or element.get_attribute("id")
                    or "Unlabelled required field"
                )
        except Exception:
            unresolved.append("Required custom control; review manually")
    return {"mode": "review", "filled": filled, "unresolved": unresolved, "submitted": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument(
        "--profile",
        default="config/candidate.json",
        help="Local verified profile JSON (export /api/profile for current values)",
    )
    args = parser.parse_args()
    if not public_url(args.url):
        parser.error("A public HTTPS application URL is required")
    profile = Profile.model_validate_json(Path(args.profile).read_text(encoding="utf-8"))
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(service_workers="block")

        def guard(route):
            request = route.request
            # Only public reads are allowed during initial page loading.
            if request.method not in {"GET", "HEAD"} or not public_url(request.url):
                route.abort()
            else:
                route.continue_()

        context.route("**/*", guard)
        context.route_web_socket("**/*", lambda ws: ws.close())
        page = context.new_page()
        page.goto(args.url, wait_until="domcontentloaded", timeout=30000)
        # Disconnect the loaded page before entering any personal facts. This also
        # blocks GET-based autosave or beacons, not merely form POST submission.
        context.unroute("**/*", guard)
        context.route("**/*", lambda route: route.abort())
        print(json.dumps(fill_verified(page, profile), indent=2))
        print(
            "Review only. Writes are blocked in this browser. CAPTCHA, custom controls and unknown answers need manual handling. Copy reviewed answers into your normal browser to submit."
        )
        input("Press Enter to close the review browser. ")
        context.close()
        browser.close()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Checks that the App Store Connect API key works, registers the bundle ID
if needed, and checks that the app exists, so a failed TestFlight upload
says what is actually missing.

With --testers it also makes sure TestFlight is ready to install from: it
lists the latest builds, creates an internal tester group with access to all
builds if there is none, and adds every App Store Connect user of the team
to it as a tester.

Reads ASC_KEY_ID, ASC_ISSUER_ID, ASC_KEY_PATH and BUNDLE_ID from the
environment. Uses only the standard library and the openssl tool, and
prints nothing secret.
"""
import base64
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.appstoreconnect.apple.com/v1"


def b64url(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def der_to_raw(sig):
    """openssl signs ES256 as DER; a JWT needs the raw 32-byte r and s."""
    def read_length(i):
        n = sig[i]
        i += 1
        if n & 0x80:
            count = n & 0x7F
            n = int.from_bytes(sig[i:i + count], "big")
            i += count
        return n, i

    if sig[0] != 0x30:
        raise ValueError("not a DER signature")
    _, i = read_length(1)
    raw = b""
    for _ in range(2):
        if sig[i] != 0x02:
            raise ValueError("not a DER signature")
        n, i = read_length(i + 1)
        raw += sig[i:i + n].lstrip(b"\0").rjust(32, b"\0")
        i += n
    return raw


def make_token():
    header = {"alg": "ES256", "kid": os.environ["ASC_KEY_ID"], "typ": "JWT"}
    now = int(time.time())
    payload = {
        "iss": os.environ["ASC_ISSUER_ID"],
        "iat": now,
        "exp": now + 600,
        "aud": "appstoreconnect-v1",
    }
    signing_input = (
        b64url(json.dumps(header).encode()) + "." + b64url(json.dumps(payload).encode())
    )
    der = subprocess.run(
        ["openssl", "dgst", "-sha256", "-sign", os.environ["ASC_KEY_PATH"]],
        input=signing_input.encode(),
        capture_output=True,
        check=True,
    ).stdout
    return signing_input + "." + b64url(der_to_raw(der))


def call(path, token, params=None, body=None):
    url = f"{API}/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = {"Authorization": f"Bearer {token}"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    request = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.load(e)
        except ValueError:
            return e.code, None


def describe(body):
    """Apple's error code and title, without details that may hold emails."""
    errors = (body or {}).get("errors") or [{}]
    return f"{errors[0].get('code', '?')}: {errors[0].get('title', '')}"


def mask(email):
    name, _, domain = email.partition("@")
    return f"{name[:2]}***@{domain}"


def setup_testing(app_id, token):
    status, body = call("builds", token, params={
        "filter[app]": app_id, "sort": "-uploadedDate", "limit": 5,
    })
    if status != 200:
        fail(f"Could not list builds ({status} {describe(body)}).")
    if not body["data"]:
        print("No builds uploaded yet.")
    for build in body["data"]:
        a = build["attributes"]
        expired = " (expired)" if a.get("expired") else ""
        print(f"Build {a['version']}: {a['processingState']}{expired}, uploaded {a['uploadedDate']}")

    status, body = call(f"apps/{app_id}/betaGroups", token)
    if status != 200:
        fail(f"Could not list TestFlight groups ({status} {describe(body)}).")
    group = next((g for g in body["data"] if g["attributes"].get("isInternalGroup")), None)
    if group is None:
        status, body = call("betaGroups", token, body={"data": {
            "type": "betaGroups",
            "attributes": {"name": "Me", "isInternalGroup": True, "hasAccessToAllBuilds": True},
            "relationships": {"app": {"data": {"type": "apps", "id": app_id}}},
        }})
        if status != 201:
            fail(f"Could not create an internal TestFlight group ({status} {describe(body)}).")
        group = body["data"]
        print("Created the internal TestFlight group \"Me\" with access to all builds.")
    else:
        all_builds = group["attributes"].get("hasAccessToAllBuilds")
        print(f"Internal TestFlight group \"{group['attributes']['name']}\" exists"
              f" (access to all builds: {'yes' if all_builds else 'no'}).")

    status, body = call(f"betaGroups/{group['id']}/betaTesters", token, params={"limit": 200})
    if status != 200:
        fail(f"Could not list testers ({status} {describe(body)}).")
    testers = {t["attributes"].get("email", "").lower() for t in body["data"]}

    status, body = call("users", token, params={"limit": 50})
    if status != 200:
        fail(f"Could not list team users ({status} {describe(body)}).")
    for user in body["data"]:
        a = user["attributes"]
        email = a["username"]
        if email.lower() in testers:
            print(f"{mask(email)} is already a tester.")
            continue
        status, body = call("betaTesters", token, body={"data": {
            "type": "betaTesters",
            "attributes": {"email": email, "firstName": a.get("firstName") or "",
                           "lastName": a.get("lastName") or ""},
            "relationships": {"betaGroups": {"data": [{"type": "betaGroups", "id": group["id"]}]}},
        }})
        if status == 201:
            print(f"Added {mask(email)} as a tester.")
        else:
            print(f"::warning::Could not add {mask(email)} as a tester ({status} {describe(body)}).")


def fail(message):
    print(f"::error::{message}")
    sys.exit(1)


def main():
    bundle_id = os.environ["BUNDLE_ID"]
    token = make_token()

    status, body = call("bundleIds", token, params={"filter[identifier]": bundle_id})
    if status == 401:
        fail("Apple rejected the API key (401). Check that ASC_KEY_ID, ASC_ISSUER_ID and "
             "ASC_KEY_P8 all come from the same key, and that API access was approved.")
    if status == 403:
        fail("The API key may not do this (403). It must be a Team key with Access = Admin.")
    if status != 200:
        fail(f"App Store Connect answered {status} when listing bundle IDs.")
    if any(b["attributes"]["identifier"] == bundle_id for b in body["data"]):
        print(f"Bundle ID {bundle_id} is registered.")
    else:
        status, _ = call("bundleIds", token, body={"data": {
            "type": "bundleIds",
            "attributes": {"identifier": bundle_id, "name": "Amir Browser", "platform": "IOS"},
        }})
        if status != 201:
            fail(f"Could not register the bundle ID {bundle_id} (App Store Connect answered "
                 f"{status}). Register it at developer.apple.com: Certificates, IDs & Profiles > "
                 "Identifiers > + > App IDs > App > Explicit.")
        print(f"Registered the bundle ID {bundle_id}.")

    status, body = call("apps", token, params={"filter[bundleId]": bundle_id})
    if status != 200:
        fail(f"App Store Connect answered {status} when listing apps.")
    apps = [a for a in body["data"] if a["attributes"]["bundleId"] == bundle_id]
    if not apps:
        fail(f"No app in App Store Connect uses {bundle_id}. Create it: App Store Connect > "
             "Apps > + > New App, and choose this bundle ID.")
    print(f"App found in App Store Connect: {apps[0]['attributes']['name']}")

    if "--testers" in sys.argv:
        setup_testing(apps[0]["id"], token)


if __name__ == "__main__":
    main()

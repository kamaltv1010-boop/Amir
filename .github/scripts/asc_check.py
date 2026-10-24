#!/usr/bin/env python3
"""Checks that the App Store Connect API key works, registers the bundle ID
if needed, and checks that the app exists, so a failed TestFlight upload
says what is actually missing.

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
        return e.code, None


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


if __name__ == "__main__":
    main()

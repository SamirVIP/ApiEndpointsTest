from flask import Flask, jsonify, request, render_template
import requests
import gzip
import zlib
import binascii
import json
import re
import time
import base64
from urllib.parse import urlparse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

app = Flask(__name__)

# ============================================================
# CONFIGURATION
# ============================================================

VERSION_API = "https://ff-version.vercel.app/update"
DECODER_API = "https://protobuf-decoder-seven.vercel.app/decode"
JWT_API = "https://macxjwt.vercel.app/get_jwt_token"

CLIENTS = {
    "client_ind": "https://client.ind.freefiremobile.com",
    "client_bp": "https://clientbp.ggpolarbear.com",
    "client_us": "https://client.us.freefiremobile.com"
}

REGIONS = {
    "ind": {"client": CLIENTS["client_ind"], "uid": "4258906717", "password": "RockingGamerz65-1WDTR63DX"},
    "br": {"client": CLIENTS["client_us"], "uid": "4113330289", "password": "FA684A835410A8AFFE785552154AD87A4CB928C03D8870DEE37AB7C019B2D162"},
    "na": {"client": CLIENTS["client_us"], "uid": "4139196327", "password": "FA680B796474B22907BFD3DF2AFA29577FA43C5B2068417AA24453F25212B854"},
    "sac": {"client": CLIENTS["client_us"], "uid": "4113343938", "password": "F7F739FCFB96A09B019D87C6B45174B76FAE406A4CD7A785F187E46C7F7A71FF"},
    "latam": {"client": CLIENTS["client_us"], "uid": "4113343938", "password": "F7F739FCFB96A09B019D87C6B45174B76FAE406A4CD7A785F187E46C7F7A71FF"},
    "mea": {"client": CLIENTS["client_bp"], "uid": "4103849657", "password": "EF315D040E99F9B63D79C7AEE6DC697F297D298EF384BAA4E50E003DB56514C4"},
    "vn": {"client": CLIENTS["client_bp"], "uid": "3688702515", "password": "18E3450FC131F6414A775896EDA8075A37818FEFEE7A795ED4BC7764346A5EEF"},
    "bd": {"client": CLIENTS["client_bp"], "uid": "4139230703", "password": "6C2D5409593C61CFD31CDA18146054D05E72F261F24343CDEA75AEF38ADF5C95"},
    "pk": {"client": CLIENTS["client_bp"], "uid": "4139224003", "password": "1812098F2587DCAEF5CC21EAD93FAA751D212CD81C586CFD4B4F48C1B49D2A88"},
    "sg": {"client": CLIENTS["client_bp"], "uid": "4139211052", "password": "3BA22FEF36B7118B9FB1E1EB3E5A6DD84BDE696BD66B494269496E9834F00F3B"},
    "id": {"client": CLIENTS["client_bp"], "uid": "4109659017", "password": "7CE44389FE7D03FF892E682D00C5BE586B12789019CCCB466080CED41806DBAB"},
    "cis": {"client": CLIENTS["client_bp"], "uid": "3301239795", "password": "DD40EE772FCBD61409BB15033E3DE1B1C54EDA83B75DF0CDD24C34C7C8798475"},
    "th": {"client": CLIENTS["client_bp"], "uid": "4113415247", "password": "2542DD73DD60B33E183C6A894F9F6A2FC7DAEC457B826C71D44BFD4470788BBB"},
    "tw": {"client": CLIENTS["client_bp"], "uid": "4113375272", "password": "6AB01F7FB110A4C9EB95DBA21BD0E63E622DF8E566157811910F81E54394A17D"},
    "eu": {"client": CLIENTS["client_bp"], "uid": "4139177376", "password": "E29B0A5C48E8B426BE3E9D977927606842310E2F14EB108F2B5D7F73D9C4B105"}
}

ENDPOINT_HEX_PAYLOADS = {
    "logingetdesc": "19d87e64f15e9db87392bc99506f0b94",
    "logingetaccountinfo": "701ab6a8dcd2e32bde5efd87d0da7545",
    "getmaillist": "59f0b3e90a6ff6ffed2f612996c74b04",
    "getlimitedeventopeninfo": "1a725b2c56ec52ba7d09623454c0a003",
    "getcustomeventopeninfo": "9aeaea80bb2ba264078712b7c32a4116",
    "getbpalldescs": "1a725b2c56ec52ba7d09623454c0a003",
    "getcollabdesc": "1a725b2c56ec52ba7d09623454c0a003"
}

VERSION_CACHE = {"version": None}
BASE_LINK = "https://dl.dir.freefiremobile.com/common/"
VALID_EXTENSIONS = (
    "png", "jpg", "jpeg", "webp", "gif", "bmp", "ktx",
    "html", "json", "mp4", "mp3", "wav", "ogg", "webm"
)

# ============================================================
# HTTP SESSION
# ============================================================

SESSION = requests.Session()

retry_strategy = Retry(
    total=3,
    connect=3,
    read=3,
    backoff_factor=0.5,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET", "POST"],
    raise_on_status=False
)

adapter = HTTPAdapter(
    max_retries=retry_strategy,
    pool_connections=50,
    pool_maxsize=50
)

SESSION.mount("http://", adapter)
SESSION.mount("https://", adapter)

BASE_HEADERS = {
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Content-Type": "application/x-www-form-urlencoded",
    "User-Agent": "UnityPlayer/2018.4.11f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
    "X-GA": "v1 1",
    "X-Unity-Version": "2018.4.11f1"
}

# ============================================================
# JWT SETTINGS
# ============================================================

# JWT generation can be slow, so do NOT use the old 10-second timeout.
JWT_CONNECT_TIMEOUT = 10
JWT_READ_TIMEOUT = 90

# Maximum total time spent waiting for a usable JWT response.
JWT_TOTAL_WAIT = 120

# If the JWT API responds with HTTP 200 but no token yet,
# wait this long before asking it again.
JWT_RETRY_DELAY = 2.0

# Maximum number of additional requests after an empty/incomplete response.
JWT_MAX_ATTEMPTS = 6


def safe_error_text(response):
    """Extract a useful error from a JWT/API response without crashing."""
    try:
        data = response.json()

        if isinstance(data, dict):
            for key in (
                "error",
                "message",
                "detail",
                "msg",
                "reason",
                "status"
            ):
                value = data.get(key)
                if value not in (None, ""):
                    return str(value)

            return json.dumps(data, ensure_ascii=False)[:1000]

        if data not in (None, ""):
            return str(data)[:1000]

    except Exception:
        pass

    text = (response.text or "").strip()
    return text[:1000] if text else f"HTTP {response.status_code}"


def get_token(region_data, release_version):
    """
    Wait properly for the JWT API.

    Behaviour:
    1. Give the JWT API up to JWT_READ_TIMEOUT seconds to respond.
    2. If it returns an actual HTTP/API error, stop immediately and return it.
    3. If it returns 200 but no usable token, retry after a short delay.
    4. Never silently convert a JWT error into a generic auth failure.
    5. Stop after JWT_TOTAL_WAIT seconds so the Flask request cannot hang forever.

    Returns:
        (token, None) on success
        (None, error_message) on failure
    """

    url = (
        f"{JWT_API}"
        f"?uid={region_data['uid']}"
        f"&password={region_data['password']}"
        f"&version={release_version}"
    )

    started = time.monotonic()
    last_error = None

    for attempt in range(1, JWT_MAX_ATTEMPTS + 1):

        elapsed = time.monotonic() - started
        if elapsed >= JWT_TOTAL_WAIT:
            break

        # Remaining overall time. The read timeout is capped so that
        # the total wait remains controlled.
        remaining = max(1, JWT_TOTAL_WAIT - elapsed)
        read_timeout = min(JWT_READ_TIMEOUT, remaining)

        try:
            print(
                f"[JWT] Request {attempt}/{JWT_MAX_ATTEMPTS} "
                f"for {region_data['uid']} "
                f"(timeout={read_timeout:.1f}s)"
            )

            response = SESSION.get(
                url,
                timeout=(JWT_CONNECT_TIMEOUT, read_timeout)
            )

            print(
                f"[JWT] HTTP {response.status_code} "
                f"after {time.monotonic() - started:.2f}s"
            )

            # --------------------------------------------------------
            # REAL HTTP ERROR
            # --------------------------------------------------------
            if response.status_code >= 400:
                error_text = safe_error_text(response)

                # Retry only temporary server-side errors.
                if response.status_code in (408, 425, 429, 500, 502, 503, 504):
                    last_error = (
                        f"JWT API temporary error "
                        f"HTTP {response.status_code}: {error_text}"
                    )

                    if time.monotonic() - started < JWT_TOTAL_WAIT:
                        time.sleep(JWT_RETRY_DELAY)
                        continue

                return None, (
                    f"JWT API returned HTTP {response.status_code}: "
                    f"{error_text}"
                )

            # --------------------------------------------------------
            # SUCCESS RESPONSE
            # --------------------------------------------------------
            try:
                data = response.json()
            except ValueError:
                data = None

            if isinstance(data, dict):

                # Token available -> proceed immediately.
                token = data.get("token")

                if isinstance(token, str):
                    token = token.strip()

                if token:
                    print(
                        f"[JWT] Token received successfully "
                        f"on attempt {attempt}"
                    )
                    return token, None

                # API may explicitly report an application-level error
                # while still using HTTP 200.
                api_error = None

                for key in (
                    "error",
                    "message",
                    "detail",
                    "msg",
                    "reason"
                ):
                    value = data.get(key)
                    if value not in (None, ""):
                        api_error = str(value)
                        break

                if api_error:
                    return None, f"JWT API error: {api_error}"

            # --------------------------------------------------------
            # EMPTY / INCOMPLETE RESPONSE
            # --------------------------------------------------------
            # HTTP response arrived, but there is no token yet.
            # Wait and ask again instead of immediately failing.
            last_error = (
                "JWT API responded, but no usable token was returned"
            )

        except requests.exceptions.ReadTimeout:
            last_error = (
                f"JWT API did not finish responding within "
                f"{read_timeout:.1f}s"
            )

        except requests.exceptions.ConnectTimeout:
            last_error = "Connection timeout while contacting JWT API"

        except requests.exceptions.ConnectionError as exc:
            last_error = f"JWT connection error: {str(exc)}"

        except requests.exceptions.RequestException as exc:
            last_error = f"JWT request error: {str(exc)}"

        except Exception as exc:
            last_error = f"JWT processing error: {str(exc)}"

        # ------------------------------------------------------------
        # RETRY EMPTY / TEMPORARY RESPONSE
        # ------------------------------------------------------------
        if time.monotonic() - started >= JWT_TOTAL_WAIT:
            break

        if attempt < JWT_MAX_ATTEMPTS:
            print(
                f"[JWT] No usable token yet. "
                f"Waiting {JWT_RETRY_DELAY}s before retry..."
            )
            time.sleep(JWT_RETRY_DELAY)

    total = time.monotonic() - started

    return None, (
        f"JWT token was not received after {total:.1f}s. "
        f"{last_error or 'Unknown JWT API error'}"
    )


# ============================================================
# HELPERS
# ============================================================

def decompress_data(data):
    try:
        return gzip.decompress(data)
    except Exception:
        pass

    try:
        return zlib.decompress(data)
    except Exception:
        pass

    try:
        return zlib.decompress(data, -zlib.MAX_WBITS)
    except Exception:
        pass

    return data


def get_release_version():
    if VERSION_CACHE["version"]:
        return VERSION_CACHE["version"]

    try:
        response = SESSION.get(VERSION_API, timeout=(5, 15))
        response.raise_for_status()

        version = response.json().get("latest_release_version")

        if version:
            VERSION_CACHE["version"] = version
            return version

    except Exception as exc:
        print(f"[VERSION] Failed: {exc}")

    return "OB55"


def get_payload_for_endpoint(endpoint_name):
    if not endpoint_name:
        return "19d87e64f15e9db87392bc99506f0b94"

    clean_name = endpoint_name.strip().lower()

    return ENDPOINT_HEX_PAYLOADS.get(
        clean_name,
        "19d87e64f15e9db87392bc99506f0b94"
    )


def sanitize_and_format_url(val):
    """
    1. Converts .ff_extend and .ktxp extensions to .jpg.
    2. Strips trailing binary garbage after extension.
    3. Cleans leading dashes/symbols before folder names.
    4. Prepends BASE_LINK for relative paths.
    """

    if not val or not isinstance(val, str):
        return None

    cleaned = val.strip('\'"* \t\n\r')

    if not cleaned:
        return None

    cleaned = re.sub(
        r'\.ff_extend\b',
        '.jpg',
        cleaned,
        flags=re.IGNORECASE
    )

    cleaned = re.sub(
        r'\.ktxp\b',
        '.jpg',
        cleaned,
        flags=re.IGNORECASE
    )

    ext_pattern = (
        r'(\.(?:png|jpg|jpeg|webp|gif|bmp|ktx|html|json|'
        r'mp4|mp3|wav|ogg|webm))'
    )

    match = re.search(ext_pattern, cleaned, re.IGNORECASE)

    if not match:
        if cleaned.lower().startswith(("http://", "https://")):
            return re.sub(r'[^\x20-\x7E].*$', '', cleaned)

        return None

    ext_end_idx = match.end()
    remainder = cleaned[ext_end_idx:]

    if remainder.startswith("?") or remainder.startswith("#"):
        valid_query = re.match(
            r'^[\?#a-zA-Z0-9_\-=&%.]+',
            remainder
        )

        if valid_query:
            cleaned = (
                cleaned[:ext_end_idx] +
                valid_query.group(0)
            )
        else:
            cleaned = cleaned[:ext_end_idx]
    else:
        cleaned = cleaned[:ext_end_idx]

    if cleaned.lower().startswith(("http://", "https://")):
        cleaned = re.sub(
            r'/(common|client)/\-+',
            r'/\1/',
            cleaned,
            flags=re.IGNORECASE
        )

        cleaned = re.sub(
            r'(https?://[^/]+/)\-+',
            r'\1',
            cleaned,
            flags=re.IGNORECASE
        )

        return cleaned

    clean_path = cleaned.lstrip('/- _*+%#@!&:=')
    clean_path = re.sub(r'^\-+', '', clean_path)

    if clean_path.lower().startswith("common/"):
        clean_path = re.sub(
            r'^common/\-+',
            'common/',
            clean_path,
            flags=re.IGNORECASE
        )

        return "https://dl.dir.freefiremobile.com/" + clean_path

    return BASE_LINK + clean_path


def decode_protobuf(raw_hex):
    try:
        decoder_response = SESSION.post(
            DECODER_API,
            json={"data": raw_hex},
            timeout=(5, 30)
        )

        if decoder_response.status_code == 200:
            decoder_json = decoder_response.json()
            protobuf = decoder_json.get("protobuf", {})

            if isinstance(protobuf, str):
                try:
                    protobuf = json.loads(protobuf)
                except Exception:
                    protobuf = {}

            if isinstance(protobuf, dict):
                return protobuf

    except Exception as exc:
        print(f"[DECODER] Failed: {exc}")

    return {}


# ============================================================
# ROUTES
# ============================================================

@app.route("/")
@app.route("/api")
def home():
    return render_template("ui.html")


@app.route("/get_version")
@app.route("/api/get_version")
def get_version_route():
    try:
        version = get_release_version()
        return jsonify({"version": version})

    except Exception as exc:
        return jsonify({
            "version": "OB53",
            "warning": str(exc)
        })


@app.route("/run_script")
@app.route("/api/run_script")
def run_script():
    start_time = time.time()

    try:
        server = request.args.get("server", "ind").lower()
        api_name = request.args.get("name")
        version_param = request.args.get("version")

        if server not in REGIONS:
            return jsonify({
                "error": f"Invalid server region '{server}'"
            }), 400

        if not api_name:
            return jsonify({
                "error": "Missing endpoint target parameter 'name'"
            }), 400

        api_path = (
            urlparse(api_name).path.lstrip("/")
            if "://" in api_name
            else api_name.lstrip("/")
        )

        clean_api_name = api_path.split("/")[-1]

        payload_hex = get_payload_for_endpoint(
            clean_api_name
        )

        release_version = (
            version_param
            if version_param
            else get_release_version()
        )

        region_data = REGIONS[server]

        # ========================================================
        # JWT: WAIT FOR REAL RESPONSE
        # ========================================================

        token, jwt_error = get_token(
            region_data,
            release_version
        )

        if not token:
            return jsonify({
                "success": False,
                "error": jwt_error or (
                    f"Authentication token generation failed "
                    f"for {server.upper()}"
                ),
                "stage": "jwt",
                "server": server,
                "version": release_version
            }), 502

        # ========================================================
        # GARANA REQUEST
        # ========================================================

        headers = BASE_HEADERS.copy()
        headers["Authorization"] = f"Bearer {token}"
        headers["ReleaseVersion"] = release_version

        url = f"{region_data['client']}/{api_path}"

        try:
            raw_payload = binascii.unhexlify(payload_hex)

            response = SESSION.post(
                url,
                headers=headers,
                data=raw_payload,
                timeout=(10, 30)
            )

        except requests.exceptions.Timeout:
            return jsonify({
                "error": (
                    f"Timeout connecting to Garena server "
                    f"[{server.upper()}]"
                ),
                "stage": "garena"
            }), 504

        except requests.exceptions.RequestException as req_err:
            return jsonify({
                "error": f"Garena Connection Fault: {str(req_err)}",
                "stage": "garena"
            }), 502

        # ========================================================
        # TOKEN REFRESH ON 401
        # ========================================================

        if response.status_code == 401:
            print(
                f"[GARANA] 401 received for {server.upper()}, "
                f"refreshing JWT..."
            )

            token, jwt_error = get_token(
                region_data,
                release_version
            )

            if not token:
                return jsonify({
                    "success": False,
                    "error": (
                        jwt_error or
                        "JWT refresh failed after Garena returned 401"
                    ),
                    "stage": "jwt_refresh"
                }), 502

            headers["Authorization"] = f"Bearer {token}"

            try:
                response = SESSION.post(
                    url,
                    headers=headers,
                    data=raw_payload,
                    timeout=(10, 30)
                )

            except requests.exceptions.Timeout:
                return jsonify({
                    "error": "Timeout during authenticated retry",
                    "stage": "garena_retry"
                }), 504

            except requests.exceptions.RequestException as exc:
                return jsonify({
                    "error": f"Garena retry failed: {str(exc)}",
                    "stage": "garena_retry"
                }), 502

        # ========================================================
        # GARANA RESPONSE CHECK
        # ========================================================

        if response.status_code != 200:
            garena_detail = safe_error_text(response)
            return jsonify({
                "success": False,
                "error": (
                    f"Garena Endpoint returned HTTP "
                    f"{response.status_code}: {garena_detail}"
                ),
                "status_code": response.status_code,
                "stage": "garena",
                "server": server,
                "release_version": release_version,
                "hint": (
                    "HTTP 401 means Garena rejected the JWT/authentication. "
                    "If this remains after the OB55/version fix, the JWT "
                    "provider or its credentials/token-generation flow must "
                    "be updated; changing the protobuf payload will not fix "
                    "an authentication rejection."
                ) if response.status_code == 401 else None
            }), response.status_code

        raw_bytes = decompress_data(response.content)

        if not raw_bytes:
            return jsonify({
                "success": False,
                "error": "Empty payload stream returned."
            }), 502

        raw_hex = raw_bytes.hex()
        raw_b64 = base64.b64encode(raw_bytes).decode("utf-8")
        decoded_ascii = raw_bytes.decode(
            "utf-8",
            errors="ignore"
        )

        protobuf_data = decode_protobuf(raw_hex)

        clean_strings = set()
        urls_set = set()

        # ========================================================
        # EXTRACT STRINGS FROM PROTOBUF JSON
        # ========================================================

        def extract_from_json_obj(obj):
            if isinstance(obj, dict):
                for val in obj.values():
                    extract_from_json_obj(val)

            elif isinstance(obj, list):
                for item in obj:
                    extract_from_json_obj(item)

            elif isinstance(obj, str):
                s_val = obj.strip()

                if s_val.startswith(("{", "[")):
                    try:
                        extract_from_json_obj(
                            json.loads(s_val)
                        )
                        return
                    except Exception:
                        pass

                formatted = sanitize_and_format_url(s_val)

                if formatted:
                    clean_strings.add(s_val)
                    urls_set.add(formatted)

        extract_from_json_obj(protobuf_data)

        # ========================================================
        # REGEX FALLBACK
        # ========================================================

        found_paths = re.findall(
            r'(https?://[^\s"\'()<>]+|'
            r'[\w\-_/]+\.(?:png|jpg|jpeg|webp|gif|bmp|ktx|html|'
            r'json|mp4|mp3|wav|ogg|webm|ff_extend|ktxp)(?:\d+)?)',
            decoded_ascii,
            re.IGNORECASE
        )

        for path in found_paths:
            formatted = sanitize_and_format_url(path)

            if formatted:
                clean_strings.add(path.strip())
                urls_set.add(formatted)

        urls_list = sorted(list(urls_set))

        execution_time_ms = round(
            (time.time() - start_time) * 1000,
            2
        )

        clean_endpoint_filename = re.sub(
            r'[^a-zA-Z0-9_\-]',
            '_',
            clean_api_name
        )

        return jsonify({
            "success": True,
            "endpoint": clean_endpoint_filename,
            "server": server,
            "version": release_version,
            "count": len(clean_strings),
            "raw_count": len(urls_list),
            "byte_size": len(raw_bytes),
            "execution_ms": execution_time_ms,
            "strings": sorted(list(clean_strings)),
            "urls": urls_list,
            "protobuf": protobuf_data,
            "raw_hex": raw_hex,
            "raw_b64": raw_b64,
            "raw_response": decoded_ascii
        })

    except Exception as exc:
        print(f"[RUN_SCRIPT] Internal error: {exc}")

        return jsonify({
            "success": False,
            "error": f"Internal Script Error: {str(exc)}"
        }), 500


# ============================================================
# CORS
# ============================================================

@app.after_request
def after_request(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = (
        "Content-Type,Authorization"
    )
    response.headers["Access-Control-Allow-Methods"] = (
        "GET,POST,OPTIONS"
    )
    return response


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    print("[CONFIG] Garena API fallback release version: OB55")
    print("[CONFIG] If Garena still returns 401, check/update the JWT API and credentials.")
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True,
        threaded=True
    )

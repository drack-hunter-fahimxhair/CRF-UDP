# ==================== STANDARD IMPORTS ====================
import sys
import asyncio
import httpx
import random
import json
import socket
import struct
import time
import os
import uuid
import itertools
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# ==================== ORIGINAL IMPORTS ====================
from google_play_scraper import app as play_scraper
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from protobuf_decoder.protobuf_decoder import Parser
from message_ids import MESSAGE_ID_TO_NAME
import thunderFF_pb2

# ==================== WEB DASHBOARD ====================
from dashboard_server import bot_state, start_web_dashboard
import math
import collections
import hashlib

# ==================== CRAFTLAND CONFIG ====================
CRAFTLAND_MODE_ENABLED = True

# ==================== SETTINGS (dynamic) ====================
SETTINGS_FILE = "settings.json"

CRAFTLAND_MAP_CODE = "#FREEFIREF02AE41D8189B133A7889C4091C5941DK200"
CRAFTLAND_MAP_CODE_DEFAULT = CRAFTLAND_MAP_CODE
CRAFTLAND_AUTH_OPCODE        = "83"
CRAFTLAND_CLIENT_VERSION     = "1.134.21"
CRAFTLAND_DEVICE_ID          = "2019121269"
CRAFTLAND_HEARTBEAT_SEC      = 1.0
CRAFTLAND_START_RETRY        = 45.0
CRAFTLAND_MAX_MATCH_DURATION = 700
CRAFTLAND_MATCH_IDLE_TIMEOUT = 15.0
# ==================== MOVEMENT & GLORY CONFIG ====================
AUTO_MOVE_ENABLED         = True
AUTO_MOVE_START_DELAY     = 2.0
AUTO_MOVE_SPAWN_TIMEOUT   = 18.0
AUTO_MOVE_LAND_TIMEOUT    = 6.0
AUTO_MOVE_TICK_INTERVAL   = 0.1
AUTO_MOVE_RUN_SPEED       = 546
AUTO_MOVE_RADIUS          = 6000
AUTO_MOVE_TURN_PER_TICK   = 25.0
AUTO_MOVE_RESYNC_DISTANCE = 2500
AUTO_MOVE_PIGGYBACK_ACK   = True
AUTO_MOVE_MSG_KEYS        = list(range(0x64, 0x6E))
AUTO_MOVE_DEFAULT_RTT     = 120

GLORY_BOOST_ENABLED       = True
GLORY_TICK_INTERVAL       = 0.05
GLORY_ACTION_EVERY        = 0.5
GLORY_PING_EVERY          = 0.5
GLORY_MSG_KEYS            = list(range(0x64, 0x6E))

TARGET_ARRIVAL_RADIUS     = 280.0
TARGET_TIMEOUT            = 22.0
ENEMY_TTL                 = 7.0
STUCK_THRESHOLD           = 6.0
STUCK_LOG_COOLDOWN        = 3.0

ANTI_AFK_DECISION_SEC     = 2.5
ANTI_AFK_IDLE_CHANCE      = 0.08
ANTI_AFK_JUMP_EVERY       = 20.0

ENABLE_SPEED_MOVEMENT       = True
MOVEMENT_SPEED_MIN          = 1.0
MOVEMENT_SPEED_MAX          = 1.4
MOVEMENT_PATTERN            = "circle"
MOVEMENT_TICK_MS            = 240
MOVEMENT_RADIUS             = 180
MOVEMENT_UPDATE_SPEED_EVERY = 4.0

MOVEMENT_STATE_IDLE_CHANCE   = 0.10
MOVEMENT_STATE_WALK_CHANCE   = 0.28
MOVEMENT_STATE_RUN_CHANCE    = 0.32
MOVEMENT_STATE_SPRINT_CHANCE = 0.10
MOVEMENT_STATE_JUMP_CHANCE   = 0.08
MOVEMENT_STATE_CROUCH_CHANCE = 0.06
MOVEMENT_STATE_PRONE_CHANCE  = 0.06

PLAYER_STATE_MAP = {"idle": 0, "walk": 1, "run": 1, "sprint": 1, "jump": 2, "crouch": 3, "prone": 4}
MOVE_STATE_MAP   = {"idle": 0, "walk": 1, "run": 2, "sprint": 3, "jump": 4, "crouch": 1, "prone": 1}
STATE_SPEED      = {"idle": 0, "walk": 45, "run": 70, "sprint": 95, "jump": 55, "crouch": 25, "prone": 15}

def load_settings():
    """Called at startup — loads persisted map code from settings.json."""
    global CRAFTLAND_MAP_CODE
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            code = (data.get("craftland_map_code") or "").strip()
            if code:
                CRAFTLAND_MAP_CODE = code
                print_info(f"[SETTINGS] Map code loaded: {CRAFTLAND_MAP_CODE[:40]}...")
        except Exception as e:
            print_error(f"[SETTINGS] load error: {e}")


def save_settings():
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump({"craftland_map_code": CRAFTLAND_MAP_CODE}, f, indent=2)
    except Exception as e:
        print_error(f"[SETTINGS] save error: {e}")


def set_map_code(new_code: str) -> str:
    """Update map code at runtime + persist. Returns normalized code."""
    global CRAFTLAND_MAP_CODE
    code = (new_code or "").strip()
    if not code:
        raise ValueError("Map code cannot be empty")
    if not code.upper().startswith("#FREEFIRE"):
        code = "#FREEFIRE" + code
    CRAFTLAND_MAP_CODE = code
    save_settings()
    print_success(f"[SETTINGS] Map code updated: {code[:60]}...")
    return code


def change_user_password(username: str, old_password: str, new_password: str) -> Tuple[bool, str]:
    users = _load_users()
    key = (username or "").strip().lower()
    for u in users:
        if (u.get("username") == key or u.get("email") == key) and u.get("password") == old_password:
            if len(new_password) < 4:
                return False, "New password must be at least 4 characters"
            u["password"] = new_password
            _save_users(users)
            print_success(f"[USER] Password changed for {key}")
            return True, "Password updated"
    return False, "Invalid current password"


# ==================== CONFIGURATION ====================
WEB_HOST = "0.0.0.0"
WEB_PORT = int(os.environ.get("PORT", 8080))
ACCOUNTS_FILE = "accounts.json"
USERS_FILE = "users.json"
TOKEN_CACHE_FILE = "token_cache.json"
DEVICES_FILE = "devices.json"
TOKEN_CACHE_TTL = 1200

# Match control (Only Lone Wolf)
START_MATCH_INTERVAL = 3.0
NEW_MATCH_DELAY = 3.0
MAX_MATCH_DURATION = 700
MATCH_IDLE_TIMEOUT = 8.0
PRIORITY_REGIONS = ["BD", "IND", "SG", "TH", "PH", "VN", "MY", "ID", "HK", "TW"]

MAX_CONSECUTIVE_PARSE_FAILURES = 5.0
NON_MATCH_RECONNECT_DELAY = 1.0

FALLBACK_UID = ""
FALLBACK_PASSWORD = ""


# ==================== PROTOBUF HELPER FUNCTIONS ====================
def _pb_varint(n):
    if n < 0:
        n = (1 << 64) + n
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            b |= 0x80
        out.append(b)
        if not n:
            break
    return bytes(out)


def _pb_tag(f, w):
    return _pb_varint((f << 3) | w)


def _pb_field(f, v):
    if isinstance(v, bool):
        v = int(v)
    if isinstance(v, int):
        return _pb_tag(f, 0) + _pb_varint(v)
    if isinstance(v, str):
        d = v.encode('utf-8')
        return _pb_tag(f, 2) + _pb_varint(len(d)) + d
    if isinstance(v, (bytes, bytearray)):
        d = bytes(v)
        return _pb_tag(f, 2) + _pb_varint(len(d)) + d
    return b""


# ==================== USER MANAGEMENT (WEB LOGIN) ====================
_users_memo: List[Dict] = []
_users_memo_time: float = 0.0
_USERS_MEMO_TTL = 5.0


def _load_users() -> List[Dict]:
    global _users_memo, _users_memo_time
    now = time.time()
    if _users_memo and (now - _users_memo_time) < _USERS_MEMO_TTL:
        return _users_memo
    if not os.path.exists(USERS_FILE):
        return []
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            _users_memo = data
            _users_memo_time = now
            return data
    except Exception as e:
        print_error(f"Could not load {USERS_FILE}: {e}")
    return []


def _save_users(users: List[Dict]):
    global _users_memo, _users_memo_time
    try:
        tmp = USERS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=2, ensure_ascii=False)
        os.replace(tmp, USERS_FILE)
        _users_memo = users
        _users_memo_time = time.time()
    except Exception as e:
        print_error(f"Could not save {USERS_FILE}: {e}")


def register_user(name: str, username: str, email: str, password: str) -> Tuple[bool, str]:
    users = _load_users()
    username = username.strip().lower()
    email = email.strip().lower()
    if not name or not username or not email or not password:
        return False, "All fields are required"
    if len(password) < 4:
        return False, "Password must be at least 4 characters"
    if any(u.get("username") == username for u in users):
        return False, "Username already taken"
    if any(u.get("email") == email for u in users):
        return False, "Email already registered"
    users.append({
        "name": name.strip(),
        "username": username,
        "email": email,
        "password": password,
        "created": time.time()
    })
    _save_users(users)
    print_success(f"[USER] Registered new dashboard user: {username}")
    return True, "Account created successfully"


def authenticate_user(user_or_email: str, password: str) -> Optional[Dict]:
    users = _load_users()
    key = user_or_email.strip().lower()
    for u in users:
        if (u.get("username") == key or u.get("email") == key) and u.get("password") == password:
            return u
    return None


# ==================== DEVICE PROFILES ====================
def get_device_for_account(account_identifier: str) -> dict:
    devices = {}
    if os.path.exists(DEVICES_FILE):
        try:
            with open(DEVICES_FILE, "r", encoding="utf-8") as f:
                devices = json.load(f)
        except Exception:
            pass

    acc_key = str(account_identifier)
    if acc_key in devices:
        return devices[acc_key]

    device_list = [
        ("Samsung", "SM-G998B", "Adreno (TM) 660", "Android OS 12 / API-31"),
        ("Xiaomi", "2201122G", "Adreno (TM) 730", "Android OS 13 / API-33"),
        ("Realme", "RMX3700", "Mali-G710", "Android OS 14 / API-34"),
        ("OnePlus", "CPH2451", "Adreno (TM) 740", "Android OS 13 / API-33"),
        ("OPPO", "CPH2611", "Adreno (TM) 720", "Android OS 14 / API-34"),
        ("Vivo", "V2203", "Mali-G710", "Android OS 12 / API-31"),
        ("Poco", "M2102J20SG", "Adreno (TM) 660", "Android OS 13 / API-33"),
    ]
    brand, model, gpu, os_ver = random.choice(device_list)

    new_device = {
        "unique_device_id": f"Google|{str(uuid.uuid4())}",
        "brand": brand,
        "model": model,
        "gpu_renderer": gpu,
        "system_software": os_ver,
        "screen_width": random.choice([1080, 1440, 720, 1280]),
        "screen_height": random.choice([2400, 3200, 1600, 2400]),
        "screen_dpi": str(random.randint(300, 420)),
        "memory": random.randint(2800, 6500),
        "processor_details": f"ARM64 FP ASIMD AES VMH | {random.randint(2200, 3200)} | {random.randint(6, 12)}",
        "client_ip": f"{random.randint(103, 223)}.{random.randint(10, 250)}.{random.randint(10, 250)}.{random.randint(10, 250)}"
    }

    devices[acc_key] = new_device
    try:
        with open(DEVICES_FILE, "w", encoding="utf-8") as f:
            json.dump(devices, f, indent=4)
    except Exception as e:
        print_error(f"Failed to save device mapping: {e}")

    return new_device


# ==================== CLOUDFLARE DNS RESOLVER & SOCKET OPTIMIZERS ====================
CLOUDFLARE_PRIMARY_DNS = "1.1.1.1"
CLOUDFLARE_SECONDARY_DNS = "1.0.0.1"
_DNS_CACHE: Dict[str, Tuple[str, float]] = {}
_DNS_CACHE_TTL = 300.0


async def resolve_host_cloudflare(hostname: str) -> str:
    if not hostname:
        return hostname

    parts = hostname.split('.')
    if len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
        return hostname

    now = time.time()
    if hostname in _DNS_CACHE:
        ip, exp = _DNS_CACHE[hostname]
        if now < exp:
            return ip

    def _query_cloudflare(server_ip: str) -> Optional[str]:
        s = None
        try:
            tx_id = random.randint(1000, 65535)
            header = struct.pack(">HHHHHH", tx_id, 0x0100, 1, 0, 0, 0)
            qname = b"".join(bytes([len(part)]) + part.encode('ascii') for part in hostname.split('.')) + b"\x00"
            query_pkt = header + qname + struct.pack(">HH", 1, 1)

            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(1.2)
            s.sendto(query_pkt, (server_ip, 53))
            resp, _ = s.recvfrom(1024)

            if len(resp) >= 12:
                ancount = struct.unpack(">H", resp[6:8])[0]
                if ancount > 0:
                    offset = 12 + len(qname) + 4
                    for _ in range(ancount):
                        if offset >= len(resp):
                            break
                        if (resp[offset] & 0xC0) == 0xC0:
                            offset += 2
                        else:
                            while offset < len(resp) and resp[offset] != 0:
                                offset += 1 + resp[offset]
                            offset += 1
                        if offset + 10 > len(resp):
                            break
                        rtype, rclass, ttl, rdlen = struct.unpack(">HHIH", resp[offset:offset + 10])
                        offset += 10
                        if rtype == 1 and rdlen == 4 and offset + 4 <= len(resp):
                            return socket.inet_ntoa(resp[offset:offset + 4])
                        offset += rdlen
        except Exception:
            pass
        finally:
            if s:
                try:
                    s.close()
                except Exception:
                    pass
        return None

    loop = asyncio.get_running_loop()
    ip = await loop.run_in_executor(None, _query_cloudflare, CLOUDFLARE_PRIMARY_DNS)
    if not ip:
        ip = await loop.run_in_executor(None, _query_cloudflare, CLOUDFLARE_SECONDARY_DNS)
    if not ip:
        try:
            ip_info = await loop.getaddrinfo(hostname, None, family=socket.AF_INET)
            if ip_info:
                ip = ip_info[0][4][0]
        except Exception:
            ip = hostname

    if ip:
        _DNS_CACHE[hostname] = (ip, now + _DNS_CACHE_TTL)
    return ip or hostname


def optimize_tcp_socket(sock: socket.socket):
    try:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)
    except Exception:
        pass


def optimize_udp_socket(sock: socket.socket):
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 131072)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 131072)
        if hasattr(socket, 'SIO_UDP_CONNRESET') and os.name == 'nt':
            try:
                sock.ioctl(socket.SIO_UDP_CONNRESET, False)
            except Exception:
                pass
    except Exception:
        pass


# ==================== NETWORK & CRYPTO ====================
client = httpx.AsyncClient(
    verify=False,
    timeout=15.0,
    limits=httpx.Limits(max_connections=100, max_keepalive_connections=50)
)

headers = {
    'User-Agent': 'UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)',
    'Connection': 'Keep-Alive',
    'Accept-Encoding': 'gzip',
    'Content-Type': 'application/x-www-form-urlencoded',
    'Expect': '100-continue',
    'X-Unity-Version': '2018.4.12f1',
    'X-GA-SV': '1789535859',
    'X-GA': 'v1 1',
    'ReleaseVersion': 'OB55'
}

AES_KEY = b'Yg&tc%DEuh6%Zc^8'
AES_IV = b'6oyZDr22E3ychjM%'

CRC7_TABLE = bytes([
    0, 9, 18, 27, 36, 45, 54, 63, 72, 65, 90, 83, 108, 101, 126, 119,
    25, 16, 11, 2, 61, 52, 47, 38, 81, 88, 67, 74, 117, 124, 103, 110,
    50, 59, 32, 41, 22, 31, 4, 13, 122, 115, 104, 97, 94, 87, 76, 69,
    43, 34, 57, 48, 15, 6, 29, 20, 99, 106, 113, 120, 71, 78, 85, 92,
    100, 109, 118, 127, 64, 73, 82, 91, 44, 37, 62, 55, 8, 1, 26, 19,
    125, 116, 111, 102, 89, 80, 75, 66, 53, 60, 39, 46, 17, 24, 3, 10,
    86, 95, 68, 77, 114, 123, 96, 105, 30, 23, 12, 5, 58, 51, 40, 33,
    79, 70, 93, 84, 107, 98, 121, 112, 7, 14, 21, 28, 35, 42, 49, 56,
    65, 72, 83, 90, 101, 108, 119, 126, 9, 0, 27, 18, 45, 36, 63, 54,
    88, 81, 74, 67, 124, 117, 110, 103, 16, 25, 2, 11, 52, 61, 38, 47,
    115, 122, 97, 104, 87, 94, 69, 76, 59, 50, 41, 32, 31, 22, 13, 4,
    106, 99, 120, 113, 78, 71, 92, 85, 34, 43, 48, 57, 6, 15, 20, 29,
    37, 44, 55, 62, 1, 8, 19, 26, 109, 100, 127, 118, 73, 64, 91, 82,
    60, 53, 46, 39, 24, 17, 10, 3, 116, 125, 102, 111, 80, 89, 66, 75,
    23, 30, 5, 12, 51, 58, 33, 40, 95, 86, 77, 68, 123, 114, 105, 96,
    14, 7, 28, 21, 42, 35, 56, 49, 70, 79, 84, 93, 98, 107, 112, 121,
])

_DELTA = 0x9E3779B9
_ROUNDS = 16
_FIELD_SIZES = {0: 1, 1: 2, 2: 2, 3: 1, 4: 2}
_FIELD_NAMES = {0: "sendOption", 1: "cmd", 2: "orderId", 3: "flags", 4: "length"}


class Colors:
    HEADER = '\033[95m'
    GREEN = '\033[92m'
    FAIL = '\033[91m'
    WARNING = '\033[93m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    WHITE = '\033[97m'
    ENDC = '\033[0m'


def print_colored(text, color=Colors.WHITE):
    try:
        print(f"{color}{text}{Colors.ENDC}")
    except Exception:
        try:
            print(f"{color}{text.encode('ascii', errors='replace').decode('ascii')}{Colors.ENDC}")
        except Exception:
            pass


def print_success(text):
    print_colored(f"[+] {text}", Colors.GREEN)
    try:
        bot_state.log(text, "success")
    except Exception:
        pass


def print_error(text):
    print_colored(f"[-] {text}", Colors.FAIL)
    try:
        bot_state.log(text, "error")
    except Exception:
        pass


def print_warning(text):
    print_colored(f"[!] {text}", Colors.WARNING)
    try:
        bot_state.log(text, "warning")
    except Exception:
        pass


def print_info(text):
    print_colored(f"[i] {text}", Colors.CYAN)
    try:
        bot_state.log(text, "info")
    except Exception:
        pass


def get_proto_field(d, key, default=None):
    if not d or not isinstance(d, dict):
        return default
    if key in d:
        val = d[key].get('data')
        return val if val is not None else default
    if str(key) in d:
        val = d[str(key)].get('data')
        return val if val is not None else default
    return default


# ==================== MATCH COUNTER ====================
_match_counters: Dict[str, int] = {}
_match_counter_lock = asyncio.Lock()


async def _inc_match(uid: str) -> int:
    async with _match_counter_lock:
        _match_counters[uid] = _match_counters.get(uid, 0) + 1
        return _match_counters[uid]


async def _dec_match(uid: str) -> int:
    async with _match_counter_lock:
        if uid in _match_counters and _match_counters[uid] > 0:
            _match_counters[uid] -= 1
        return _match_counters.get(uid, 0)


async def _get_match_count(uid: str) -> int:
    async with _match_counter_lock:
        return _match_counters.get(uid, 0)


async def _get_total_match_count() -> int:
    async with _match_counter_lock:
        return sum(_match_counters.values())


# ==================== TOKEN CACHE ====================
_token_cache_memo: Dict[str, Any] = {}
_token_cache_memo_time: float = 0.0
_TOKEN_CACHE_MEMO_TTL = 5.0


def _json_serializer(obj):
    if isinstance(obj, (bytes, bytearray)):
        return {"__bytes_hex__": bytes(obj).hex()}
    raise TypeError(f"Type {type(obj)} not serializable")


def _json_deserializer(obj):
    if isinstance(obj, dict):
        if "__bytes_hex__" in obj and len(obj) == 1:
            try:
                return bytes.fromhex(obj["__bytes_hex__"])
            except Exception:
                return b""
        return {k: _json_deserializer(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_deserializer(x) for x in obj]
    return obj


def _load_token_cache() -> Dict[str, Any]:
    global _token_cache_memo, _token_cache_memo_time
    now = time.time()
    if _token_cache_memo and (now - _token_cache_memo_time) < _TOKEN_CACHE_MEMO_TTL:
        return _token_cache_memo

    if not os.path.exists(TOKEN_CACHE_FILE):
        return {}
    try:
        with open(TOKEN_CACHE_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if not content:
            return {}
        data = json.loads(content)
        if not isinstance(data, dict):
            raise ValueError("Cache root must be dict")
        parsed = _json_deserializer(data)
        _token_cache_memo = parsed
        _token_cache_memo_time = now
        return parsed
    except Exception as e:
        print_error(f"Token cache corrupt → deleting: {e}")
        try:
            os.remove(TOKEN_CACHE_FILE)
        except Exception:
            pass
        return {}


def _save_token_cache(cache: Dict[str, Any]):
    global _token_cache_memo, _token_cache_memo_time
    try:
        tmp_file = TOKEN_CACHE_FILE + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, default=_json_serializer)
        os.replace(tmp_file, TOKEN_CACHE_FILE)
        _token_cache_memo = cache
        _token_cache_memo_time = time.time()
    except Exception as e:
        print_error(f"Token cache save error: {e}")


def cache_get(uid: str) -> Optional[Dict]:
    cache = _load_token_cache()
    entry = cache.get(str(uid))
    if not entry:
        return None
    if time.time() - entry.get("cached_at", 0) > TOKEN_CACHE_TTL:
        print_info(f"[CACHE] UID {uid} expired. Re-login needed.")
        cache_invalidate(uid)
        return None
    if not str(entry.get("account_id", "")).isdigit() or int(entry.get("account_id", 0)) <= 0:
        print_warning(f"[CACHE] UID {uid} invalid account_id ({entry.get('account_id')}) → invalidating")
        cache_invalidate(uid)
        return None
    entry["account_id"] = int(entry["account_id"])
    if not isinstance(entry.get("login_payload_data"), (bytes, bytearray)):
        print_warning(f"[CACHE] UID {uid} missing payload → invalidating")
        cache_invalidate(uid)
        return None
    return entry


def cache_set(uid: str, account_data: Dict):
    cache = _load_token_cache()
    entry = dict(account_data)
    entry["cached_at"] = time.time()
    cache[str(uid)] = entry
    _save_token_cache(cache)
    print_success(f"[CACHE] Saved credentials for UID {uid}")


def cache_invalidate(uid: str):
    cache = _load_token_cache()
    if str(uid) in cache:
        del cache[str(uid)]
        _save_token_cache(cache)
        print_warning(f"[CACHE] Invalidated: {uid}")


# ==================== ENCRYPTION & PROTOBUF ====================
async def aes_encrypt(payload, key, iv):
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return cipher.encrypt(pad(payload, AES.block_size))


async def get_playstore_version():
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            None,
            lambda: play_scraper('com.dts.freefireth', lang='hi', country='id')
        )
        return result.get("version")
    except Exception:
        return "1.132.8"


async def version_config():
    app_version = await get_playstore_version()
    api_url = (
        "https://version.ggwhitehawk.com/live/ver.php"
        f"?version={app_version}"
        "&lang=hi&device=android&channel=android"
        "&appstore=googleplay&region=BD"
        "&whitelist_version=1.3.0&whitelist_sp_version=1.0.0"
    )
    try:
        response = await client.get(api_url)
        response.raise_for_status()
        data = response.json()
        server_url = data.get("server_url")
        remote_version = data.get("remote_version")
        latest_release_version = data.get("latest_release_version")
        if not server_url or not remote_version or not latest_release_version:
            return None
        return latest_release_version, remote_version, server_url
    except Exception:
        return None


async def get_access_token(uid, password):
    url = "https://100067.connect.garena.com/oauth/guest/token/grant"
    hdrs = {
        "Host": "100067.connect.garena.com",
        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 12; SM-G998B Build/SP1A.210812.016)",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "close"
    }
    data = {
        "uid": uid,
        "password": password,
        "response_type": "token",
        "client_type": "2",
        "client_secret": "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3",
        "client_id": "100067"
    }
    for attempt in range(5):
        try:
            response = await client.post(url, headers=hdrs, data=data)
            if response.status_code == 200:
                response_data = response.json()
                open_id = response_data.get("open_id")
                access_token = response_data.get("access_token")
                platform = response_data.get("platform", 4)
                if open_id and access_token:
                    return open_id, access_token, platform
            if response.status_code == 429:
                await asyncio.sleep(1)
                continue
        except Exception:
            pass
        await asyncio.sleep(0.5)
    return None


async def parse_results(parsed_results):
    result_dict = {}
    for result in parsed_results:
        field_data = {"wire_type": result.wire_type}
        if result.wire_type == "varint":
            field_data["data"] = result.data
        elif result.wire_type == "string":
            field_data["data"] = result.data
        elif result.wire_type == "bytes":
            field_data["data"] = result.data
        elif result.wire_type == "length_delimited":
            if hasattr(result.data, "results"):
                field_data["data"] = await parse_results(result.data.results)
            elif isinstance(result.data, list):
                field_data["data"] = await parse_results(result.data)
            else:
                field_data["data"] = str(result.data)
        result_dict[str(result.field)] = field_data
    return result_dict


async def decode_protobuf(data):
    parsed_results = Parser().parse(data)
    parsed_results_dict = await parse_results(parsed_results)
    return json.dumps(parsed_results_dict)


def encode_varint_sync(n: int) -> bytes:
    out = bytearray()
    if n < 0:
        n &= 0xFFFFFFFFFFFFFFFF
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            b |= 0x80
        out.append(b)
        if not n:
            break
    return bytes(out)


def _pb_varint_fn(fn, val):
    return encode_varint_sync((fn << 3) | 0) + encode_varint_sync(val)


def _pb_length_fn(fn, val):
    enc = val.encode('utf-8') if isinstance(val, str) else val
    return encode_varint_sync((fn << 3) | 2) + encode_varint_sync(len(enc)) + enc


def create_proto(fields) -> bytes:
    packet = bytearray()
    for field, value in fields.items():
        if isinstance(field, str):
            field = int(field)
        if isinstance(value, dict):
            packet.extend(_pb_length_fn(field, bytes(create_proto(value))))
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    packet.extend(_pb_length_fn(field, bytes(create_proto(item))))
                elif isinstance(item, str):
                    packet.extend(_pb_length_fn(field, item))
                elif isinstance(item, (bytes, bytearray)):
                    packet.extend(_pb_length_fn(field, bytes(item)))
                elif isinstance(item, bool):
                    packet.extend(_pb_varint_fn(field, 1 if item else 0))
                elif isinstance(item, int):
                    packet.extend(_pb_varint_fn(field, item))
        elif isinstance(value, bool):
            packet.extend(_pb_varint_fn(field, 1 if value else 0))
        elif isinstance(value, int):
            packet.extend(_pb_varint_fn(field, value))
        elif isinstance(value, str):
            packet.extend(_pb_length_fn(field, value))
        elif isinstance(value, (bytes, bytearray)):
            packet.extend(_pb_length_fn(field, bytes(value)))
    return bytes(packet)


def encrypt_aes(hex_data: str) -> str:
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    return cipher.encrypt(pad(bytes.fromhex(hex_data), AES.block_size)).hex()


def create_packet(Pk, N, K, V):
    if isinstance(K, str):
        K = bytes.fromhex(K) if len(K) == 32 else K.encode()
    if isinstance(V, str):
        V = bytes.fromhex(V) if len(V) == 32 else V.encode()
    PkEnc = AES.new(K, AES.MODE_CBC, V).encrypt(pad(bytes.fromhex(Pk), 16)).hex()
    L = len(PkEnc) // 2
    hexlen = hex(L)[2:]
    if len(hexlen) % 2 != 0:
        hexlen = '0' + hexlen
    total_pad = 12 - len(N) - len(hexlen)
    if total_pad < 0:
        total_pad = 0
    return bytes.fromhex(N + ('0' * total_pad) + hexlen + PkEnc)


def decode_varint(data, offset):
    result = 0
    shift = 0
    while offset < len(data):
        byte = data[offset]
        result |= (byte & 0x7F) << shift
        offset += 1
        if not (byte & 0x80):
            return result, offset
        shift += 7
    return None, offset


def extract_raw_fields(data: bytes) -> dict:
    result = {}
    offset = 0
    data_len = len(data)
    while offset < data_len:
        header, offset = decode_varint(data, offset)
        if header is None:
            break
        fn = header >> 3
        wt = header & 0x7
        if wt == 0:
            v, offset = decode_varint(data, offset)
            if v is not None:
                result[fn] = v
        elif wt == 2:
            length, offset = decode_varint(data, offset)
            if length is None or offset + length > data_len:
                break
            result[fn] = bytes(data[offset:offset + length])
            offset += length
        elif wt == 1:
            offset += 8
        elif wt == 3:
            offset += 4
        else:
            break
    return result


async def EncRypTMajoRLoGin(open_id: str, access_token: str, version: str,
                            platform: str = "4", lang_code: str = "en",
                            region: str = "BD") -> bytes:
    fields = {
        3: str(datetime.now())[:-7],
        4: "free fire",
        5: 1,
        7: str(version),
        8: "Android OS 11 / API-30 (RP1A.200720.011/230921V810)",
        9: "Handheld",
        10: "Grameenphone",
        11: "WIFI",
        12: 1708,
        13: 750,
        14: "480",
        15: "ARM64 FP ASIMD AES | 2000 | 8",
        16: 5767,
        17: "Mali-G52 MC2",
        18: "OpenGL ES 3.2 v1.r26p0-01eac0.f143e3f9482527bbad36b3ec27f93e59",
        19: f"Google|{uuid.uuid4()}",
        20: "103.200.36.134",
        21: str(lang_code),
        22: str(open_id),
        23: str(platform),
        24: "Handheld",
        25: "INFINIX MOBILITY LIMITED Infinix X6812",
        26: str(region).upper(),
        29: str(access_token),
        30: 1,
        41: "Grameenphone",
        42: "WIFI",
        57: "7428b253defc164018c604a1ebbfebdf",
        60: 110962,
        61: 80611,
        62: 1051,
        64: 80829,
        65: 110962,
        66: 80829,
        67: 110962,
        73: 2,
        74: "/data/app/~~MxBbX9YA6AkFscre_RExgw==/com.dts.freefireth-hLOkTeh1Q46L_oLV4UXQTg==/lib/arm64",
        76: 1,
        77: "b8e0cd5e295eee42f5860d3c86e483dd|/data/app/~~MxBbX9YA6AkFscre_RExgw==/com.dts.freefireth-hLOkTeh1Q46L_oLV4UXQTg==/base.apk",
        78: 3,
        79: 2,
        81: "64",
        83: "2019121229",
        85: 3,
        86: "OpenGLES2",
        87: 4095,
        88: int(platform) if str(platform).isdigit() else 4,
        91: {9: 65},
        92: 10508,
        93: "android",
        94: "KqsHT76RdsVKvnpkirzc2FQs3eu0OZChfZxMTZn+Rjv06Ri2qeOQkyPcdk5JceWKmXhOFFUPuNy9S8esTr37yCT5piY32iUcehVw0bL4F4lzAmyD",
        95: 111207,
        96: '{"cur_rate":[60,90],"support_etc2":false}',
        97: 1,
        98: 1,
        99: str(platform),
        100: str(platform),
        102: "B\\FFP[[\tf",
        103: 1,
        104: 28754,
        105: 1,
        106: "https://dl.ak.freefiremobile.com/live/ABHotUpdates/|https://core-ak.freefiremobile.com/live/ABHotUpdates/|a4332cb1c1a84e51dd77441e4856ed5a",
        107: "1.477aa00e98bf924c"
    }
    proto_bytes = create_proto(fields)
    encrypted_hex = encrypt_aes(proto_bytes.hex())
    return bytes.fromhex(encrypted_hex)


async def build_majorlogin_payload(open_id, access_token, platform, client_version, device_info, verr=None):
    try:
        return await EncRypTMajoRLoGin(
            open_id=str(open_id),
            access_token=str(access_token),
            version=str(verr or client_version),
            platform=str(platform),
            lang_code="en",
            region="BD"
        )
    except Exception as e:
        print_error(f"build_majorlogin_payload error: {e}")
        return None


async def send_majorlogin(data, release_version, server_url):
    try:
        url = f"{server_url}MajorLogin" if server_url.endswith('/') else f"{server_url}/MajorLogin"
        req_headers = headers.copy()
        req_headers["ReleaseVersion"] = str(release_version)
        response = await client.post(url, headers=req_headers, data=data)
        if response.status_code != 200:
            return None
        response_content = response.content
        if len(response_content) < 40:
            return None

        res_proto = thunderFF_pb2.MajorLoginRes()
        try:
            res_proto.ParseFromString(response_content)
        except Exception:
            pass

        if not res_proto.account_id or not res_proto.token or not res_proto.url:
            for offset in [64, 0, 48, 32, 80, 16, 128, 8, 96, 60, 56, 40, 24, 20, 12, 4]:
                if offset >= len(response_content):
                    continue
                rf = extract_raw_fields(response_content[offset:])
                acc = rf.get(1)
                tok = rf.get(8)
                srv = rf.get(10)
                if isinstance(acc, int) and acc > 0 and isinstance(tok, (bytes, bytearray)) and isinstance(srv, (bytes, bytearray)):
                    res_proto.account_id = acc
                    res_proto.token = tok.decode('utf-8', 'ignore')
                    res_proto.url = srv.decode('utf-8', 'ignore')
                    if isinstance(rf.get(2), (bytes, bytearray)):
                        res_proto.region = rf[2].decode('utf-8', 'ignore')
                    if isinstance(rf.get(21), int):
                        res_proto.server_time = rf[21]
                    if isinstance(rf.get(22), (bytes, bytearray)) and len(rf[22]) == 16:
                        res_proto.aes_ak = bytes(rf[22])
                    if isinstance(rf.get(23), (bytes, bytearray)) and len(rf[23]) == 16:
                        res_proto.iv_i = bytes(rf[23])
                    break

        dict_res = {}
        try:
            parsed = Parser().parse(response_content.hex())
            dict_res = await parse_results(parsed)
        except Exception:
            pass

        key_val = get_proto_field(dict_res, 22) or res_proto.aes_ak
        iv_val = get_proto_field(dict_res, 23) or res_proto.iv_i

        if isinstance(key_val, str):
            try:
                key_val = bytes.fromhex(key_val)
            except Exception:
                pass
        if isinstance(iv_val, str):
            try:
                iv_val = bytes.fromhex(iv_val)
            except Exception:
                pass

        if key_val:
            try:
                res_proto.aes_ak = key_val
            except Exception:
                pass
        if iv_val:
            try:
                res_proto.iv_i = iv_val
            except Exception:
                pass

        if not res_proto.account_id or res_proto.account_id <= 0:
            print_error("send_majorlogin failed: account_id is 0")
            return None

        return res_proto
    except Exception as e:
        print_error(f"send_majorlogin error: {e}")
        return None


async def send_getlogin(data, base_url, token, release_version):
    try:
        url = f"{base_url.rstrip('/')}/GetLoginData"
        req_headers = headers.copy()
        req_headers["ReleaseVersion"] = release_version
        req_headers['Authorization'] = f"Bearer {token}"
        req_headers['Host'] = "clientbp.ppmainecoonghj.com"
        response = await client.post(url, headers=req_headers, data=data)
        if response.status_code != 200:
            return None
        response_content = response.content

        res_proto = thunderFF_pb2.GetLoginDataRes()
        try:
            res_proto.ParseFromString(response_content)
        except Exception:
            pass

        def _extract_addr(raw_bytes, field_no):
            try:
                pos = 0
                n = len(raw_bytes)

                def read_varint(buf, p):
                    res = 0
                    sh = 0
                    while p < len(buf):
                        b = buf[p]
                        p += 1
                        res |= (b & 0x7F) << sh
                        if not (b & 0x80):
                            break
                        sh += 7
                    return res, p

                fields = {}
                while pos < n:
                    try:
                        key, pos = read_varint(raw_bytes, pos)
                    except Exception:
                        break
                    fn = key >> 3
                    wt = key & 0x07
                    try:
                        if wt == 0:
                            val, pos = read_varint(raw_bytes, pos)
                        elif wt == 2:
                            ln, pos = read_varint(raw_bytes, pos)
                            val = raw_bytes[pos:pos + ln]
                            pos += ln
                        elif wt == 5:
                            val = raw_bytes[pos:pos + 4]
                            pos += 4
                        elif wt == 1:
                            val = raw_bytes[pos:pos + 8]
                            pos += 8
                        else:
                            break
                    except Exception:
                        break
                    fields.setdefault(fn, []).append(val)

                if field_no in fields:
                    v = fields[field_no][0]
                    if isinstance(v, bytes):
                        try:
                            return v.decode('utf-8', 'ignore')
                        except Exception:
                            return None
                    return str(v)
            except Exception:
                return None

        try:
            for offset in range(0, min(80, len(response_content))):
                fa = _extract_addr(response_content[offset:], 14)
                ia = _extract_addr(response_content[offset:], 32)
                if fa and ":" in fa and ia and ":" in ia:
                    res_proto.functional_addrs = fa
                    res_proto.informational_addrs = ia
                    break
        except Exception:
            pass

        dict_res = {}
        try:
            parsed = Parser().parse(response_content.hex())
            dict_res = await parse_results(parsed)
        except Exception:
            pass

        return res_proto, dict_res
    except Exception as e:
        print_error(f"send_getlogin error: {e}")
        return None


def _tcp_region_byte(region="BD") -> str:
    reg = str(region).upper() if region else "BD"
    return "19" if reg == "BD" else ("14" if reg == "IND" else "15")


async def build_tcp_startup_packet(account_id, token, server_time, key, iv, region="BD", typ='OnLine'):
    uid_hex = f"{int(account_id):016x}"
    ts_hex = f"{int(server_time):08x}"
    enc = (await aes_encrypt(token.encode(), key, iv)).hex()
    enc_len = f"{len(enc) // 2:08x}"
    rb = _tcp_region_byte(region)
    if typ == 'OnLine':
        op = CRAFTLAND_AUTH_OPCODE if CRAFTLAND_MODE_ENABLED else "90"
        return f"{op}{rb}{uid_hex}{ts_hex}00000000{enc_len}{enc}"
    return f"81{rb}{uid_hex}{ts_hex}{enc_len}{enc}"


def craftland_client_info_packet(key, iv, region="BD", device_id=CRAFTLAND_DEVICE_ID):
    rb = _tcp_region_byte(region)
    proto = create_proto({
        1: 6,
        2: {1: 3, 2: str(device_id), 3: 2, 4: 1},
    })
    return create_packet(proto.hex(), f"1d{rb}", key, iv)


def craftland_preload_packet(key, iv, region="BD"):
    rb = _tcp_region_byte(region)
    return create_packet("0820", f"0e{rb}", key, iv)


def craftland_heartbeat_packet(key, iv, region="BD"):
    rb = _tcp_region_byte(region)
    return create_packet("080f", f"0e{rb}", key, iv)


async def send_keep_alive(region="BD", key=AES_KEY, iv=AES_IV) -> bytes:
    """Encrypted TCP keepalive (0e<reg> 080f) using session key/iv."""
    rb = _tcp_region_byte(region)
    return create_packet("080f", f"0e{rb}", key, iv)


async def Craftland_Solo_Start_Matchmaking_Packet(key, iv, account_id,
                                                  map_code=None,
                                                  region="BD"):
    if map_code is None:
        map_code = CRAFTLAND_MAP_CODE
    full_code = str(map_code).strip()
    if not full_code.upper().startswith("#FREEFIRE"):
        full_code = f"#FREEFIRE{full_code}"
    full_code = full_code.split("/")[0]
    raw_code = full_code[len("#FREEFIRE"):]

    f15_f3 = bytes.fromhex(
        "7f585e501001094d5607035c07040c52065803050d055f01545006065c04540255000406055056581206054d7c5c42414a18"
        "091d061d1208034e05557e7b02586c40637e78674a467b67597d750f770a607802707c0a1700457b5f6752765a7c4d7b657e"
        "7654547776405a79555e5b5b535460470412515b5f4d1e617d1e7749410648666b66420540445c4b5b4166124b7a4d440960"
        "7e7f5f446b1e440d0e1308024b5e704d6067455773435d6d515d097a664118066c7a436e4377766b081008454500641e5262"
        "601a69097d426d5e4252437b5e4a1b771a584c42780c11074f747853735e49415379591c094b7060077c4e404a7259575e06"
        "62790c1a084e0259654c57444d657b42787354680f404678626f437f6d7f5173640a1700014d7a4f797a4a66075109015900"
        "7d49567f5c43606860425464615c090c14074d711a035160630875411f035f055a6306514c1a58077612771962030d1a054b"
        "52487e50457f6a7108606e01436868740060445a1e444e067e7477081002094d46730712505b477d5775435c61654b434704"
        "04487702425d7e4e700f16064c5647445d795f5f597441524c5c1c60765141517f62471608636e4604"
    )
    f15_f7 = bytes.fromhex("1305424a42000601030815137d5f5d58536a7f595b725f515252")
    f15_f11 = bytes.fromhex(
        "03626253513634614174746e53417456324b796f566c553830755549304745586b56484865494c6e674a354f324f48436549"
        "776472635a5a4c6d662f4c4f74546339487966536954386c5262527948795938526e6d634b714c4e52324f2b4d4d7965555a"
        "305a616730686443576447496f325632363677747751527055695744354b327a6933466649566e73515a552f7a4a4d656242"
        "67506a7a4a6f717162664369425358674732774e507a7663733264486b65383869702f424f73544f62354f4e31394e586731"
        "4d412f336e584d47434f64724a4b482b4332512f3178485336447771486a535941437a556448655a7565345577347366684a"
        "5955667952354a73445167326344734f2b344e38522b306c77396f456a6e536439506a436758314a4c564f51647537376a51"
        "444574354973694738666e59632b4371535538454167356549687a6a59466b6b2b6e627a7970664745455a6c4b5758665074"
        "5653427932484a475a3061627852435a792b48486578466d726b48796c4f4f456a304a58336e522b7650597961627a572f49"
        "374733672b523853663237506d387348336f656e4e66374c6f69706a454868525955337166506562695956446d7a756a766a"
        "37773953486a6b30375a724a6c4c6137726f6e48315650623042684d554754796b732f6c6d304e6964437a4b695330646561"
        "6f772b4f2b4e3742313131577175376778742b6848544a39352b6b4237376e737657445051746d73716a6c545653495a3649"
        "32394d79434c78376c4d33736251484c7a5552596e72614b454352676474396f5946766e493247727837456f63706670427a"
        "43326163676152545a57786a69365441464674487368596b5569666f3931666e505933535875317a72374b4454686c685436"
        "75547645415261785430384576574266356d4d6c465a2f3934345176475362474144616e3538367758534e726b49616f4952"
        "446f5158466a32346c4d5475704d4c3555394d30762f4a3241396b622f534f7a4e38673d3d"
    )

    fields = {
        1: 51,
        2: {
            1: 1,
            2: raw_code,
            5: bytes.fromhex("01090a121920222729"),
            6: 6,
            8: "en",
            14: 1,
            15: {
                1: f"INDIA_NOTINIT?{account_id}",
                2: 130,
                3: f15_f3,
                4: bytes.fromhex("795b5f5c"),
                6: 12,
                7: f15_f7,
                8: CRAFTLAND_CLIENT_VERSION,
                9: 3,
                10: 1,
                11: f15_f11,
            },
            17: {
                1: "Craftland_Search",
                2: f"{full_code}/1",
            },
        },
    }
    proto_hex = create_proto(fields).hex()
    rb = _tcp_region_byte(region)
    return create_packet(proto_hex, f"0e{rb}", key, iv)


async def has_ssan_zig(n):
    z = (n << 1) & 0xFFFFFFFFFFFFFFFF
    out = bytearray()
    while z >= 0x80:
        out.append((z & 0x7F) | 0x80)
        z >>= 7
    out.append(z)
    return bytes(out)


async def uleb_encode(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            b |= 0x80
        out.append(b)
        if not n:
            break
    return bytes(out)


async def tea_enc(v0, v1, k0, k1, k2, k3):
    s = 0
    for _ in range(_ROUNDS):
        s = (s + _DELTA) & 0xFFFFFFFF
        v0 = (v0 + (((((v1 << 4) & 0xFFFFFFFF) + k0) & 0xFFFFFFFF ^
                      ((v1 + s) & 0xFFFFFFFF) ^
                      (((v1 >> 5) + k1) & 0xFFFFFFFF)))) & 0xFFFFFFFF
        v1 = (v1 + (((((v0 << 4) & 0xFFFFFFFF) + k2) & 0xFFFFFFFF ^
                      ((v0 + s) & 0xFFFFFFFF) ^
                      (((v0 >> 5) + k3) & 0xFFFFFFFF)))) & 0xFFFFFFFF
    return v0, v1


async def tea_dec(v0, v1, k0, k1, k2, k3):
    s = (_DELTA * _ROUNDS) & 0xFFFFFFFF
    for _ in range(_ROUNDS):
        v1 = (v1 - (((((v0 << 4) & 0xFFFFFFFF) + k2) & 0xFFFFFFFF ^
                      ((v0 + s) & 0xFFFFFFFF) ^
                      (((v0 >> 5) + k3) & 0xFFFFFFFF)))) & 0xFFFFFFFF
        v0 = (v0 - (((((v1 << 4) & 0xFFFFFFFF) + k0) & 0xFFFFFFFF ^
                      ((v1 + s) & 0xFFFFFFFF) ^
                      (((v1 >> 5) + k1) & 0xFFFFFFFF)))) & 0xFFFFFFFF
        s = (s - _DELTA) & 0xFFFFFFFF
    return v0, v1


async def tea_cbc_encrypt(padded, key_bytes):
    k0, k1, k2, k3 = (struct.unpack_from("<I", key_bytes, o)[0] for o in (0, 4, 8, 12))
    out = bytearray(len(padded))
    prev_cipher = bytearray(8)
    prev_intermediate = bytearray(8)
    for i in range(0, len(padded), 8):
        xored = bytearray(8)
        for j in range(8):
            xored[j] = padded[i + j] ^ prev_cipher[j]
        e0, e1 = await tea_enc(
            struct.unpack_from("<I", xored, 0)[0],
            struct.unpack_from("<I", xored, 4)[0],
            k0, k1, k2, k3,
        )
        enc = bytearray(8)
        struct.pack_into("<I", enc, 0, e0)
        struct.pack_into("<I", enc, 4, e1)
        for j in range(8):
            out[i + j] = enc[j] ^ prev_intermediate[j]
        prev_cipher[:] = out[i:i + 8]
        prev_intermediate[:] = xored
    return bytes(out)


async def build_padded(content):
    pad_len = (8 - (len(content) + 10) % 8) % 8
    return bytes([pad_len, 0, 0]) + b"\x00" * pad_len + content + b"\x00" * 7


async def encode_header(layout, send_option, cmd, order_id, flags, length, k, v80):
    out = bytearray()
    for code in layout:
        value = {0: send_option, 1: cmd, 2: order_id, 3: flags, 4: length}[code]
        if _FIELD_SIZES[code] == 1:
            out.append((value & 0xFF) ^ k)
        else:
            v = ((value & 0xFFFF) ^ v80) & 0xFFFF
            out.append(v & 0xFF)
            out.append((v >> 8) & 0xFF)
    return bytes(out)


async def crc7_buff(crc, buf):
    c = crc & 0x7F
    for b in buf:
        c = CRC7_TABLE[((2 * (c & 0xFF)) ^ (b & 0xFF)) & 0xFF] & 0x7F
    return c & 0x7F


async def sv_frame(msg_key, layout, send_option, cmd, order_id, flags, content, key, encrypted=True):
    k = key[0]
    v80 = ((k << 8) | k) & 0xFFFF
    body = await tea_cbc_encrypt(await build_padded(content), key) if encrypted else content
    hdr = bytearray([msg_key, 0]) + await encode_header(layout, send_option, cmd, order_id, flags, len(body), k, v80)
    packet = bytearray(hdr + body)
    packet[1] = await crc7_buff(0, bytes(packet[2:])) & 0x7F
    return bytes(packet)


async def produce_xor_key(secret_key):
    k = secret_key[0] if secret_key and len(secret_key) > 0 else 10
    return k, ((k << 8) | k) & 0xFFFF


async def parse_layout(layout):
    if isinstance(layout, str):
        return [int(ch) for ch in layout.strip()]
    return list(layout)


async def tea_cbc_decrypt(body, key_bytes):
    k0, k1, k2, k3 = (struct.unpack_from("<I", key_bytes, o)[0] for o in (0, 4, 8, 12))
    out = bytearray(len(body))
    prev_intermediate = bytearray(8)
    prev_cipher = bytearray(8)
    xored = bytearray(8)
    dec = bytearray(8)
    for i in range(0, len(body), 8):
        for j in range(8):
            xored[j] = body[i + j] ^ prev_intermediate[j]
        d0, d1 = await tea_dec(
            struct.unpack_from("<I", xored, 0)[0],
            struct.unpack_from("<I", xored, 4)[0],
            k0, k1, k2, k3
        )
        struct.pack_into("<I", dec, 0, d0)
        struct.pack_into("<I", dec, 4, d1)
        for j in range(8):
            out[i + j] = dec[j] ^ prev_cipher[j]
        prev_cipher[:] = body[i:i + 8]
        prev_intermediate[:] = dec
    return bytes(out)


async def build_hello_packet(text, key, layout):
    data = text.encode("utf-8")
    if len(data) > 25:
        raise ValueError(f"Text is too long ({len(data)} bytes)")
    content = b"\x10\x00\x00\x00" + data + b"\x00" * (29 - 4 - len(data))
    k, v80 = await produce_xor_key(key)
    layout = await parse_layout(layout)
    padded = await build_padded(content)
    enc_body = await tea_cbc_encrypt(padded, key)
    header_bytes = await encode_header(layout, 1, 1, 0, 1, len(enc_body), k, v80)
    packet = bytearray([0x63, 0x00]) + header_bytes + enc_body
    packet[1] = await crc7_buff(0, packet[2:]) & 0x7F
    return bytes(packet).hex()


async def classify(frame):
    cmd = frame["cmd"]
    msg_name = MESSAGE_ID_TO_NAME.get(cmd, f"UNKNOWN_{cmd}")
    if msg_name == "UDP_HELLO":
        return "HELLO"
    if msg_name == "UDP_ACK":
        return "ACK"
    if msg_name == "UDP_PING":
        return "PING"
    if msg_name == "RUDP_JOIN_MATCH":
        return "JOIN_MATCH"
    if msg_name.startswith("RUDP_"):
        return msg_name
    if msg_name.startswith("UDP_"):
        return msg_name
    return "DATA"


async def build_packet(msg_key, layout, send_option, cmd, order_id, flags, content, key, encrypted=True):
    k = key[0]
    v80 = ((k << 8) | k) & 0xFFFF
    body = await tea_cbc_encrypt(await build_padded(content), key) if encrypted else content
    hdr = bytearray([msg_key, 0])
    for code in layout:
        value = {0: send_option, 1: cmd, 2: order_id, 3: flags, 4: len(body)}[code]
        if _FIELD_SIZES[code] == 1:
            hdr.append((value & 0xFF) ^ k)
        else:
            v = ((value & 0xFFFF) ^ v80) & 0xFFFF
            hdr.append(v & 0xFF)
            hdr.append((v >> 8) & 0xFF)
    packet = bytearray(hdr + body)
    packet[1] = await crc7_buff(0, bytes(packet[2:])) & 0x7F
    return bytes(packet)


async def layouts_from_mask(mask):
    ru = [int(c) for c in str(mask).strip()]
    nr = [c for c in ru if c != 2]
    return ru, nr


async def reply_for(frame, key, mask, ack_key=0x68, ping_key=0x6D, hello_key=0x5B, ack_style="short"):
    ru, nr = await layouts_from_mask(mask)
    typ = await classify(frame)
    if typ == "HELLO":
        if ack_style == "echo":
            content = frame["content"] if frame["content"] else b"\x10\x00\x00\x00"
            return typ, await build_packet(hello_key, nr, 1, 1, None, 1, content, key)
        return typ, await build_packet(ack_key, nr, 0, 2, None, 1, b"\x01\x00", key)
    if typ == "ACK":
        content = frame["content"] if frame["content"] else b"\x01\x00"
        return typ, await build_packet(ack_key, nr, 0, 2, None, 1, content, key)
    if typ == "PING":
        c = frame["content"]
        counter = c[:4] if len(c) >= 4 else c
        return typ, await build_packet(ping_key, nr, 0, 3, None, 0, counter + b"\x00\x00\x00", key, encrypted=False)
    if typ == "JOIN_MATCH":
        return typ, await build_packet(ack_key, nr, 0, 2, None, 1, b"\x02\x00", key)
    return typ, None


async def keepalive_ping(sock, ip, port, key_bytes, mask, stop_event, move_state=None):
    nr = (await layouts_from_mask(mask))[1]
    ping_keys = [0x66, 0x6D, 0x69, 0x6C, 0x6B, 0x6E, 0x6F, 0x70]
    loop = asyncio.get_event_loop()
    i = 0
    while not stop_event.is_set():
        pk = ping_keys[i % len(ping_keys)]
        counter = int(time.time() * 1000) & 0xFFFFFFFF
        pkt = await build_packet(pk, nr, 0, 3, None, 0, struct.pack("<I", counter) + b"\x00\x00\x00", key_bytes, encrypted=False)
        try:
            await loop.sock_sendto(sock, pkt, (ip, port))
            if move_state is not None:
                move_state.ping_sent = {c: t for c, t in move_state.ping_sent.items() if time.time() - t < 10}
                move_state.ping_sent[counter] = time.time()
        except Exception:
            pass
        i += 1
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=3.0)
        except asyncio.TimeoutError:
            pass


async def try_header(buf, layout, k, v80):
    off = 2
    out = {}
    for code in layout:
        size = _FIELD_SIZES[code]
        if off + size > len(buf):
            return None
        out[_FIELD_NAMES[code]] = (buf[off] ^ k) if size == 1 else ((buf[off] | (buf[off + 1] << 8)) ^ v80) & 0xFFFF
        off += size
    out["headerLen"] = off
    return out


async def oicq_unpad(padded):
    if not padded or len(padded) < 8:
        return None
    if not all(padded[-1 - i] == 0 for i in range(7)):
        return None
    pad_len = padded[0] & 0x07
    s = 3 + pad_len
    e = len(padded) - 7
    return padded[s:e] if s < e else b""


async def peek_reliable_order(packet, key, mask):
    try:
        data = bytes(packet)
        if len(data) < 8:
            return None
        k = key[0]
        v80 = ((k << 8) | k) & 0xFFFF
        if (data[1] & 0x7F) != await crc7_buff(0, data[2:]):
            return None
        f = await try_header(data, (await layouts_from_mask(mask))[0], k, v80)
        if not f or f["flags"] > 7 or f["sendOption"] > 7 or f.get("orderId") is None:
            return None
        extra = 3 if (f["flags"] & 4) else 0
        if f["length"] != len(data) - f["headerLen"] - extra or not (f["flags"] & 1):
            return None
        return f["orderId"]
    except Exception:
        return None


async def decode_packet(packet, key, mask=None):
    data = bytes(packet) if isinstance(packet, bytes) else bytes.fromhex(packet)
    if len(data) < 8:
        return None
    k = key[0]
    v80 = ((k << 8) | k) & 0xFFFF
    crc_ok = (data[1] & 0x7F) == await crc7_buff(0, data[2:])
    candidates = []
    if mask:
        ru, nr = await layouts_from_mask(mask)
        layouts = [("RUDP", ru), ("nonRUDP", nr)]
    else:
        layouts = [("RUDP", list(p)) for p in itertools.permutations([0, 1, 2, 3, 4])]
        layouts += [("nonRUDP", list(p)) for p in itertools.permutations([0, 1, 3, 4])]
    for kind, layout in layouts:
        f = await try_header(data, layout, k, v80)
        if not f or f["flags"] > 7 or f["sendOption"] > 7:
            continue
        extra = 3 if f["flags"] & 4 else 0
        if f["length"] != len(data) - f["headerLen"] - extra:
            continue
        ack_order = None
        if extra:
            ack_order = ((data[f["headerLen"]] | (data[f["headerLen"] + 1] << 8)) ^ v80) & 0xFFFF
            f["headerLen"] += extra
        body = data[f["headerLen"]:f["headerLen"] + f["length"]]
        content = None
        padded = None
        if f["flags"] & 1:
            if len(body) < 8 or len(body) % 8 != 0:
                continue
            padded = await tea_cbc_decrypt(body, key)
            content = await oicq_unpad(padded)
            if content is None:
                continue
        else:
            content = body
        score = (1 if crc_ok else 0) + (1 if content is not None else 0)
        candidates.append({
            "kind": kind, "layout": layout, "headerLen": f["headerLen"],
            "msgKey": data[0], "cmd": f["cmd"], "flags": f["flags"],
            "sendOption": f["sendOption"], "orderId": f.get("orderId"),
            "ackOrder": ack_order, "length": f["length"],
            "content": content, "crcOk": crc_ok, "padded": padded,
            "score": score, "total": len(data),
        })
    if not candidates:
        return None
    candidates.sort(key=lambda c: c["score"], reverse=True)
    return candidates[0]


async def build_craftland_hello_packet(text, key, layout):
    data = text.encode("utf-8")[:25]
    content = b"\x10\x00\x00\x00" + data + b"\x00" * (29 - 4 - len(data))
    ru_layout = await parse_layout(layout)
    pkt = await build_packet(0x5E, ru_layout, 1, 1, 0, 1, content, key, encrypted=True)
    return pkt.hex()


async def build_craftland_join_packet(step, account_id, match_id, order_id, key, layout):
    content = bytes([step]) + await uleb_encode(int(account_id)) + await uleb_encode(int(match_id))
    ru_layout = await parse_layout(layout)
    msg_key = 0x5C if step == 1 else 0x5E
    pkt = await build_packet(msg_key, ru_layout, 2, 3043, order_id, 1, content, key, encrypted=True)
    return pkt.hex()


async def build_craftland_auth448_packet(udp_key_hex, match_code, account_id, match_id,
                                         room_code, room_name_bytes=b"",
                                         client_version=CRAFTLAND_CLIENT_VERSION,
                                         device_id=CRAFTLAND_DEVICE_ID,
                                         slot_byte=12):
    udp_key = bytes.fromhex(udp_key_hex) if isinstance(udp_key_hex, str) else bytes(udp_key_hex)
    ru_layout = await parse_layout(match_code)

    A_block = bytes.fromhex("2000e90700000000010103010104494e0003030001000004")
    cv_b = str(client_version).encode("utf-8")
    dev_b = str(device_id).encode("utf-8")
    rc_b = str(room_code).encode("utf-8")
    rn_b = bytes(room_name_bytes) if isinstance(room_name_bytes, (bytes, bytearray)) else str(room_name_bytes).encode("utf-8")

    block16 = bytes([0, 0, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, slot_byte & 0xFF, 0])
    dotnet_ticks = 621355968000000000 + int(time.time() * 10_000_000)
    ticks_zig = await has_ssan_zig(dotnet_ticks)
    ip_b = b"127.0.0.1"
    dh_b = hashlib.sha256(f"craftland_{account_id}".encode()).hexdigest().encode("utf-8")

    body = (
        await uleb_encode(int(account_id)) +
        await uleb_encode(int(match_id)) +
        b"\x01" +
        await uleb_encode(53) +
        await uleb_encode(int(match_id)) +
        A_block +
        await has_ssan_zig(len(cv_b)) + cv_b +
        await has_ssan_zig(len(dev_b)) + dev_b +
        (b"\x00" * 8) +
        await has_ssan_zig(len(rc_b)) + rc_b +
        await has_ssan_zig(len(rn_b)) + rn_b +
        (b"\x00" * 8) +
        block16 +
        ticks_zig +
        b"\x02\x00" +
        await has_ssan_zig(len(ip_b)) + ip_b +
        await has_ssan_zig(len(dh_b)) + dh_b +
        b"\x00"
    )

    pkt1 = await sv_frame(0x60, ru_layout, 2, 448, 2, 1, body, udp_key)
    pkt2 = await sv_frame(0x5A, ru_layout, 2, 448, 2, 1, body, udp_key)
    return pkt1.hex(), pkt2.hex()

# ==================== MOVEMENT (2001 / 2002 / 2003) ====================
def read_varint(data: bytes, offset: int) -> Tuple[int, int]:
    r, s = 0, 0
    while True:
        if offset >= len(data):
            raise IndexError("offset out of bounds")
        b = data[offset]
        offset += 1
        r |= (b & 0x7F) << s
        if not (b & 0x80):
            break
        s += 7
    return r, offset


MSG_PLAYER_STATE_SYNC = next(
    (mid for mid, name in MESSAGE_ID_TO_NAME.items() if name == "UDP_PLAYER_STATE_SYNC"),
    2001,
)


async def zigzag_encode(n):
    z = ((n << 1) ^ (n >> 63)) & 0xFFFFFFFFFFFFFFFF
    return await uleb_encode(z)


def zigzag_decode(n):
    return (n >> 1) ^ -(n & 1)


def read_varints(buf):
    out = []
    off = 0
    while off < len(buf):
        v, off = read_varint(buf, off)
        out.append(v)
    return out


def float_to_u32(f):
    return struct.unpack("<I", struct.pack("<f", float(f) + 0.0))[0]


class MoveState:
    def __init__(self):
        self.session_start = time.time()
        self.slot = None
        self.player_id = None
        self.server_pos = None
        self.server_physx_state = None
        self.server_vel_y = 0
        self.server_update_seq = 0
        self.pending_ack = None
        self.rtt_ms = None
        self.ping_sent = {}
        self.cmd_counts = collections.Counter()
        self.undecoded = 0
        self.owner_uid = None
        self.enemy_positions = {}
        self.target = None
        self.target_set_at = 0.0

    def diagnostics(self):
        top = ", ".join(f"{c}x{n}" for c, n in self.cmd_counts.most_common(8)) or "none"
        return f"cmds[{top}] | undecoded {self.undecoded} | 2001 seq {self.server_update_seq} | slot {self.slot}"

    def on_server_frame(self, frame):
        self.cmd_counts[frame["cmd"]] += 1
        if frame.get("kind") == "RUDP" and frame.get("orderId") is not None:
            oid = frame["orderId"]
            if self.pending_ack is None or ((oid - self.pending_ack) & 0xFFFF) < 0x8000:
                self.pending_ack = oid

        if frame["cmd"] == 101:
            c = frame.get("content") or b""
            try:
                _, p = read_varint(c, 0)
                _, p = read_varint(c, p)
                self.player_id, _ = read_varint(c, p)
            except Exception:
                pass

        if frame["cmd"] == MSG_PLAYER_STATE_SYNC:
            self._on_own_state(frame["content"] or b"")
        elif frame["cmd"] == 3:
            c = frame.get("content") or b""
            if len(c) >= 4:
                sent = self.ping_sent.pop(struct.unpack_from("<I", c, 0)[0], None)
                if sent is not None:
                    self.rtt_ms = int((time.time() - sent) * 1000)

    def _on_own_state(self, content):
        try:
            v = read_varints(content)
        except Exception:
            return
        if len(v) < 16 or v[0] != 0 or v[1] != 2:
            return
        self.slot = v[2]
        self.server_pos = (zigzag_decode(v[3]), zigzag_decode(v[4]), zigzag_decode(v[5]))
        self.server_vel_y = zigzag_decode(v[12])
        self.server_physx_state = v[14]
        self.server_update_seq += 1
        try:
            self._try_parse_extra_players(v)
        except Exception:
            pass

    def _try_parse_extra_players(self, v):
        own = self.slot
        idx = 27
        now = time.time()
        while idx + 3 < len(v):
            slot = v[idx]
            if 1 <= slot <= 50 and slot != own:
                try:
                    px = zigzag_decode(v[idx + 1])
                    py = zigzag_decode(v[idx + 2])
                    pz = zigzag_decode(v[idx + 3])
                    if -10000 <= px <= 10000 and -2000 <= py <= 5000 and -10000 <= pz <= 10000:
                        self.enemy_positions[slot] = (px, py, pz, now)
                        idx += 4
                        continue
                except Exception:
                    pass
            idx += 1

    def nearest_enemy(self, from_pos):
        now = time.time()
        self.enemy_positions = {
            s: p for s, p in self.enemy_positions.items() if now - p[3] < ENEMY_TTL
        }
        if not self.enemy_positions:
            return None
        best = None
        best_d = float("inf")
        for p in self.enemy_positions.values():
            d = math.hypot(p[0] - from_pos[0], p[2] - from_pos[2])
            if d < best_d:
                best_d = d
                best = (p[0], p[1], p[2])
        return best


async def build_player_state_sync_2001(key_bytes, mask, msg_key, slot, pos, stick, move_input, vel,
                                       physx_state, physx_pose, facing, net_tick, counter_ms,
                                       ack_order=None):
    body = bytearray()
    body += await uleb_encode((1 << 24) | int(slot))
    for value in (*pos, *stick, *move_input, *vel):
        body += await zigzag_encode(int(round(value)))
    body += await uleb_encode(int(physx_state))
    body += await uleb_encode(int(physx_pose))
    for f in facing:
        body += await uleb_encode(float_to_u32(f))
    body += b"\x00\x00"
    body += await uleb_encode(int(net_tick))
    body += b"\x00\x00\x00"
    body += await uleb_encode(int(counter_ms))
    body = bytes(body)

    k = key_bytes[0]
    v80 = ((k << 8) | k) & 0xFFFF
    flags = 4 if ack_order is not None else 0
    nr = (await layouts_from_mask(mask))[1]
    hdr = bytearray([msg_key & 0xFF, 0])
    hdr += await encode_header(nr, 0, MSG_PLAYER_STATE_SYNC, None, flags, len(body), k, v80)
    if ack_order is not None:
        a = ((int(ack_order) & 0xFFFF) ^ v80) & 0xFFFF
        hdr += bytes([a & 0xFF, a >> 8, k])
    packet = bytearray(hdr + body)
    packet[1] = await crc7_buff(0, bytes(packet[2:])) & 0x7F
    return bytes(packet)


async def build_action_beacon_2002(key_bytes, mask, msg_key, slot, pos, action_type=1, ack_order=None):
    body = bytearray()
    body += await uleb_encode((2 << 24) | int(slot))
    body += await zigzag_encode(int(pos[0]))
    body += await zigzag_encode(int(pos[2]))
    body += await uleb_encode(int(action_type))
    body += b"\x00\x00"
    k = key_bytes[0]
    v80 = ((k << 8) | k) & 0xFFFF
    nr = (await layouts_from_mask(mask))[1]
    hdr = bytearray([msg_key & 0xFF, 0])
    hdr += await encode_header(nr, 0, 2002, None, 4 if ack_order else 0, len(body), k, v80)
    if ack_order:
        a = ((int(ack_order) & 0xFFFF) ^ v80) & 0xFFFF
        hdr += bytes([a & 0xFF, a >> 8, k])
    pkt = bytearray(hdr + body)
    pkt[1] = await crc7_buff(0, bytes(pkt[2:])) & 0x7F
    return bytes(pkt)


async def build_position_heartbeat_2003(key_bytes, mask, msg_key, slot, pos, ack_order=None):
    body = bytearray()
    body += await uleb_encode((3 << 24) | int(slot))
    for v in (pos[0], pos[1], pos[2]):
        body += await zigzag_encode(int(v))
    body += b"\x00\x00\x00\x00"
    k = key_bytes[0]
    v80 = ((k << 8) | k) & 0xFFFF
    nr = (await layouts_from_mask(mask))[1]
    hdr = bytearray([msg_key & 0xFF, 0])
    hdr += await encode_header(nr, 0, 2003, None, 4 if ack_order else 0, len(body), k, v80)
    if ack_order:
        a = ((int(ack_order) & 0xFFFF) ^ v80) & 0xFFFF
        hdr += bytes([a & 0xFF, a >> 8, k])
    pkt = bytearray(hdr + body)
    pkt[1] = await crc7_buff(0, bytes(pkt[2:])) & 0x7F
    return bytes(pkt)


async def build_extra_ping_cmd3(key_bytes, mask, msg_key, counter):
    body = struct.pack("<I", counter & 0xFFFFFFFF) + b"\x00\x00\x00"
    k = key_bytes[0]
    v80 = ((k << 8) | k) & 0xFFFF
    nr = (await layouts_from_mask(mask))[1]
    hdr = bytearray([msg_key & 0xFF, 0])
    hdr += await encode_header(nr, 0, 3, None, 0, len(body), k, v80)
    pkt = bytearray(hdr + body)
    pkt[1] = await crc7_buff(0, bytes(pkt[2:])) & 0x7F
    return bytes(pkt)


async def auto_move_loop(sock, ip, port, key_bytes, mask, state: MoveState, stop_event, label=""):
    loop = asyncio.get_event_loop()

    async def wait(seconds):
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=seconds)
            return True
        except asyncio.TimeoutError:
            return False

    next_report = time.time() + AUTO_MOVE_SPAWN_TIMEOUT
    landed_deadline = None
    while True:
        if state.slot is not None and state.server_pos is not None:
            if landed_deadline is None:
                landed_deadline = time.time() + AUTO_MOVE_LAND_TIMEOUT
            if (state.server_physx_state == 0 and state.server_vel_y == 0) or time.time() > landed_deadline:
                break
        elif time.time() > next_report:
            print_warning(f"[MOVE]{label} spawn timeout — forcing start: {state.diagnostics()}")
            state.slot = state.slot or 1
            state.server_pos = state.server_pos or (0, 0, 0)
            state.server_physx_state = 0
            state.server_vel_y = 0
            break
        if await wait(0.2):
            return

    if await wait(AUTO_MOVE_START_DELAY):
        return

    if state.slot is None:
        state.slot = 1
    if state.server_pos is None:
        state.server_pos = (0, 0, 0)

    pos = list(state.server_pos)
    seen_seq = state.server_update_seq
    heading = random.uniform(-math.pi, math.pi)
    stick = (math.sin(heading) * 100, 0.0, math.cos(heading) * 100)
    last_send = time.time()
    last_pos = tuple(pos)
    stuck_timer = 0.0
    last_stuck_log = 0.0

    afk_decision_at = time.time() + ANTI_AFK_DECISION_SEC
    afk_jump_at = time.time() + ANTI_AFK_JUMP_EVERY
    cur_state = "run"
    cur_speed_update = time.time()
    speed_mult = 1.0
    circle_angle = random.uniform(-math.pi, math.pi)
    circle_dir = random.choice([-1, 1])

    last_glory_ping = 0.0
    last_action_beacon = 0.0
    last_pos_hb = 0.0

    print_success(f"[MOVE]{label} Started | uid={state.owner_uid} slot={state.slot} spawn={[round(x) for x in pos]}")

    while not stop_event.is_set():
        now = time.time()
        dt_ms = (now - last_send) * 1000.0
        last_send = now

        if state.server_update_seq != seen_seq and state.server_pos:
            seen_seq = state.server_update_seq
            sx, sy, sz = state.server_pos
            if math.hypot(sx - pos[0], sz - pos[2]) > AUTO_MOVE_RESYNC_DISTANCE:
                pos = [sx, sy, sz]

        moved = math.hypot(pos[0] - last_pos[0], pos[2] - last_pos[2])
        if moved < 4.0:
            stuck_timer += AUTO_MOVE_TICK_INTERVAL
        else:
            stuck_timer = 0.0
            last_pos = tuple(pos)
        if stuck_timer > STUCK_THRESHOLD and (now - last_stuck_log) > STUCK_LOG_COOLDOWN:
            last_stuck_log = now
            state.target = None

        target_age = (now - state.target_set_at) if state.target else 999
        nearest = state.nearest_enemy(pos)
        if nearest is not None:
            state.target = nearest
            state.target_set_at = now
        elif state.target is None or target_age > TARGET_TIMEOUT:
            ang = random.uniform(-math.pi, math.pi)
            dist = random.uniform(1200, AUTO_MOVE_RADIUS)
            state.target = (pos[0] + math.sin(ang) * dist, pos[1], pos[2] + math.cos(ang) * dist)
            state.target_set_at = now

        if ENABLE_SPEED_MOVEMENT and (now - cur_speed_update) >= MOVEMENT_UPDATE_SPEED_EVERY:
            cur_speed_update = now
            speed_mult = random.uniform(MOVEMENT_SPEED_MIN, MOVEMENT_SPEED_MAX)

        if now >= afk_decision_at:
            afk_decision_at = now + ANTI_AFK_DECISION_SEC
            weights = [
                ("idle", MOVEMENT_STATE_IDLE_CHANCE),
                ("walk", MOVEMENT_STATE_WALK_CHANCE),
                ("run", MOVEMENT_STATE_RUN_CHANCE),
                ("sprint", MOVEMENT_STATE_SPRINT_CHANCE),
                ("jump", MOVEMENT_STATE_JUMP_CHANCE),
                ("crouch", MOVEMENT_STATE_CROUCH_CHANCE),
                ("prone", MOVEMENT_STATE_PRONE_CHANCE),
            ]
            r = random.uniform(0, sum(w for _, w in weights))
            acc = 0.0
            cur_state = "run"
            for name, w in weights:
                acc += w
                if r <= acc:
                    cur_state = name
                    break
            if random.random() < ANTI_AFK_IDLE_CHANCE:
                heading += random.uniform(-math.pi, math.pi)
                stick = (math.sin(heading) * 100, 0.0, math.cos(heading) * 100)

        move_input = (0, 0)
        vel = (0, 0, 0)
        pose = 0
        chasing = False

        if state.target is not None:
            dx = state.target[0] - pos[0]
            dz = state.target[2] - pos[2]
            if math.hypot(dx, dz) < TARGET_ARRIVAL_RADIUS:
                state.target = None
            else:
                chasing = True
                speed = AUTO_MOVE_RUN_SPEED * speed_mult
                step = speed * dt_ms / 100.0
                want = math.atan2(dx, dz)
                diff = (want - heading + math.pi) % (2 * math.pi) - math.pi
                max_turn = math.radians(AUTO_MOVE_TURN_PER_TICK)
                heading += max(-max_turn, min(max_turn, diff))
                ux, uz = math.sin(heading), math.cos(heading)
                stick = (ux * 100, 0.0, uz * 100)
                move_input = (stick[0], stick[2])
                vel = (ux * speed, 0, uz * speed)
                pose = MOVE_STATE_MAP.get("run", 2)
                pos[0] += ux * step
                pos[2] += uz * step

        if not chasing:
            if cur_state == "idle":
                pose = PLAYER_STATE_MAP["idle"]
            else:
                if MOVEMENT_PATTERN == "circle":
                    circle_angle += circle_dir * (MOVEMENT_TICK_MS / 1000.0) * 1.2
                    wx = pos[0] + math.sin(circle_angle) * MOVEMENT_RADIUS
                    wz = pos[2] + math.cos(circle_angle) * MOVEMENT_RADIUS
                else:
                    if random.random() < 0.05:
                        heading += random.uniform(-math.pi / 3, math.pi / 3)
                    wx = pos[0] + math.sin(heading) * MOVEMENT_RADIUS
                    wz = pos[2] + math.cos(heading) * MOVEMENT_RADIUS

                dx, dz = wx - pos[0], wz - pos[2]
                if abs(dx) + abs(dz) < 1.0:
                    dx, dz = math.sin(heading), math.cos(heading)
                want = math.atan2(dx, dz)
                diff = (want - heading + math.pi) % (2 * math.pi) - math.pi
                heading += max(-math.radians(15), min(math.radians(15), diff))
                ux, uz = math.sin(heading), math.cos(heading)

                speed = STATE_SPEED.get(cur_state, 70) * speed_mult
                step = speed * dt_ms / 100.0
                stick = (ux * 100, 0.0, uz * 100)
                move_input = (stick[0], stick[2])
                vel = (ux * speed, 0, uz * speed)
                pose = MOVE_STATE_MAP.get(cur_state, 1)
                pos[0] += ux * step
                pos[2] += uz * step

            if now >= afk_jump_at:
                afk_jump_at = now + ANTI_AFK_JUMP_EVERY
                pose = PLAYER_STATE_MAP["jump"]

        facing = (math.sin(heading), 0.0, math.cos(heading))
        rtt = state.rtt_ms if state.rtt_ms is not None else AUTO_MOVE_DEFAULT_RTT
        ack = None
        if AUTO_MOVE_PIGGYBACK_ACK and state.pending_ack is not None:
            ack, state.pending_ack = state.pending_ack, None

        try:
            pkt = await build_player_state_sync_2001(
                key_bytes, mask, random.choice(AUTO_MOVE_MSG_KEYS), state.slot,
                pos, stick, move_input, vel, 0, pose, facing,
                max(1, min(1000, rtt)), int((now - state.session_start) * 1000), ack_order=ack
            )
            await loop.sock_sendto(sock, pkt, (ip, port))
        except Exception:
            pass

        if GLORY_BOOST_ENABLED:
            if now - last_glory_ping >= GLORY_PING_EVERY:
                last_glory_ping = now
                try:
                    p = await build_extra_ping_cmd3(
                        key_bytes, mask, random.choice(GLORY_MSG_KEYS), int(now * 1000) & 0xFFFFFFFF
                    )
                    await loop.sock_sendto(sock, p, (ip, port))
                except Exception:
                    pass

            if now - last_action_beacon >= GLORY_ACTION_EVERY:
                last_action_beacon = now
                try:
                    b = await build_action_beacon_2002(
                        key_bytes, mask, random.choice(GLORY_MSG_KEYS),
                        state.slot, pos, action_type=random.choice([1, 2, 3, 4])
                    )
                    await loop.sock_sendto(sock, b, (ip, port))
                except Exception:
                    pass

            if now - last_pos_hb >= GLORY_ACTION_EVERY:
                last_pos_hb = now
                try:
                    hb = await build_position_heartbeat_2003(
                        key_bytes, mask, random.choice(GLORY_MSG_KEYS), state.slot, pos
                    )
                    await loop.sock_sendto(sock, hb, (ip, port))
                except Exception:
                    pass

        if await wait(GLORY_TICK_INTERVAL if GLORY_BOOST_ENABLED else AUTO_MOVE_TICK_INTERVAL):
            return

async def play_game_craftland(server_ip_port, auth448_pkt1_hex, auth448_pkt2_hex,
                              udp_key, match_code, account_id, match_id, match_index):
    match_start_time = time.time()
    ping_task = None
    move_task = None
    force_move_task = None
    sock = None
    ping_stop = asyncio.Event()
    move_state = MoveState()
    uid_str = str(account_id)
    move_state.owner_uid = uid_str
    completed_cleanly = False

    try:
        ip, port = server_ip_port.split(":")
        port = int(port)
        resolved_ip = await resolve_host_cloudflare(ip)

        loop = asyncio.get_event_loop()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        optimize_udp_socket(sock)
        sock.setblocking(False)

        udp_key_bytes = bytes.fromhex(udp_key)
        nr_layout = (await layouts_from_mask(match_code))[1]

        hello_hex = await build_craftland_hello_packet(
            f"{account_id}_{random.randint(1000, 9999)}", udp_key_bytes, match_code
        )
        join1_hex = await build_craftland_join_packet(1, account_id, match_id, 0, udp_key_bytes, match_code)
        join2_hex = await build_craftland_join_packet(2, account_id, match_id, 1, udp_key_bytes, match_code)

        await loop.sock_sendto(sock, bytes.fromhex(hello_hex), (resolved_ip, port))
        phase = "hello"
        phase_ts = time.time()
        auth_sent = False
        local_closed = False
        send_lock = asyncio.Lock()

        ping_task = asyncio.create_task(
            keepalive_ping(sock, resolved_ip, port, udp_key_bytes, match_code, ping_stop, move_state)
        )
        last_activity = time.time()
        ack_top, ack_sent_at = None, 0.0

        print_colored(
            f"🎮 [CRAFTLAND #{match_index}] UDP started → {server_ip_port} (DNS: {resolved_ip})",
            Colors.MAGENTA
        )

        async def force_move_after_delay():
            nonlocal move_task
            await asyncio.sleep(12.0)
            if AUTO_MOVE_ENABLED and move_task is None:
                print_warning(f"[MOVE][CRAFTLAND #{match_index}] FORCE-START (12s fallback)")
                move_task = asyncio.create_task(
                    auto_move_loop(sock, resolved_ip, port, udp_key_bytes, match_code,
                                   move_state, ping_stop, label=f"[CRAFTLAND #{match_index}]")
                )

        force_move_task = asyncio.create_task(force_move_after_delay())

        async def send_auth448():
            nonlocal phase, auth_sent, move_task
            if auth_sent:
                return
            async with send_lock:
                if auth_sent:
                    return
                auth_sent = True
                phase = "in_game"
                try:
                    await loop.sock_sendto(sock, bytes.fromhex(auth448_pkt1_hex), (resolved_ip, port))
                    await asyncio.sleep(0.6)
                    await loop.sock_sendto(sock, bytes.fromhex(auth448_pkt2_hex), (resolved_ip, port))
                    print_success(f"[CRAFTLAND #{match_index}] JOIN(3043) + AUTH(448) sent!")
                    if AUTO_MOVE_ENABLED and move_task is None:
                        move_task = asyncio.create_task(
                            auto_move_loop(sock, resolved_ip, port, udp_key_bytes, match_code,
                                           move_state, ping_stop, label=f"[CRAFTLAND #{match_index}]")
                        )
                except Exception as e:
                    print_error(f"[CRAFTLAND #{match_index}] auth448 err: {e}")

        while not local_closed:
            if time.time() - match_start_time > CRAFTLAND_MAX_MATCH_DURATION:
                completed_cleanly = True
                break
            try:
                response, server_addr = await asyncio.wait_for(
                    loop.sock_recvfrom(sock, 65535), timeout=1.0
                )
                if response:
                    last_activity = time.time()
                    frame = await decode_packet(response, udp_key_bytes, match_code)
                    if not frame:
                        move_state.undecoded += 1
                        oid = await peek_reliable_order(response, udp_key_bytes, match_code)
                        if oid is not None:
                            nxt = (oid + 1) & 0xFFFF
                            fresh_ack = ack_top is None or (((nxt - ack_top) & 0xFFFF) < 0x8000 and nxt != ack_top)
                            if fresh_ack or time.time() - ack_sent_at > 0.25:
                                try:
                                    top_ = nxt if fresh_ack else ack_top
                                    pkt_ = await build_packet(
                                        0x68, nr_layout, 0, 2, None, 1,
                                        top_.to_bytes(2, "little"), udp_key_bytes
                                    )
                                    await loop.sock_sendto(sock, pkt_, server_addr)
                                    ack_top, ack_sent_at = top_, time.time()
                                except Exception:
                                    pass
                        continue

                    move_state.on_server_frame(frame)
                    cmd = frame.get('cmd')
                    order_id = frame.get('orderId')
                    flags = frame.get('flags', 0)

                    if cmd in [103, 107]:
                        print_success(f"[CRAFTLAND #{match_index}] Completed (cmd {cmd})")
                        completed_cleanly = True
                        local_closed = True
                        continue

                    if (flags & 1) and order_id is not None:
                        try:
                            next_expected = (order_id + 1) & 0xFFFF
                            if ack_top is None or ((next_expected - ack_top) & 0xFFFF) < 0x8000:
                                ack_top, ack_sent_at = next_expected, time.time()
                            data_ack = await build_packet(
                                0x68, nr_layout, 0, 2, None, 1,
                                next_expected.to_bytes(2, "little"), udp_key_bytes
                            )
                            await loop.sock_sendto(sock, data_ack, server_addr)
                        except Exception:
                            pass

                    if cmd == 130:
                        print_success(f"[CRAFTLAND #{match_index}] Loaded into Craftland")
                        continue

                    ptype = await classify(frame)
                    if ptype == "PING":
                        _, reply = await reply_for(frame, udp_key_bytes, match_code)
                        if reply:
                            await loop.sock_sendto(sock, reply, server_addr)
                        continue

                    if phase == "hello" and cmd == 1:
                        phase = "join1"
                        phase_ts = time.time()
                        await loop.sock_sendto(sock, bytes.fromhex(join1_hex), (resolved_ip, port))
                    elif phase == "join1" and (cmd == 3045 or (order_id is not None and order_id >= 1)):
                        phase = "join2"
                        phase_ts = time.time()
                        await loop.sock_sendto(sock, bytes.fromhex(join2_hex), (resolved_ip, port))
                    elif phase == "join2" and (cmd == 3045 or (order_id is not None and order_id >= 3)):
                        await send_auth448()

            except asyncio.TimeoutError:
                now = time.time()
                if phase == "hello":
                    if now - phase_ts > 5.0:
                        try:
                            await loop.sock_sendto(sock, bytes.fromhex(hello_hex), (resolved_ip, port))
                        except Exception:
                            pass
                        phase_ts = now
                    if now - match_start_time > 25.0:
                        print_warning(f"[CRAFTLAND #{match_index}] Handshake timeout")
                        break
                elif phase == "join1":
                    if now - phase_ts > 2.0:
                        try:
                            await loop.sock_sendto(sock, bytes.fromhex(join1_hex), (resolved_ip, port))
                        except Exception:
                            pass
                        phase_ts = now
                    if now - match_start_time > 25.0:
                        print_warning(f"[CRAFTLAND #{match_index}] JOIN1 timeout")
                        break
                elif phase == "join2":
                    if now - phase_ts > 2.0:
                        try:
                            await loop.sock_sendto(sock, bytes.fromhex(join2_hex), (resolved_ip, port))
                        except Exception:
                            pass
                        phase_ts = now
                    if now - match_start_time > 25.0:
                        await send_auth448()
                elif phase == "in_game":
                    if now - last_activity > CRAFTLAND_MATCH_IDLE_TIMEOUT:
                        print_success(f"[CRAFTLAND #{match_index}] Finished naturally")
                        completed_cleanly = True
                        break
                continue
            except BlockingIOError:
                await asyncio.sleep(0.05)
            except OSError:
                await asyncio.sleep(0.5)
                continue
            except Exception:
                await asyncio.sleep(0.5)
                continue

        return f"match #{match_index} finished"
    except asyncio.CancelledError:
        raise
    except Exception as e:
        print_error(f"[CRAFTLAND #{match_index}] error: {e}")
        return f"match #{match_index} error"
    finally:
        if completed_cleanly:
            try:
                bot_state.increment_match(uid_str)
            except Exception:
                pass
        ping_stop.set()
        for t in (force_move_task, move_task, ping_task):
            if t:
                t.cancel()
                try:
                    await t
                except asyncio.CancelledError:
                    pass
                except Exception:
                    pass
        if sock:
            try:
                sock.close()
            except Exception:
                pass
        remaining = await _dec_match(uid_str)
        total = await _get_total_match_count()
        print_info(
            f"[CRAFTLAND #{match_index}] Closed. "
            f"UID active: {remaining} | Total active: {total}"
        )
        try:
            bot_state.update_status(uid_str, "IN_MATCH" if remaining > 0 else "ONLINE", remaining)
        except Exception:
            pass


# ==================== LONE WOLF MAIN LOOP ====================
async def functional_lone_wolf(addrs, starter_packet, account_region, client_version,
                                key, iv, account_id="", account_data=None,
                                max_reconnects=10):
    reconnects = 0
    ip, port = addrs.split(":")
    play_matches: List[asyncio.Task] = []
    no_response_count = 0
    search_attempts = 0
    last_start_time = 0.0
    uid_str = str(account_id)

    consecutive_parse_failures = 0

    current_token = starter_packet
    current_key = key
    current_iv = iv
    current_account_data = account_data

    async def _read_tcp_frames(reader, buf: bytearray, timeout_sec: float = 0.5):
        frames = []
        try:
            chunk = await asyncio.wait_for(reader.read(8192), timeout=timeout_sec)
            if not chunk:
                raise ConnectionError("Connection closed by server")
            buf.extend(chunk)
        except asyncio.TimeoutError:
            return frames
        while len(buf) >= 5:
            plen = int.from_bytes(buf[2:5], "big")
            if plen > 262144:
                buf.clear()
                break
            if len(buf) < 5 + plen:
                break
            frames.append(bytes(buf[:5 + plen]))
            del buf[:5 + plen]
        return frames

    try:
        while True:
            writer = None
            try:
                if current_account_data:
                    fresh = None
                    if current_account_data.get('auth_type') == 'guest' and current_account_data.get('auth_uid'):
                        fresh = cache_get(str(current_account_data['auth_uid']))
                    elif current_account_data.get('auth_type') == 'token' and current_account_data.get('auth_token'):
                        fresh = cache_get(f"tok_{current_account_data['auth_token'][:20]}")

                    if fresh:
                        current_account_data = fresh
                        current_key = fresh['aes_ak']
                        current_iv = fresh['iv_i']
                        current_token = await build_tcp_startup_packet(
                            fresh['account_id'],
                            fresh['token'],
                            fresh['server_time'],
                            current_key,
                            current_iv,
                            region=fresh.get('region', account_region),
                            typ='OnLine'
                        )
                    else:
                        print_warning(f"[FUNCTIONAL] Cache miss for {uid_str} → re-login needed")
                        try:
                            if current_account_data.get('auth_uid'):
                                cache_invalidate(str(current_account_data['auth_uid']))
                            if current_account_data.get('auth_token'):
                                cache_invalidate(f"tok_{current_account_data['auth_token'][:20]}")
                        except Exception:
                            pass
                        raise ConnectionError("Cache expired, triggering fresh login")

                resolved_ip = await resolve_host_cloudflare(ip)
                reader, writer = await asyncio.open_connection(resolved_ip, int(port))

                raw_sock = writer.get_extra_info('socket')
                if raw_sock:
                    optimize_tcp_socket(raw_sock)

                writer.write(bytes.fromhex(current_token))
                await writer.drain()

                try:
                    init_ka = await send_keep_alive(account_region, current_key, current_iv)
                    if init_ka and writer and not writer.is_closing():
                        writer.write(init_ka)
                        await asyncio.wait_for(writer.drain(), timeout=3)
                except Exception:
                    pass

                print_success(f"[FUNCTIONAL] TCP Gateway Connected for UID: {uid_str} (DNS: {resolved_ip})")
                reconnects = 0
                no_response_count = 0
                last_start_time = 0.0

                rx_buf = bytearray()
                own_id = current_account_data.get('account_id') if current_account_data else uid_str
                raw_map_fallback = CRAFTLAND_MAP_CODE.replace("#FREEFIRE", "").split("/")[0]
                fallback_room_name = b""

                # Step 1: Drain initial frames briefly
                drain_until = asyncio.get_running_loop().time() + 0.2
                while asyncio.get_running_loop().time() < drain_until:
                    await _read_tcp_frames(reader, rx_buf, 0.2)

                # Step 2: 1d<reg> Client Info
                ci_pkt = craftland_client_info_packet(current_key, current_iv, region=account_region)
                writer.write(ci_pkt)
                await writer.drain()
                print_info(f"[CRAFTLAND] {uid_str} client info (1d) sent")
                await asyncio.sleep(0.1)

                # Step 3: 0e<reg> Preload (0820)
                pl_pkt = craftland_preload_packet(current_key, current_iv, region=account_region)
                writer.write(pl_pkt)
                await writer.drain()
                print_info(f"[CRAFTLAND] {uid_str} preload (0820) sent")

                # Step 4: Wait for 0e00 preload ack (f4 == 32)
                ack_deadline = asyncio.get_running_loop().time() + 4.0
                preload_ok = False
                while not preload_ok and asyncio.get_running_loop().time() < ack_deadline:
                    for frm in await _read_tcp_frames(reader, rx_buf, 0.4):
                        if frm.hex().startswith("0e00"):
                            rf = extract_raw_fields(frm[5:])
                            if rf.get(4) == 32:
                                preload_ok = True
                                print_success(f"[CRAFTLAND] {uid_str} preload ack (f4=32) OK")
                                break

                # Step 5: Craftland Solo Start Matchmaking
                try:
                    bot_state.update_status(uid_str, "SEARCHING", await _get_match_count(uid_str))
                except Exception:
                    pass

                cl_start = await Craftland_Solo_Start_Matchmaking_Packet(
                    current_key, current_iv, own_id,
                    map_code=CRAFTLAND_MAP_CODE, region=account_region
                )
                writer.write(cl_start)
                await writer.drain()
                search_attempts += 1
                last_start_time = asyncio.get_running_loop().time()
                last_hb_time = last_start_time
                print_info(f"[CRAFTLAND] Matchmaking sent #{search_attempts} | map={CRAFTLAND_MAP_CODE}")

                # Step 6: Heartbeat + Wait for 0e00 Match Found
                while True:
                    play_matches[:] = [m for m in play_matches if not m.done()]
                    now = asyncio.get_running_loop().time()

                    active_count = await _get_match_count(uid_str)
                    try:
                        bot_state.update_status(
                            uid_str,
                            "SEARCHING" if active_count == 0 else "IN_MATCH",
                            active_count
                        )
                    except Exception:
                        pass

                    if now - last_hb_time >= CRAFTLAND_HEARTBEAT_SEC:
                        hb_pkt = craftland_heartbeat_packet(current_key, current_iv, region=account_region)
                        writer.write(hb_pkt)
                        await writer.drain()
                        last_hb_time = now

                    if now - last_start_time >= CRAFTLAND_START_RETRY:
                        search_attempts += 1
                        cl_start = await Craftland_Solo_Start_Matchmaking_Packet(
                            current_key, current_iv, own_id,
                            map_code=CRAFTLAND_MAP_CODE, region=account_region
                        )
                        writer.write(cl_start)
                        await writer.drain()
                        last_start_time = now
                        print_info(f"[CRAFTLAND] Retry match-start #{search_attempts}")

                    frames = await _read_tcp_frames(reader, rx_buf, 0.35)
                    if not frames:
                        no_response_count += 1
                        if no_response_count > 120:
                            print_warning(f"[FUNCTIONAL] Gateway silent ({uid_str}). Reconnecting...")
                            raise ConnectionError("Gateway idle timeout")
                        continue

                    no_response_count = 0
                    matched_and_restarting = False

                    for frm in frames:
                        fh = frm.hex()
                        if not fh.startswith("0e00"):
                            continue

                        rf = extract_raw_fields(frm[5:])
                        f4 = rf.get(4)

                        if f4 == 2 and isinstance(rf.get(5), (bytes, bytearray)):
                            try:
                                f5_room = extract_raw_fields(rf[5])
                                if isinstance(f5_room.get(27), (bytes, bytearray)):
                                    f27 = extract_raw_fields(f5_room[27])
                                    if isinstance(f27.get(2), (bytes, bytearray)):
                                        fallback_room_name = bytes(f27[2])
                            except Exception:
                                pass
                            continue

                        if f4 == 16 and isinstance(rf.get(5), (bytes, bytearray)):
                            f5 = extract_raw_fields(rf[5])
                            block_val = f5.get(1)
                            srv_raw = f5.get(2)
                            key_raw = f5.get(3)
                            rc_raw = f5.get(19)
                            rn_raw = f5.get(20)
                            mask_raw = f5.get(42) or rf.get(42)

                            server_ip_port = srv_raw.decode("utf-8", errors="ignore").strip() if isinstance(srv_raw, (bytes, bytearray)) else ""
                            if isinstance(key_raw, (bytes, bytearray)):
                                udp_key = key_raw.hex() if len(key_raw) == 16 else key_raw.decode("utf-8", errors="ignore").strip()
                            else:
                                udp_key = ""
                            room_code = rc_raw.decode("utf-8", errors="ignore").strip() if isinstance(rc_raw, (bytes, bytearray)) else raw_map_fallback
                            room_name_b = bytes(rn_raw) if isinstance(rn_raw, (bytes, bytearray)) else fallback_room_name
                            match_code = ""
                            if isinstance(mask_raw, (bytes, bytearray)):
                                match_code = mask_raw.decode("utf-8", errors="ignore").strip()[-5:]
                            elif mask_raw is not None:
                                match_code = str(mask_raw).strip()[-5:]

                            effective_acc_id = rf.get(1) or account_id or own_id

                            if udp_key and match_code and ":" in server_ip_port and block_val:
                                print_colored("=" * 60, Colors.GREEN)
                                print_colored(
                                    f"CRAFTLAND MATCH FOUND! server={server_ip_port} | mask={match_code}",
                                    Colors.GREEN
                                )
                                print_colored("=" * 60, Colors.GREEN)

                                p448_1, p448_2 = await build_craftland_auth448_packet(
                                    udp_key, match_code, effective_acc_id, block_val,
                                    room_code=room_code or raw_map_fallback,
                                    room_name_bytes=room_name_b,
                                    client_version=CRAFTLAND_CLIENT_VERSION,
                                    device_id=CRAFTLAND_DEVICE_ID,
                                )

                                match_index = await _inc_match(uid_str)
                                total = await _get_total_match_count()
                                print_success(
                                    f"[CRAFTLAND] UDP task started. "
                                    f"UID active: {match_index} | Total: {total}"
                                )

                                try:
                                    bot_state.update_status(uid_str, "IN_MATCH", match_index)
                                except Exception:
                                    pass

                                new_match = asyncio.create_task(
                                    play_game_craftland(
                                        server_ip_port, p448_1, p448_2, udp_key, match_code,
                                        effective_acc_id, block_val, match_index
                                    )
                                )
                                play_matches.append(new_match)
                                consecutive_parse_failures = 0

                                while not new_match.done():
                                    try:
                                        dg = await asyncio.wait_for(reader.read(4096), timeout=1.0)
                                        if not dg:
                                            break
                                    except asyncio.TimeoutError:
                                        continue
                                    except Exception:
                                        break

                                try:
                                    await new_match
                                except Exception as e:
                                    print_error(f"[CRAFTLAND] Match #{match_index} error: {e}")

                                try:
                                    writer.close()
                                    await writer.wait_closed()
                                except Exception:
                                    pass

                                print_info(f"[OFFLINE] {NEW_MATCH_DELAY}s offline → next Craftland match")
                                await asyncio.sleep(NEW_MATCH_DELAY)
                                reconnects = 0
                                matched_and_restarting = True
                                break
                            else:
                                consecutive_parse_failures += 1
                                print_warning(
                                    f"[FUNCTIONAL] Incomplete Craftland match packet "
                                    f"(#{consecutive_parse_failures}/{MAX_CONSECUTIVE_PARSE_FAILURES})"
                                )
                                if consecutive_parse_failures >= MAX_CONSECUTIVE_PARSE_FAILURES:
                                    if current_account_data:
                                        try:
                                            if current_account_data.get('auth_uid'):
                                                cache_invalidate(str(current_account_data['auth_uid']))
                                            if current_account_data.get('auth_token'):
                                                cache_invalidate(f"tok_{current_account_data['auth_token'][:20]}")
                                        except Exception:
                                            pass
                                    consecutive_parse_failures = 0

                    if matched_and_restarting:
                        break

            except asyncio.CancelledError:
                print_warning(f"[FUNCTIONAL] Cancelled — cancelling {len(play_matches)} UDP matches")
                for m in play_matches:
                    if not m.done():
                        m.cancel()
                if play_matches:
                    await asyncio.gather(*play_matches, return_exceptions=True)
                play_matches.clear()
                raise
            except Exception as e:
                print_error(f"[FUNCTIONAL] TCP state ({uid_str}): {e}")
                play_matches[:] = [m for m in play_matches if not m.done()]

                if writer:
                    try:
                        writer.close()
                        await writer.wait_closed()
                    except Exception:
                        pass

                if "Cache expired" in str(e):
                    print_warning(f"[FUNCTIONAL] Triggering re-login for {uid_str}")
                    break

                reconnects += 1
                if reconnects > max_reconnects:
                    print_error("[FUNCTIONAL] Max reconnects reached, retrying...")
                    reconnects = 0
                    await asyncio.sleep(3)
                    continue

                await asyncio.sleep(min(reconnects, 2))

    except asyncio.CancelledError:
        print_warning(f"[FUNCTIONAL] Outer cancelled. {len(play_matches)} UDP matches still running.")
        for m in play_matches:
            if not m.done():
                m.cancel()
        if play_matches:
            await asyncio.gather(*play_matches, return_exceptions=True)
        play_matches.clear()
        raise


async def informational(addrs, starter_packet, key, iv, region="BD", max_reconnects=3):
    reconnects = 0
    ip, port = addrs.split(":")
    while True:
        writer = None
        ping_task = None
        try:
            resolved_ip = await resolve_host_cloudflare(ip)
            reader, writer = await asyncio.open_connection(resolved_ip, int(port))

            raw_sock = writer.get_extra_info('socket')
            if raw_sock:
                optimize_tcp_socket(raw_sock)

            writer.write(bytes.fromhex(starter_packet))
            await writer.drain()
            reconnects = 0

            try:
                init_ka = await send_keep_alive(region, key, iv)
                if init_ka and writer and not writer.is_closing():
                    writer.write(init_ka)
                    await asyncio.wait_for(writer.drain(), timeout=3)
            except Exception:
                pass

            async def info_keepalive():
                ka_bytes = await send_keep_alive(region, key, iv)
                while True:
                    await asyncio.sleep(5)
                    try:
                        if writer and not writer.is_closing():
                            writer.write(ka_bytes)
                            await writer.drain()
                    except Exception:
                        break

            ping_task = asyncio.create_task(info_keepalive())

            while True:
                data = await reader.read(8192)
                if not data:
                    raise ConnectionError("Connection closed")
        except asyncio.CancelledError:
            if ping_task:
                ping_task.cancel()
            if writer:
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass
            raise
        except Exception:
            if ping_task:
                ping_task.cancel()
            if writer:
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass
            reconnects += 1
            if reconnects > max_reconnects:
                await asyncio.sleep(3)
                reconnects = 0
            else:
                await asyncio.sleep(1)


# ==================== ACCOUNT PROCESSORS ====================

def _register_credentials(account_data: Dict):
    try:
        acc_id = str(account_data['account_id'])
        bot_state.account_credentials[acc_id] = account_data
        if account_data.get('auth_uid'):
            bot_state.account_credentials[str(account_data['auth_uid'])] = account_data
        if account_data.get('auth_token'):
            bot_state.account_credentials[f"tok_{account_data['auth_token'][:20]}"] = account_data
    except Exception:
        pass


async def refresh_account_profile(account_data_or_uid: Any):
    try:
        if isinstance(account_data_or_uid, str):
            uid = str(account_data_or_uid)
            account_data = bot_state.account_credentials.get(uid)
        else:
            account_data = account_data_or_uid
            uid = str(account_data.get('account_id'))

        if not account_data:
            return

        url = account_data.get('server_url')
        token = account_data.get('token')
        release_version = account_data.get('release_version')
        payload = account_data.get('login_payload_data')

        if not (url and token and release_version and payload):
            return

        res = await send_getlogin(payload, url, token, release_version)
        if res:
            res_proto, dict_res = res
            level = int(get_proto_field(dict_res, 6, 1))
            exp = int(get_proto_field(dict_res, 7, 0))
            likes = int(get_proto_field(dict_res, 8, 0))
            nickname = res_proto.nickname or get_proto_field(dict_res, 4, "")

            acc_id = str(account_data['account_id'])
            if exp > 0:
                bot_state.update_exp(acc_id, exp, level)
            if likes > 0 and acc_id in bot_state.accounts:
                bot_state.accounts[acc_id]["likes"] = likes
            if nickname and acc_id in bot_state.accounts:
                bot_state.accounts[acc_id]["nickname"] = nickname
            print_info(f"[EXP-REFRESH] UID {acc_id} -> Level: {level}, EXP: {exp}")
    except Exception as e:
        print_error(f"refresh_account_profile error: {e}")


async def process_account_uid_pass(uid: str, password: str) -> Optional[Dict]:
    cached = cache_get(uid)
    if cached:
        print_success(f"[CACHE HIT] UID {uid} loaded from token_cache.json")
        acc_id = str(cached['account_id'])
        bot_state.register_account(
            uid=acc_id,
            nickname=cached.get('nickname', f"Player_{acc_id}"),
            region=cached.get('region', 'BD'),
            level=cached.get('level', 1),
            exp=cached.get('exp', 0),
            likes=cached.get('likes', 0)
        )
        _register_credentials(cached)
        return cached

    print_info(f"[LOGIN] Full login for UID {uid}...")
    try:
        verconfig_res = await version_config()
        if verconfig_res is None:
            return None
        release_version, client_version, server_url = verconfig_res

        tokengrant_response = await get_access_token(uid, password)
        if tokengrant_response is None:
            return None
        open_id, access_token, platform = tokengrant_response

        device_info = get_device_for_account(uid)

        login_payload_data = await build_majorlogin_payload(open_id, access_token, platform, client_version, device_info)
        if login_payload_data is None:
            return None

        majorlogin_response = await send_majorlogin(login_payload_data, release_version, server_url)
        if majorlogin_response is None:
            return None

        getlogin_result = await send_getlogin(login_payload_data, majorlogin_response.url, majorlogin_response.token, release_version)
        if getlogin_result is None:
            return None
        res_proto, dict_res = getlogin_result

        acc_id = str(majorlogin_response.account_id)
        level = int(get_proto_field(dict_res, 6, 1))
        exp = int(get_proto_field(dict_res, 7, 0))
        likes = int(get_proto_field(dict_res, 8, 0))
        nickname = res_proto.nickname or get_proto_field(dict_res, 4, f"Player_{acc_id}")
        region = majorlogin_response.region or get_proto_field(dict_res, 3, "BD")

        func_addr = res_proto.functional_addrs
        info_addr = res_proto.informational_addrs

        if not isinstance(func_addr, str) or not func_addr or ":" not in func_addr:
            func_addr = None
        if not isinstance(info_addr, str) or not info_addr or ":" not in info_addr:
            info_addr = None

        key_val = majorlogin_response.aes_ak
        iv_val = majorlogin_response.iv_i
        if not isinstance(key_val, (bytes, bytearray)) or len(key_val) < 16:
            key_val = AES_KEY
        if not isinstance(iv_val, (bytes, bytearray)) or len(iv_val) < 16:
            iv_val = AES_IV

        bot_state.register_account(uid=acc_id, nickname=nickname, region=region, level=level, exp=exp, likes=likes)

        account_data = {
            'account_id': majorlogin_response.account_id,
            'nickname': nickname,
            'region': region,
            'level': level,
            'exp': exp,
            'likes': likes,
            'open_id': open_id,
            'access_token': access_token,
            'platform': str(platform),
            'token': majorlogin_response.token,
            'server_time': majorlogin_response.server_time,
            'aes_ak': key_val,
            'iv_i': iv_val,
            'functional_addrs': func_addr,
            'informational_addrs': info_addr,
            'release_version': release_version,
            'client_version': client_version,
            'server_url': majorlogin_response.url,
            'login_payload_data': login_payload_data,
            'auth_type': 'guest',
            'auth_uid': uid,
            'auth_password': password
        }
        _register_credentials(account_data)
        cache_set(uid, account_data)
        return account_data
    except Exception as e:
        print_error(f"process_account_uid_pass error: {e}")
        return None


async def process_account_token(access_token: str) -> Optional[Dict]:
    cache_key = f"tok_{access_token[:20]}"
    cached = cache_get(cache_key)
    if cached:
        print_success(f"[CACHE HIT] Token loaded from cache")
        acc_id = str(cached['account_id'])
        bot_state.register_account(
            uid=acc_id,
            nickname=cached.get('nickname', f"Player_{acc_id}"),
            region=cached.get('region', 'BD'),
            level=cached.get('level', 1),
            exp=cached.get('exp', 0),
            likes=cached.get('likes', 0)
        )
        _register_credentials(cached)
        return cached

    print_info("[LOGIN] Full login with Access Token...")
    try:
        verconfig_res = await version_config()
        if verconfig_res is None:
            return None
        release_version, client_version, server_url = verconfig_res

        url = f"https://100067.connect.garena.com/oauth/token/inspect?token={access_token}"
        hdrs = {
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "close",
            "Content-Type": "application/x-www-form-urlencoded",
            "Host": "100067.connect.garena.com",
            "User-Agent": "GarenaMSDK/4.0.19P4(G011A ;Android 9;en;US;)"
        }
        resp = await client.get(url, headers=hdrs, timeout=10.0)
        data = resp.json()

        if 'error' in data:
            return None

        open_id = data.get('open_id')
        platform = data.get('platform', 4)

        if not open_id:
            return None

        device_info = get_device_for_account(open_id)

        login_payload_data = await build_majorlogin_payload(open_id, access_token, str(platform), client_version, device_info)
        if not login_payload_data:
            return None

        majorlogin_response = await send_majorlogin(login_payload_data, release_version, server_url)
        if majorlogin_response is None:
            return None

        getlogin_result = await send_getlogin(
            login_payload_data,
            majorlogin_response.url,
            majorlogin_response.token,
            release_version
        )
        if getlogin_result is None:
            return None

        res_proto, dict_res = getlogin_result
        acc_id = str(majorlogin_response.account_id)
        level = int(get_proto_field(dict_res, 6, 1))
        exp = int(get_proto_field(dict_res, 7, 0))
        likes = int(get_proto_field(dict_res, 8, 0))
        nickname = res_proto.nickname or get_proto_field(dict_res, 4, f"Player_{acc_id}")
        region = majorlogin_response.region or get_proto_field(dict_res, 3, "BD")

        key_val = majorlogin_response.aes_ak
        iv_val = majorlogin_response.iv_i
        if not isinstance(key_val, (bytes, bytearray)) or len(key_val) < 16:
            key_val = AES_KEY
        if not isinstance(iv_val, (bytes, bytearray)) or len(iv_val) < 16:
            iv_val = AES_IV

        bot_state.register_account(uid=acc_id, nickname=nickname, region=region, level=level, exp=exp, likes=likes)

        account_data = {
            'account_id': majorlogin_response.account_id,
            'nickname': nickname,
            'region': region,
            'level': level,
            'exp': exp,
            'likes': likes,
            'open_id': open_id,
            'access_token': access_token,
            'platform': str(platform),
            'token': majorlogin_response.token,
            'server_time': majorlogin_response.server_time,
            'aes_ak': key_val,
            'iv_i': iv_val,
            'functional_addrs': res_proto.functional_addrs or get_proto_field(dict_res, 14),
            'informational_addrs': res_proto.informational_addrs or get_proto_field(dict_res, 32),
            'release_version': release_version,
            'client_version': client_version,
            'server_url': majorlogin_response.url,
            'login_payload_data': login_payload_data,
            'auth_type': 'token',
            'auth_token': access_token
        }
        _register_credentials(account_data)
        cache_set(cache_key, account_data)
        return account_data
    except Exception as e:
        print_error(f"process_account_token error: {e}")
        return None


async def run_account_worker(account_data: Dict, label: str):
    acc_id = str(account_data['account_id'])
    informational_task = None
    exp_task = None
    functional_task = None
    try:
        reg = account_data.get('region', 'BD')
        func_addr = account_data.get('functional_addrs')
        info_addr = account_data.get('informational_addrs')

        if not func_addr or not isinstance(func_addr, str) or ":" not in func_addr:
            print_warning(f"[!] No functional_addrs for {acc_id}")
            while True:
                await asyncio.sleep(60)
            return

        tcp_packet_online = await build_tcp_startup_packet(
            account_data['account_id'],
            account_data['token'],
            account_data['server_time'],
            account_data['aes_ak'],
            account_data['iv_i'],
            region=reg,
            typ='OnLine'
        )

        tcp_packet_chat = await build_tcp_startup_packet(
            account_data['account_id'],
            account_data['token'],
            account_data['server_time'],
            account_data['aes_ak'],
            account_data['iv_i'],
            region=reg,
            typ='ChaT'
        )

        if info_addr and isinstance(info_addr, str) and ":" in info_addr:
            informational_task = asyncio.create_task(
                informational(
                    info_addr,
                    tcp_packet_chat,
                    account_data['aes_ak'],
                    account_data['iv_i'],
                    region=reg
                )
            )

        async def exp_refresher():
            while True:
                await asyncio.sleep(90)
                fresh = bot_state.account_credentials.get(acc_id)
                if fresh:
                    await refresh_account_profile(fresh)

        exp_task = asyncio.create_task(exp_refresher())

        functional_task = asyncio.create_task(
            functional_lone_wolf(
                func_addr,
                tcp_packet_online,
                account_data['region'],
                account_data['client_version'],
                account_data['aes_ak'],
                account_data['iv_i'],
                account_id=acc_id,
                account_data=account_data
            )
        )

        await functional_task

    except asyncio.CancelledError:
        raise
    except Exception as e:
        print_error(f"run_account_worker error for {label}: {e}")
    finally:
        for t in (informational_task, exp_task, functional_task):
            if t and not t.done():
                t.cancel()
        for t in (informational_task, exp_task, functional_task):
            if t:
                try:
                    await t
                except (asyncio.CancelledError, Exception):
                    pass


async def account_loop_guest(uid: str, password: str):
    while True:
        try:
            print_info(f"[LOGIN] Starting login for Guest UID: {uid}...")
            try:
                bot_state.update_status(str(uid), "CONNECTING")
            except Exception:
                pass
            account_data = await process_account_uid_pass(uid, password)
            if not account_data:
                print_error(f"Login failed for UID: {uid}. Retrying in 15 seconds...")
                try:
                    bot_state.update_status(str(uid), "ERROR")
                except Exception:
                    pass
                await asyncio.sleep(15)
                continue

            await run_account_worker(account_data, uid)
            print_warning(f"Session finished for {uid}. Reconnecting in 3s...")
            await asyncio.sleep(3)
        except asyncio.CancelledError:
            print_warning(f"Worker for {uid} stopped.")
            try:
                bot_state.update_status(str(uid), "OFFLINE")
            except Exception:
                pass
            break
        except Exception as e:
            print_error(f"Error for UID {uid}: {e}. Retrying in 10s...")
            await asyncio.sleep(10)


async def account_loop_token(token: str):
    token_label = token[:10]
    while True:
        try:
            print_info("[LOGIN] Starting login with Access Token...")
            account_data = await process_account_token(token)
            if not account_data:
                print_error("Login failed for Token. Retrying in 15 seconds...")
                await asyncio.sleep(15)
                continue

            acc_id = str(account_data['account_id'])
            await run_account_worker(account_data, acc_id)
            print_warning("Token session finished. Reconnecting in 3s...")
            await asyncio.sleep(3)
        except asyncio.CancelledError:
            print_warning(f"Worker for token {token_label} stopped.")
            break
        except Exception as e:
            print_error(f"Token error: {e}. Retrying in 10s...")
            await asyncio.sleep(10)


# ==================== ACCOUNTS LOADER ====================

def load_accounts():
    accounts = []
    if os.path.exists(ACCOUNTS_FILE):
        try:
            with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    accounts = data
        except Exception as e:
            print_error(f"Could not load {ACCOUNTS_FILE}: {e}")

    if not accounts and FALLBACK_UID and FALLBACK_PASSWORD:
        accounts.append({"uid": FALLBACK_UID, "password": FALLBACK_PASSWORD})

    return accounts


# ==================== DASHBOARD WIRING (late) ====================
# সব helper ডেফাইন হওয়ার পরে dashboard_server-এ inject করি।
try:
    import dashboard_server as _dash
    _dash.LOAD_USERS = _load_users
    _dash.SET_MAP_CODE = set_map_code
    _dash.CHANGE_PASSWORD = change_user_password
    _dash.CRAFTLAND_MAP_CODE_GETTER = lambda: CRAFTLAND_MAP_CODE
    _dash.GET_TOTAL_MATCHES = _get_total_match_count
    _dash.GET_MATCH_COUNT = _get_match_count
    print_info("[WIRING] Dashboard helpers injected OK")
except Exception as _e:
    print_error(f"[WIRING] dashboard inject failed: {_e}")


# ==================== MAIN ====================

async def main():
    # ০) সেটিংস লোড
    try:
        load_settings()
    except Exception as e:
        print_error(f"[SETTINGS] load failed: {e}")

    print_colored("=" * 60, Colors.CYAN)
    print_colored("    MAHIR Craftland UDP", Colors.GREEN)
    print_colored("    FreeFire Lone Wolf Auto-Match Bot", Colors.WHITE)
    print_colored("=" * 60, Colors.CYAN)
    print_info(f"Web Port: {WEB_PORT}")
    print_info(f"Map Code: {CRAFTLAND_MAP_CODE}")
    print_info(f"Start Match Interval: {START_MATCH_INTERVAL}s")
    print_info(f"Offline Wait: {NEW_MATCH_DELAY}s (after match found)")
    print_info(f"Non-match Reconnect: {NON_MATCH_RECONNECT_DELAY}s")
    print_info(f"Cache Invalidation Threshold: {MAX_CONSECUTIVE_PARSE_FAILURES}x")
    print_info(f"Cache TTL: {TOKEN_CACHE_TTL}s ({TOKEN_CACHE_TTL // 60} min)")
    print_info(f"Priority Regions: {PRIORITY_REGIONS}")
    print_info("Device System: 1 ID = 1 Persistent Device ID (devices.json)")
    print_info(f"Users File: {USERS_FILE}")
    print_info(f"Settings File: {SETTINGS_FILE}")
    print_colored("=" * 60, Colors.CYAN)

    # ১) ওয়েব ড্যাশবোর্ড
    try:
        await start_web_dashboard(host=WEB_HOST, port=WEB_PORT)
        print_success(f"Web Dashboard live at http://localhost:{WEB_PORT}")
    except Exception as e:
        print_error(f"Could not start web dashboard: {e}")

    # ২) একক অ্যাকাউন্ট যোগ
    async def on_account_added_handler(data):
        if not data:
            return
        if "token" in data and data["token"]:
            t = str(data["token"]).strip()
            if not t:
                return
            key = t[:10]
            if key in bot_state.account_workers and not bot_state.account_workers[key].done():
                print_warning(f"[ADD] Token worker already running for {key}")
                return
            task = asyncio.create_task(account_loop_token(t))
            bot_state.account_workers[key] = task
            print_success(f"[ADD] Token account started: {key}...")
        elif "uid" in data and "password" in data:
            u = str(data["uid"]).strip()
            p = str(data["password"]).strip()
            if not u or not p:
                return
            if u in bot_state.account_workers and not bot_state.account_workers[u].done():
                print_warning(f"[ADD] Guest worker already running for UID {u}")
                return
            task = asyncio.create_task(account_loop_guest(u, p))
            bot_state.account_workers[u] = task
            print_success(f"[ADD] Guest account started: {u}")

    # ৩) Bulk add
    async def on_account_bulk_added_handler(accounts: List[Dict]):
        added = 0
        skipped = 0
        for data in accounts:
            try:
                if data.get("token"):
                    t = str(data["token"]).strip()
                    if not t:
                        skipped += 1
                        continue
                    key = t[:10]
                    if key in bot_state.account_workers and not bot_state.account_workers[key].done():
                        skipped += 1
                        continue
                    task = asyncio.create_task(account_loop_token(t))
                    bot_state.account_workers[key] = task
                    added += 1
                elif data.get("uid") and data.get("password"):
                    u = str(data["uid"]).strip()
                    p = str(data["password"]).strip()
                    if not u or not p:
                        skipped += 1
                        continue
                    if u in bot_state.account_workers and not bot_state.account_workers[u].done():
                        skipped += 1
                        continue
                    task = asyncio.create_task(account_loop_guest(u, p))
                    bot_state.account_workers[u] = task
                    added += 1
                else:
                    skipped += 1
            except Exception as e:
                print_error(f"[BULK] add failed: {e}")
                skipped += 1
        print_success(f"[BULK] {added} started, {skipped} skipped")
        return added

    # ৪) প্রোফাইল রিফ্রেশ
    async def on_refresh_account_handler(uid):
        await refresh_account_profile(uid)

    # ৫) ম্যাপ কোড পরিবর্তন
    async def on_map_code_changed_handler(new_code: str) -> str:
        return set_map_code(new_code)

    # ৫.৫) Restart single account
    async def on_account_restart_handler(uid):
        uid = str(uid).strip()
        if not uid:
            return {"ok": False, "error": "uid required"}

        # Credentials খুঁজুন — bot_state.account_credentials-এ
        account_data = bot_state.account_credentials.get(uid)
        auth_uid = None
        auth_token = None
        auth_password = None

        if account_data:
            auth_uid = account_data.get("auth_uid")
            auth_token = account_data.get("auth_token")
            auth_password = account_data.get("auth_password")

        # না পেলে accounts.json-এ
        if not auth_uid and not auth_token:
            for acc in load_accounts():
                if str(acc.get("uid")) == uid:
                    auth_uid = acc["uid"]
                    auth_password = acc.get("password")
                    break
                if acc.get("token") and acc["token"][:10] == uid:
                    auth_token = acc["token"]
                    break

        # পুরনো worker cancel
        keys_to_kill = {uid}
        if auth_uid:
            keys_to_kill.add(str(auth_uid))
        if auth_token:
            keys_to_kill.add(f"tok_{auth_token[:20]}")
            keys_to_kill.add(auth_token[:10])

        for k in keys_to_kill:
            w = bot_state.account_workers.get(k)
            if w and not w.done():
                try:
                    w.cancel()
                except Exception:
                    pass
            bot_state.account_workers.pop(k, None)

        await asyncio.sleep(0.4)

        # নতুন worker spawn
        if auth_token:
            task = asyncio.create_task(account_loop_token(auth_token))
            bot_state.account_workers[auth_token[:10]] = task
            print_success(f"[RESTART] Token account {auth_token[:10]}... restarted")
        elif auth_uid and auth_password:
            task = asyncio.create_task(account_loop_guest(str(auth_uid), str(auth_password)))
            bot_state.account_workers[str(auth_uid)] = task
            print_success(f"[RESTART] Guest account {auth_uid} restarted")
        else:
            return {"ok": False, "error": "credentials not found"}

        return {"ok": True}

    # ৫.৬) Restart all accounts
    async def on_accounts_restart_all_handler():
        accounts = load_accounts()
        restarted = 0
        for acc in accounts:
            try:
                if acc.get("token"):
                    tok = str(acc["token"]).strip()
                    key = tok[:10]
                    w = bot_state.account_workers.get(key)
                    if w and not w.done():
                        w.cancel()
                    bot_state.account_workers.pop(key, None)
                    await asyncio.sleep(0.05)
                    task = asyncio.create_task(account_loop_token(tok))
                    bot_state.account_workers[key] = task
                    restarted += 1
                elif acc.get("uid") and acc.get("password"):
                    u = str(acc["uid"]).strip()
                    p = str(acc["password"]).strip()
                    w = bot_state.account_workers.get(u)
                    if w and not w.done():
                        w.cancel()
                    bot_state.account_workers.pop(u, None)
                    await asyncio.sleep(0.05)
                    task = asyncio.create_task(account_loop_guest(u, p))
                    bot_state.account_workers[u] = task
                    restarted += 1
            except Exception as e:
                print_error(f"[RESTART-ALL] {e}")

        print_success(f"[RESTART-ALL] {restarted} accounts restarted")
        return {"ok": True, "restarted": restarted}

    # ৬) পাসওয়ার্ড পরিবর্তন
    async def on_password_change_handler(username: str, old_password: str, new_password: str):
        return change_user_password(username, old_password, new_password)

    # ৭) সব কলব্যাক রেজিস্টার
    bot_state.refresh_callbacks["on_account_added"] = on_account_added_handler
    bot_state.refresh_callbacks["on_account_bulk_added"] = on_account_bulk_added_handler
    bot_state.refresh_callbacks["on_refresh_account"] = on_refresh_account_handler
    bot_state.refresh_callbacks["on_map_code_changed"] = on_map_code_changed_handler
    bot_state.refresh_callbacks["on_password_change"] = on_password_change_handler
    bot_state.refresh_callbacks["on_account_restart"] = on_account_restart_handler
    bot_state.refresh_callbacks["on_accounts_restart_all"] = on_accounts_restart_all_handler
    
    # ৮) accounts.json থেকে অটো স্টার্ট
    accounts = load_accounts()

    if not accounts:
        print_warning(f"No accounts found in {ACCOUNTS_FILE}! Add accounts from Web Dashboard.")
        print_warning(f"Open: http://localhost:{WEB_PORT}")

    for acc in accounts:
        try:
            if "token" in acc and acc["token"]:
                t = str(acc["token"]).strip()
                if t and t[:10] not in bot_state.account_workers:
                    task = asyncio.create_task(account_loop_token(t))
                    bot_state.account_workers[t[:10]] = task
            elif "uid" in acc and "password" in acc and acc["uid"]:
                u = str(acc["uid"]).strip()
                p = str(acc["password"]).strip()
                if u and p and u not in bot_state.account_workers:
                    task = asyncio.create_task(account_loop_guest(u, p))
                    bot_state.account_workers[u] = task
        except Exception as e:
            print_error(f"[STARTUP] failed to start account: {e}")

    # ৯) মেইন লুপ
    try:
        while True:
            await asyncio.sleep(1)
            try:
                dead = [k for k, t in bot_state.account_workers.items() if t.done()]
                for k in dead:
                    bot_state.account_workers.pop(k, None)
            except Exception:
                pass
    except (KeyboardInterrupt, asyncio.CancelledError):
        print_warning("\n[STOP] Shutting down all accounts...")
        for t in list(bot_state.account_workers.values()):
            try:
                t.cancel()
            except Exception:
                pass
        if bot_state.account_workers:
            await asyncio.gather(*bot_state.account_workers.values(), return_exceptions=True)
        print_success("All sessions cleanly closed.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print_warning("\nProgram stopped by user.")
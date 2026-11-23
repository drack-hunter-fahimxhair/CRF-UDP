# -*- coding: utf-8 -*-
"""
MAHIR Craftland UDP - Web Dashboard Server
aiohttp-based async server with auth, map-code editor, bulk-add, password change.
"""

import asyncio
import json
import os
import secrets
import time
from typing import Dict, List, Any, Optional, Callable
from aiohttp import web


# ==================== BOT STATE ====================

class BotState:
    def __init__(self):
        self.accounts: Dict[str, Dict[str, Any]] = {}
        self.logs: List[Dict[str, Any]] = []
        self.max_logs = 500
        self.total_matches = 0
        self.total_gained_exp = 0
        self.start_time = time.time()
        self.account_workers: Dict[str, asyncio.Task] = {}
        self.refresh_callbacks: Dict[str, Any] = {}
        self.account_credentials: Dict[str, Dict[str, Any]] = {}
        self.sessions: Dict[str, Dict[str, Any]] = {}

    # ---------- logging ----------
    def log(self, message: str, level: str = "info", uid: Optional[str] = None):
        entry = {
            "time": time.strftime("%H:%M:%S"),
            "ts": time.time(),
            "level": level,
            "message": message,
            "msg": message,   # alias for new frontend
            "uid": uid,
        }
        self.logs.append(entry)
        if len(self.logs) > self.max_logs:
            self.logs = self.logs[-self.max_logs:]

    # ---------- accounts ----------
    def register_account(self, uid, nickname, region, level=1, exp=0, likes=0):
        uid_str = str(uid)
        if uid_str not in self.accounts:
            self.accounts[uid_str] = {
                "uid": uid_str,
                "nickname": nickname or f"Player_{uid_str[:6]}",
                "region": region or "BD",
                "level": level or 1,
                "initial_exp": exp,
                "current_exp": exp,
                "gained_exp": 0,
                "likes": likes or 0,
                "status": "ONLINE",
                "matches_played": 0,
                "active_matches": 0,
                "last_match_time": None,
                "last_updated": time.strftime("%H:%M:%S"),
            }
        else:
            acc = self.accounts[uid_str]
            if nickname:
                acc["nickname"] = nickname
            if region:
                acc["region"] = region
            if level:
                acc["level"] = level
            acc["current_exp"] = exp
            acc["gained_exp"] = max(0, exp - acc["initial_exp"])
            acc["likes"] = likes
            acc["status"] = "ONLINE"
            acc["last_updated"] = time.strftime("%H:%M:%S")
        self.recalc_totals()

    def update_exp(self, uid, current_exp, level=None):
        uid_str = str(uid)
        if uid_str in self.accounts:
            acc = self.accounts[uid_str]
            old = acc["current_exp"]
            acc["current_exp"] = current_exp
            if level is not None and level > 0:
                acc["level"] = level
            acc["gained_exp"] = max(0, current_exp - acc["initial_exp"])
            acc["last_updated"] = time.strftime("%H:%M:%S")
            diff = current_exp - old
            if diff > 0:
                self.log(
                    f"Account {acc['nickname']} ({uid_str}) gained +{diff} EXP! Total: +{acc['gained_exp']}",
                    "success", uid_str
                )
            self.recalc_totals()

    def update_status(self, uid, status, active_matches=None):
        uid_str = str(uid)
        if uid_str in self.accounts:
            self.accounts[uid_str]["status"] = status
            if active_matches is not None:
                self.accounts[uid_str]["active_matches"] = active_matches
            self.accounts[uid_str]["last_updated"] = time.strftime("%H:%M:%S")

    def increment_match(self, uid):
        uid_str = str(uid)
        self.total_matches += 1
        if uid_str in self.accounts:
            self.accounts[uid_str]["matches_played"] += 1
            self.accounts[uid_str]["last_match_time"] = time.strftime("%H:%M:%S")
            self.accounts[uid_str]["last_updated"] = time.strftime("%H:%M:%S")
            self.log(
                f"Account {self.accounts[uid_str]['nickname']} finished Match #{self.accounts[uid_str]['matches_played']}",
                "info", uid_str
            )

    def recalc_totals(self):
        self.total_gained_exp = sum(a.get("gained_exp", 0) for a in self.accounts.values())

    # ---------- sessions ----------
    def create_session(self, user):
        tok = secrets.token_urlsafe(32)
        self.sessions[tok] = {"user": user, "expires": time.time() + 7 * 86400}
        return tok

    def get_session(self, tok):
        s = self.sessions.get(tok)
        if not s:
            return None
        if s["expires"] < time.time():
            self.sessions.pop(tok, None)
            return None
        return s

    def drop_session(self, tok):
        self.sessions.pop(tok, None)


bot_state = BotState()


# ==================== WIRING (injected from app.py) ====================
# app.py শেষে এই global গুলো inject করে (সব helper ডেফাইন হওয়ার পরে):
#   _dash.LOAD_USERS = _load_users
#   _dash.SET_MAP_CODE = set_map_code
#   _dash.CHANGE_PASSWORD = change_user_password
#   _dash.CRAFTLAND_MAP_CODE_GETTER = lambda: CRAFTLAND_MAP_CODE
#   _dash.GET_TOTAL_MATCHES = _get_total_match_count
#   _dash.GET_MATCH_COUNT = _get_match_count

LOAD_USERS: Optional[Callable] = None
SET_MAP_CODE: Optional[Callable] = None
CHANGE_PASSWORD: Optional[Callable] = None
CRAFTLAND_MAP_CODE_GETTER: Optional[Callable] = None
GET_TOTAL_MATCHES: Optional[Callable] = None
GET_MATCH_COUNT: Optional[Callable] = None


# ==================== AUTH HELPERS ====================

def _get_token(request: web.Request) -> str:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return request.cookies.get("mahir_token", "")


def require_auth(handler):
    async def wrapper(request: web.Request):
        tok = _get_token(request)
        sess = bot_state.get_session(tok)
        if not sess:
            return web.json_response({"ok": False, "error": "unauthorized"}, status=401)
        request["session"] = sess
        request["token"] = tok
        return await handler(request)
    return wrapper


# ==================== STATIC ====================

TEMPLATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")


async def handle_index(request: web.Request) -> web.Response:
    if os.path.exists(TEMPLATE_PATH):
        with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        return web.Response(text=content, content_type="text/html", charset="utf-8")
    return web.Response(text="<h1>index.html not found!</h1>", content_type="text/html")


# ==================== AUTH ROUTES ====================

async def handle_login(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid json"}, status=400)

    username = (data.get("username") or "").strip().lower()
    password = data.get("password") or ""

    if not callable(LOAD_USERS):
        return web.json_response({"ok": False, "error": "auth not wired"}, status=500)

    try:
        users = LOAD_USERS() or []
    except Exception as e:
        return web.json_response({"ok": False, "error": f"load users failed: {e}"}, status=500)

    user = None
    for u in users:
        if (u.get("username") == username or u.get("email") == username) and u.get("password") == password:
            user = u
            break

    if not user:
        return web.json_response({"ok": False, "error": "Invalid credentials"}, status=401)

    tok = bot_state.create_session(user)
    resp = web.json_response({
        "ok": True,
        "token": tok,
        "user": {
            "username": user.get("username"),
            "name": user.get("name", user.get("username")),
        }
    })
    resp.set_cookie("mahir_token", tok, max_age=7 * 86400, httponly=True, samesite="Lax")
    bot_state.log(f"[AUTH] {username} logged in", "success")
    return resp


@require_auth
async def handle_logout(request: web.Request) -> web.Response:
    bot_state.drop_session(request["token"])
    resp = web.json_response({"ok": True})
    resp.del_cookie("mahir_token")
    return resp


@require_auth
async def handle_me(request: web.Request) -> web.Response:
    user = request["session"]["user"]
    return web.json_response({
        "ok": True,
        "user": {"username": user.get("username"), "name": user.get("name")}
    })


@require_auth
async def handle_change_password(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid json"}, status=400)

    if not callable(CHANGE_PASSWORD):
        return web.json_response({"ok": False, "error": "password helper not wired"}, status=500)

    user = request["session"]["user"]
    try:
        ok, msg = CHANGE_PASSWORD(
            user.get("username"),
            data.get("old_password", ""),
            data.get("new_password", ""),
        )
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)}, status=500)

    if ok:
        bot_state.log(f"[AUTH] Password changed for {user.get('username')}", "success")
    return web.json_response({"ok": ok, "error": None if ok else msg, "message": msg})


# ==================== MAP CODE ====================

@require_auth
async def handle_get_map_code(request: web.Request) -> web.Response:
    if callable(CRAFTLAND_MAP_CODE_GETTER):
        try:
            code = CRAFTLAND_MAP_CODE_GETTER()
        except Exception:
            code = ""
    else:
        code = ""
    return web.json_response({"ok": True, "code": code})


@require_auth
async def handle_set_map_code(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid json"}, status=400)

    if not callable(SET_MAP_CODE):
        return web.json_response({"ok": False, "error": "map helper not wired"}, status=500)

    try:
        new_code = SET_MAP_CODE(data.get("code", ""))
        return web.json_response({"ok": True, "code": new_code})
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)}, status=400)


# ==================== ACCOUNTS ====================

@require_auth
async def handle_accounts_list(request: web.Request) -> web.Response:
    accounts_data = list(bot_state.accounts.values())
    accounts_data.sort(key=lambda x: x.get("gained_exp", 0), reverse=True)

    workers_alive = 0
    try:
        workers_alive = sum(1 for t in bot_state.account_workers.values() if not t.done())
    except Exception:
        pass

    total_active = 0
    if callable(GET_TOTAL_MATCHES):
        try:
            total_active = await GET_TOTAL_MATCHES()
        except Exception:
            total_active = 0
    else:
        total_active = sum(a.get("active_matches", 0) for a in accounts_data)

    return web.json_response({
        "ok": True,
        "accounts": accounts_data,
        "workers": workers_alive,
        "active_matches": total_active,
        "total_matches": bot_state.total_matches,
    })


@require_auth
async def handle_get_stats(request: web.Request) -> web.Response:
    """Backward-compatible /api/stats endpoint."""
    accounts_data = list(bot_state.accounts.values())
    accounts_data.sort(key=lambda x: x.get("gained_exp", 0), reverse=True)

    workers_alive = 0
    try:
        workers_alive = sum(1 for t in bot_state.account_workers.values() if not t.done())
    except Exception:
        pass

    total_active = 0
    if callable(GET_TOTAL_MATCHES):
        try:
            total_active = await GET_TOTAL_MATCHES()
        except Exception:
            total_active = 0
    else:
        total_active = sum(a.get("active_matches", 0) for a in accounts_data)

    return web.json_response({
        "total_accounts": len(bot_state.accounts),
        "total_matches": bot_state.total_matches,
        "total_gained_exp": bot_state.total_gained_exp,
        "accounts": accounts_data,
        "logs": bot_state.logs[-60:],
        "uptime": int(time.time() - bot_state.start_time),
        "workers": workers_alive,
        "active_matches": total_active,
    })


@require_auth
async def handle_add_account(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid json"}, status=400)

    accounts_file = "accounts.json"
    existing: List[Dict[str, Any]] = []
    if os.path.exists(accounts_file):
        try:
            with open(accounts_file, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            existing = []

    if "uid" in data and "password" in data:
        uid = str(data["uid"]).strip()
        pwd = str(data["password"]).strip()
        if not uid or not pwd:
            return web.json_response({"ok": False, "error": "UID and Password required"})
        existing = [a for a in existing if str(a.get("uid")) != uid]
        existing.append({"uid": uid, "password": pwd})
    elif "token" in data and data["token"]:
        tok = str(data["token"]).strip()
        if not tok:
            return web.json_response({"ok": False, "error": "Token required"})
        existing = [a for a in existing if a.get("token") != tok]
        existing.append({"token": tok})
    else:
        return web.json_response({"ok": False, "error": "Invalid payload"})

    try:
        with open(accounts_file, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2)
    except Exception as e:
        return web.json_response({"ok": False, "error": f"save failed: {e}"}, status=500)

    cb = bot_state.refresh_callbacks.get("on_account_added")
    if callable(cb):
        try:
            await cb(data)
        except Exception as e:
            bot_state.log(f"[ADD] callback error: {e}", "error")

    bot_state.log(f"New account added: {data.get('uid') or 'Token'}", "success")
    return web.json_response({"ok": True})


@require_auth
async def handle_delete_account(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid json"}, status=400)

    uid = str(data.get("uid", "")).strip()
    if not uid:
        return web.json_response({"ok": False, "error": "uid required"}, status=400)

    accounts_file = "accounts.json"
    if os.path.exists(accounts_file):
        try:
            with open(accounts_file, "r", encoding="utf-8") as f:
                existing = json.load(f)
            existing = [a for a in existing if str(a.get("uid")) != uid and str(a.get("token")) != uid]
            with open(accounts_file, "w", encoding="utf-8") as f:
                json.dump(existing, f, indent=2)
        except Exception:
            pass

    bot_state.accounts.pop(uid, None)

    if uid in bot_state.account_workers:
        try:
            bot_state.account_workers[uid].cancel()
        except Exception:
            pass
        bot_state.account_workers.pop(uid, None)

    bot_state.log(f"Account {uid} removed", "warning", uid)
    return web.json_response({"ok": True})


@require_auth
async def handle_refresh_account(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid json"}, status=400)

    uid = str(data.get("uid", "")).strip()
    if not uid:
        return web.json_response({"ok": False, "error": "uid required"}, status=400)

    cb = bot_state.refresh_callbacks.get("on_refresh_account")
    if callable(cb):
        asyncio.create_task(cb(uid))
    return web.json_response({"ok": True})


@require_auth
async def handle_bulk_add(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid json"}, status=400)

    accounts = data.get("accounts") or []
    if not isinstance(accounts, list):
        return web.json_response({"ok": False, "error": "accounts must be a list"}, status=400)

    accounts_file = "accounts.json"
    existing: List[Dict[str, Any]] = []
    if os.path.exists(accounts_file):
        try:
            with open(accounts_file, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            existing = []

    def _key(acc):
        if "uid" in acc:
            return ("uid", str(acc["uid"]))
        if "token" in acc:
            return ("token", str(acc["token"]))
        return (None, None)

    index = {_key(a): a for a in existing}
    added = 0
    for acc in accounts:
        if not isinstance(acc, dict):
            continue
        if "uid" in acc and "password" in acc:
            k = ("uid", str(acc["uid"]).strip())
            if not k[1]:
                continue
            index[k] = {"uid": k[1], "password": str(acc["password"]).strip()}
            added += 1
        elif "token" in acc:
            k = ("token", str(acc["token"]).strip())
            if not k[1]:
                continue
            index[k] = {"token": k[1]}
            added += 1

    merged = list(index.values())
    try:
        with open(accounts_file, "w", encoding="utf-8") as f:
            json.dump(merged, f, indent=2)
    except Exception as e:
        return web.json_response({"ok": False, "error": f"save failed: {e}"}, status=500)

    cb = bot_state.refresh_callbacks.get("on_account_bulk_added")
    if callable(cb):
        try:
            await cb(accounts)
        except Exception as e:
            bot_state.log(f"[BULK] callback error: {e}", "error")

    bot_state.log(f"[BULK] {added} accounts added via dashboard", "success")
    return web.json_response({"ok": True, "added": added})

# ==================== RESTART ====================

@require_auth
async def handle_restart_account(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid json"}, status=400)

    uid = str(data.get("uid", "")).strip()
    if not uid:
        return web.json_response({"ok": False, "error": "uid required"}, status=400)

    cb = bot_state.refresh_callbacks.get("on_account_restart")
    if not callable(cb):
        return web.json_response({"ok": False, "error": "restart handler not wired"}, status=500)

    try:
        result = await cb(uid)
        return web.json_response(result or {"ok": True})
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)}, status=500)


@require_auth
async def handle_restart_all(request: web.Request) -> web.Response:
    cb = bot_state.refresh_callbacks.get("on_accounts_restart_all")
    if not callable(cb):
        return web.json_response({"ok": False, "error": "restart-all handler not wired"}, status=500)

    try:
        result = await cb()
        return web.json_response(result or {"ok": True})
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)}, status=500)

# ==================== LOGS ====================

@require_auth
async def handle_logs(request: web.Request) -> web.Response:
    out = []
    for entry in bot_state.logs[-200:]:
        out.append({
            "ts": entry.get("ts", time.time()),
            "msg": entry.get("msg") or f"[{entry.get('time','')}] {entry.get('message','')}",
            "level": entry.get("level", "info"),
        })
    return web.json_response({"ok": True, "logs": out})


# ==================== APP FACTORY ====================

async def start_web_dashboard(host: str = "0.0.0.0", port: int = 5000):
    app = web.Application(client_max_size=2 * 1024 * 1024)

    # Static
    app.router.add_get("/", handle_index)
    app.router.add_get("/index.html", handle_index)

    # Auth
    app.router.add_post("/api/login", handle_login)
    app.router.add_post("/api/logout", handle_logout)
    app.router.add_get("/api/me", handle_me)
    app.router.add_post("/api/change-password", handle_change_password)

    # Settings
    app.router.add_get("/api/map-code", handle_get_map_code)
    app.router.add_post("/api/map-code", handle_set_map_code)

    # Accounts
    app.router.add_get("/api/accounts", handle_accounts_list)
    app.router.add_get("/api/stats", handle_get_stats)  # backward compat
    app.router.add_post("/api/account/add", handle_add_account)
    app.router.add_post("/api/account/delete", handle_delete_account)
    app.router.add_post("/api/account/refresh", handle_refresh_account)
    app.router.add_post("/api/accounts/bulk", handle_bulk_add)
    # Accounts (existing এর সাথে যোগ করুন)
    app.router.add_post("/api/account/restart", handle_restart_account)
    app.router.add_post("/api/accounts/restart-all", handle_restart_all)
    # Logs
    app.router.add_get("/api/logs", handle_logs)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    print(f"\033[92m[+] Web Dashboard running on http://localhost:{port}\033[0m")
    return runner
import os
import json
import time
import hmac
import hashlib
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, Request, Response, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# Configuration
CONFIG = {
    "DASH_USER": os.getenv("DASH_USER", "partner_makefood"),
    "DASH_PASS": os.getenv("DASH_PASS", "MakeFood@2026!"),
    "SECRET_KEY": os.getenv("SECRET_KEY", "makefood_super_secret_partner_portal_key_2026"),
    "CLIENT_ID": os.getenv("GOOGLE_CLIENT_ID", ""),
    "CLIENT_SECRET": os.getenv("GOOGLE_CLIENT_SECRET", ""),
    "REFRESH_TOKEN": os.getenv("GOOGLE_REFRESH_TOKEN", ""),
    "ADSENSE_ACCOUNT": os.getenv("ADSENSE_ACCOUNT", "accounts/pub-9077963246978786"),
    "TARGET_DOMAIN": os.getenv("TARGET_DOMAIN", "make-food.com"),
    "GA4_PROPERTY_ID": os.getenv("GA4_PROPERTY_ID", "properties/507998425")
}

# Optional local tokens file override (for local debugging only, not in git)
try:
    tokens_file = "google_tokens.json"
    if os.path.exists(tokens_file):
        with open(tokens_file, "r", encoding="utf-8") as f:
            t_data = json.load(f)
            if t_data.get("refresh_token") and not CONFIG["REFRESH_TOKEN"]:
                CONFIG["REFRESH_TOKEN"] = t_data["refresh_token"]
except Exception:
    pass

app = FastAPI(title="Make-Food.com Partner Portal")

# OAuth Token Cache
token_cache = {
    "access_token": None,
    "expires_at": 0
}

def get_google_access_token() -> str:
    now = time.time()
    if token_cache["access_token"] and token_cache["expires_at"] > now + 60:
        return token_cache["access_token"]
    
    # Refresh token
    payload = urllib.parse.urlencode({
        "client_id": CONFIG["CLIENT_ID"],
        "client_secret": CONFIG["CLIENT_SECRET"],
        "refresh_token": CONFIG["REFRESH_TOKEN"],
        "grant_type": "refresh_token"
    }).encode("utf-8")
    
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=payload, headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        token_cache["access_token"] = data["access_token"]
        token_cache["expires_at"] = now + data.get("expires_in", 3600)
        return data["access_token"]

def sign_session(username: str) -> str:
    sig = hmac.new(CONFIG["SECRET_KEY"].encode("utf-8"), username.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{username}:{sig}"

def verify_session(cookie: Optional[str]) -> bool:
    if not cookie or ":" not in cookie:
        return False
    user, sig = cookie.split(":", 1)
    if user != CONFIG["DASH_USER"]:
        return False
    expected = hmac.new(CONFIG["SECRET_KEY"].encode("utf-8"), user.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig, expected)

def is_authenticated(request: Request) -> bool:
    cookie = request.cookies.get("session_token")
    return verify_session(cookie)

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if is_authenticated(request):
        return RedirectResponse(url="/", status_code=302)
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Login - Make-Food.com Partner Portal</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
        <style>body { font-family: 'Plus Jakarta Sans', sans-serif; }</style>
    </head>
    <body class="bg-slate-950 text-slate-100 min-h-screen flex items-center justify-center p-4">
        <div class="w-full max-w-md">
            <div class="bg-slate-900 border border-slate-800 rounded-2xl p-8 shadow-2xl relative overflow-hidden">
                <div class="absolute -top-24 -right-24 w-48 h-48 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none"></div>
                <div class="absolute -bottom-24 -left-24 w-48 h-48 bg-amber-500/10 rounded-full blur-3xl pointer-events-none"></div>

                <div class="text-center mb-8 relative">
                    <div class="inline-flex items-center justify-center w-14 h-14 rounded-xl bg-gradient-to-tr from-amber-500 to-emerald-500 p-0.5 mb-4 shadow-lg shadow-emerald-500/20">
                        <div class="w-full h-full bg-slate-900 rounded-[10px] flex items-center justify-center">
                            <span class="text-2xl">🍲</span>
                        </div>
                    </div>
                    <h1 class="text-2xl font-bold tracking-tight text-white">Make-Food.com</h1>
                    <p class="text-sm text-slate-400 mt-1">Partner Revenue & Analytics Portal</p>
                </div>

                <form method="POST" action="/login" class="space-y-5">
                    <div>
                        <label class="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">Username</label>
                        <input type="text" name="username" required autocomplete="username"
                            placeholder="Enter partner username"
                            class="w-full px-4 py-3 bg-slate-800/80 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition">
                    </div>
                    <div>
                        <label class="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">Password</label>
                        <input type="password" name="password" required autocomplete="current-password"
                            placeholder="••••••••••••"
                            class="w-full px-4 py-3 bg-slate-800/80 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition">
                    </div>
                    <button type="submit"
                        class="w-full py-3.5 px-4 bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-slate-950 font-bold rounded-xl shadow-lg shadow-emerald-500/25 transition duration-200">
                        Access Dashboard
                    </button>
                </form>

                <div class="mt-6 pt-6 border-t border-slate-800/60 text-center">
                    <p class="text-xs text-slate-500 flex items-center justify-center gap-1.5">
                        <span class="w-2 h-2 rounded-full bg-emerald-500 inline-block animate-pulse"></span>
                        Authorized Partner Access • 256-bit Encrypted
                    </p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    if username == CONFIG["DASH_USER"] and password == CONFIG["DASH_PASS"]:
        response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        response.set_cookie(
            key="session_token",
            value=sign_session(username),
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=86400 * 30  # 30 days
        )
        return response
    return HTMLResponse("""
        <script>
            alert("Invalid username or password. Please try again.");
            window.location.href = "/login";
        </script>
    """, status_code=401)

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie("session_token")
    return response

@app.get("/api/stats")
async def get_stats(request: Request, range: str = "last30"):
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    token = get_google_access_token()
    
    # Map range
    range_map = {
        "today": "TODAY",
        "yesterday": "YESTERDAY",
        "last7": "LAST_7_DAYS",
        "last30": "LAST_30_DAYS",
        "month": "THIS_MONTH"
    }
    date_range = range_map.get(range, "LAST_30_DAYS")
    
    # 1. Fetch Daily Timeseries
    daily_params = [
        ("dateRange", date_range),
        ("metrics", "ESTIMATED_EARNINGS"),
        ("metrics", "PAGE_VIEWS"),
        ("metrics", "PAGE_VIEWS_RPM"),
        ("metrics", "IMPRESSIONS"),
        ("metrics", "CLICKS"),
        ("dimensions", "DATE"),
        ("filters", f"DOMAIN_NAME=={CONFIG['TARGET_DOMAIN']}")
    ]
    url_daily = f"https://adsense.googleapis.com/v2/{CONFIG['ADSENSE_ACCOUNT']}/reports:generate?{urllib.parse.urlencode(daily_params)}"
    req_daily = urllib.request.Request(url_daily, headers={"Authorization": f"Bearer {token}"})
    
    daily_data = []
    totals = {"earnings": 0.0, "views": 0, "rpm": 0.0, "impressions": 0, "clicks": 0, "ctr": 0.0}
    
    try:
        with urllib.request.urlopen(req_daily) as resp:
            res_daily = json.loads(resp.read().decode("utf-8"))
            for row in res_daily.get("rows", []):
                cells = [c.get("value", "0") for c in row.get("cells", [])]
                if len(cells) >= 6:
                    d_str, earn, views, rpm, imps, clicks = cells[0], float(cells[1]), int(cells[2]), float(cells[3]), int(cells[4]), int(cells[5])
                    daily_data.append({
                        "date": d_str,
                        "earnings": earn,
                        "pageviews": views,
                        "rpm": rpm,
                        "impressions": imps,
                        "clicks": clicks
                    })
            if res_daily.get("totals", {}).get("cells"):
                t_cells = res_daily["totals"]["cells"]
                if len(t_cells) >= 6:
                    totals["earnings"] = float(t_cells[1].get("value", "0"))
                    totals["views"] = int(t_cells[2].get("value", "0"))
                    totals["rpm"] = float(t_cells[3].get("value", "0"))
                    totals["impressions"] = int(t_cells[4].get("value", "0"))
                    totals["clicks"] = int(t_cells[5].get("value", "0"))
                    if totals["impressions"] > 0:
                        totals["ctr"] = round((totals["clicks"] / totals["impressions"]) * 100, 2)
    except Exception as e:
        print("Error fetching daily report:", e)

    # 2. Fetch Countries
    country_params = [
        ("dateRange", date_range),
        ("metrics", "ESTIMATED_EARNINGS"),
        ("metrics", "PAGE_VIEWS"),
        ("metrics", "IMPRESSIONS"),
        ("dimensions", "COUNTRY_NAME"),
        ("filters", f"DOMAIN_NAME=={CONFIG['TARGET_DOMAIN']}")
    ]
    url_country = f"https://adsense.googleapis.com/v2/{CONFIG['ADSENSE_ACCOUNT']}/reports:generate?{urllib.parse.urlencode(country_params)}"
    req_country = urllib.request.Request(url_country, headers={"Authorization": f"Bearer {token}"})
    countries = []
    try:
        with urllib.request.urlopen(req_country) as resp:
            res_c = json.loads(resp.read().decode("utf-8"))
            for row in res_c.get("rows", []):
                cells = [c.get("value", "0") for c in row.get("cells", [])]
                if len(cells) >= 4:
                    c_name, earn, views, imps = cells[0], float(cells[1]), int(cells[2]), int(cells[3])
                    countries.append({"country": c_name, "earnings": earn, "pageviews": views, "impressions": imps})
            countries = sorted(countries, key=lambda x: x["earnings"], reverse=True)[:10]
    except Exception as e:
        print("Error fetching countries:", e)

    # 3. Fetch Platforms / Devices
    plat_params = [
        ("dateRange", date_range),
        ("metrics", "ESTIMATED_EARNINGS"),
        ("metrics", "PAGE_VIEWS"),
        ("dimensions", "PLATFORM_TYPE_NAME"),
        ("filters", f"DOMAIN_NAME=={CONFIG['TARGET_DOMAIN']}")
    ]
    url_plat = f"https://adsense.googleapis.com/v2/{CONFIG['ADSENSE_ACCOUNT']}/reports:generate?{urllib.parse.urlencode(plat_params)}"
    req_plat = urllib.request.Request(url_plat, headers={"Authorization": f"Bearer {token}"})
    platforms = []
    try:
        with urllib.request.urlopen(req_plat) as resp:
            res_p = json.loads(resp.read().decode("utf-8"))
            for row in res_p.get("rows", []):
                cells = [c.get("value", "0") for c in row.get("cells", [])]
                if len(cells) >= 3:
                    p_name, earn, views = cells[0], float(cells[1]), int(cells[2])
                    platforms.append({"platform": p_name, "earnings": earn, "pageviews": views})
    except Exception as e:
        print("Error fetching platforms:", e)

    return {
        "domain": CONFIG["TARGET_DOMAIN"],
        "date_range": date_range,
        "totals": totals,
        "daily": daily_data,
        "countries": countries,
        "platforms": platforms,
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

@app.get("/", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=302)
    
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Make-Food.com — Partner Revenue & Analytics</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
        <style>
            body { font-family: 'Plus Jakarta Sans', sans-serif; }
            .glass { background: rgba(15, 23, 42, 0.75); backdrop-filter: blur(16px); }
        </style>
    </head>
    <body class="bg-slate-950 text-slate-100 min-h-screen">
        <!-- Top Navigation -->
        <header class="border-b border-slate-800/80 glass sticky top-0 z-50">
            <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-amber-500 to-emerald-500 flex items-center justify-center shadow-lg shadow-emerald-500/20 text-xl">
                        🍲
                    </div>
                    <div>
                        <div class="flex items-center gap-2">
                            <h1 class="text-lg font-extrabold tracking-tight text-white">Make-Food.com</h1>
                            <span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1">
                                <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                                LIVE SYNC
                            </span>
                        </div>
                        <p class="text-xs text-slate-400">Partner Revenue & Traffic Portal</p>
                    </div>
                </div>

                <!-- Range Selector & User Profile -->
                <div class="flex items-center gap-3">
                    <div class="bg-slate-900 border border-slate-800 rounded-xl p-1 flex items-center gap-1 text-xs">
                        <button onclick="setRange('today')" id="btn-today" class="px-3 py-1.5 rounded-lg text-slate-400 hover:text-white transition">Today</button>
                        <button onclick="setRange('yesterday')" id="btn-yesterday" class="px-3 py-1.5 rounded-lg text-slate-400 hover:text-white transition">Yesterday</button>
                        <button onclick="setRange('last7')" id="btn-last7" class="px-3 py-1.5 rounded-lg text-slate-400 hover:text-white transition">7 Days</button>
                        <button onclick="setRange('last30')" id="btn-last30" class="px-3 py-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 font-semibold border border-emerald-500/20 transition">30 Days</button>
                        <button onclick="setRange('month')" id="btn-month" class="px-3 py-1.5 rounded-lg text-slate-400 hover:text-white transition">This Month</button>
                    </div>

                    <a href="/logout" title="Sign Out" class="px-3 py-1.5 text-xs font-semibold text-slate-400 hover:text-rose-400 border border-slate-800 rounded-xl hover:border-rose-500/30 transition flex items-center gap-1.5">
                        <span>Logout</span>
                    </a>
                </div>
            </div>
        </header>

        <!-- Main Content -->
        <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
            <!-- Metric KPI Cards -->
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
                <!-- Revenue -->
                <div class="bg-slate-900 border border-slate-800/80 rounded-2xl p-5 relative overflow-hidden">
                    <div class="absolute top-0 right-0 w-24 h-24 bg-emerald-500/10 rounded-full blur-2xl"></div>
                    <div class="flex items-center justify-between text-slate-400 text-xs font-medium uppercase tracking-wider mb-2">
                        <span>Total Earnings</span>
                        <span class="text-emerald-400 font-bold">USD</span>
                    </div>
                    <div id="stat-earnings" class="text-3xl font-extrabold text-white tracking-tight">$0.00</div>
                    <div class="text-[11px] text-slate-400 mt-2 flex items-center gap-1">
                        <span class="text-emerald-400 font-semibold">100% verified</span> from AdSense API
                    </div>
                </div>

                <!-- Pageviews -->
                <div class="bg-slate-900 border border-slate-800/80 rounded-2xl p-5 relative overflow-hidden">
                    <div class="absolute top-0 right-0 w-24 h-24 bg-sky-500/10 rounded-full blur-2xl"></div>
                    <div class="flex items-center justify-between text-slate-400 text-xs font-medium uppercase tracking-wider mb-2">
                        <span>Page Views</span>
                        <span class="text-sky-400 text-base">👁️</span>
                    </div>
                    <div id="stat-views" class="text-3xl font-extrabold text-white tracking-tight">0</div>
                    <div class="text-[11px] text-slate-400 mt-2">
                        Direct recipe views
                    </div>
                </div>

                <!-- RPM -->
                <div class="bg-slate-900 border border-slate-800/80 rounded-2xl p-5 relative overflow-hidden">
                    <div class="absolute top-0 right-0 w-24 h-24 bg-amber-500/10 rounded-full blur-2xl"></div>
                    <div class="flex items-center justify-between text-slate-400 text-xs font-medium uppercase tracking-wider mb-2">
                        <span>Page RPM</span>
                        <span class="text-amber-400 text-base">📈</span>
                    </div>
                    <div id="stat-rpm" class="text-3xl font-extrabold text-white tracking-tight">$0.00</div>
                    <div class="text-[11px] text-slate-400 mt-2">
                        Revenue per 1,000 views
                    </div>
                </div>

                <!-- Impressions -->
                <div class="bg-slate-900 border border-slate-800/80 rounded-2xl p-5 relative overflow-hidden">
                    <div class="absolute top-0 right-0 w-24 h-24 bg-purple-500/10 rounded-full blur-2xl"></div>
                    <div class="flex items-center justify-between text-slate-400 text-xs font-medium uppercase tracking-wider mb-2">
                        <span>Impressions</span>
                        <span class="text-purple-400 text-base">📊</span>
                    </div>
                    <div id="stat-impressions" class="text-3xl font-extrabold text-white tracking-tight">0</div>
                    <div class="text-[11px] text-slate-400 mt-2">
                        Ad impressions served
                    </div>
                </div>

                <!-- Clicks & CTR -->
                <div class="bg-slate-900 border border-slate-800/80 rounded-2xl p-5 relative overflow-hidden">
                    <div class="absolute top-0 right-0 w-24 h-24 bg-teal-500/10 rounded-full blur-2xl"></div>
                    <div class="flex items-center justify-between text-slate-400 text-xs font-medium uppercase tracking-wider mb-2">
                        <span>Clicks (CTR)</span>
                        <span class="text-teal-400 text-base">🖱️</span>
                    </div>
                    <div id="stat-clicks" class="text-3xl font-extrabold text-white tracking-tight">0 <span class="text-sm font-medium text-slate-400" id="stat-ctr">(0%)</span></div>
                    <div class="text-[11px] text-slate-400 mt-2">
                        User interactions
                    </div>
                </div>
            </div>

            <!-- Charts Section -->
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <!-- Earnings Chart -->
                <div class="bg-slate-900 border border-slate-800/80 rounded-2xl p-6">
                    <div class="flex items-center justify-between mb-4">
                        <h2 class="text-base font-bold text-white flex items-center gap-2">
                            <span>💵 Daily Revenue Trend</span>
                        </h2>
                        <span class="text-xs text-slate-400">USD ($)</span>
                    </div>
                    <div class="h-64">
                        <canvas id="earningsChart"></canvas>
                    </div>
                </div>

                <!-- Traffic Chart -->
                <div class="bg-slate-900 border border-slate-800/80 rounded-2xl p-6">
                    <div class="flex items-center justify-between mb-4">
                        <h2 class="text-base font-bold text-white flex items-center gap-2">
                            <span>📈 Pageviews & Impressions</span>
                        </h2>
                        <span class="text-xs text-slate-400">Volume</span>
                    </div>
                    <div class="h-64">
                        <canvas id="trafficChart"></canvas>
                    </div>
                </div>
            </div>

            <!-- Bottom Breakdown: Countries & Devices -->
            <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <!-- Top Countries Table -->
                <div class="lg:col-span-2 bg-slate-900 border border-slate-800/80 rounded-2xl p-6">
                    <div class="flex items-center justify-between mb-4">
                        <h2 class="text-base font-bold text-white">🌍 Top Countries by Performance</h2>
                        <span class="text-xs text-slate-400">Ranked by revenue</span>
                    </div>
                    <div class="overflow-x-auto">
                        <table class="w-full text-left text-sm">
                            <thead class="text-xs uppercase text-slate-400 border-b border-slate-800">
                                <tr>
                                    <th class="py-3 px-2">Country</th>
                                    <th class="py-3 px-2 text-right">Pageviews</th>
                                    <th class="py-3 px-2 text-right">Impressions</th>
                                    <th class="py-3 px-2 text-right">Earnings</th>
                                </tr>
                            </thead>
                            <tbody id="countryTableBody" class="divide-y divide-slate-800/60 text-slate-300">
                                <tr><td colspan="4" class="py-4 text-center text-slate-500">Loading data...</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>

                <!-- Devices / Platforms Breakdown -->
                <div class="bg-slate-900 border border-slate-800/80 rounded-2xl p-6 flex flex-col justify-between">
                    <div>
                        <div class="flex items-center justify-between mb-4">
                            <h2 class="text-base font-bold text-white">📱 Device Breakdown</h2>
                            <span class="text-xs text-slate-400">Platform share</span>
                        </div>
                        <div class="h-48 flex items-center justify-center">
                            <canvas id="platformChart"></canvas>
                        </div>
                    </div>
                    <div id="platformCards" class="grid grid-cols-3 gap-2 mt-4 pt-4 border-t border-slate-800 text-center">
                    </div>
                </div>
            </div>

            <!-- Daily Breakdown Table -->
            <div class="bg-slate-900 border border-slate-800/80 rounded-2xl p-6">
                <div class="flex items-center justify-between mb-4">
                    <h2 class="text-base font-bold text-white">📅 Detailed Daily Log</h2>
                    <button onclick="exportCSV()" class="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-semibold transition">
                        Export CSV
                    </button>
                </div>
                <div class="overflow-x-auto max-h-96">
                    <table class="w-full text-left text-sm">
                        <thead class="text-xs uppercase text-slate-400 border-b border-slate-800 sticky top-0 bg-slate-900">
                            <tr>
                                <th class="py-3 px-4">Date</th>
                                <th class="py-3 px-4 text-right">Earnings ($)</th>
                                <th class="py-3 px-4 text-right">Pageviews</th>
                                <th class="py-3 px-4 text-right">Page RPM ($)</th>
                                <th class="py-3 px-4 text-right">Impressions</th>
                                <th class="py-3 px-4 text-right">Clicks</th>
                            </tr>
                        </thead>
                        <tbody id="dailyTableBody" class="divide-y divide-slate-800/60 text-slate-300 font-mono text-xs">
                            <tr><td colspan="6" class="py-4 text-center text-slate-500">Loading data...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </main>

        <footer class="border-t border-slate-800/80 py-6 mt-12 text-center text-xs text-slate-500">
            Make-Food.com Partner Portal • Connected to Google AdSense Management API & GA4 • All Rights Reserved
        </footer>

        <script>
            let currentRange = 'last30';
            let earningsChart, trafficChart, platformChart;
            let rawDailyData = [];

            function setRange(range) {
                currentRange = range;
                ['today', 'yesterday', 'last7', 'last30', 'month'].forEach(r => {
                    const btn = document.getElementById('btn-' + r);
                    if (r === range) {
                        btn.className = "px-3 py-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 font-semibold border border-emerald-500/20 transition";
                    } else {
                        btn.className = "px-3 py-1.5 rounded-lg text-slate-400 hover:text-white transition";
                    }
                });
                loadDashboardData();
            }

            async function loadDashboardData() {
                try {
                    const res = await fetch(`/api/stats?range=${currentRange}`);
                    if (!res.ok) {
                        if (res.status === 401) window.location.href = '/login';
                        return;
                    }
                    const data = await res.json();
                    renderDashboard(data);
                } catch (e) {
                    console.error("Failed to load dashboard:", e);
                }
            }

            function renderDashboard(data) {
                // KPIs
                const t = data.totals;
                document.getElementById('stat-earnings').innerText = '$' + t.earnings.toFixed(2);
                document.getElementById('stat-views').innerText = t.views.toLocaleString();
                document.getElementById('stat-rpm').innerText = '$' + t.rpm.toFixed(2);
                document.getElementById('stat-impressions').innerText = t.impressions.toLocaleString();
                document.getElementById('stat-clicks').innerText = t.clicks.toLocaleString();
                document.getElementById('stat-ctr').innerText = `(${t.ctr}%)`;

                // Charts
                rawDailyData = data.daily || [];
                const labels = rawDailyData.map(d => d.date);
                const earnings = rawDailyData.map(d => d.earnings);
                const views = rawDailyData.map(d => d.pageviews);
                const impressions = rawDailyData.map(d => d.impressions);

                // 1. Earnings Chart
                if (earningsChart) earningsChart.destroy();
                const ctxE = document.getElementById('earningsChart').getContext('2d');
                earningsChart = new Chart(ctxE, {
                    type: 'line',
                    data: {
                        labels: labels,
                        datasets: [{
                            label: 'Earnings ($)',
                            data: earnings,
                            borderColor: '#10b981',
                            backgroundColor: 'rgba(16, 185, 129, 0.1)',
                            fill: true,
                            tension: 0.3,
                            borderWidth: 2,
                            pointRadius: labels.length > 15 ? 1 : 3
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { display: false } },
                        scales: {
                            x: { grid: { color: 'rgba(51, 65, 85, 0.3)' }, ticks: { color: '#94a3b8', font: { size: 10 } } },
                            y: { grid: { color: 'rgba(51, 65, 85, 0.3)' }, ticks: { color: '#94a3b8', callback: v => '$' + v } }
                        }
                    }
                });

                // 2. Traffic Chart
                if (trafficChart) trafficChart.destroy();
                const ctxT = document.getElementById('trafficChart').getContext('2d');
                trafficChart = new Chart(ctxT, {
                    type: 'bar',
                    data: {
                        labels: labels,
                        datasets: [
                            {
                                label: 'Pageviews',
                                data: views,
                                backgroundColor: '#38bdf8',
                                borderRadius: 4
                            },
                            {
                                label: 'Impressions',
                                data: impressions,
                                backgroundColor: '#a855f7',
                                borderRadius: 4
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { position: 'top', labels: { color: '#94a3b8', boxWidth: 12 } } },
                        scales: {
                            x: { grid: { display: false }, ticks: { color: '#94a3b8', font: { size: 10 } } },
                            y: { grid: { color: 'rgba(51, 65, 85, 0.3)' }, ticks: { color: '#94a3b8' } }
                        }
                    }
                });

                // 3. Platform Chart
                if (platformChart) platformChart.destroy();
                const ctxP = document.getElementById('platformChart').getContext('2d');
                const plats = data.platforms || [];
                const pLabels = plats.map(p => p.platform.replace('High-end mobile devices', 'Mobile').replace('Tablets', 'Tablet'));
                const pEarnings = plats.map(p => p.earnings);
                platformChart = new Chart(ctxP, {
                    type: 'doughnut',
                    data: {
                        labels: pLabels,
                        datasets: [{
                            data: pEarnings,
                            backgroundColor: ['#10b981', '#38bdf8', '#f59e0b'],
                            borderWidth: 0
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { position: 'bottom', labels: { color: '#94a3b8', boxWidth: 10, font: { size: 10 } } } }
                    }
                });

                // Platform Cards
                const pCardsHtml = plats.map(p => {
                    const shortName = p.platform.replace('High-end mobile devices', 'Mobile').replace('Tablets', 'Tablet');
                    return `
                        <div class="bg-slate-800/50 p-2 rounded-xl">
                            <div class="text-[10px] text-slate-400 uppercase">${shortName}</div>
                            <div class="text-sm font-bold text-white">$${p.earnings.toFixed(2)}</div>
                            <div class="text-[10px] text-slate-400">${p.pageviews} views</div>
                        </div>
                    `;
                }).join('');
                document.getElementById('platformCards').innerHTML = pCardsHtml;

                // Countries Table
                const cTbody = document.getElementById('countryTableBody');
                if (!data.countries || data.countries.length === 0) {
                    cTbody.innerHTML = '<tr><td colspan="4" class="py-4 text-center text-slate-500">No country data available</td></tr>';
                } else {
                    cTbody.innerHTML = data.countries.map(c => `
                        <tr class="hover:bg-slate-800/30 transition">
                            <td class="py-2.5 px-2 font-medium text-white">${c.country}</td>
                            <td class="py-2.5 px-2 text-right">${c.pageviews.toLocaleString()}</td>
                            <td class="py-2.5 px-2 text-right">${c.impressions.toLocaleString()}</td>
                            <td class="py-2.5 px-2 text-right font-bold text-emerald-400">$${c.earnings.toFixed(2)}</td>
                        </tr>
                    `).join('');
                }

                // Daily Table
                const dTbody = document.getElementById('dailyTableBody');
                if (rawDailyData.length === 0) {
                    dTbody.innerHTML = '<tr><td colspan="6" class="py-4 text-center text-slate-500">No daily data available</td></tr>';
                } else {
                    const sortedDaily = [...rawDailyData].reverse();
                    dTbody.innerHTML = sortedDaily.map(d => `
                        <tr class="hover:bg-slate-800/30 transition">
                            <td class="py-2.5 px-4 font-sans text-slate-200">${d.date}</td>
                            <td class="py-2.5 px-4 text-right font-bold text-emerald-400">$${d.earnings.toFixed(2)}</td>
                            <td class="py-2.5 px-4 text-right">${d.pageviews.toLocaleString()}</td>
                            <td class="py-2.5 px-4 text-right text-amber-400">$${d.rpm.toFixed(2)}</td>
                            <td class="py-2.5 px-4 text-right">${d.impressions.toLocaleString()}</td>
                            <td class="py-2.5 px-4 text-right">${d.clicks}</td>
                        </tr>
                    `).join('');
                }
            }

            function exportCSV() {
                if (!rawDailyData.length) return;
                let csv = "Date,Earnings_USD,Pageviews,RPM_USD,Impressions,Clicks\\n";
                rawDailyData.forEach(d => {
                    csv += `${d.date},${d.earnings},${d.pageviews},${d.rpm},${d.impressions},${d.clicks}\\n`;
                });
                const blob = new Blob([csv], { type: 'text/csv' });
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.setAttribute('href', url);
                a.setAttribute('download', `make-food-report-${currentRange}.csv`);
                a.click();
            }

            // Initial load
            loadDashboardData();
        </script>
    </body>
    </html>
    """

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

import os
import json
import time
import hmac
import hashlib
import urllib.request
import urllib.parse
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Request, Response, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

# Configuration
CONFIG = {
    "DASH_USER": os.getenv("DASH_USER", "partner_makefood"),
    "DASH_PASS": os.getenv("DASH_PASS", "MakeFood@2026!"),
    "SECRET_KEY": os.getenv("SECRET_KEY", "makefood_super_secret_partner_portal_key_2026"),
    "CLIENT_ID": os.getenv("GOOGLE_CLIENT_ID", ""),
    "CLIENT_SECRET": os.getenv("GOOGLE_CLIENT_SECRET", ""),
    "REFRESH_TOKEN": os.getenv("GOOGLE_REFRESH_TOKEN", ""),
    "GITHUB_TOKEN": os.getenv("GITHUB_TOKEN", ""),
    "COOLIFY_TOKEN": os.getenv("COOLIFY_TOKEN", ""),
    "COOLIFY_URL": os.getenv("COOLIFY_URL", "http://37.60.243.199:8000"),
    "MAKEFOOD_COOLIFY_UUID": "svnx0t7xgbrn9xbxmrmlq3f4",
    "ADSENSE_ACCOUNT": "accounts/pub-9077963246978786",
    "TARGET_DOMAIN": "make-food.com",
    "REPO_NAME": "hichamelmounaim/make-food.com"
}

app = FastAPI(title="Make-Food.com — Portal")

# Memory Cache for recipes & token
token_cache = {"access_token": None, "expires_at": 0}
recipes_cache = {"data": [], "last_loaded": 0}

def get_google_access_token() -> str:
    now = time.time()
    if token_cache["access_token"] and token_cache["expires_at"] > now + 60:
        return token_cache["access_token"]
    
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

def get_recipes_data() -> List[dict]:
    now = time.time()
    if recipes_cache["data"] and now - recipes_cache["last_loaded"] < 600:
        return recipes_cache["data"]
    
    try:
        url = f"https://raw.githubusercontent.com/{CONFIG['REPO_NAME']}/main/src/data/recipes.json"
        req = urllib.request.Request(url, headers={"Authorization": f"token {CONFIG['GITHUB_TOKEN']}"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            recipes_cache["data"] = data
            recipes_cache["last_loaded"] = now
            return data
    except Exception as e:
        print("Error fetching recipes from GitHub raw:", e)
        # Fallback to local if running in container / local repo
        local_path = "/app/data/recipes.json"
        if not os.path.exists(local_path):
            local_path = "D:/recipe-sites/make-food.com/src/data/recipes.json"
        if os.path.exists(local_path):
            with open(local_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                recipes_cache["data"] = data
                recipes_cache["last_loaded"] = now
                return data
        return recipes_cache["data"]

def push_recipes_to_github_and_redeploy(all_recipes: list, commit_message: str):
    """Saves recipes array to GitHub main branch and triggers Coolify rebuild."""
    recipes_cache["data"] = all_recipes
    recipes_cache["last_loaded"] = time.time()

    gh_h = {
        "Authorization": f"token {CONFIG['GITHUB_TOKEN']}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json"
    }

    # 1. Get latest commit SHA
    req_c = urllib.request.Request(f"https://api.github.com/repos/{CONFIG['REPO_NAME']}/commits/main", headers=gh_h)
    with urllib.request.urlopen(req_c) as r_c:
        commit_info = json.loads(r_c.read().decode("utf-8"))
        latest_commit_sha = commit_info["sha"]

    # 2. Create blob
    full_json_str = json.dumps(all_recipes, ensure_ascii=False)
    blob_payload = {"content": full_json_str, "encoding": "utf-8"}
    req_b = urllib.request.Request(f"https://api.github.com/repos/{CONFIG['REPO_NAME']}/git/blobs", data=json.dumps(blob_payload).encode("utf-8"), headers=gh_h, method="POST")
    with urllib.request.urlopen(req_b) as r_b:
        blob_sha = json.loads(r_b.read().decode("utf-8"))["sha"]

    # 3. Create tree
    tree_payload = {
        "base_tree": latest_commit_sha,
        "tree": [{
            "path": "src/data/recipes.json",
            "mode": "100644",
            "type": "blob",
            "sha": blob_sha
        }]
    }
    req_t = urllib.request.Request(f"https://api.github.com/repos/{CONFIG['REPO_NAME']}/git/trees", data=json.dumps(tree_payload).encode("utf-8"), headers=gh_h, method="POST")
    with urllib.request.urlopen(req_t) as r_t:
        tree_sha = json.loads(r_t.read().decode("utf-8"))["sha"]

    # 4. Create commit
    commit_payload = {
        "message": commit_message,
        "tree": tree_sha,
        "parents": [latest_commit_sha]
    }
    req_cm = urllib.request.Request(f"https://api.github.com/repos/{CONFIG['REPO_NAME']}/git/commits", data=json.dumps(commit_payload).encode("utf-8"), headers=gh_h, method="POST")
    with urllib.request.urlopen(req_cm) as r_cm:
        new_commit_sha = json.loads(r_cm.read().decode("utf-8"))["sha"]

    # 5. Update ref
    ref_payload = {"sha": new_commit_sha, "force": False}
    req_ref = urllib.request.Request(f"https://api.github.com/repos/{CONFIG['REPO_NAME']}/git/refs/heads/main", data=json.dumps(ref_payload).encode("utf-8"), headers=gh_h, method="PATCH")
    with urllib.request.urlopen(req_ref):
        pass

    # 6. Trigger Coolify redeployment
    coolify_h = {"Authorization": f"Bearer {CONFIG['COOLIFY_TOKEN']}", "Content-Type": "application/json"}
    req_dep = urllib.request.Request(f"{CONFIG['COOLIFY_URL']}/api/v1/deploy?uuid={CONFIG['MAKEFOOD_COOLIFY_UUID']}", headers=coolify_h, method="POST")
    try:
        urllib.request.urlopen(req_dep)
    except Exception as e:
        print("Note: Coolify deploy trigger exception:", e)

def sign_session(username: str) -> str:
    sig = hmac.new(CONFIG["SECRET_KEY"].encode(), username.encode(), hashlib.sha256).hexdigest()
    return f"{username}:{sig}"

def verify_session(token: str) -> Optional[str]:
    try:
        username, sig = token.split(":")
        expected = hmac.new(CONFIG["SECRET_KEY"].encode(), username.encode(), hashlib.sha256).hexdigest()
        if hmac.compare_digest(sig, expected):
            return username
    except Exception:
        pass
    return None

def is_authenticated(request: Request) -> bool:
    token = request.cookies.get("session_token")
    if not token:
        return False
    return verify_session(token) is not None

# ================= AUTH ROUTES =================
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if is_authenticated(request):
        return RedirectResponse(url="/")
    
    return HTMLResponse("""
    <!DOCTYPE html>
    <html lang="ar" dir="rtl" id="htmlTag">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Make-Food.com — تسجيل دخول الشريك / Partner Login</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&family=Cairo:wght@400;600;700;800&display=swap" rel="stylesheet">
        <style>
            body { font-family: 'Cairo', 'Plus Jakarta Sans', sans-serif; }
            [dir="ltr"] body { font-family: 'Plus Jakarta Sans', sans-serif; }
            .font-num { font-family: 'Plus Jakarta Sans', sans-serif; }
        </style>
    </head>
    <body class="bg-slate-950 text-slate-100 min-h-screen flex items-center justify-center p-4">
        <div class="w-full max-w-md">
            <div class="bg-slate-900/90 backdrop-blur-xl border border-slate-800 rounded-3xl p-8 shadow-2xl relative overflow-hidden">
                <div class="absolute -top-24 -right-24 w-48 h-48 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none"></div>
                <div class="absolute -bottom-24 -left-24 w-48 h-48 bg-amber-500/10 rounded-full blur-3xl pointer-events-none"></div>

                <div class="flex justify-end mb-4">
                    <button onclick="toggleLang()" id="loginLangBtn" class="px-2.5 py-1 rounded-lg bg-slate-800 border border-slate-700 text-xs text-slate-300 hover:text-white flex items-center gap-1">
                        🌐 <span id="loginLangText">English</span>
                    </button>
                </div>

                <div class="text-center mb-8 relative">
                    <div class="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-tr from-amber-500 to-emerald-500 p-0.5 mb-4 shadow-lg shadow-emerald-500/20">
                        <div class="w-full h-full bg-slate-900 rounded-[14px] flex items-center justify-center text-3xl">
                            🍲
                        </div>
                    </div>
                    <h1 class="text-2xl font-extrabold tracking-tight text-white font-['Plus_Jakarta_Sans']">Make-Food.com</h1>
                    <p id="loginSubtitle" class="text-sm text-slate-400 mt-1">بوابة إدارة الموقع، المقالات والأرباح</p>
                </div>

                <form method="POST" action="/login" class="space-y-5">
                    <div>
                        <label id="lblUsername" class="block text-xs font-bold text-slate-300 mb-2">اسم المستخدم (Username)</label>
                        <input type="text" name="username" required autocomplete="username" dir="ltr"
                            placeholder="partner_makefood"
                            class="w-full px-4 py-3 bg-slate-800/80 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition text-left">
                    </div>
                    <div>
                        <label id="lblPassword" class="block text-xs font-bold text-slate-300 mb-2">كلمة المرور (Password)</label>
                        <input type="password" name="password" required autocomplete="current-password" dir="ltr"
                            placeholder="••••••••••••"
                            class="w-full px-4 py-3 bg-slate-800/80 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition text-left">
                    </div>
                    <button type="submit" id="btnSubmitLogin"
                        class="w-full py-3.5 px-4 bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-slate-950 font-bold rounded-xl shadow-lg shadow-emerald-500/25 transition duration-200 text-base">
                        تسجيل الدخول إلى المنصة
                    </button>
                </form>

                <div class="mt-6 pt-6 border-t border-slate-800/60 text-center">
                    <p class="text-xs text-slate-400 flex items-center justify-center gap-2">
                        <span class="w-2 h-2 rounded-full bg-emerald-500 inline-block animate-pulse"></span>
                        <span id="loginFooterText">مربوط بـ AdSense (بالدرهم المغربي MAD 🇲🇦)</span>
                    </p>
                </div>
            </div>
        </div>

        <script>
            let currentLang = localStorage.getItem('portal_lang') || 'ar';
            function applyLang(lang) {
                currentLang = lang;
                localStorage.setItem('portal_lang', lang);
                const html = document.getElementById('htmlTag');
                if (lang === 'en') {
                    html.setAttribute('lang', 'en');
                    html.setAttribute('dir', 'ltr');
                    document.getElementById('loginLangText').innerText = 'العربية';
                    document.getElementById('loginSubtitle').innerText = 'Website Management, Content & Revenue Portal';
                    document.getElementById('lblUsername').innerText = 'Partner Username';
                    document.getElementById('lblPassword').innerText = 'Password';
                    document.getElementById('btnSubmitLogin').innerText = 'Sign In to Portal';
                    document.getElementById('loginFooterText').innerText = 'Connected to AdSense (Moroccan Dirham MAD 🇲🇦)';
                } else {
                    html.setAttribute('lang', 'ar');
                    html.setAttribute('dir', 'rtl');
                    document.getElementById('loginLangText').innerText = 'English';
                    document.getElementById('loginSubtitle').innerText = 'بوابة إدارة الموقع، المقالات والأرباح';
                    document.getElementById('lblUsername').innerText = 'اسم المستخدم (Username)';
                    document.getElementById('lblPassword').innerText = 'كلمة المرور (Password)';
                    document.getElementById('btnSubmitLogin').innerText = 'تسجيل الدخول إلى المنصة';
                    document.getElementById('loginFooterText').innerText = 'مربوط بـ AdSense (بالدرهم المغربي MAD 🇲🇦)';
                }
            }
            function toggleLang() {
                applyLang(currentLang === 'ar' ? 'en' : 'ar');
            }
            applyLang(currentLang);
        </script>
    </body>
    </html>
    """)

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
            max_age=86400 * 30
        )
        return response
    return HTMLResponse("""
        <script>
            alert("اسم المستخدم أو كلمة المرور غير صحيحة / Invalid credentials!");
            window.location.href = "/login";
        </script>
    """, status_code=401)

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie("session_token")
    return response

# ================= STATS API =================
@app.get("/api/stats")
async def get_stats(request: Request, range: str = "last30"):
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    token = get_google_access_token()
    range_map = {
        "today": "TODAY",
        "yesterday": "YESTERDAY",
        "last7": "LAST_7_DAYS",
        "last30": "LAST_30_DAYS",
        "month": "THIS_MONTH"
    }
    date_range = range_map.get(range, "LAST_30_DAYS")
    
    daily_params = [
        ("dateRange", date_range),
        ("metrics", "ESTIMATED_EARNINGS"),
        ("metrics", "PAGE_VIEWS"),
        ("metrics", "PAGE_VIEWS_RPM"),
        ("metrics", "IMPRESSIONS"),
        ("metrics", "CLICKS"),
        ("dimensions", "DATE"),
        ("reportingTimeZone", "ACCOUNT_TIME_ZONE")
    ]
    query_string = urllib.parse.urlencode(daily_params)
    url_daily = f"https://adsense.googleapis.com/v2/{CONFIG['ADSENSE_ACCOUNT']}/reports:generate?{query_string}"
    
    req_daily = urllib.request.Request(url_daily, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req_daily) as resp:
            data_daily = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print("AdSense API Error:", e)
        data_daily = {}

    headers = [h.get("name") for h in data_daily.get("headers", [])]
    rows = data_daily.get("rows", [])
    
    daily_history = []
    tot_earnings = 0.0
    tot_views = 0
    tot_impressions = 0
    tot_clicks = 0

    def get_val(row, header_name):
        try:
            idx = headers.index(header_name)
            v = row["cells"][idx]["value"]
            return float(v) if "." in v else int(v)
        except Exception:
            return 0

    for r in rows:
        d_str = r["cells"][headers.index("DATE")]["value"] if "DATE" in headers else ""
        earn = float(get_val(r, "ESTIMATED_EARNINGS"))
        views = int(get_val(r, "PAGE_VIEWS"))
        rpm = float(get_val(r, "PAGE_VIEWS_RPM"))
        imps = int(get_val(r, "IMPRESSIONS"))
        clicks = int(get_val(r, "CLICKS"))

        tot_earnings += earn
        tot_views += views
        tot_impressions += imps
        tot_clicks += clicks

        daily_history.append({
            "date": d_str,
            "earnings": round(earn, 2),
            "views": views,
            "rpm": round(rpm, 2),
            "impressions": imps,
            "clicks": clicks
        })

    avg_rpm = round((tot_earnings / tot_views * 1000), 2) if tot_views > 0 else 0.0
    ctr = round((tot_clicks / tot_impressions * 100), 2) if tot_impressions > 0 else 0.0

    # Country report
    country_params = [
        ("dateRange", date_range),
        ("metrics", "PAGE_VIEWS"),
        ("metrics", "ESTIMATED_EARNINGS"),
        ("dimensions", "COUNTRY_NAME"),
        ("reportingTimeZone", "ACCOUNT_TIME_ZONE")
    ]
    query_country = urllib.parse.urlencode(country_params)
    url_country = f"https://adsense.googleapis.com/v2/{CONFIG['ADSENSE_ACCOUNT']}/reports:generate?{query_country}"
    req_country = urllib.request.Request(url_country, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req_country) as resp:
            data_country = json.loads(resp.read().decode("utf-8"))
    except Exception:
        data_country = {}

    c_headers = [h.get("name") for h in data_country.get("headers", [])]
    c_rows = data_country.get("rows", [])
    countries = []
    for r in c_rows:
        try:
            c_name = r["cells"][c_headers.index("COUNTRY_NAME")]["value"]
            c_views = int(r["cells"][c_headers.index("PAGE_VIEWS")]["value"])
            c_earn = float(r["cells"][c_headers.index("ESTIMATED_EARNINGS")]["value"])
            countries.append({"country": c_name, "views": c_views, "earnings": round(c_earn, 2)})
        except Exception:
            pass
    countries.sort(key=lambda x: x["views"], reverse=True)

    # Platforms report
    plat_params = [
        ("dateRange", date_range),
        ("metrics", "PAGE_VIEWS"),
        ("dimensions", "PLATFORM_TYPE_NAME"),
        ("reportingTimeZone", "ACCOUNT_TIME_ZONE")
    ]
    query_plat = urllib.parse.urlencode(plat_params)
    url_plat = f"https://adsense.googleapis.com/v2/{CONFIG['ADSENSE_ACCOUNT']}/reports:generate?{query_plat}"
    req_plat = urllib.request.Request(url_plat, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req_plat) as resp:
            data_plat = json.loads(resp.read().decode("utf-8"))
    except Exception:
        data_plat = {}

    p_headers = [h.get("name") for h in data_plat.get("headers", [])]
    p_rows = data_plat.get("rows", [])
    platforms = []
    for r in p_rows:
        try:
            p_name = r["cells"][p_headers.index("PLATFORM_TYPE_NAME")]["value"]
            p_views = int(r["cells"][p_headers.index("PAGE_VIEWS")]["value"])
            platforms.append({"platform": p_name, "views": p_views})
        except Exception:
            pass

    return {
        "currency": "MAD",
        "domain": CONFIG["TARGET_DOMAIN"],
        "totals": {
            "earnings": round(tot_earnings, 2),
            "views": tot_views,
            "rpm": avg_rpm,
            "impressions": tot_impressions,
            "clicks": tot_clicks,
            "ctr": ctr,
            "currency": "MAD"
        },
        "daily": daily_history,
        "countries": countries[:10],
        "platforms": platforms,
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

# ================= POSTS & RECIPES FULL CRUD API =================
@app.get("/api/recipes")
async def list_recipes(request: Request, search: str = "", category: str = "", limit: int = 30, offset: int = 0):
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    recipes = get_recipes_data()
    
    # Collect distinct categories
    all_cats = set()
    for r in recipes:
        if r.get("categories"):
            for c in r["categories"]:
                name = c.get("name") if isinstance(c, dict) else str(c)
                if name:
                    all_cats.add(name.strip())

    filtered = recipes
    if category and category.lower() != "all":
        c_lower = category.lower()
        filtered = [
            r for r in filtered
            if any(c_lower in (c.get("name", "").lower() if isinstance(c, dict) else str(c).lower()) for c in r.get("categories", []))
            or c_lower in r.get("recipe", {}).get("category", "").lower()
        ]

    if search:
        s_lower = search.lower()
        filtered = [
            r for r in filtered
            if s_lower in r.get("title", "").lower()
            or s_lower in r.get("slug", "").lower()
            or s_lower in r.get("seo", {}).get("focus_keyword", "").lower()
        ]
    
    total = len(filtered)
    paginated = filtered[offset:offset+limit]
    
    results = []
    for r in paginated:
        cat_name = "General"
        if r.get("categories") and len(r["categories"]) > 0:
            c0 = r["categories"][0]
            cat_name = c0.get("name", "General") if isinstance(c0, dict) else str(c0)
        img = r.get("featured_image", {}).get("url", "") if isinstance(r.get("featured_image"), dict) else ""
        results.append({
            "id": r.get("wp_post_id") or r.get("slug"),
            "title": r.get("title"),
            "slug": r.get("slug"),
            "url": f"https://make-food.com/{r.get('slug')}/",
            "category": cat_name,
            "published_at": r.get("published_at"),
            "image": img,
            "prep_time": r.get("recipe", {}).get("prep_time", ""),
            "cook_time": r.get("recipe", {}).get("cook_time", ""),
            "servings": r.get("recipe", {}).get("yield", "")
        })
    
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": (offset + limit) < total,
        "categories": sorted(list(all_cats)),
        "recipes": results
    }

@app.get("/api/recipes/get/{slug}")
async def get_recipe_detail(slug: str, request: Request):
    """Read full recipe details for editing and viewing."""
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    recipes = get_recipes_data()
    found = None
    for r in recipes:
        if r.get("slug") == slug or str(r.get("wp_post_id")) == slug:
            found = r
            break
            
    if not found:
        raise HTTPException(status_code=404, detail="Recipe not found")
        
    ings_list = []
    for ing in found.get("recipe", {}).get("ingredients", []):
        if isinstance(ing, dict):
            raw = ing.get("raw") or f"{ing.get('amount', '')} {ing.get('unit', '')} {ing.get('name', '')}".strip()
            ings_list.append(raw)
        elif isinstance(ing, str):
            ings_list.append(ing)
            
    inst_list = []
    for step in found.get("recipe", {}).get("instructions", []):
        if isinstance(step, dict):
            inst_list.append(step.get("text", ""))
        elif isinstance(step, str):
            inst_list.append(step)
            
    cat_name = "Dinner"
    if found.get("categories") and len(found["categories"]) > 0:
        c0 = found["categories"][0]
        cat_name = c0.get("name", "Dinner") if isinstance(c0, dict) else str(c0)
        
    author_name = found.get("author", {}).get("name", "Maria") if isinstance(found.get("author"), dict) else "Maria"
    img_url = found.get("featured_image", {}).get("url", "") if isinstance(found.get("featured_image"), dict) else ""
    rec = found.get("recipe", {})
    
    prep_m = rec.get("prep_time_minutes") or 15
    cook_m = rec.get("cook_time_minutes") or 25
    y_str = str(rec.get("yield", "4")).replace(" servings", "").replace(" serving", "").strip()

    return {
        "success": True,
        "recipe": {
            "id": found.get("wp_post_id") or found.get("slug"),
            "original_slug": found.get("slug"),
            "slug": found.get("slug"),
            "title": found.get("title", ""),
            "category": cat_name,
            "author": author_name,
            "description": rec.get("description") or found.get("seo", {}).get("meta_description", ""),
            "featured_image": img_url,
            "prep_time": prep_m,
            "cook_time": cook_m,
            "servings": y_str or "4",
            "ingredients_raw": "\n".join(ings_list),
            "instructions_raw": "\n".join(inst_list),
            "article_html": found.get("article_html", ""),
            "live_url": f"https://make-food.com/{found.get('slug')}/"
        }
    }

@app.post("/api/recipes/create")
async def create_recipe(
    request: Request,
    title: str = Form(...),
    slug: str = Form(...),
    category: str = Form("Dinner"),
    author: str = Form("Maria"),
    description: str = Form(""),
    featured_image: str = Form(""),
    prep_time: int = Form(15),
    cook_time: int = Form(25),
    servings: int = Form(4),
    ingredients_raw: str = Form(""),
    instructions_raw: str = Form(""),
    article_html: str = Form("")
):
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    slug_clean = slug.strip().lower().replace(" ", "-").replace("/", "")
    if not slug_clean:
        slug_clean = title.strip().lower().replace(" ", "-")
    
    ingredients = []
    for line in ingredients_raw.strip().split("\n"):
        line = line.strip()
        if line:
            ingredients.append({"name": line, "amount": "", "unit": "", "raw": line})
            
    instructions = []
    for idx, line in enumerate(instructions_raw.strip().split("\n")):
        line = line.strip()
        if line:
            instructions.append({"step_number": idx + 1, "text": line})

    new_recipe = {
        "wp_post_id": int(time.time()),
        "wp_recipe_id": int(time.time()),
        "title": title.strip(),
        "recipe_card_title": title.strip(),
        "slug": slug_clean,
        "url_path": f"/{slug_clean}/",
        "canonical_url": f"https://make-food.com/{slug_clean}/",
        "published_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "author": {"id": "1", "name": author.strip() or "Maria"},
        "featured_image": {
            "id": "1",
            "url": featured_image.strip() or "https://images.unsplash.com/photo-1495521821757-a1efb6729352?auto=format&fit=crop&w=1200&q=80",
            "path": "",
            "alt": title.strip(),
            "width": 1200,
            "height": 800
        },
        "categories": [{"id": "1", "name": category.strip(), "slug": category.strip().lower().replace(" ", "-")}],
        "tags": [],
        "seo": {
            "meta_title": title.strip(),
            "meta_description": (description.strip()[:155] if description else title.strip()),
            "focus_keyword": title.strip()
        },
        "article_html": article_html.strip() or f"<p>{description.strip()}</p>",
        "recipe": {
            "description": description.strip() or title.strip(),
            "prep_time": f"{prep_time} min",
            "prep_time_minutes": prep_time,
            "cook_time": f"{cook_time} min",
            "cook_time_minutes": cook_time,
            "total_time": f"{prep_time + cook_time} min",
            "total_time_minutes": prep_time + cook_time,
            "yield": f"{servings} servings",
            "serving_size": "1 plate",
            "cuisine": "American",
            "category": category.strip(),
            "cooking_method": "",
            "diet": "",
            "keywords": [],
            "notes_html": "",
            "ingredients": ingredients,
            "instructions": instructions,
            "nutrition": {
                "calories": "350 kcal",
                "protein": "15g",
                "carbohydrates": "30g",
                "fat": "12g"
            },
            "ratings": {"average": 5.0, "count": 1}
        }
    }

    all_recipes = get_recipes_data()
    all_recipes.insert(0, new_recipe)
    
    try:
        push_recipes_to_github_and_redeploy(all_recipes, f"feat(recipes): publish recipe '{title.strip()}' via partner portal")
        return {
            "success": True,
            "slug": slug_clean,
            "live_url": f"https://make-food.com/{slug_clean}/",
            "message": f"تم نشر المقال '{title}' بنجاح! / Recipe published successfully!"
        }
    except Exception as e:
        print("Error saving recipe to GitHub:", e)
        return {"success": False, "error": str(e)}

@app.post("/api/recipes/update")
async def update_recipe(
    request: Request,
    original_slug: str = Form(...),
    title: str = Form(...),
    slug: str = Form(...),
    category: str = Form("Dinner"),
    author: str = Form("Maria"),
    description: str = Form(""),
    featured_image: str = Form(""),
    prep_time: int = Form(15),
    cook_time: int = Form(25),
    servings: int = Form(4),
    ingredients_raw: str = Form(""),
    instructions_raw: str = Form(""),
    article_html: str = Form("")
):
    """Update an existing recipe and redeploy to make-food.com."""
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    slug_clean = slug.strip().lower().replace(" ", "-").replace("/", "")
    if not slug_clean:
        slug_clean = original_slug
        
    all_recipes = get_recipes_data()
    target_idx = None
    for i, r in enumerate(all_recipes):
        if r.get("slug") == original_slug or str(r.get("wp_post_id")) == original_slug:
            target_idx = i
            break
            
    if target_idx is None:
        raise HTTPException(status_code=404, detail="Original recipe not found")
        
    r = all_recipes[target_idx]
    
    ingredients = []
    for line in ingredients_raw.strip().split("\n"):
        line = line.strip()
        if line:
            ingredients.append({"name": line, "amount": "", "unit": "", "raw": line})
            
    instructions = []
    for idx, line in enumerate(instructions_raw.strip().split("\n")):
        line = line.strip()
        if line:
            instructions.append({"step_number": idx + 1, "text": line})
            
    # Update properties
    r["title"] = title.strip()
    r["recipe_card_title"] = title.strip()
    r["slug"] = slug_clean
    r["url_path"] = f"/{slug_clean}/"
    r["canonical_url"] = f"https://make-food.com/{slug_clean}/"
    
    if not isinstance(r.get("author"), dict):
        r["author"] = {"id": "1", "name": author.strip() or "Maria"}
    else:
        r["author"]["name"] = author.strip() or "Maria"
        
    if not isinstance(r.get("featured_image"), dict):
        r["featured_image"] = {"id": "1", "url": featured_image.strip(), "alt": title.strip()}
    else:
        if featured_image.strip():
            r["featured_image"]["url"] = featured_image.strip()
        r["featured_image"]["alt"] = title.strip()
        
    r["categories"] = [{"id": "1", "name": category.strip(), "slug": category.strip().lower().replace(" ", "-")}]
    
    if not isinstance(r.get("seo"), dict):
        r["seo"] = {}
    r["seo"]["meta_title"] = title.strip()
    r["seo"]["meta_description"] = description.strip()[:155] if description else title.strip()
    r["seo"]["focus_keyword"] = title.strip()
    
    r["article_html"] = article_html.strip() or f"<p>{description.strip()}</p>"
    
    if not isinstance(r.get("recipe"), dict):
        r["recipe"] = {}
    rec = r["recipe"]
    rec["description"] = description.strip() or title.strip()
    rec["prep_time"] = f"{prep_time} min"
    rec["prep_time_minutes"] = prep_time
    rec["cook_time"] = f"{cook_time} min"
    rec["cook_time_minutes"] = cook_time
    rec["total_time"] = f"{prep_time + cook_time} min"
    rec["total_time_minutes"] = prep_time + cook_time
    rec["yield"] = f"{servings} servings"
    rec["category"] = category.strip()
    rec["ingredients"] = ingredients
    rec["instructions"] = instructions
    
    try:
        push_recipes_to_github_and_redeploy(all_recipes, f"feat(recipes): update recipe '{title.strip()}' via partner portal")
        return {
            "success": True,
            "slug": slug_clean,
            "live_url": f"https://make-food.com/{slug_clean}/",
            "message": f"تم تحديث المقال '{title}' بنجاح! / Recipe updated successfully!"
        }
    except Exception as e:
        print("Error updating recipe in GitHub:", e)
        return {"success": False, "error": str(e)}

@app.post("/api/recipes/delete")
async def delete_recipe(request: Request, slug: str = Form(...)):
    """Delete an existing recipe and redeploy make-food.com."""
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    all_recipes = get_recipes_data()
    target_idx = None
    target_title = slug
    for i, r in enumerate(all_recipes):
        if r.get("slug") == slug or str(r.get("wp_post_id")) == slug:
            target_idx = i
            target_title = r.get("title", slug)
            break
            
    if target_idx is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
        
    all_recipes.pop(target_idx)
    
    try:
        push_recipes_to_github_and_redeploy(all_recipes, f"feat(recipes): delete recipe '{target_title}' via partner portal")
        return {
            "success": True,
            "deleted_slug": slug,
            "message": f"تم حذف المقال '{target_title}' بنجاح! / Recipe deleted successfully!"
        }
    except Exception as e:
        print("Error deleting recipe from GitHub:", e)
        return {"success": False, "error": str(e)}

# ================= AI GENERATION & REWRITER API =================
@app.post("/api/ai/models")
async def fetch_ai_models(request: Request):
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        body = await request.json()
    except Exception:
        body = {}
        
    provider = body.get("provider", "google")
    api_key = body.get("api_key", "").strip()
    
    if not api_key:
        return {"success": False, "error": "API Key is required"}
        
    try:
        if provider == "google":
            url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
            req = urllib.request.Request(url, headers={"User-Agent": "MakeFoodPortal/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models = [
                    {"id": m["name"].replace("models/", ""), "name": m.get("displayName", m["name"])}
                    for m in data.get("models", [])
                    if "generateContent" in m.get("supportedGenerationMethods", [])
                ]
                models.sort(key=lambda x: ("gemini-1.5" in x["id"] or "gemini-2.0" in x["id"]), reverse=True)
                return {"success": True, "provider": "google", "models": models}
        else:
            url = "https://openrouter.ai/api/v1/models"
            req = urllib.request.Request(url, headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "https://partner.make-food.com",
                "X-Title": "MakeFood Partner Portal"
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models = [{"id": m["id"], "name": m.get("name", m["id"])} for m in data.get("data", [])]
                return {"success": True, "provider": "openrouter", "models": models[:60]}
    except Exception as e:
        return {"success": False, "error": f"Failed to fetch models: {str(e)}"}

@app.post("/api/ai/generate")
async def generate_recipe_ai(request: Request):
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        body = await request.json()
    except Exception:
        body = {}
        
    provider = body.get("provider", "google")
    api_key = body.get("api_key", "").strip()
    model = body.get("model", "gemini-1.5-flash")
    mode = body.get("mode", "name")
    input_text = body.get("input_text", "").strip()
    
    if not api_key:
        return {"success": False, "error": "API Key is required. Please set it in AI Settings."}
    if not input_text:
        return {"success": False, "error": "Recipe title or source inspiration content is required."}

    system_instruction = (
        "You are a professional culinary chef, recipe creator, and food SEO expert for 'make-food.com'. "
        "Your goal is to output an authentic, highly detailed, mouthwatering, and 100% original recipe in valid JSON format. "
        "Strictly adhere to this JSON structure with NO markdown fences or preamble:\n"
        "{\n"
        '  "title": "Engaging Recipe Title",\n'
        '  "slug": "kebab-case-recipe-slug",\n'
        '  "category": "Dinner",\n'
        '  "description": "2-3 sentences SEO meta description",\n'
        '  "prep_time": 15,\n'
        '  "cook_time": 25,\n'
        '  "servings": 4,\n'
        '  "ingredients": ["1 tbsp olive oil", "2 cloves minced garlic", ...],\n'
        '  "instructions": ["Step 1 text...", "Step 2 text...", ...],\n'
        '  "article_html": "<p>Introduction...</p><h2>Why You Will Love This</h2><p>...</p><h2>Chef Tips</h2><ul><li>...</li></ul>"\n'
        "}"
    )

    if mode == "name":
        user_prompt = f"Create a comprehensive original recipe and engaging food article based on this recipe name: '{input_text}'."
    else:
        user_prompt = f"Rewrite and transform the following recipe / food inspiration text into a completely fresh, 100% original, high-quality recipe with rich article HTML:\n\n{input_text}"

    try:
        raw_output = ""
        if provider == "google":
            model_clean = model.replace("models/", "")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_clean}:generateContent?key={api_key}"
            payload = {
                "system_instruction": {"parts": [{"text": system_instruction}]},
                "contents": [{"parts": [{"text": user_prompt}]}],
                "generationConfig": {"temperature": 0.7, "response_mime_type": "application/json"}
            }
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=35) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
                raw_output = res_data["candidates"][0]["content"]["parts"][0]["text"]
        else:
            url = "https://openrouter.ai/api/v1/chat/completions"
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.7
            }
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://partner.make-food.com"
            })
            with urllib.request.urlopen(req, timeout=35) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
                raw_output = res_data["choices"][0]["message"]["content"]

        clean_json_str = raw_output.strip()
        if clean_json_str.startswith("```json"):
            clean_json_str = clean_json_str[7:]
        if clean_json_str.startswith("```"):
            clean_json_str = clean_json_str[3:]
        if clean_json_str.endswith("```"):
            clean_json_str = clean_json_str[:-3]
        clean_json_str = clean_json_str.strip()

        recipe_json = json.loads(clean_json_str)
        return {"success": True, "recipe": recipe_json}
    except Exception as e:
        return {"success": False, "error": f"AI Generation failed: {str(e)}"}

# ================= DASHBOARD HTML =================
@app.get("/", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    if not is_authenticated(request):
        return RedirectResponse(url="/login")

    return HTMLResponse("""
    <!DOCTYPE html>
    <html lang="ar" dir="rtl" id="htmlRoot">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Make-Food.com — لوحة إدارة الشريك / Partner Portal</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Cairo:wght@400;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
        <style>
            body { font-family: 'Cairo', 'Plus Jakarta Sans', sans-serif; }
            [dir="ltr"] body { font-family: 'Plus Jakarta Sans', sans-serif; }
            .font-num { font-family: 'Plus Jakarta Sans', sans-serif; }
            .font-code { font-family: 'JetBrains Mono', monospace; }
            .custom-scrollbar::-webkit-scrollbar { width: 6px; height: 6px; }
            .custom-scrollbar::-webkit-scrollbar-track { background: #0f172a; }
            .custom-scrollbar::-webkit-scrollbar-thumb { background: #334155; border-radius: 4px; }
            .custom-scrollbar::-webkit-scrollbar-thumb:hover { background: #10b981; }
        </style>
    </head>
    <body class="bg-slate-950 text-slate-100 min-h-screen flex flex-col selection:bg-emerald-500 selection:text-slate-950">

        <!-- Top Navigation -->
        <header class="sticky top-0 z-40 bg-slate-900/90 backdrop-blur-md border-b border-slate-800">
            <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
                
                <!-- Logo & Brand -->
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-amber-500 to-emerald-500 p-0.5 flex-shrink-0 shadow-md shadow-emerald-500/20">
                        <div class="w-full h-full bg-slate-950 rounded-[10px] flex items-center justify-center text-xl">
                            🍲
                        </div>
                    </div>
                    <div>
                        <div class="flex items-center gap-2">
                            <h1 class="text-base font-bold text-white tracking-tight font-['Plus_Jakarta_Sans']">Make-Food.com</h1>
                            <span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-num">
                                MAD 🇲🇦
                            </span>
                        </div>
                        <p id="topSubtitle" class="text-[11px] text-slate-400 hidden sm:block">لوحة الشريك الخاصة بالإحصائيات والمقالات</p>
                    </div>
                </div>

                <!-- Navigation Tabs -->
                <nav class="flex items-center gap-1 sm:gap-2">
                    <button onclick="switchTab('analytics')" id="nav-analytics" class="px-3 py-2 rounded-xl text-xs sm:text-sm font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 transition flex items-center gap-1.5">
                        <span>📊</span> <span id="tabNameAnalytics">الإحصائيات والأرباح</span>
                    </button>
                    <button onclick="switchTab('recipes')" id="nav-recipes" class="px-3 py-2 rounded-xl text-xs sm:text-sm font-semibold text-slate-400 hover:text-white hover:bg-slate-800/60 transition flex items-center gap-1.5">
                        <span>📝</span> <span id="tabNameRecipes">المقالات والوصفات</span>
                    </button>
                    <button onclick="switchTab('create')" id="nav-create" class="px-3 py-2 rounded-xl text-xs sm:text-sm font-semibold text-slate-400 hover:text-white hover:bg-slate-800/60 transition flex items-center gap-1.5">
                        <span>➕</span> <span id="tabNameCreate">إنشاء مقال جديد</span>
                    </button>
                    <button onclick="switchTab('settings')" id="nav-settings" class="px-3 py-2 rounded-xl text-xs sm:text-sm font-semibold text-slate-400 hover:text-white hover:bg-slate-800/60 transition flex items-center gap-1.5">
                        <span>⚙️</span> <span id="tabNameSettings">الإعدادات و AI</span>
                    </button>
                </nav>

                <!-- Actions: Language Switch & Logout -->
                <div class="flex items-center gap-2">
                    <button onclick="toggleLanguage()" id="btnToggleLang"
                        class="px-2.5 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs font-bold text-slate-200 transition flex items-center gap-1.5">
                        <span>🌐</span>
                        <span id="langBtnText">English</span>
                    </button>
                    <a href="/logout" class="p-2 rounded-xl text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 border border-transparent hover:border-rose-500/20 transition text-xs font-semibold flex items-center gap-1">
                        <span>🚪</span> <span id="logoutBtnText" class="hidden md:inline">خروج</span>
                    </a>
                </div>

            </div>
        </header>

        <!-- Main Workspace -->
        <main class="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">

            <!-- ================= TAB 1: REVENUE & ANALYTICS ================= -->
            <div id="tab-analytics" class="space-y-8">
                
                <!-- Range Controls & Headline -->
                <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-slate-900/60 border border-slate-800/80 p-4 rounded-2xl">
                    <div>
                        <h2 id="kpiSectionTitle" class="text-base font-bold text-white flex items-center gap-2">
                            <span>📈</span> مداخيل وزيارات الموقع الحي make-food.com
                        </h2>
                        <p id="kpiSectionSub" class="text-xs text-slate-400 mt-1">مربوطة بـ Google AdSense Management API ومحسوبة بالدرهم المغربي (MAD)</p>
                    </div>
                    
                    <!-- Date Range Switcher -->
                    <div class="flex items-center gap-1 bg-slate-800/80 p-1 rounded-xl border border-slate-700/60 text-xs font-num">
                        <button onclick="changeRange('today')" id="btn-today" class="px-2.5 py-1.5 rounded-lg text-slate-400 hover:text-white transition">Today</button>
                        <button onclick="changeRange('yesterday')" id="btn-yesterday" class="px-2.5 py-1.5 rounded-lg text-slate-400 hover:text-white transition">Yesterday</button>
                        <button onclick="changeRange('last7')" id="btn-last7" class="px-2.5 py-1.5 rounded-lg text-slate-400 hover:text-white transition">7 Days</button>
                        <button onclick="changeRange('last30')" id="btn-last30" class="px-2.5 py-1.5 rounded-lg bg-emerald-500/20 text-emerald-300 font-bold border border-emerald-500/30 transition">30 Days</button>
                        <button onclick="changeRange('month')" id="btn-month" class="px-2.5 py-1.5 rounded-lg text-slate-400 hover:text-white transition">This Month</button>
                    </div>
                </div>

                <!-- KPI Overview Grid (Currency in MAD) -->
                <div class="grid grid-cols-2 lg:grid-cols-5 gap-4">
                    
                    <!-- Revenue in MAD -->
                    <div class="col-span-2 sm:col-span-1 bg-gradient-to-br from-emerald-950/40 via-slate-900 to-slate-900 border border-emerald-500/30 rounded-2xl p-5 shadow-lg relative overflow-hidden">
                        <div class="flex items-center justify-between mb-2">
                            <span id="kpiTitleEarnings" class="text-xs font-bold text-emerald-400">الأرباح المقدرة</span>
                            <span class="text-xs bg-emerald-500/20 text-emerald-300 px-1.5 py-0.5 rounded font-num">MAD</span>
                        </div>
                        <div class="text-2xl sm:text-3xl font-extrabold text-white font-num flex items-baseline gap-1.5">
                            <span id="kpi-earnings">0.00</span>
                            <span class="text-sm font-semibold text-emerald-400">د.م.</span>
                        </div>
                        <p id="kpiSubEarnings" class="text-[11px] text-slate-400 mt-2">100% مباشرة من AdSense للموقع</p>
                    </div>

                    <!-- Pageviews -->
                    <div class="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-lg">
                        <div class="flex items-center justify-between mb-2">
                            <span id="kpiTitleViews" class="text-xs font-bold text-slate-400">مشاهدات الصفحة</span>
                            <span class="text-slate-500 text-xs">👁️</span>
                        </div>
                        <div id="kpi-views" class="text-2xl sm:text-3xl font-extrabold text-white font-num">0</div>
                        <p id="kpiSubViews" class="text-[11px] text-slate-500 mt-2">عدد الزيارات الإجمالية</p>
                    </div>

                    <!-- Page RPM in MAD -->
                    <div class="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-lg">
                        <div class="flex items-center justify-between mb-2">
                            <span id="kpiTitleRpm" class="text-xs font-bold text-slate-400">معدل الألف (RPM)</span>
                            <span class="text-xs text-amber-400 font-num">MAD</span>
                        </div>
                        <div class="text-2xl sm:text-3xl font-extrabold text-amber-400 font-num flex items-baseline gap-1">
                            <span id="kpi-rpm">0.00</span>
                            <span class="text-xs font-normal text-slate-400">د.م.</span>
                        </div>
                        <p id="kpiSubRpm" class="text-[11px] text-slate-500 mt-2">الربح لكل 1,000 مشاهدة</p>
                    </div>

                    <!-- Impressions -->
                    <div class="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-lg">
                        <div class="flex items-center justify-between mb-2">
                            <span id="kpiTitleImps" class="text-xs font-bold text-slate-400">مرات الظهور</span>
                            <span class="text-slate-500 text-xs">📊</span>
                        </div>
                        <div id="kpi-impressions" class="text-2xl sm:text-3xl font-extrabold text-white font-num">0</div>
                        <p id="kpiSubImps" class="text-[11px] text-slate-500 mt-2">مرات عرض الإعلانات</p>
                    </div>

                    <!-- Clicks & CTR -->
                    <div class="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-lg">
                        <div class="flex items-center justify-between mb-2">
                            <span id="kpiTitleClicks" class="text-xs font-bold text-slate-400">النقرات (CTR)</span>
                            <span class="text-slate-500 text-xs">🎯</span>
                        </div>
                        <div class="text-2xl sm:text-3xl font-extrabold text-white font-num flex items-baseline gap-1.5">
                            <span id="kpi-clicks">0</span>
                            <span id="kpi-ctr" class="text-xs font-semibold text-emerald-400 font-num">(0.0%)</span>
                        </div>
                        <p id="kpiSubClicks" class="text-[11px] text-slate-500 mt-2">نسبة النقر إلى الظهور</p>
                    </div>

                </div>

                <!-- Charts Section -->
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <!-- Daily Revenue Chart (MAD) -->
                    <div class="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-lg">
                        <div class="flex items-center justify-between mb-6">
                            <div>
                                <h3 id="chartTitleRevenue" class="text-sm font-bold text-white flex items-center gap-2">
                                    <span>💰</span> منحنى الأرباح اليومية (بالدرهم المغربي)
                                </h3>
                                <p class="text-xs text-slate-400 mt-1 font-num">Make-Food.com AdSense Daily Revenue</p>
                            </div>
                            <span class="px-2 py-1 rounded bg-slate-800 text-[11px] text-emerald-400 font-bold font-num">MAD</span>
                        </div>
                        <div class="h-64">
                            <canvas id="revenueChart"></canvas>
                        </div>
                    </div>

                    <!-- Traffic & Impressions Chart -->
                    <div class="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-lg">
                        <div class="flex items-center justify-between mb-6">
                            <div>
                                <h3 id="chartTitleTraffic" class="text-sm font-bold text-white flex items-center gap-2">
                                    <span>📈</span> منحنى المشاهدات والظهور اليومي
                                </h3>
                                <p id="chartTitleTrafficSub" class="text-xs text-slate-400 mt-1">تطور الترافيك</p>
                            </div>
                            <span class="px-2 py-1 rounded bg-slate-800 text-[11px] text-slate-400 font-num">Views & Imps</span>
                        </div>
                        <div class="h-64">
                            <canvas id="trafficChart"></canvas>
                        </div>
                    </div>
                </div>

                <!-- Countries & Daily Breakdown Tables -->
                <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    
                    <!-- Top Countries -->
                    <div class="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-lg">
                        <h3 id="tableTitleCountries" class="text-sm font-bold text-white mb-1 flex items-center gap-2">
                            <span>🌍</span> مصادر الزيارات حسب الدول
                        </h3>
                        <p id="tableTitleCountriesSub" class="text-xs text-slate-400 mb-4">الأكثر جلباً للترافيك</p>
                        <div class="overflow-x-auto max-h-72 custom-scrollbar">
                            <table class="w-full text-right text-sm" id="countriesTableTag">
                                <thead>
                                    <tr class="text-slate-400 text-xs border-b border-slate-800">
                                        <th id="thCountry" class="pb-2 font-semibold">الدولة</th>
                                        <th id="thViews" class="pb-2 font-semibold font-num">الزيارات</th>
                                        <th id="thEarnings" class="pb-2 font-semibold font-num">الربح (MAD)</th>
                                    </tr>
                                </thead>
                                <tbody id="countriesTableBody" class="divide-y divide-slate-800/60 font-num">
                                    <tr><td colspan="3" class="py-4 text-center text-slate-500 text-xs">جاري التحميل...</td></tr>
                                </tbody>
                            </table>
                        </div>
                    </div>

                    <!-- Daily Performance Log Table -->
                    <div class="col-span-2 bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-lg">
                        <div class="flex items-center justify-between mb-4">
                            <div>
                                <h3 id="tableTitleDaily" class="text-sm font-bold text-white flex items-center gap-2">
                                    <span>📅</span> التقرير اليومي المفصل للأداء
                                </h3>
                                <p id="tableTitleDailySub" class="text-xs text-slate-400 mt-1">مداخيل كل يوم بالدرهم المغربي</p>
                            </div>
                            <button onclick="exportDailyCSV()" id="btnExportCSV" class="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs text-slate-300 font-num flex items-center gap-1 transition">
                                <span>📥</span> <span>Export CSV</span>
                            </button>
                        </div>
                        <div class="overflow-x-auto max-h-72 custom-scrollbar">
                            <table class="w-full text-right text-sm" id="dailyTableTag">
                                <thead>
                                    <tr class="text-slate-400 text-xs border-b border-slate-800">
                                        <th id="thDate" class="pb-2 font-semibold font-num">التاريخ</th>
                                        <th id="thDayViews" class="pb-2 font-semibold font-num">المشاهدات</th>
                                        <th id="thDayRPM" class="pb-2 font-semibold font-num">الـ RPM</th>
                                        <th id="thDayImps" class="pb-2 font-semibold font-num">الظهور</th>
                                        <th id="thDayClicks" class="pb-2 font-semibold font-num">النقرات</th>
                                        <th id="thDayEarn" class="pb-2 font-semibold font-num">الأرباح (MAD)</th>
                                    </tr>
                                </thead>
                                <tbody id="dailyTableBody" class="divide-y divide-slate-800/60 font-num">
                                    <tr><td colspan="6" class="py-4 text-center text-slate-500 text-xs">جاري التحميل...</td></tr>
                                </tbody>
                            </table>
                        </div>
                    </div>

                </div>

            </div>

            <!-- ================= TAB 2: POSTS & RECIPES FULL CRUD ================= -->
            <div id="tab-recipes" class="hidden space-y-6">
                
                <!-- Controls Bar -->
                <div class="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4 bg-slate-900/60 border border-slate-800/80 p-5 rounded-2xl">
                    <div>
                        <div class="flex items-center gap-2">
                            <h2 id="recipesListTitle" class="text-base font-bold text-white">جميع مقالات ووصفات make-food.com</h2>
                            <span id="recipes-count-badge" class="px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-num">
                                1,181
                            </span>
                        </div>
                        <p id="recipesListSub" class="text-xs text-slate-400 mt-1">تصفح، ابحث، عدّل أو احذف أي وصفة مع نشر فوري وتلقائي على الموقع الحي</p>
                    </div>

                    <!-- Search, Category Filter, and Add Button -->
                    <div class="flex flex-wrap items-center gap-2.5">
                        <div class="w-full sm:w-56">
                            <input type="text" id="recipeSearchInput" onkeyup="handleRecipeSearch()"
                                placeholder="🔍 ابحث عن أي وصفة..."
                                class="w-full px-3.5 py-2 bg-slate-800 border border-slate-700 rounded-xl text-white placeholder-slate-500 text-xs focus:outline-none focus:ring-2 focus:ring-emerald-500 transition">
                        </div>
                        
                        <div class="w-full sm:w-40">
                            <select id="recipeCategoryFilter" onchange="handleCategoryFilter()"
                                class="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-xl text-white text-xs focus:outline-none focus:ring-2 focus:ring-emerald-500 transition font-num">
                                <option value="all">كل التصنيفات (All)</option>
                            </select>
                        </div>

                        <button onclick="switchTab('create')" id="btnHeaderNewPost"
                            class="px-4 py-2 bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold rounded-xl text-xs shadow-md shadow-emerald-500/20 transition flex items-center gap-1.5 whitespace-nowrap">
                            <span>➕</span> <span id="btnHeaderNewPostText">مقال جديد</span>
                        </button>
                    </div>
                </div>

                <!-- Recipes Grid -->
                <div id="recipesGrid" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    <div class="col-span-3 text-center py-12 text-slate-500">جاري تحميل الوصفات...</div>
                </div>

                <!-- Load More Button -->
                <div id="loadMoreContainer" class="text-center py-4 hidden">
                    <button onclick="loadMoreRecipes()" id="btnLoadMore"
                        class="px-6 py-2.5 bg-slate-900 hover:bg-slate-800 border border-slate-700 rounded-xl text-xs font-bold text-slate-300 hover:text-white transition shadow-lg">
                        <span>⬇️</span> <span id="btnLoadMoreText">تحميل المزيد من الوصفات</span>
                    </button>
                </div>
            </div>

            <!-- ================= TAB 3: CREATE NEW POST (WITH AI ASSISTANT) ================= -->
            <div id="tab-create" class="hidden space-y-6">
                <div class="bg-slate-900 border border-slate-800/80 rounded-2xl p-6 sm:p-8 max-w-4xl mx-auto space-y-8">
                    
                    <!-- AI Generation Studio Box -->
                    <div class="bg-gradient-to-r from-emerald-950/40 via-slate-900 to-amber-950/40 border border-emerald-500/30 rounded-2xl p-6 relative overflow-hidden">
                        <div class="flex items-center justify-between mb-4">
                            <div class="flex items-center gap-2">
                                <span class="text-2xl">⚡</span>
                                <h3 id="aiStudioTitle" class="text-base font-bold text-white">المساعد الذكي لكتابة وإعادة صياغة الوصفات (AI Recipe Studio)</h3>
                            </div>
                            <span class="px-2.5 py-1 rounded-lg bg-emerald-500/10 text-emerald-400 text-xs font-bold border border-emerald-500/20 flex items-center gap-1">
                                <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                                <span id="activeAiModelBadge">Gemini / OpenRouter</span>
                            </span>
                        </div>

                        <!-- Mode Selector -->
                        <div class="flex items-center gap-2 mb-4 bg-slate-900/80 p-1 rounded-xl border border-slate-800 text-xs max-w-md">
                            <button onclick="setAiMode('name')" id="aiModeBtnName" class="flex-1 py-1.5 rounded-lg bg-emerald-500/20 text-emerald-300 font-bold transition">
                                💡 فقط باسم الوصفة
                            </button>
                            <button onclick="setAiMode('rewrite')" id="aiModeBtnRewrite" class="flex-1 py-1.5 rounded-lg text-slate-400 hover:text-white transition">
                                🔄 إعادة صياغة مقال / إلهام
                            </button>
                        </div>

                        <!-- Prompt Input -->
                        <div class="space-y-3">
                            <div id="aiNameInputBox">
                                <label id="lblAiName" class="block text-xs font-bold text-slate-300 mb-1">اكتب اسم الوصفة بالإنجليزية (مثال: Tuscan Garlic Butter Salmon):</label>
                                <input type="text" id="aiRecipeName" dir="ltr"
                                    placeholder="e.g. Creamy Tuscan Garlic Butter Salmon with Spinach"
                                    class="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-xl text-white text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 text-left font-num">
                            </div>

                            <div id="aiRewriteInputBox" class="hidden">
                                <label id="lblAiRewrite" class="block text-xs font-bold text-slate-300 mb-1">ضع رابط أو نص المقال الخارجي لإعادة صياغته بطريقة حصرية واحترافية:</label>
                                <textarea id="aiSourceContent" rows="4" dir="ltr"
                                    placeholder="Paste source recipe article or text here..."
                                    class="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-xl text-white text-xs focus:outline-none focus:ring-2 focus:ring-emerald-500 text-left font-num"></textarea>
                            </div>

                            <div class="flex items-center justify-between pt-2">
                                <p class="text-[11px] text-slate-400">
                                    💡 <span id="aiNoteText">يقوم الذكاء الاصطناعي بتوليد العنوان، المكونات، الخطوات، وقت الطهي، ومقالة SEO كاملة.</span>
                                </p>
                                <button type="button" onclick="triggerAiGeneration()" id="btnGenerateAi"
                                    class="py-2.5 px-6 bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-slate-950 font-extrabold rounded-xl shadow-lg shadow-emerald-500/20 transition text-xs flex items-center gap-2">
                                    <span>✨</span> <span id="btnTextGenerateAi">توليد الوصفة بالذكاء الاصطناعي</span>
                                </button>
                            </div>
                        </div>
                    </div>

                    <!-- Main Recipe Form -->
                    <form id="createRecipeForm" onsubmit="handleCreateRecipe(event)" class="space-y-6">
                        <div class="border-b border-slate-800 pb-4 flex items-center justify-between">
                            <div>
                                <h3 id="formSectionTitle" class="text-base font-bold text-white">تفاصيل المقال والوصفة لـ make-food.com</h3>
                                <p id="formSectionSub" class="text-xs text-slate-400 mt-1">راجع البيانات ثم اضغط نشر لتظهر فورياً على الموقع الحي</p>
                            </div>
                            <span class="text-xs text-slate-500 font-num">make-food.com</span>
                        </div>

                        <!-- Title & Slug -->
                        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                            <div>
                                <label id="lblPostTitle" class="block text-xs font-bold text-slate-300 mb-2">عنوان المقال (Title) *</label>
                                <input type="text" id="postTitle" required onkeyup="autoSlug()" dir="ltr"
                                    placeholder="e.g. Garlic Butter Roast Chicken"
                                    class="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-xl text-white text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 text-left font-num">
                            </div>
                            <div>
                                <label id="lblPostSlug" class="block text-xs font-bold text-slate-300 mb-2">الرابط الدائم (Slug) *</label>
                                <input type="text" id="postSlug" required dir="ltr"
                                    placeholder="garlic-butter-roast-chicken"
                                    class="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-xl text-white text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 text-left font-num">
                            </div>
                        </div>

                        <!-- Category, Author & Featured Image -->
                        <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
                            <div>
                                <label id="lblPostCategory" class="block text-xs font-bold text-slate-300 mb-2">التصنيف (Category)</label>
                                <select id="postCategory" class="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-xl text-white text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 font-num">
                                    <option value="Dinner">Dinner</option>
                                    <option value="Breakfast">Breakfast</option>
                                    <option value="Dessert">Dessert</option>
                                    <option value="Appetizer">Appetizer</option>
                                    <option value="Salad">Salad</option>
                                    <option value="Soup">Soup</option>
                                    <option value="Pasta">Pasta</option>
                                    <option value="Seafood">Seafood</option>
                                    <option value="Chicken">Chicken</option>
                                    <option value="Beef">Beef</option>
                                </select>
                            </div>
                            <div>
                                <label id="lblPostAuthor" class="block text-xs font-bold text-slate-300 mb-2">اسم الكاتب (Author)</label>
                                <input type="text" id="postAuthor" value="Maria" dir="ltr"
                                    class="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-xl text-white text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 text-left font-num">
                            </div>
                            <div>
                                <label id="lblPostImage" class="block text-xs font-bold text-slate-300 mb-2">رابط الصورة البارزة (Image URL)</label>
                                <input type="url" id="postImage" onchange="previewImage()" dir="ltr"
                                    placeholder="https://images.unsplash.com/photo-..."
                                    class="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-xl text-white text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 text-left font-num">
                            </div>
                        </div>

                        <!-- Image Preview Box -->
                        <div id="imagePreviewBox" class="hidden">
                            <img id="imagePreviewEl" src="" alt="Preview" class="w-full max-h-48 object-cover rounded-xl border border-slate-800">
                        </div>

                        <!-- Cooking Timers & Servings -->
                        <div class="grid grid-cols-3 gap-4 bg-slate-800/40 p-4 rounded-xl border border-slate-800 text-center font-num">
                            <div>
                                <label id="lblPrepTime" class="block text-xs font-semibold text-slate-400 mb-1">وقت التحضير (دقيقة)</label>
                                <input type="number" id="postPrepTime" value="15" min="1"
                                    class="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded-lg text-white text-center text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500">
                            </div>
                            <div>
                                <label id="lblCookTime" class="block text-xs font-semibold text-slate-400 mb-1">وقت الطهي (دقيقة)</label>
                                <input type="number" id="postCookTime" value="25" min="1"
                                    class="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded-lg text-white text-center text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500">
                            </div>
                            <div>
                                <label id="lblServings" class="block text-xs font-semibold text-slate-400 mb-1">عدد الحصص</label>
                                <input type="number" id="postServings" value="4" min="1"
                                    class="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded-lg text-white text-center text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500">
                            </div>
                        </div>

                        <!-- Description (SEO Meta) -->
                        <div>
                            <label id="lblPostDesc" class="block text-xs font-bold text-slate-300 mb-2">الوصف التعريفي (SEO Meta Description)</label>
                            <textarea id="postDescription" rows="2" dir="ltr"
                                placeholder="A mouthwatering recipe featuring tender chicken with crispy skin..."
                                class="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-xl text-white text-xs focus:outline-none focus:ring-2 focus:ring-emerald-500 text-left font-num"></textarea>
                        </div>

                        <!-- Ingredients & Instructions -->
                        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                            <div>
                                <label id="lblPostIngs" class="block text-xs font-bold text-slate-300 mb-2">المكونات (سطر لكل مكون) *</label>
                                <textarea id="postIngredients" rows="7" required dir="ltr"
                                    placeholder="1 whole chicken&#10;4 tbsp butter&#10;4 cloves garlic, minced&#10;1 tsp rosemary&#10;Salt and black pepper to taste"
                                    class="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-xl text-white text-xs font-mono focus:outline-none focus:ring-2 focus:ring-emerald-500 text-left"></textarea>
                            </div>
                            <div>
                                <label id="lblPostSteps" class="block text-xs font-bold text-slate-300 mb-2">خطوات التحضير (سطر لكل خطوة) *</label>
                                <textarea id="postInstructions" rows="7" required dir="ltr"
                                    placeholder="Preheat oven to 400°F (200°C).&#10;Pat chicken dry with paper towels.&#10;Rub butter, garlic and herbs under skin.&#10;Roast for 50-60 minutes until golden.&#10;Rest for 10 minutes before carving."
                                    class="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-xl text-white text-xs font-mono focus:outline-none focus:ring-2 focus:ring-emerald-500 text-left"></textarea>
                            </div>
                        </div>

                        <!-- Full Article HTML Content -->
                        <div>
                            <label id="lblPostHtml" class="block text-xs font-bold text-slate-300 mb-2">محتوى المقالة الكامل (Article HTML Content)</label>
                            <textarea id="postHtml" rows="8" dir="ltr"
                                placeholder="<p>Introduction text...</p>&#10;<h2>Why This Recipe Works</h2>&#10;<p>...</p>"
                                class="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-xl text-white text-xs font-mono focus:outline-none focus:ring-2 focus:ring-emerald-500 text-left"></textarea>
                        </div>

                        <!-- Submit Button -->
                        <div class="pt-4 border-t border-slate-800 flex items-center justify-between">
                            <p class="text-xs text-slate-400">
                                🚀 <span id="publishNoteText">سيتم النشر فورياً عبر Git وبناء الموقع الحي أوتوماتيكياً.</span>
                            </p>
                            <button type="submit" id="btnPublishRecipe"
                                class="py-3 px-8 bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-slate-950 font-extrabold rounded-xl shadow-lg shadow-emerald-500/25 transition text-sm flex items-center gap-2">
                                <span>🚀</span> <span id="btnTextPublish">نشر الوصفة مباشرة على make-food.com</span>
                            </button>
                        </div>
                    </form>

                </div>
            </div>

            <!-- ================= TAB 4: AI SETTINGS & MODEL FETCHER ================= -->
            <div id="tab-settings" class="space-y-6">
                <div class="bg-slate-900 border border-slate-800/80 rounded-2xl p-6 sm:p-8 max-w-3xl mx-auto space-y-6">
                    <div>
                        <h3 id="settingsTitle" class="text-base font-bold text-white flex items-center gap-2">
                            <span>⚙️</span> إعدادات نماذج الذكاء الاصطناعي (AI Provider & Models)
                        </h3>
                        <p id="settingsSub" class="text-xs text-slate-400 mt-1">
                            قم بربط مفتاح الـ API الخاص بك لجلب الموديلات المتوفرة وكتابة الوصفات تلقائياً.
                        </p>
                    </div>

                    <!-- Provider Selector -->
                    <div>
                        <label id="lblProvider" class="block text-xs font-bold text-slate-300 mb-2">اختر مزود الذكاء الاصطناعي (Provider)</label>
                        <div class="grid grid-cols-2 gap-4">
                            <label class="flex items-center gap-3 p-3 bg-slate-800/80 border border-slate-700 rounded-xl cursor-pointer hover:border-emerald-500/50 transition">
                                <input type="radio" name="ai_provider" value="google" checked onchange="handleProviderChange()" class="text-emerald-500 focus:ring-emerald-500">
                                <div>
                                    <div class="text-sm font-bold text-white flex items-center gap-1.5">
                                        <span>Google Gemini</span>
                                        <span class="text-[10px] bg-blue-500/10 text-blue-400 px-1.5 py-0.5 rounded font-num">Recommended</span>
                                    </div>
                                    <div class="text-[11px] text-slate-400">Gemini 1.5 Pro / Flash API</div>
                                </div>
                            </label>
                            
                            <label class="flex items-center gap-3 p-3 bg-slate-800/80 border border-slate-700 rounded-xl cursor-pointer hover:border-emerald-500/50 transition">
                                <input type="radio" name="ai_provider" value="openrouter" onchange="handleProviderChange()" class="text-emerald-500 focus:ring-emerald-500">
                                <div>
                                    <div class="text-sm font-bold text-white flex items-center gap-1.5">
                                        <span>OpenRouter</span>
                                        <span class="text-[10px] bg-purple-500/10 text-purple-400 px-1.5 py-0.5 rounded font-num">Multi-model</span>
                                    </div>
                                    <div class="text-[11px] text-slate-400">Claude, GPT-4o, Llama 3...</div>
                                </div>
                            </label>
                        </div>
                    </div>

                    <!-- API Key Input -->
                    <div>
                        <div class="flex items-center justify-between mb-2">
                            <label id="lblApiKey" class="text-xs font-bold text-slate-300">مفتاح الـ API (API Key)</label>
                            <span id="apiKeyHint" class="text-[11px] text-slate-500 font-num">Key is stored locally in your browser</span>
                        </div>
                        <div class="flex gap-2">
                            <input type="password" id="userApiKey" dir="ltr"
                                placeholder="AIzaSy... / sk-or-v1-..."
                                class="flex-1 px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-xl text-white text-xs font-mono focus:outline-none focus:ring-2 focus:ring-emerald-500 text-left">
                            <button type="button" onclick="saveApiKey()" id="btnSaveKey"
                                class="px-4 py-2.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 text-xs font-bold rounded-xl transition">
                                حفظ المفتاح
                            </button>
                        </div>
                    </div>

                    <!-- Model Selection & Fetch Button -->
                    <div class="bg-slate-800/40 p-4 rounded-xl border border-slate-800 space-y-3">
                        <div class="flex items-center justify-between">
                            <div>
                                <label id="lblModelSelect" class="block text-xs font-bold text-white">الموديل المختار للكتابة (Active Model)</label>
                                <p id="lblModelSelectSub" class="text-[11px] text-slate-400">انقر على جلب الموديلات لتحديث القائمة مباشرة من حسابك</p>
                            </div>
                            <button type="button" onclick="fetchAvailableModels()" id="btnFetchModels"
                                class="py-2 px-4 bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/30 rounded-xl text-xs font-bold transition flex items-center gap-1.5 font-num">
                                <span>🔄</span> <span id="btnTextFetchModels">جلب الموديلات المتوفرة (Fetch Models)</span>
                            </button>
                        </div>

                        <select id="selectedAiModel" onchange="saveActiveModel()"
                            class="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-xl text-white text-xs font-mono focus:outline-none focus:ring-2 focus:ring-emerald-500">
                            <option value="gemini-1.5-flash">gemini-1.5-flash (Default Fast)</option>
                            <option value="gemini-1.5-pro">gemini-1.5-pro (High Quality)</option>
                        </select>
                    </div>

                    <div class="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-xs text-emerald-300 flex items-start gap-2">
                        <span class="text-base">🔒</span>
                        <p id="securityNoteText">
                            مفتاح الـ API ديالك كيتحفظ بأمان فـ LocalStorage ديال المتصفح ديالك فقط، وماكيتخزنش فـ شي قاعدة بيانات خارجية.
                        </p>
                    </div>
                </div>
            </div>

        </main>

        <!-- ================= EDIT RECIPE MODAL (UPDATE) ================= -->
        <div id="editRecipeModal" class="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-md hidden items-center justify-center p-4">
            <div class="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-4xl max-h-[92vh] flex flex-col shadow-2xl overflow-hidden">
                
                <!-- Modal Header -->
                <div class="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/90">
                    <div class="flex items-center gap-2">
                        <span class="text-xl">✏️</span>
                        <div>
                            <h3 id="modalEditTitle" class="text-base font-bold text-white">تعديل الوصفة / Edit Recipe</h3>
                            <p id="modalEditSub" class="text-xs text-slate-400">تعديل المقال ونشره مباشرة على make-food.com</p>
                        </div>
                    </div>
                    <button onclick="closeEditModal()" class="w-8 h-8 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white flex items-center justify-center transition">
                        ✕
                    </button>
                </div>

                <!-- Modal Body (Scrollable) -->
                <form id="editRecipeForm" onsubmit="handleUpdateRecipe(event)" class="overflow-y-auto p-6 space-y-5 custom-scrollbar">
                    <input type="hidden" id="editOriginalSlug">

                    <!-- Title & Slug -->
                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div>
                            <label class="block text-xs font-bold text-slate-300 mb-1">عنوان المقال (Title) *</label>
                            <input type="text" id="editTitle" required dir="ltr"
                                class="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-xl text-white text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 font-num">
                        </div>
                        <div>
                            <label class="block text-xs font-bold text-slate-300 mb-1">الرابط الدائم (Slug) *</label>
                            <input type="text" id="editSlug" required dir="ltr"
                                class="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-xl text-white text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 font-num">
                        </div>
                    </div>

                    <!-- Category, Author & Image -->
                    <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
                        <div>
                            <label class="block text-xs font-bold text-slate-300 mb-1">التصنيف (Category)</label>
                            <input type="text" id="editCategory" dir="ltr"
                                class="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-xl text-white text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 font-num">
                        </div>
                        <div>
                            <label class="block text-xs font-bold text-slate-300 mb-1">اسم الكاتب (Author)</label>
                            <input type="text" id="editAuthor" dir="ltr"
                                class="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-xl text-white text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 font-num">
                        </div>
                        <div>
                            <label class="block text-xs font-bold text-slate-300 mb-1">رابط الصورة (Image URL)</label>
                            <input type="url" id="editImage" dir="ltr" onchange="previewEditImage()"
                                class="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-xl text-white text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 font-num">
                        </div>
                    </div>

                    <!-- Timers & Servings -->
                    <div class="grid grid-cols-3 gap-4 bg-slate-800/40 p-4 rounded-xl border border-slate-800 text-center font-num">
                        <div>
                            <label class="block text-xs font-semibold text-slate-400 mb-1">وقت التحضير (دقيقة)</label>
                            <input type="number" id="editPrepTime" min="1"
                                class="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded-lg text-white text-center text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500">
                        </div>
                        <div>
                            <label class="block text-xs font-semibold text-slate-400 mb-1">وقت الطهي (دقيقة)</label>
                            <input type="number" id="editCookTime" min="1"
                                class="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded-lg text-white text-center text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500">
                        </div>
                        <div>
                            <label class="block text-xs font-semibold text-slate-400 mb-1">عدد الحصص</label>
                            <input type="number" id="editServings" min="1"
                                class="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded-lg text-white text-center text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500">
                        </div>
                    </div>

                    <!-- Description -->
                    <div>
                        <label class="block text-xs font-bold text-slate-300 mb-1">الوصف التعريفي (Description / SEO)</label>
                        <textarea id="editDescription" rows="2" dir="ltr"
                            class="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-xl text-white text-xs focus:outline-none focus:ring-2 focus:ring-emerald-500 font-num"></textarea>
                    </div>

                    <!-- Ingredients & Steps -->
                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div>
                            <label class="block text-xs font-bold text-slate-300 mb-1">المكونات (سطر لكل مكون) *</label>
                            <textarea id="editIngredients" rows="7" required dir="ltr"
                                class="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-xl text-white text-xs font-mono focus:outline-none focus:ring-2 focus:ring-emerald-500"></textarea>
                        </div>
                        <div>
                            <label class="block text-xs font-bold text-slate-300 mb-1">خطوات التحضير (سطر لكل خطوة) *</label>
                            <textarea id="editInstructions" rows="7" required dir="ltr"
                                class="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-xl text-white text-xs font-mono focus:outline-none focus:ring-2 focus:ring-emerald-500"></textarea>
                        </div>
                    </div>

                    <!-- Article HTML -->
                    <div>
                        <label class="block text-xs font-bold text-slate-300 mb-1">محتوى المقالة الكامل (Article HTML)</label>
                        <textarea id="editHtml" rows="7" dir="ltr"
                            class="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-xl text-white text-xs font-mono focus:outline-none focus:ring-2 focus:ring-emerald-500"></textarea>
                    </div>

                    <!-- Modal Actions -->
                    <div class="pt-4 border-t border-slate-800 flex items-center justify-end gap-3">
                        <button type="button" onclick="closeEditModal()" id="btnCancelEdit"
                            class="px-5 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-bold transition">
                            إلغاء / Cancel
                        </button>
                        <button type="submit" id="btnSaveEditRecipe"
                            class="px-6 py-2.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-extrabold text-xs shadow-lg shadow-emerald-500/20 transition flex items-center gap-2">
                            <span>💾</span> <span id="btnTextSaveEdit">حفظ التعديل وإعادة النشر</span>
                        </button>
                    </div>
                </form>

            </div>
        </div>

        <!-- ================= DELETE CONFIRMATION MODAL (DELETE) ================= -->
        <div id="deleteConfirmModal" class="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-md hidden items-center justify-center p-4">
            <div class="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-md p-6 shadow-2xl space-y-4">
                <div class="w-12 h-12 rounded-2xl bg-rose-500/10 text-rose-400 border border-rose-500/20 flex items-center justify-center text-2xl mx-auto">
                    🗑️
                </div>
                <div class="text-center">
                    <h3 id="deleteModalTitle" class="text-base font-bold text-white">تأكيد حذف الوصفة / Confirm Deletion</h3>
                    <p id="deleteModalSub" class="text-xs text-slate-400 mt-1">هل أنت متأكد من رغبتك في حذف هذا المقال نهائياً من الموقع الحي؟</p>
                    <div id="deleteRecipeTargetTitle" class="mt-3 p-3 bg-slate-800/80 rounded-xl text-xs font-bold text-rose-300 font-num"></div>
                </div>
                <div class="flex items-center gap-3 pt-2">
                    <button type="button" onclick="closeDeleteModal()" id="btnCancelDelete"
                        class="flex-1 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-bold transition">
                        إلغاء
                    </button>
                    <button type="button" onclick="executeDeleteRecipe()" id="btnConfirmDeleteAction"
                        class="flex-1 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-extrabold shadow-lg shadow-rose-600/25 transition flex items-center justify-center gap-1.5">
                        <span>🗑️</span> <span id="btnTextConfirmDelete">نعم، احذف المقال</span>
                    </button>
                </div>
            </div>
        </div>

        <!-- Toast Notifications Container -->
        <div id="toastContainer" class="fixed bottom-6 left-6 z-50 flex flex-col gap-2 pointer-events-none"></div>

        <!-- Translation Dictionary & Core Frontend Script -->
        <script>
            let currentLang = localStorage.getItem('portal_lang') || 'ar';
            let currentRange = 'last30';
            let revenueChartInstance = null;
            let trafficChartInstance = null;
            let currentAiMode = 'name';
            
            // Recipes list state
            let allRecipesData = [];
            let currentOffset = 0;
            const pageSize = 30;
            let selectedCategory = 'all';
            let pendingDeleteSlug = null;

            const dict = {
                ar: {
                    topSubtitle: "لوحة الشريك الخاصة بالإحصائيات والمقالات",
                    tabAnalytics: "الإحصائيات والأرباح",
                    tabRecipes: "المقالات والوصفات (CRUD)",
                    tabCreate: "إنشاء مقال جديد",
                    tabSettings: "الإعدادات و الذكاء الاصطناعي",
                    logout: "خروج",
                    langBtn: "English",
                    kpiTitle: "مداخيل وزيارات الموقع الحي make-food.com",
                    kpiSub: "مربوطة بـ Google AdSense Management API ومحسوبة بالدرهم المغربي (MAD)",
                    earnings: "الأرباح المقدرة",
                    earningsSub: "100% مباشرة من AdSense للموقع",
                    views: "مشاهدات الصفحة",
                    viewsSub: "عدد الزيارات الإجمالية",
                    rpm: "معدل الألف (RPM)",
                    rpmSub: "الربح لكل 1,000 مشاهدة",
                    impressions: "مرات الظهور",
                    impressionsSub: "مرات عرض الإعلانات",
                    clicks: "النقرات (CTR)",
                    clicksSub: "نسبة النقر إلى الظهور",
                    chartRevenue: "💰 منحنى الأرباح اليومية (بالدرهم المغربي)",
                    chartTraffic: "📈 منحنى المشاهدات والظهور اليومي",
                    chartTrafficSub: "تطور الترافيك",
                    countriesTitle: "🌍 مصادر الزيارات حسب الدول",
                    countriesSub: "الأكثر جلباً للترافيك",
                    thCountry: "الدولة",
                    thViews: "الزيارات",
                    thEarn: "الربح (MAD)",
                    dailyTitle: "📅 التقرير اليومي المفصل للأداء",
                    dailySub: "مداخيل كل يوم بالدرهم المغربي",
                    thDate: "التاريخ",
                    thDayViews: "المشاهدات",
                    thDayRPM: "الـ RPM",
                    thDayImps: "الظهور",
                    thDayClicks: "النقرات",
                    thDayEarn: "الأرباح (MAD)",
                    recipesTitle: "جميع مقالات ووصفات make-food.com",
                    recipesSub: "تصفح، ابحث، عدّل أو احذف أي وصفة مع نشر فوري وتلقائي على الموقع الحي",
                    btnNewPost: "مقال جديد",
                    loadMoreText: "تحميل المزيد من الوصفات",
                    viewLive: "مشاهدة حية ↗",
                    editRecipe: "تعديل",
                    deleteRecipe: "حذف",
                    modalEditTitle: "تعديل الوصفة",
                    modalEditSub: "تعديل المقال ونشره مباشرة على make-food.com",
                    btnCancel: "إلغاء",
                    btnSaveEdit: "حفظ التعديل وإعادة النشر",
                    deleteModalTitle: "تأكيد حذف الوصفة",
                    deleteModalSub: "هل أنت متأكد من رغبتك في حذف هذا المقال نهائياً من الموقع الحي؟",
                    btnConfirmDelete: "نعم، احذف المقال"
                },
                en: {
                    topSubtitle: "Make-Food.com Partner Management & Content Portal",
                    tabAnalytics: "Revenue & Analytics",
                    tabRecipes: "Articles & Recipes (CRUD)",
                    tabCreate: "Create New Post",
                    tabSettings: "AI Settings & Models",
                    logout: "Logout",
                    langBtn: "العربية",
                    kpiTitle: "Live Performance & Revenue for make-food.com",
                    kpiSub: "Connected via Google AdSense Management API in Moroccan Dirham (MAD)",
                    earnings: "Estimated Earnings",
                    earningsSub: "100% direct from AdSense",
                    views: "Page Views",
                    viewsSub: "Total page impressions",
                    rpm: "Page RPM",
                    rpmSub: "Revenue per 1,000 views",
                    impressions: "Impressions",
                    impressionsSub: "Ad impressions delivered",
                    clicks: "Clicks (CTR)",
                    clicksSub: "Click-through rate",
                    chartRevenue: "💰 Daily Revenue Trend (Moroccan Dirham MAD)",
                    chartTraffic: "📈 Daily Views & Impressions",
                    chartTrafficSub: "Traffic metrics",
                    countriesTitle: "🌍 Traffic Breakdown by Country",
                    countriesSub: "Top traffic sources",
                    thCountry: "Country",
                    thViews: "Views",
                    thEarn: "Earnings (MAD)",
                    dailyTitle: "📅 Daily Performance Log",
                    dailySub: "Daily revenue & metrics in MAD",
                    thDate: "Date",
                    thDayViews: "Views",
                    thDayRPM: "RPM",
                    thDayImps: "Imps",
                    thDayClicks: "Clicks",
                    thDayEarn: "Earnings (MAD)",
                    recipesTitle: "All Articles & Recipes for make-food.com",
                    recipesSub: "Browse, search, edit, or delete any recipe with instant live deployment",
                    btnNewPost: "New Recipe",
                    loadMoreText: "Load More Recipes",
                    viewLive: "View Live ↗",
                    editRecipe: "Edit",
                    deleteRecipe: "Delete",
                    modalEditTitle: "Edit Recipe",
                    modalEditSub: "Modify content and deploy directly to make-food.com",
                    btnCancel: "Cancel",
                    btnSaveEdit: "Save & Redeploy",
                    deleteModalTitle: "Confirm Deletion",
                    deleteModalSub: "Are you sure you want to permanently delete this recipe from make-food.com?",
                    btnConfirmDelete: "Yes, Delete Recipe"
                }
            };

            function showToast(message, type = 'success') {
                const container = document.getElementById('toastContainer');
                const toast = document.createElement('div');
                toast.className = `px-4 py-3 rounded-xl shadow-2xl text-xs font-bold text-white flex items-center gap-2 pointer-events-auto transition-all duration-300 transform translate-y-2 opacity-0 ${type === 'error' ? 'bg-rose-600 border border-rose-500' : 'bg-emerald-600 border border-emerald-500'}`;
                toast.innerHTML = `<span>${type === 'error' ? '⚠️' : '✅'}</span> <span>${message}</span>`;
                container.appendChild(toast);
                setTimeout(() => {
                    toast.classList.remove('translate-y-2', 'opacity-0');
                }, 10);
                setTimeout(() => {
                    toast.classList.add('opacity-0');
                    setTimeout(() => toast.remove(), 300);
                }, 4000);
            }

            function applyLanguage(lang) {
                currentLang = lang;
                localStorage.setItem('portal_lang', lang);
                const html = document.getElementById('htmlRoot');
                const t = dict[lang];

                if (lang === 'en') {
                    html.setAttribute('lang', 'en');
                    html.setAttribute('dir', 'ltr');
                    document.getElementById('countriesTableTag').className = "w-full text-left text-sm";
                    document.getElementById('dailyTableTag').className = "w-full text-left text-sm";
                } else {
                    html.setAttribute('lang', 'ar');
                    html.setAttribute('dir', 'rtl');
                    document.getElementById('countriesTableTag').className = "w-full text-right text-sm";
                    document.getElementById('dailyTableTag').className = "w-full text-right text-sm";
                }

                document.getElementById('langBtnText').innerText = t.langBtn;
                document.getElementById('topSubtitle').innerText = t.topSubtitle;
                document.getElementById('tabNameAnalytics').innerText = t.tabAnalytics;
                document.getElementById('tabNameRecipes').innerText = t.tabRecipes;
                document.getElementById('tabNameCreate').innerText = t.tabCreate;
                document.getElementById('tabNameSettings').innerText = t.tabSettings;
                document.getElementById('logoutBtnText').innerText = t.logout;

                document.getElementById('kpiSectionTitle').innerText = t.kpiTitle;
                document.getElementById('kpiSectionSub').innerText = t.kpiSub;
                document.getElementById('kpiTitleEarnings').innerText = t.earnings;
                document.getElementById('kpiSubEarnings').innerText = t.earningsSub;
                document.getElementById('kpiTitleViews').innerText = t.views;
                document.getElementById('kpiSubViews').innerText = t.viewsSub;
                document.getElementById('kpiTitleRpm').innerText = t.rpm;
                document.getElementById('kpiSubRpm').innerText = t.rpmSub;
                document.getElementById('kpiTitleImps').innerText = t.impressions;
                document.getElementById('kpiSubImps').innerText = t.impressionsSub;
                document.getElementById('kpiTitleClicks').innerText = t.clicks;
                document.getElementById('kpiSubClicks').innerText = t.clicksSub;

                document.getElementById('chartTitleRevenue').innerText = t.chartRevenue;
                document.getElementById('chartTitleTraffic').innerText = t.chartTraffic;
                document.getElementById('chartTitleTrafficSub').innerText = t.chartTrafficSub;
                document.getElementById('tableTitleCountries').innerText = t.countriesTitle;
                document.getElementById('tableTitleCountriesSub').innerText = t.countriesSub;
                document.getElementById('thCountry').innerText = t.thCountry;
                document.getElementById('thViews').innerText = t.thViews;
                document.getElementById('thEarnings').innerText = t.thEarn;

                document.getElementById('tableTitleDaily').innerText = t.dailyTitle;
                document.getElementById('tableTitleDailySub').innerText = t.dailySub;
                document.getElementById('thDate').innerText = t.thDate;
                document.getElementById('thDayViews').innerText = t.thDayViews;
                document.getElementById('thDayRPM').innerText = t.thDayRPM;
                document.getElementById('thDayImps').innerText = t.thDayImps;
                document.getElementById('thDayClicks').innerText = t.thDayClicks;
                document.getElementById('thDayEarn').innerText = t.thDayEarn;

                document.getElementById('recipesListTitle').innerText = t.recipesTitle;
                document.getElementById('recipesListSub').innerText = t.recipesSub;
                document.getElementById('btnHeaderNewPostText').innerText = t.btnNewPost;
                document.getElementById('btnLoadMoreText').innerText = t.loadMoreText;

                document.getElementById('modalEditTitle').innerText = t.modalEditTitle;
                document.getElementById('modalEditSub').innerText = t.modalEditSub;
                document.getElementById('btnCancelEdit').innerText = t.btnCancel;
                document.getElementById('btnTextSaveEdit').innerText = t.btnSaveEdit;
                document.getElementById('deleteModalTitle').innerText = t.deleteModalTitle;
                document.getElementById('deleteModalSub').innerText = t.deleteModalSub;
                document.getElementById('btnCancelDelete').innerText = t.btnCancel;
                document.getElementById('btnTextConfirmDelete').innerText = t.btnConfirmDelete;

                renderRecipesGrid(allRecipesData, false);
            }

            function toggleLanguage() {
                applyLanguage(currentLang === 'ar' ? 'en' : 'ar');
            }

            function switchTab(tabId) {
                ['analytics', 'recipes', 'create', 'settings'].forEach(id => {
                    const tabEl = document.getElementById(`tab-${id}`);
                    const navEl = document.getElementById(`nav-${id}`);
                    if (id === tabId) {
                        tabEl.classList.remove('hidden');
                        navEl.className = "px-3 py-2 rounded-xl text-xs sm:text-sm font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 transition flex items-center gap-1.5";
                    } else {
                        tabEl.classList.add('hidden');
                        navEl.className = "px-3 py-2 rounded-xl text-xs sm:text-sm font-semibold text-slate-400 hover:text-white hover:bg-slate-800/60 transition flex items-center gap-1.5";
                    }
                });
                if (tabId === 'recipes' && allRecipesData.length === 0) {
                    loadRecipesList(true);
                }
            }

            async function loadStats(range) {
                currentRange = range;
                ['today', 'yesterday', 'last7', 'last30', 'month'].forEach(r => {
                    const btn = document.getElementById(`btn-${r}`);
                    if (r === range) {
                        btn.className = "px-2.5 py-1.5 rounded-lg bg-emerald-500/20 text-emerald-300 font-bold border border-emerald-500/30 transition";
                    } else {
                        btn.className = "px-2.5 py-1.5 rounded-lg text-slate-400 hover:text-white transition";
                    }
                });

                try {
                    const res = await fetch(`/api/stats?range=${range}`);
                    const data = await res.json();
                    
                    document.getElementById('kpi-earnings').innerText = Number(data.totals.earnings).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
                    document.getElementById('kpi-views').innerText = Number(data.totals.views).toLocaleString();
                    document.getElementById('kpi-rpm').innerText = Number(data.totals.rpm).toFixed(2);
                    document.getElementById('kpi-impressions').innerText = Number(data.totals.impressions).toLocaleString();
                    document.getElementById('kpi-clicks').innerText = Number(data.totals.clicks).toLocaleString();
                    document.getElementById('kpi-ctr').innerText = `(${data.totals.ctr}%)`;

                    renderCharts(data.daily);
                    renderCountries(data.countries);
                    renderDailyTable(data.daily);
                } catch (e) {
                    console.error("Failed to load stats:", e);
                }
            }

            function changeRange(range) {
                loadStats(range);
            }

            function renderCharts(dailyData) {
                const labels = dailyData.map(d => d.date.slice(5));
                const earnings = dailyData.map(d => d.earnings);
                const views = dailyData.map(d => d.views);
                const impressions = dailyData.map(d => d.impressions);

                if (revenueChartInstance) revenueChartInstance.destroy();
                const ctxRev = document.getElementById('revenueChart').getContext('2d');
                revenueChartInstance = new Chart(ctxRev, {
                    type: 'line',
                    data: {
                        labels: labels,
                        datasets: [{
                            label: currentLang === 'ar' ? 'الأرباح (د.م.)' : 'Earnings (MAD)',
                            data: earnings,
                            borderColor: '#10b981',
                            backgroundColor: 'rgba(16, 185, 129, 0.1)',
                            borderWidth: 2,
                            fill: true,
                            tension: 0.3
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { display: false } },
                        scales: {
                            x: { grid: { color: 'rgba(51, 65, 85, 0.3)' }, ticks: { color: '#94a3b8' } },
                            y: { grid: { color: 'rgba(51, 65, 85, 0.3)' }, ticks: { color: '#94a3b8' } }
                        }
                    }
                });

                if (trafficChartInstance) trafficChartInstance.destroy();
                const ctxTr = document.getElementById('trafficChart').getContext('2d');
                trafficChartInstance = new Chart(ctxTr, {
                    type: 'bar',
                    data: {
                        labels: labels,
                        datasets: [
                            {
                                label: currentLang === 'ar' ? 'مشاهدات الصفحة' : 'Pageviews',
                                data: views,
                                backgroundColor: '#38bdf8',
                                borderRadius: 4
                            },
                            {
                                label: currentLang === 'ar' ? 'مرات الظهور' : 'Impressions',
                                data: impressions,
                                backgroundColor: 'rgba(56, 189, 248, 0.3)',
                                borderRadius: 4
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { labels: { color: '#cbd5e1' } } },
                        scales: {
                            x: { grid: { display: false }, ticks: { color: '#94a3b8' } },
                            y: { grid: { color: 'rgba(51, 65, 85, 0.3)' }, ticks: { color: '#94a3b8' } }
                        }
                    }
                });
            }

            function renderCountries(countries) {
                const tbody = document.getElementById('countriesTableBody');
                if (!countries || !countries.length) {
                    tbody.innerHTML = '<tr><td colspan="3" class="py-4 text-center text-slate-500 text-xs">لا تتوفر بيانات</td></tr>';
                    return;
                }
                tbody.innerHTML = countries.map(c => `
                    <tr class="hover:bg-slate-800/40 transition">
                        <td class="py-2.5 font-medium text-slate-200">${c.country}</td>
                        <td class="py-2.5 text-slate-400">${c.views.toLocaleString()}</td>
                        <td class="py-2.5 font-bold text-emerald-400">${c.earnings.toFixed(2)}</td>
                    </tr>
                `).join('');
            }

            let dailyDataCache = [];
            function renderDailyTable(daily) {
                dailyDataCache = daily;
                const tbody = document.getElementById('dailyTableBody');
                if (!daily || !daily.length) {
                    tbody.innerHTML = '<tr><td colspan="6" class="py-4 text-center text-slate-500 text-xs">لا تتوفر بيانات</td></tr>';
                    return;
                }
                const sorted = [...daily].reverse();
                tbody.innerHTML = sorted.map(d => `
                    <tr class="hover:bg-slate-800/40 transition">
                        <td class="py-2.5 font-bold text-white">${d.date}</td>
                        <td class="py-2.5 text-slate-300">${d.views.toLocaleString()}</td>
                        <td class="py-2.5 text-amber-400 font-semibold">${d.rpm.toFixed(2)}</td>
                        <td class="py-2.5 text-slate-400">${d.impressions.toLocaleString()}</td>
                        <td class="py-2.5 text-slate-400">${d.clicks}</td>
                        <td class="py-2.5 font-extrabold text-emerald-400">${d.earnings.toFixed(2)}</td>
                    </tr>
                `).join('');
            }

            function exportDailyCSV() {
                if (!dailyDataCache.length) return;
                let csv = "Date,Page Views,Page RPM (MAD),Impressions,Clicks,Earnings (MAD)\n";
                dailyDataCache.forEach(d => {
                    csv += `${d.date},${d.views},${d.rpm},${d.impressions},${d.clicks},${d.earnings}\n`;
                });
                const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `makefood-adsense-${currentRange}.csv`;
                a.click();
            }

            // ================= RECIPES FULL CRUD (LIST, READ, UPDATE, DELETE) =================
            async function loadRecipesList(reset = false) {
                if (reset) {
                    currentOffset = 0;
                    allRecipesData = [];
                }
                const search = document.getElementById('recipeSearchInput').value || '';
                const category = document.getElementById('recipeCategoryFilter').value || 'all';

                try {
                    const res = await fetch(`/api/recipes?search=${encodeURIComponent(search)}&category=${encodeURIComponent(category)}&limit=${pageSize}&offset=${currentOffset}`);
                    const data = await res.json();
                    
                    if (reset) {
                        allRecipesData = data.recipes || [];
                    } else {
                        allRecipesData = allRecipesData.concat(data.recipes || []);
                    }

                    document.getElementById('recipes-count-badge').innerText = `${data.total.toLocaleString()} recipes`;

                    // Populate categories dropdown if empty
                    const catSelect = document.getElementById('recipeCategoryFilter');
                    if (catSelect.options.length <= 1 && data.categories && data.categories.length) {
                        data.categories.forEach(cat => {
                            const opt = document.createElement('option');
                            opt.value = cat;
                            opt.innerText = cat;
                            catSelect.appendChild(opt);
                        });
                    }

                    renderRecipesGrid(allRecipesData, false);

                    // Show/hide Load More
                    const loadMoreContainer = document.getElementById('loadMoreContainer');
                    if (data.has_more) {
                        loadMoreContainer.classList.remove('hidden');
                    } else {
                        loadMoreContainer.classList.add('hidden');
                    }
                } catch (e) {
                    console.error("Failed to load recipes:", e);
                }
            }

            function loadMoreRecipes() {
                currentOffset += pageSize;
                loadRecipesList(false);
            }

            function handleCategoryFilter() {
                loadRecipesList(true);
            }

            let searchTimeout = null;
            function handleRecipeSearch() {
                clearTimeout(searchTimeout);
                searchTimeout = setTimeout(() => {
                    loadRecipesList(true);
                }, 300);
            }

            function renderRecipesGrid(recipes, append = false) {
                const container = document.getElementById('recipesGrid');
                if (!recipes.length) {
                    container.innerHTML = '<div class="col-span-3 text-center py-12 text-slate-500">No recipes found matching your query.</div>';
                    return;
                }
                const t = dict[currentLang];
                container.innerHTML = recipes.map(r => `
                    <div class="bg-slate-900 border border-slate-800 rounded-2xl p-4 flex flex-col justify-between hover:border-slate-700 transition shadow-lg group">
                        <div class="flex gap-4">
                            <img src="${r.image || 'https://images.unsplash.com/photo-1495521821757-a1efb6729352?auto=format&fit=crop&w=300&q=80'}" alt="${r.title}" class="w-20 h-20 rounded-xl object-cover border border-slate-800 flex-shrink-0">
                            <div class="overflow-hidden w-full">
                                <span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20 font-num">
                                    ${r.category}
                                </span>
                                <h3 class="text-xs sm:text-sm font-bold text-white mt-1.5 truncate group-hover:text-emerald-400 transition" title="${r.title}">${r.title}</h3>
                                <p class="text-[11px] text-slate-400 mt-1 font-num">${r.prep_time || '15 min'} • ${r.servings || '4 servings'}</p>
                            </div>
                        </div>

                        <!-- Card Action Buttons (View, Edit, Delete) -->
                        <div class="flex items-center justify-between pt-3 border-t border-slate-800/80 mt-3">
                            <span class="text-[10px] text-slate-500 font-num">${r.published_at ? r.published_at.slice(0, 10) : ''}</span>
                            
                            <div class="flex items-center gap-1.5">
                                <a href="${r.url}" target="_blank" class="px-2 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-[11px] font-bold text-emerald-400 hover:text-emerald-300 transition flex items-center gap-0.5 font-num" title="View live page">
                                    <span>👁️</span> <span>${t.viewLive}</span>
                                </a>
                                <button onclick="openEditModal('${r.slug}')" class="px-2 py-1 rounded-lg bg-blue-500/10 hover:bg-blue-500/20 border border-blue-500/20 text-[11px] font-bold text-blue-400 hover:text-blue-300 transition flex items-center gap-0.5" title="Edit recipe">
                                    <span>✏️</span> <span>${t.editRecipe}</span>
                                </button>
                                <button onclick="confirmDeleteRecipe('${r.slug}', '${encodeURIComponent(r.title)}')" class="px-2 py-1 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/20 text-[11px] font-bold text-rose-400 hover:text-rose-300 transition flex items-center gap-0.5" title="Delete recipe">
                                    <span>🗑️</span>
                                </button>
                            </div>
                        </div>
                    </div>
                `).join('');
            }

            // Edit Recipe Modal
            async function openEditModal(slug) {
                const modal = document.getElementById('editRecipeModal');
                modal.classList.remove('hidden');
                modal.classList.add('flex');

                document.getElementById('btnSaveEditRecipe').disabled = true;
                document.getElementById('btnTextSaveEdit').innerText = 'Loading...';

                try {
                    const res = await fetch(`/api/recipes/get/${slug}`);
                    const data = await res.json();
                    if (!data.success) throw new Error(data.detail || "Failed to load recipe details");

                    const r = data.recipe;
                    document.getElementById('editOriginalSlug').value = r.original_slug;
                    document.getElementById('editTitle').value = r.title;
                    document.getElementById('editSlug').value = r.slug;
                    document.getElementById('editCategory').value = r.category;
                    document.getElementById('editAuthor').value = r.author;
                    document.getElementById('editImage').value = r.featured_image;
                    document.getElementById('editPrepTime').value = r.prep_time;
                    document.getElementById('editCookTime').value = r.cook_time;
                    document.getElementById('editServings').value = r.servings;
                    document.getElementById('editDescription').value = r.description;
                    document.getElementById('editIngredients').value = r.ingredients_raw;
                    document.getElementById('editInstructions').value = r.instructions_raw;
                    document.getElementById('editHtml').value = r.article_html;

                    document.getElementById('btnSaveEditRecipe').disabled = false;
                    document.getElementById('btnTextSaveEdit').innerText = dict[currentLang].btnSaveEdit;
                } catch (e) {
                    showToast(e.message, 'error');
                    closeEditModal();
                }
            }

            function closeEditModal() {
                const modal = document.getElementById('editRecipeModal');
                modal.classList.add('hidden');
                modal.classList.remove('flex');
            }

            async function handleUpdateRecipe(e) {
                e.preventDefault();
                const btn = document.getElementById('btnSaveEditRecipe');
                const btnText = document.getElementById('btnTextSaveEdit');
                btn.disabled = true;
                btnText.innerText = currentLang === 'ar' ? 'جاري الحفظ وإعادة البناء...' : 'Saving & Redeploying...';

                const formData = new FormData();
                formData.append('original_slug', document.getElementById('editOriginalSlug').value);
                formData.append('title', document.getElementById('editTitle').value);
                formData.append('slug', document.getElementById('editSlug').value);
                formData.append('category', document.getElementById('editCategory').value);
                formData.append('author', document.getElementById('editAuthor').value);
                formData.append('featured_image', document.getElementById('editImage').value);
                formData.append('prep_time', document.getElementById('editPrepTime').value);
                formData.append('cook_time', document.getElementById('editCookTime').value);
                formData.append('servings', document.getElementById('editServings').value);
                formData.append('description', document.getElementById('editDescription').value);
                formData.append('ingredients_raw', document.getElementById('editIngredients').value);
                formData.append('instructions_raw', document.getElementById('editInstructions').value);
                formData.append('article_html', document.getElementById('editHtml').value);

                try {
                    const res = await fetch('/api/recipes/update', { method: 'POST', body: formData });
                    const data = await res.json();
                    if (!data.success) throw new Error(data.error || "Update failed");

                    showToast(data.message, 'success');
                    closeEditModal();
                    loadRecipesList(true);
                } catch (err) {
                    showToast(err.message, 'error');
                } finally {
                    btn.disabled = false;
                    btnText.innerText = dict[currentLang].btnSaveEdit;
                }
            }

            // Delete Recipe Modal
            function confirmDeleteRecipe(slug, encodedTitle) {
                pendingDeleteSlug = slug;
                const title = decodeURIComponent(encodedTitle);
                document.getElementById('deleteRecipeTargetTitle').innerText = title;
                const modal = document.getElementById('deleteConfirmModal');
                modal.classList.remove('hidden');
                modal.classList.add('flex');
            }

            function closeDeleteModal() {
                pendingDeleteSlug = null;
                const modal = document.getElementById('deleteConfirmModal');
                modal.classList.add('hidden');
                modal.classList.remove('flex');
            }

            async function executeDeleteRecipe() {
                if (!pendingDeleteSlug) return;
                const btn = document.getElementById('btnConfirmDeleteAction');
                const btnText = document.getElementById('btnTextConfirmDelete');
                btn.disabled = true;
                btnText.innerText = currentLang === 'ar' ? 'جاري الحذف...' : 'Deleting...';

                const formData = new FormData();
                formData.append('slug', pendingDeleteSlug);

                try {
                    const res = await fetch('/api/recipes/delete', { method: 'POST', body: formData });
                    const data = await res.json();
                    if (!data.success) throw new Error(data.error || "Delete failed");

                    showToast(data.message, 'success');
                    closeDeleteModal();
                    loadRecipesList(true);
                } catch (err) {
                    showToast(err.message, 'error');
                } finally {
                    btn.disabled = false;
                    btnText.innerText = dict[currentLang].btnConfirmDelete;
                }
            }

            // Create Recipe Form Handlers
            function autoSlug() {
                const title = document.getElementById('postTitle').value;
                const slugInput = document.getElementById('postSlug');
                slugInput.value = title.trim().toLowerCase()
                    .replace(/[^a-z0-9\s-]/g, '')
                    .replace(/[\s_-]+/g, '-')
                    .replace(/^-+|-+$/g, '');
            }

            function previewImage() {
                const url = document.getElementById('postImage').value;
                const box = document.getElementById('imagePreviewBox');
                const img = document.getElementById('imagePreviewEl');
                if (url) {
                    img.src = url;
                    box.classList.remove('hidden');
                } else {
                    box.classList.add('hidden');
                }
            }

            // AI Studio & Settings
            function setAiMode(mode) {
                currentAiMode = mode;
                const btnName = document.getElementById('aiModeBtnName');
                const btnRewrite = document.getElementById('aiModeBtnRewrite');
                const nameBox = document.getElementById('aiNameInputBox');
                const rewriteBox = document.getElementById('aiRewriteInputBox');

                if (mode === 'name') {
                    btnName.className = "flex-1 py-1.5 rounded-lg bg-emerald-500/20 text-emerald-300 font-bold transition";
                    btnRewrite.className = "flex-1 py-1.5 rounded-lg text-slate-400 hover:text-white transition";
                    nameBox.classList.remove('hidden');
                    rewriteBox.classList.add('hidden');
                } else {
                    btnRewrite.className = "flex-1 py-1.5 rounded-lg bg-emerald-500/20 text-emerald-300 font-bold transition";
                    btnName.className = "flex-1 py-1.5 rounded-lg text-slate-400 hover:text-white transition";
                    rewriteBox.classList.remove('hidden');
                    nameBox.classList.add('hidden');
                }
            }

            function getActiveProvider() {
                const radios = document.getElementsByName('ai_provider');
                for (const r of radios) {
                    if (r.checked) return r.value;
                }
                return 'google';
            }

            function handleProviderChange() {
                const provider = getActiveProvider();
                const key = localStorage.getItem(`ai_key_${provider}`) || '';
                document.getElementById('userApiKey').value = key;
                updateActiveModelBadge();
            }

            function saveApiKey() {
                const provider = getActiveProvider();
                const key = document.getElementById('userApiKey').value.trim();
                localStorage.setItem(`ai_key_${provider}`, key);
                showToast(currentLang === 'ar' ? 'تم حفظ المفتاح بأمان في المتصفح!' : 'API Key saved securely in browser!');
                updateActiveModelBadge();
            }

            function saveActiveModel() {
                const model = document.getElementById('selectedAiModel').value;
                localStorage.setItem('active_ai_model', model);
                updateActiveModelBadge();
            }

            function updateActiveModelBadge() {
                const provider = getActiveProvider();
                const model = localStorage.getItem('active_ai_model') || (provider === 'google' ? 'gemini-1.5-flash' : 'openai/gpt-4o');
                const badge = document.getElementById('activeAiModelBadge');
                badge.innerText = `${provider.toUpperCase()}: ${model.split('/').pop()}`;
            }

            async function fetchAvailableModels() {
                const provider = getActiveProvider();
                const apiKey = document.getElementById('userApiKey').value.trim() || localStorage.getItem(`ai_key_${provider}`);
                if (!apiKey) {
                    showToast(currentLang === 'ar' ? 'يرجى إدخال مفتاح الـ API أولاً' : 'Please enter an API Key first', 'error');
                    return;
                }

                const btn = document.getElementById('btnFetchModels');
                const btnText = document.getElementById('btnTextFetchModels');
                btn.disabled = true;
                btnText.innerText = currentLang === 'ar' ? 'جاري جلب الموديلات...' : 'Fetching models...';

                try {
                    const res = await fetch('/api/ai/models', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ provider: provider, api_key: apiKey })
                    });
                    const data = await res.json();
                    if (!data.success) throw new Error(data.error || "Failed to fetch models");

                    const select = document.getElementById('selectedAiModel');
                    select.innerHTML = '';
                    data.models.forEach(m => {
                        const opt = document.createElement('option');
                        opt.value = m.id;
                        opt.innerText = `${m.name} (${m.id})`;
                        select.appendChild(opt);
                    });

                    saveActiveModel();
                    showToast(currentLang === 'ar' ? `تم جلب ${data.models.length} موديل متوفر بنجاح!` : `Successfully fetched ${data.models.length} models!`);
                } catch (e) {
                    showToast(e.message, 'error');
                } finally {
                    btn.disabled = false;
                    btnText.innerText = currentLang === 'ar' ? 'جلب الموديلات المتوفرة (Fetch Models)' : 'Fetch Models';
                }
            }

            async function triggerAiGeneration() {
                const provider = getActiveProvider();
                const apiKey = document.getElementById('userApiKey').value.trim() || localStorage.getItem(`ai_key_${provider}`);
                if (!apiKey) {
                    showToast(currentLang === 'ar' ? 'يرجى ضبط مفتاح الـ API في تبويب الإعدادات أولاً' : 'Please configure your API Key in Settings first', 'error');
                    switchTab('settings');
                    return;
                }

                const model = document.getElementById('selectedAiModel').value || (provider === 'google' ? 'gemini-1.5-flash' : 'openai/gpt-4o');
                const inputText = currentAiMode === 'name' ? document.getElementById('aiRecipeName').value.trim() : document.getElementById('aiSourceContent').value.trim();

                if (!inputText) {
                    showToast(currentLang === 'ar' ? 'يرجى إدخال اسم الوصفة أو النص الملهم أولاً' : 'Please enter a recipe title or inspiration text first', 'error');
                    return;
                }

                const btn = document.getElementById('btnGenerateAi');
                const btnText = document.getElementById('btnTextGenerateAi');
                btn.disabled = true;
                btnText.innerText = currentLang === 'ar' ? 'جاري الكتابة بالذكاء الاصطناعي... ⏳' : 'Generating with AI... ⏳';

                try {
                    const res = await fetch('/api/ai/generate', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            provider: provider,
                            api_key: apiKey,
                            model: model,
                            mode: currentAiMode,
                            input_text: inputText
                        })
                    });
                    const data = await res.json();
                    if (!data.success) throw new Error(data.error || "Generation failed");

                    const rec = data.recipe;
                    document.getElementById('postTitle').value = rec.title || '';
                    document.getElementById('postSlug').value = rec.slug || '';
                    if (rec.category) document.getElementById('postCategory').value = rec.category;
                    if (rec.prep_time) document.getElementById('postPrepTime').value = rec.prep_time;
                    if (rec.cook_time) document.getElementById('postCookTime').value = rec.cook_time;
                    if (rec.servings) document.getElementById('postServings').value = rec.servings;
                    if (rec.description) document.getElementById('postDescription').value = rec.description;

                    if (rec.ingredients && Array.isArray(rec.ingredients)) {
                        document.getElementById('postIngredients').value = rec.ingredients.join('\n');
                    }
                    if (rec.instructions && Array.isArray(rec.instructions)) {
                        document.getElementById('postInstructions').value = rec.instructions.join('\n');
                    }
                    if (rec.article_html) {
                        document.getElementById('postHtml').value = rec.article_html;
                    }

                    showToast(currentLang === 'ar' ? 'تم توليد المقال والوصفة بنجاح!' : 'Recipe generated successfully!');
                } catch (e) {
                    showToast(e.message, 'error');
                } finally {
                    btn.disabled = false;
                    btnText.innerText = currentLang === 'ar' ? 'توليد الوصفة بالذكاء الاصطناعي' : 'Generate with AI';
                }
            }

            async function handleCreateRecipe(e) {
                e.preventDefault();
                const btn = document.getElementById('btnPublishRecipe');
                const btnText = document.getElementById('btnTextPublish');
                btn.disabled = true;
                btnText.innerText = currentLang === 'ar' ? 'جاري النشر وبناء الموقع... ⏳' : 'Publishing & Deploying... ⏳';

                const formData = new FormData();
                formData.append('title', document.getElementById('postTitle').value);
                formData.append('slug', document.getElementById('postSlug').value);
                formData.append('category', document.getElementById('postCategory').value);
                formData.append('author', document.getElementById('postAuthor').value);
                formData.append('featured_image', document.getElementById('postImage').value);
                formData.append('prep_time', document.getElementById('postPrepTime').value);
                formData.append('cook_time', document.getElementById('postCookTime').value);
                formData.append('servings', document.getElementById('postServings').value);
                formData.append('description', document.getElementById('postDescription').value);
                formData.append('ingredients_raw', document.getElementById('postIngredients').value);
                formData.append('instructions_raw', document.getElementById('postInstructions').value);
                formData.append('article_html', document.getElementById('postHtml').value);

                try {
                    const res = await fetch('/api/recipes/create', { method: 'POST', body: formData });
                    const data = await res.json();
                    if (!data.success) throw new Error(data.error || "Publication failed");

                    showToast(data.message, 'success');
                    document.getElementById('createRecipeForm').reset();
                    switchTab('recipes');
                    loadRecipesList(true);
                } catch (err) {
                    showToast(err.message, 'error');
                } finally {
                    btn.disabled = false;
                    btnText.innerText = currentLang === 'ar' ? 'نشر الوصفة مباشرة على make-food.com' : 'Publish to make-food.com';
                }
            }

            // Initialization on page load
            window.addEventListener('DOMContentLoaded', () => {
                applyLanguage(currentLang);
                loadStats('last30');
                handleProviderChange();
            });
        </script>
    </body>
    </html>
    """)

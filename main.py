import os
import json
import time
import hmac
import hashlib
import urllib.request
import urllib.parse
from datetime import datetime
from typing import Optional, List

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
    
    # Fetch from GitHub raw
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
        return recipes_cache.get("data", [])

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

# ================= AUTH ROUTES =================
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if is_authenticated(request):
        return RedirectResponse(url="/", status_code=302)
    return """
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>تسجيل الدخول — Make-Food.com Partner Portal</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;800&family=Plus+Jakarta+Sans:wght@500;700&display=swap" rel="stylesheet">
        <style>body { font-family: 'Tajawal', sans-serif; }</style>
    </head>
    <body class="bg-slate-950 text-slate-100 min-h-screen flex items-center justify-center p-4">
        <div class="w-full max-w-md">
            <div class="bg-slate-900 border border-slate-800 rounded-2xl p-8 shadow-2xl relative overflow-hidden">
                <div class="absolute -top-24 -right-24 w-48 h-48 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none"></div>
                <div class="absolute -bottom-24 -left-24 w-48 h-48 bg-amber-500/10 rounded-full blur-3xl pointer-events-none"></div>

                <div class="text-center mb-8 relative">
                    <div class="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-tr from-amber-500 to-emerald-500 p-0.5 mb-4 shadow-lg shadow-emerald-500/20">
                        <div class="w-full h-full bg-slate-900 rounded-[14px] flex items-center justify-center text-3xl">
                            🍲
                        </div>
                    </div>
                    <h1 class="text-2xl font-extrabold tracking-tight text-white font-['Plus_Jakarta_Sans']">Make-Food.com</h1>
                    <p class="text-sm text-slate-400 mt-1">بوابة إدارة الموقع، المقالات والأرباح</p>
                </div>

                <form method="POST" action="/login" class="space-y-5">
                    <div>
                        <label class="block text-xs font-bold text-slate-300 mb-2">اسم المستخدم (Username)</label>
                        <input type="text" name="username" required autocomplete="username" dir="ltr"
                            placeholder="partner_makefood"
                            class="w-full px-4 py-3 bg-slate-800/80 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition text-left">
                    </div>
                    <div>
                        <label class="block text-xs font-bold text-slate-300 mb-2">كلمة المرور (Password)</label>
                        <input type="password" name="password" required autocomplete="current-password" dir="ltr"
                            placeholder="••••••••••••"
                            class="w-full px-4 py-3 bg-slate-800/80 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition text-left">
                    </div>
                    <button type="submit"
                        class="w-full py-3.5 px-4 bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-slate-950 font-bold rounded-xl shadow-lg shadow-emerald-500/25 transition duration-200 text-base">
                        تسجيل الدخول إلى المنصة
                    </button>
                </form>

                <div class="mt-6 pt-6 border-t border-slate-800/60 text-center">
                    <p class="text-xs text-slate-400 flex items-center justify-center gap-2">
                        <span class="w-2 h-2 rounded-full bg-emerald-500 inline-block animate-pulse"></span>
                        <span>مربوط مباشرة بـ AdSense (بالدرهم المغربي 🇲🇦)</span>
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
            max_age=86400 * 30
        )
        return response
    return HTMLResponse("""
        <script>
            alert("اسم المستخدم أو كلمة المرور غير صحيحة!");
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
    totals = {"earnings": 0.0, "views": 0, "rpm": 0.0, "impressions": 0, "clicks": 0, "ctr": 0.0, "currency": "MAD"}
    
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

    # 3. Fetch Platforms
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
        "currency": "MAD",
        "date_range": date_range,
        "totals": totals,
        "daily": daily_data,
        "countries": countries,
        "platforms": platforms,
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

# ================= POSTS & RECIPES API =================
@app.get("/api/recipes")
async def list_recipes(request: Request, search: str = "", limit: int = 50, offset: int = 0):
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    recipes = get_recipes_data()
    if search:
        s_lower = search.lower()
        recipes = [r for r in recipes if s_lower in r.get("title", "").lower() or s_lower in r.get("slug", "").lower()]
    
    total = len(recipes)
    paginated = recipes[offset:offset+limit]
    
    results = []
    for r in paginated:
        cat_name = "General"
        if r.get("categories") and len(r["categories"]) > 0:
            cat_name = r["categories"][0].get("name", "General")
        img = r.get("featured_image", {}).get("url", "")
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
    
    return {"total": total, "recipes": results}

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
    
    # Parse ingredients and steps
    ingredients = []
    for line in ingredients_raw.strip().split("\n"):
        line = line.strip()
        if line:
            ingredients.append({"name": line, "amount": "", "unit": ""})
            
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
        "categories": [{"id": "1", "name": category.strip(), "slug": category.strip().lower()}],
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

    # 1. Update in-memory cache
    all_recipes = get_recipes_data()
    all_recipes.insert(0, new_recipe)
    recipes_cache["data"] = all_recipes
    
    # 2. Push to GitHub using Git Data API
    try:
        gh_h = {"Authorization": f"token {CONFIG['GITHUB_TOKEN']}", "Accept": "application/vnd.github.v3+json", "Content-Type": "application/json"}
        # Get latest commit
        req_c = urllib.request.Request(f"https://api.github.com/repos/{CONFIG['REPO_NAME']}/commits/main", headers=gh_h)
        with urllib.request.urlopen(req_c) as r_c:
            commit_info = json.loads(r_c.read().decode("utf-8"))
            latest_commit_sha = commit_info["sha"]

        # Create blob
        full_json_str = json.dumps(all_recipes, ensure_ascii=False)
        blob_payload = {"content": full_json_str, "encoding": "utf-8"}
        req_b = urllib.request.Request(f"https://api.github.com/repos/{CONFIG['REPO_NAME']}/git/blobs", data=json.dumps(blob_payload).encode("utf-8"), headers=gh_h, method="POST")
        with urllib.request.urlopen(req_b) as r_b:
            blob_sha = json.loads(r_b.read().decode("utf-8"))["sha"]

        # Create tree
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

        # Create commit
        commit_payload = {
            "message": f"feat(recipes): publish recipe '{title.strip()}' via partner portal",
            "tree": tree_sha,
            "parents": [latest_commit_sha]
        }
        req_cm = urllib.request.Request(f"https://api.github.com/repos/{CONFIG['REPO_NAME']}/git/commits", data=json.dumps(commit_payload).encode("utf-8"), headers=gh_h, method="POST")
        with urllib.request.urlopen(req_cm) as r_cm:
            new_commit_sha = json.loads(r_cm.read().decode("utf-8"))["sha"]

        # Update ref
        ref_payload = {"sha": new_commit_sha, "force": False}
        req_ref = urllib.request.Request(f"https://api.github.com/repos/{CONFIG['REPO_NAME']}/git/refs/heads/main", data=json.dumps(ref_payload).encode("utf-8"), headers=gh_h, method="PATCH")
        with urllib.request.urlopen(req_ref):
            pass

        # 3. Trigger Coolify deployment
        coolify_h = {"Authorization": f"Bearer {CONFIG['COOLIFY_TOKEN']}", "Content-Type": "application/json"}
        req_dep = urllib.request.Request(f"{CONFIG['COOLIFY_URL']}/api/v1/deploy?uuid={CONFIG['MAKEFOOD_COOLIFY_UUID']}", headers=coolify_h, method="POST")
        try:
            urllib.request.urlopen(req_dep)
        except Exception:
            pass

        return {
            "success": True,
            "slug": slug_clean,
            "live_url": f"https://make-food.com/{slug_clean}/",
            "message": f"تم نشر المقال '{title}' بنجاح وجاري إعادة بناء الموقع حياً!"
        }
    except Exception as e:
        print("Error saving recipe to GitHub:", e)
        return {
            "success": False,
            "error": str(e)
        }

# ================= DASHBOARD UI =================
@app.get("/", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=302)
    
    return """
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Make-Food.com — Portal الإدارة، المقالات والأرباح</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;800&family=Plus+Jakarta+Sans:wght@500;700;800&display=swap" rel="stylesheet">
        <style>
            body { font-family: 'Tajawal', sans-serif; }
            .font-num { font-family: 'Plus Jakarta Sans', sans-serif; }
            .glass { background: rgba(15, 23, 42, 0.85); backdrop-filter: blur(16px); }
        </style>
    </head>
    <body class="bg-slate-950 text-slate-100 min-h-screen">
        <!-- Top Navigation -->
        <header class="border-b border-slate-800/80 glass sticky top-0 z-50">
            <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
                <!-- Brand & Status -->
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-amber-500 to-emerald-500 flex items-center justify-center shadow-lg shadow-emerald-500/20 text-2xl">
                        🍲
                    </div>
                    <div>
                        <div class="flex items-center gap-2">
                            <h1 class="text-lg font-extrabold tracking-tight text-white font-num">Make-Food.com</h1>
                            <span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1 font-num">
                                <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                                LIVE
                            </span>
                            <span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20">
                                درهم مغربي (MAD) 🇲🇦
                            </span>
                        </div>
                        <p class="text-xs text-slate-400">لوحة التحكم، النشر والمداخيل الحصرية</p>
                    </div>
                </div>

                <!-- Tabs & Controls -->
                <div class="flex items-center gap-3">
                    <div class="bg-slate-900 border border-slate-800 rounded-xl p-1 flex items-center gap-1 text-xs">
                        <button onclick="switchTab('analytics')" id="tab-btn-analytics" class="px-3.5 py-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 font-bold border border-emerald-500/20 transition flex items-center gap-1.5">
                            <span>📊 الإحصائيات والأرباح</span>
                        </button>
                        <button onclick="switchTab('recipes')" id="tab-btn-recipes" class="px-3.5 py-1.5 rounded-lg text-slate-400 hover:text-white transition flex items-center gap-1.5">
                            <span>📝 المقالات والوصفات</span>
                        </button>
                        <button onclick="switchTab('create')" id="tab-btn-create" class="px-3.5 py-1.5 rounded-lg text-slate-400 hover:text-white transition flex items-center gap-1.5">
                            <span>➕ نشر مقال جديد</span>
                        </button>
                    </div>

                    <a href="/logout" title="تسجيل الخروج" class="px-3 py-1.5 text-xs font-bold text-slate-400 hover:text-rose-400 border border-slate-800 rounded-xl hover:border-rose-500/30 transition flex items-center gap-1">
                        <span>خروج</span>
                    </a>
                </div>
            </div>
        </header>

        <!-- Main Wrapper -->
        <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">

            <!-- ================= TAB 1: REVENUE & ANALYTICS ================= -->
            <div id="tab-analytics" class="space-y-8">
                <!-- Filter Range Header -->
                <div class="flex flex-col sm:flex-row items-center justify-between gap-4 bg-slate-900/60 border border-slate-800/80 p-4 rounded-2xl">
                    <div>
                        <h2 class="text-base font-bold text-white">مؤشرات الأداء والأرباح لـ make-food.com</h2>
                        <p class="text-xs text-slate-400">مباشرة من Google AdSense Management API بعملة الدرهم المغربي (MAD)</p>
                    </div>
                    <div class="bg-slate-900 border border-slate-800 rounded-xl p-1 flex items-center gap-1 text-xs font-num">
                        <button onclick="setRange('today')" id="btn-today" class="px-3 py-1.5 rounded-lg text-slate-400 hover:text-white transition">Today</button>
                        <button onclick="setRange('yesterday')" id="btn-yesterday" class="px-3 py-1.5 rounded-lg text-slate-400 hover:text-white transition">Yesterday</button>
                        <button onclick="setRange('last7')" id="btn-last7" class="px-3 py-1.5 rounded-lg text-slate-400 hover:text-white transition">7 Days</button>
                        <button onclick="setRange('last30')" id="btn-last30" class="px-3 py-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 font-bold border border-emerald-500/20 transition">30 Days</button>
                        <button onclick="setRange('month')" id="btn-month" class="px-3 py-1.5 rounded-lg text-slate-400 hover:text-white transition">This Month</button>
                    </div>
                </div>

                <!-- KPI Metric Cards -->
                <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
                    <!-- Revenue in MAD -->
                    <div class="bg-slate-900 border border-slate-800/80 rounded-2xl p-5 relative overflow-hidden">
                        <div class="absolute top-0 left-0 w-24 h-24 bg-emerald-500/10 rounded-full blur-2xl"></div>
                        <div class="flex items-center justify-between text-slate-400 text-xs font-bold uppercase tracking-wider mb-2">
                            <span>إجمالي الأرباح</span>
                            <span class="text-emerald-400 font-bold">درهم مغربي</span>
                        </div>
                        <div id="stat-earnings" class="text-3xl font-extrabold text-white tracking-tight font-num">0.00 د.م.</div>
                        <div class="text-[11px] text-slate-400 mt-2 flex items-center gap-1">
                            <span class="text-emerald-400 font-bold">100% مؤكد</span> من AdSense الرسمي
                        </div>
                    </div>

                    <!-- Pageviews -->
                    <div class="bg-slate-900 border border-slate-800/80 rounded-2xl p-5 relative overflow-hidden">
                        <div class="absolute top-0 left-0 w-24 h-24 bg-sky-500/10 rounded-full blur-2xl"></div>
                        <div class="flex items-center justify-between text-slate-400 text-xs font-bold uppercase tracking-wider mb-2">
                            <span>مشاهدات الصفحات</span>
                            <span class="text-sky-400 text-base">👁️</span>
                        </div>
                        <div id="stat-views" class="text-3xl font-extrabold text-white tracking-tight font-num">0</div>
                        <div class="text-[11px] text-slate-400 mt-2">
                            عدد قراءات المقالات
                        </div>
                    </div>

                    <!-- RPM in MAD -->
                    <div class="bg-slate-900 border border-slate-800/80 rounded-2xl p-5 relative overflow-hidden">
                        <div class="absolute top-0 left-0 w-24 h-24 bg-amber-500/10 rounded-full blur-2xl"></div>
                        <div class="flex items-center justify-between text-slate-400 text-xs font-bold uppercase tracking-wider mb-2">
                            <span>معدل الربح (RPM)</span>
                            <span class="text-amber-400 text-base">📈</span>
                        </div>
                        <div id="stat-rpm" class="text-3xl font-extrabold text-white tracking-tight font-num">0.00 د.م.</div>
                        <div class="text-[11px] text-slate-400 mt-2">
                            الربح لكل 1,000 مشاهدة
                        </div>
                    </div>

                    <!-- Impressions -->
                    <div class="bg-slate-900 border border-slate-800/80 rounded-2xl p-5 relative overflow-hidden">
                        <div class="absolute top-0 left-0 w-24 h-24 bg-purple-500/10 rounded-full blur-2xl"></div>
                        <div class="flex items-center justify-between text-slate-400 text-xs font-bold uppercase tracking-wider mb-2">
                            <span>ظهور الإعلانات</span>
                            <span class="text-purple-400 text-base">📊</span>
                        </div>
                        <div id="stat-impressions" class="text-3xl font-extrabold text-white tracking-tight font-num">0</div>
                        <div class="text-[11px] text-slate-400 mt-2">
                            مرات ظهور الإعلانات
                        </div>
                    </div>

                    <!-- Clicks & CTR -->
                    <div class="bg-slate-900 border border-slate-800/80 rounded-2xl p-5 relative overflow-hidden">
                        <div class="absolute top-0 left-0 w-24 h-24 bg-teal-500/10 rounded-full blur-2xl"></div>
                        <div class="flex items-center justify-between text-slate-400 text-xs font-bold uppercase tracking-wider mb-2">
                            <span>النقرات (CTR)</span>
                            <span class="text-teal-400 text-base">🖱️</span>
                        </div>
                        <div id="stat-clicks" class="text-3xl font-extrabold text-white tracking-tight font-num">0 <span class="text-sm font-medium text-slate-400" id="stat-ctr">(0%)</span></div>
                        <div class="text-[11px] text-slate-400 mt-2">
                            تفاعل الزوار مع الإعلانات
                        </div>
                    </div>
                </div>

                <!-- Charts Row -->
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <!-- Daily Revenue Chart -->
                    <div class="bg-slate-900 border border-slate-800/80 rounded-2xl p-6">
                        <div class="flex items-center justify-between mb-4">
                            <h2 class="text-base font-bold text-white flex items-center gap-2">
                                <span>💵 مسار الأرباح اليومية (بالدرهم المغربي)</span>
                            </h2>
                            <span class="text-xs text-slate-400">MAD (د.م.)</span>
                        </div>
                        <div class="h-64">
                            <canvas id="earningsChart"></canvas>
                        </div>
                    </div>

                    <!-- Traffic Chart -->
                    <div class="bg-slate-900 border border-slate-800/80 rounded-2xl p-6">
                        <div class="flex items-center justify-between mb-4">
                            <h2 class="text-base font-bold text-white flex items-center gap-2">
                                <span>📈 حركة المشاهدات والظهور اليومي</span>
                            </h2>
                            <span class="text-xs text-slate-400">حجم الزيارات</span>
                        </div>
                        <div class="h-64">
                            <canvas id="trafficChart"></canvas>
                        </div>
                    </div>
                </div>

                <!-- Breakdown: Countries & Devices -->
                <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    <!-- Countries Table -->
                    <div class="lg:col-span-2 bg-slate-900 border border-slate-800/80 rounded-2xl p-6">
                        <div class="flex items-center justify-between mb-4">
                            <h2 class="text-base font-bold text-white">🌍 توزيع الأرباح حسب الدول</h2>
                            <span class="text-xs text-slate-400">مرتبة حسب العائد</span>
                        </div>
                        <div class="overflow-x-auto">
                            <table class="w-full text-right text-sm">
                                <thead class="text-xs uppercase text-slate-400 border-b border-slate-800">
                                    <tr>
                                        <th class="py-3 px-3">الدولة</th>
                                        <th class="py-3 px-3 text-left">المشاهدات</th>
                                        <th class="py-3 px-3 text-left">الظهور</th>
                                        <th class="py-3 px-3 text-left">الأرباح (د.م.)</th>
                                    </tr>
                                </thead>
                                <tbody id="countryTableBody" class="divide-y divide-slate-800/60 text-slate-300">
                                    <tr><td colspan="4" class="py-4 text-center text-slate-500">جاري تحميل البيانات...</td></tr>
                                </tbody>
                            </table>
                        </div>
                    </div>

                    <!-- Device Breakdown -->
                    <div class="bg-slate-900 border border-slate-800/80 rounded-2xl p-6 flex flex-col justify-between">
                        <div>
                            <div class="flex items-center justify-between mb-4">
                                <h2 class="text-base font-bold text-white">📱 توزيع الأجهزة</h2>
                                <span class="text-xs text-slate-400">الهاتف مقابل الحاسوب</span>
                            </div>
                            <div class="h-48 flex items-center justify-center">
                                <canvas id="platformChart"></canvas>
                            </div>
                        </div>
                        <div id="platformCards" class="grid grid-cols-3 gap-2 mt-4 pt-4 border-t border-slate-800 text-center font-num">
                        </div>
                    </div>
                </div>

                <!-- Daily Breakdown Log Table -->
                <div class="bg-slate-900 border border-slate-800/80 rounded-2xl p-6">
                    <div class="flex items-center justify-between mb-4">
                        <h2 class="text-base font-bold text-white">📅 السجل اليومي للأرباح والمشاهدات</h2>
                        <button onclick="exportCSV()" class="px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-bold transition flex items-center gap-1.5">
                            <span>📥 تصدير ملف Excel / CSV</span>
                        </button>
                    </div>
                    <div class="overflow-x-auto max-h-96">
                        <table class="w-full text-right text-sm">
                            <thead class="text-xs uppercase text-slate-400 border-b border-slate-800 sticky top-0 bg-slate-900">
                                <tr>
                                    <th class="py-3 px-4">التاريخ</th>
                                    <th class="py-3 px-4 text-left">الأرباح (د.م.)</th>
                                    <th class="py-3 px-4 text-left">المشاهدات</th>
                                    <th class="py-3 px-4 text-left">الـ RPM (د.م.)</th>
                                    <th class="py-3 px-4 text-left">الظهور</th>
                                    <th class="py-3 px-4 text-left">النقرات</th>
                                </tr>
                            </thead>
                            <tbody id="dailyTableBody" class="divide-y divide-slate-800/60 text-slate-300 font-num text-xs">
                                <tr><td colspan="6" class="py-4 text-center text-slate-500">جاري تحميل البيانات...</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <!-- ================= TAB 2: POSTS & RECIPES LIST ================= -->
            <div id="tab-recipes" class="hidden space-y-6">
                <div class="flex flex-col sm:flex-row items-center justify-between gap-4 bg-slate-900/60 border border-slate-800/80 p-4 rounded-2xl">
                    <div>
                        <div class="flex items-center gap-2">
                            <h2 class="text-base font-bold text-white">جميع مقالات ووصفات make-food.com</h2>
                            <span id="recipes-count-badge" class="px-2 py-0.5 rounded-full text-xs font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-num">
                                1,181 وصفة
                            </span>
                        </div>
                        <p class="text-xs text-slate-400 mt-1">تصفح، ابحث وشاهد المقالات المنشورة حياً على الموقع</p>
                    </div>
                    <div class="w-full sm:w-72">
                        <input type="text" id="recipeSearchInput" onkeyup="handleRecipeSearch()"
                            placeholder="🔍 ابحث عن أي وصفة أو تصنيف..."
                            class="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-xl text-white placeholder-slate-500 text-xs focus:outline-none focus:ring-2 focus:ring-emerald-500 transition">
                    </div>
                </div>

                <!-- Recipes Grid -->
                <div id="recipesGrid" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    <div class="col-span-3 text-center py-12 text-slate-500">جاري تحميل الوصفات...</div>
                </div>
            </div>

            <!-- ================= TAB 3: CREATE NEW POST ================= -->
            <div id="tab-create" class="hidden space-y-6">
                <div class="bg-slate-900 border border-slate-800/80 rounded-2xl p-6 sm:p-8 max-w-4xl mx-auto">
                    <div class="border-b border-slate-800 pb-4 mb-6 flex items-center justify-between">
                        <div>
                            <h2 class="text-lg font-bold text-white">✨ إنشاء ونشر مقال / وصفة جديدة في make-food.com</h2>
                            <p class="text-xs text-slate-400 mt-1">يتم نشر المقال فورياً وتحديث خريطة الموقع والروابط بدون أي تعقيد</p>
                        </div>
                        <span class="text-2xl">📝</span>
                    </div>

                    <form id="createRecipeForm" onsubmit="handleCreateRecipe(event)" class="space-y-6">
                        <!-- Title & Slug -->
                        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                            <div>
                                <label class="block text-xs font-bold text-slate-300 mb-2">عنوان الوصفة / المقال *</label>
                                <input type="text" id="postTitle" required onkeyup="autoSlug()"
                                    placeholder="مثال: Crispy Garlic Parmesan Chicken Wings"
                                    class="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-xl text-white text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 transition font-num text-left" dir="ltr">
                            </div>
                            <div>
                                <label class="block text-xs font-bold text-slate-300 mb-2">رابط المقال (Slug) *</label>
                                <div class="flex items-center bg-slate-800 border border-slate-700 rounded-xl px-3 text-slate-500 text-xs font-num" dir="ltr">
                                    <span>make-food.com/</span>
                                    <input type="text" id="postSlug" required
                                        placeholder="crispy-garlic-chicken-wings"
                                        class="w-full py-2.5 bg-transparent text-emerald-400 font-bold focus:outline-none text-left">
                                </div>
                            </div>
                        </div>

                        <!-- Category & Author & Image -->
                        <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
                            <div>
                                <label class="block text-xs font-bold text-slate-300 mb-2">التصنيف (Category)</label>
                                <select id="postCategory" class="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-xl text-white text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 transition">
                                    <option value="Dinner">Dinner (عشاء)</option>
                                    <option value="Breakfast">Breakfast (فطور)</option>
                                    <option value="Lunch">Lunch (غداء)</option>
                                    <option value="Dessert">Dessert (حلويات)</option>
                                    <option value="Salad">Salad (سلطات)</option>
                                    <option value="Soup">Soup (شوربات)</option>
                                    <option value="Snack">Snack (وجبات خفيفة)</option>
                                </select>
                            </div>
                            <div>
                                <label class="block text-xs font-bold text-slate-300 mb-2">اسم الكاتب (Author)</label>
                                <input type="text" id="postAuthor" value="Maria"
                                    class="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-xl text-white text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 transition font-num text-left" dir="ltr">
                            </div>
                            <div>
                                <label class="block text-xs font-bold text-slate-300 mb-2">رابط الصورة البارزة (Image URL)</label>
                                <input type="url" id="postImage" onchange="previewImage()"
                                    placeholder="https://images.unsplash.com/..."
                                    class="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-xl text-white text-xs focus:outline-none focus:ring-2 focus:ring-emerald-500 transition font-num text-left" dir="ltr">
                            </div>
                        </div>

                        <!-- Image Preview Box -->
                        <div id="imagePreviewBox" class="hidden">
                            <label class="block text-xs font-bold text-slate-400 mb-1">معاينة الصورة البارزة:</label>
                            <img id="imagePreviewEl" src="" alt="Preview" class="h-44 w-full object-cover rounded-xl border border-slate-700">
                        </div>

                        <!-- Timings & Servings -->
                        <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 bg-slate-800/40 p-4 rounded-xl border border-slate-800">
                            <div>
                                <label class="block text-xs font-bold text-slate-300 mb-1">وقت التحضير (بالدقائق)</label>
                                <input type="number" id="postPrepTime" value="15" min="1"
                                    class="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm font-num text-center">
                            </div>
                            <div>
                                <label class="block text-xs font-bold text-slate-300 mb-1">وقت الطهي (بالدقائق)</label>
                                <input type="number" id="postCookTime" value="25" min="0"
                                    class="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm font-num text-center">
                            </div>
                            <div>
                                <label class="block text-xs font-bold text-slate-300 mb-1">عدد الحصص (Servings)</label>
                                <input type="number" id="postServings" value="4" min="1"
                                    class="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm font-num text-center">
                            </div>
                        </div>

                        <!-- Short Description -->
                        <div>
                            <label class="block text-xs font-bold text-slate-300 mb-2">مقدمة ووصف مختصر للوصفة (Excerpt / Description) *</label>
                            <textarea id="postDescription" rows="2" required
                                placeholder="اكتب وصفاً جذاباً ومختصراً يصف هذه الوصفة..."
                                class="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-xl text-white text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 transition"></textarea>
                        </div>

                        <!-- Ingredients Builder -->
                        <div>
                            <div class="flex items-center justify-between mb-2">
                                <label class="text-xs font-bold text-slate-300">المكونات (Ingredients) — سطر لكل مكون *</label>
                                <span class="text-[11px] text-slate-400">مثال: 500g Chicken breast, sliced</span>
                            </div>
                            <textarea id="postIngredients" rows="4" required dir="ltr"
                                placeholder="2 tbsp olive oil&#10;1 tsp smoked paprika&#10;3 cloves garlic, minced&#10;Salt and freshly cracked black pepper"
                                class="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-xl text-white text-xs focus:outline-none focus:ring-2 focus:ring-emerald-500 transition font-num text-left"></textarea>
                        </div>

                        <!-- Instructions Builder -->
                        <div>
                            <div class="flex items-center justify-between mb-2">
                                <label class="text-xs font-bold text-slate-300">خطوات التحضير (Instructions / Steps) — سطر لكل خطوة *</label>
                                <span class="text-[11px] text-slate-400">يتم ترقيمها تلقائياً</span>
                            </div>
                            <textarea id="postInstructions" rows="4" required dir="ltr"
                                placeholder="Preheat the oven to 400°F (200°C) and line a baking sheet.&#10;In a large bowl, toss the ingredients until evenly coated.&#10;Spread evenly on the baking sheet and bake for 25 minutes until golden brown."
                                class="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-xl text-white text-xs focus:outline-none focus:ring-2 focus:ring-emerald-500 transition font-num text-left"></textarea>
                        </div>

                        <!-- Article Body HTML -->
                        <div>
                            <label class="block text-xs font-bold text-slate-300 mb-2">نص المقال الكامل (Article Body / HTML) [اختياري]</label>
                            <textarea id="postArticleHtml" rows="5" dir="ltr"
                                placeholder="<p>This easy chicken recipe is perfect for busy weeknights...</p><h3>Why You Will Love This Recipe</h3><p>...</p>"
                                class="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-xl text-white text-xs focus:outline-none focus:ring-2 focus:ring-emerald-500 transition font-mono text-left"></textarea>
                        </div>

                        <!-- Submit Button -->
                        <div class="pt-4 border-t border-slate-800 flex items-center justify-between">
                            <p class="text-xs text-slate-400 flex items-center gap-1.5">
                                <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                                <span>سيتم نشر المقال فورياً وتحديث النطاق الحي</span>
                            </p>
                            <button type="submit" id="btnPublish"
                                class="py-3 px-8 bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-slate-950 font-extrabold rounded-xl shadow-lg shadow-emerald-500/25 transition duration-200 text-sm flex items-center gap-2">
                                <span>🚀 نشر المقال في make-food.com</span>
                            </button>
                        </div>
                    </form>
                </div>
            </div>
        </main>

        <footer class="border-t border-slate-800/80 py-6 mt-12 text-center text-xs text-slate-500">
            Make-Food.com Partner Portal • أرباح AdSense بالدرهم المغربي 🇲🇦 • نظام النشر الآلي
        </footer>

        <!-- JS Logic -->
        <script>
            let currentRange = 'last30';
            let earningsChart, trafficChart, platformChart;
            let rawDailyData = [];
            let allRecipesData = [];

            function switchTab(tabId) {
                ['analytics', 'recipes', 'create'].forEach(t => {
                    document.getElementById('tab-' + t).classList.add('hidden');
                    const btn = document.getElementById('tab-btn-' + t);
                    btn.className = "px-3.5 py-1.5 rounded-lg text-slate-400 hover:text-white transition flex items-center gap-1.5";
                });
                document.getElementById('tab-' + tabId).classList.remove('hidden');
                document.getElementById('tab-btn-' + tabId).className = "px-3.5 py-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 font-bold border border-emerald-500/20 transition flex items-center gap-1.5";

                if (tabId === 'recipes' && allRecipesData.length === 0) {
                    loadRecipesList();
                }
            }

            function setRange(range) {
                currentRange = range;
                ['today', 'yesterday', 'last7', 'last30', 'month'].forEach(r => {
                    const btn = document.getElementById('btn-' + r);
                    if (r === range) {
                        btn.className = "px-3 py-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 font-bold border border-emerald-500/20 transition";
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
                const t = data.totals;
                // Render in MAD
                document.getElementById('stat-earnings').innerText = t.earnings.toFixed(2) + ' د.م.';
                document.getElementById('stat-views').innerText = t.views.toLocaleString();
                document.getElementById('stat-rpm').innerText = t.rpm.toFixed(2) + ' د.م.';
                document.getElementById('stat-impressions').innerText = t.impressions.toLocaleString();
                document.getElementById('stat-clicks').innerText = t.clicks.toLocaleString();
                document.getElementById('stat-ctr').innerText = `(${t.ctr}%)`;

                rawDailyData = data.daily || [];
                const labels = rawDailyData.map(d => d.date);
                const earnings = rawDailyData.map(d => d.earnings);
                const views = rawDailyData.map(d => d.pageviews);
                const impressions = rawDailyData.map(d => d.impressions);

                // 1. Earnings Chart (MAD)
                if (earningsChart) earningsChart.destroy();
                const ctxE = document.getElementById('earningsChart').getContext('2d');
                earningsChart = new Chart(ctxE, {
                    type: 'line',
                    data: {
                        labels: labels,
                        datasets: [{
                            label: 'الأرباح (د.م.)',
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
                        plugins: { 
                            legend: { display: false },
                            tooltip: { callbacks: { label: c => c.parsed.y.toFixed(2) + ' MAD (درهم)' } }
                        },
                        scales: {
                            x: { grid: { color: 'rgba(51, 65, 85, 0.3)' }, ticks: { color: '#94a3b8', font: { size: 10 } } },
                            y: { grid: { color: 'rgba(51, 65, 85, 0.3)' }, ticks: { color: '#94a3b8', callback: v => v + ' د.م.' } }
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
                                label: 'مشاهدات المقالات',
                                data: views,
                                backgroundColor: '#38bdf8',
                                borderRadius: 4
                            },
                            {
                                label: 'ظهور الإعلانات',
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
                const pLabels = plats.map(p => p.platform.replace('High-end mobile devices', 'الهواتف').replace('Desktop', 'الحواسيب').replace('Tablets', 'التابليت'));
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
                        plugins: { 
                            legend: { position: 'bottom', labels: { color: '#94a3b8', boxWidth: 10, font: { size: 11 } } },
                            tooltip: { callbacks: { label: c => `${c.label}: ${c.parsed.toFixed(2)} د.م.` } }
                        }
                    }
                });

                // Platform Cards
                document.getElementById('platformCards').innerHTML = plats.map(p => {
                    const shortName = p.platform.replace('High-end mobile devices', 'الهواتف').replace('Desktop', 'الحواسيب').replace('Tablets', 'التابليت');
                    return `
                        <div class="bg-slate-800/50 p-2 rounded-xl">
                            <div class="text-[10px] text-slate-400">${shortName}</div>
                            <div class="text-sm font-bold text-white">${p.earnings.toFixed(2)} د.م.</div>
                            <div class="text-[10px] text-slate-400">${p.pageviews} زيارة</div>
                        </div>
                    `;
                }).join('');

                // Countries Table
                const cTbody = document.getElementById('countryTableBody');
                if (!data.countries || data.countries.length === 0) {
                    cTbody.innerHTML = '<tr><td colspan="4" class="py-4 text-center text-slate-500">لا توجد بيانات دول متاحة</td></tr>';
                } else {
                    cTbody.innerHTML = data.countries.map(c => `
                        <tr class="hover:bg-slate-800/30 transition">
                            <td class="py-2.5 px-3 font-medium text-white">${c.country}</td>
                            <td class="py-2.5 px-3 text-left font-num">${c.pageviews.toLocaleString()}</td>
                            <td class="py-2.5 px-3 text-left font-num">${c.impressions.toLocaleString()}</td>
                            <td class="py-2.5 px-3 text-left font-bold text-emerald-400 font-num">${c.earnings.toFixed(2)} د.م.</td>
                        </tr>
                    `).join('');
                }

                // Daily Table
                const dTbody = document.getElementById('dailyTableBody');
                if (rawDailyData.length === 0) {
                    dTbody.innerHTML = '<tr><td colspan="6" class="py-4 text-center text-slate-500">لا توجد بيانات متاحة</td></tr>';
                } else {
                    const sortedDaily = [...rawDailyData].reverse();
                    dTbody.innerHTML = sortedDaily.map(d => `
                        <tr class="hover:bg-slate-800/30 transition">
                            <td class="py-2.5 px-4 font-sans text-slate-200 text-right">${d.date}</td>
                            <td class="py-2.5 px-4 text-left font-bold text-emerald-400">${d.earnings.toFixed(2)} د.م.</td>
                            <td class="py-2.5 px-4 text-left">${d.pageviews.toLocaleString()}</td>
                            <td class="py-2.5 px-4 text-left text-amber-400">${d.rpm.toFixed(2)} د.م.</td>
                            <td class="py-2.5 px-4 text-left">${d.impressions.toLocaleString()}</td>
                            <td class="py-2.5 px-4 text-left">${d.clicks}</td>
                        </tr>
                    `).join('');
                }
            }

            function exportCSV() {
                if (!rawDailyData.length) return;
                let csv = "Date,Earnings_MAD,Pageviews,RPM_MAD,Impressions,Clicks\\n";
                rawDailyData.forEach(d => {
                    csv += `${d.date},${d.earnings},${d.pageviews},${d.rpm},${d.impressions},${d.clicks}\\n`;
                });
                const blob = new Blob([csv], { type: 'text/csv' });
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.setAttribute('href', url);
                a.setAttribute('download', `make-food-adsense-MAD-${currentRange}.csv`);
                a.click();
            }

            // Recipes List
            async function loadRecipesList() {
                const search = document.getElementById('recipeSearchInput').value || '';
                try {
                    const res = await fetch(`/api/recipes?search=${encodeURIComponent(search)}&limit=60`);
                    const data = await res.json();
                    allRecipesData = data.recipes || [];
                    document.getElementById('recipes-count-badge').innerText = `${data.total.toLocaleString()} وصفة`;
                    renderRecipesGrid(allRecipesData);
                } catch (e) {
                    console.error("Failed to load recipes:", e);
                }
            }

            function renderRecipesGrid(recipes) {
                const container = document.getElementById('recipesGrid');
                if (!recipes.length) {
                    container.innerHTML = '<div class="col-span-3 text-center py-12 text-slate-500">لم يتم العثور على أي وصفة تطابق البحث.</div>';
                    return;
                }
                container.innerHTML = recipes.map(r => `
                    <div class="bg-slate-900 border border-slate-800 rounded-2xl p-4 flex gap-4 hover:border-slate-700 transition">
                        <img src="${r.image || 'https://images.unsplash.com/photo-1495521821757-a1efb6729352?auto=format&fit=crop&w=300&q=80'}" alt="${r.title}" class="w-24 h-24 rounded-xl object-cover border border-slate-800 flex-shrink-0">
                        <div class="flex flex-col justify-between overflow-hidden w-full">
                            <div>
                                <span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20">
                                    ${r.category}
                                </span>
                                <h3 class="text-sm font-bold text-white mt-1.5 truncate" title="${r.title}">${r.title}</h3>
                                <p class="text-[11px] text-slate-400 mt-1 font-num">${r.prep_time || '15 min'} • ${r.servings || '4 servings'}</p>
                            </div>
                            <div class="flex items-center justify-between pt-2 border-t border-slate-800/80 mt-2">
                                <span class="text-[10px] text-slate-500 font-num">${r.published_at ? r.published_at.slice(0, 10) : ''}</span>
                                <a href="${r.url}" target="_blank" class="text-xs font-bold text-emerald-400 hover:text-emerald-300 flex items-center gap-1">
                                    <span>مشاهدة حية ↗</span>
                                </a>
                            </div>
                        </div>
                    </div>
                `).join('');
            }

            let searchTimeout = null;
            function handleRecipeSearch() {
                clearTimeout(searchTimeout);
                searchTimeout = setTimeout(() => {
                    loadRecipesList();
                }, 300);
            }

            function autoSlug() {
                const title = document.getElementById('postTitle').value;
                const slugInput = document.getElementById('postSlug');
                slugInput.value = title.trim().toLowerCase()
                    .replace(/[^\w\s-]/g, '')
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

            async function handleCreateRecipe(e) {
                e.preventDefault();
                const btn = document.getElementById('btnPublish');
                btn.disabled = true;
                btn.innerHTML = `<span>⏳ جاري النشر والتحديث في السيرفر...</span>`;

                const formData = new FormData();
                formData.append('title', document.getElementById('postTitle').value);
                formData.append('slug', document.getElementById('postSlug').value);
                formData.append('category', document.getElementById('postCategory').value);
                formData.append('author', document.getElementById('postAuthor').value);
                formData.append('description', document.getElementById('postDescription').value);
                formData.append('featured_image', document.getElementById('postImage').value);
                formData.append('prep_time', document.getElementById('postPrepTime').value);
                formData.append('cook_time', document.getElementById('postCookTime').value);
                formData.append('servings', document.getElementById('postServings').value);
                formData.append('ingredients_raw', document.getElementById('postIngredients').value);
                formData.append('instructions_raw', document.getElementById('postInstructions').value);
                formData.append('article_html', document.getElementById('postArticleHtml').value);

                try {
                    const res = await fetch('/api/recipes/create', { method: 'POST', body: formData });
                    const result = await res.json();
                    if (result.success) {
                        alert(`🎉 ${result.message}\\n\\nالرابط المباشر:\\n${result.live_url}`);
                        document.getElementById('createRecipeForm').reset();
                        document.getElementById('imagePreviewBox').classList.add('hidden');
                        switchTab('recipes');
                        loadRecipesList();
                    } else {
                        alert('حدث خطأ أثناء النشر: ' + (result.error || 'Unknown error'));
                    }
                } catch (err) {
                    alert('خطأ في الاتصال بالسيرفر: ' + err);
                } finally {
                    btn.disabled = false;
                    btn.innerHTML = `<span>🚀 نشر المقال في make-food.com</span>`;
                }
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

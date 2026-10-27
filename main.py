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
    <html lang="ar" dir="rtl" id="htmlTag">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>تسجيل الدخول — Make-Food.com</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;800&family=Plus+Jakarta+Sans:wght@500;700&display=swap" rel="stylesheet">
        <style>body { font-family: 'Tajawal', 'Plus Jakarta Sans', sans-serif; }</style>
    </head>
    <body class="bg-slate-950 text-slate-100 min-h-screen flex items-center justify-center p-4">
        <div class="w-full max-w-md">
            <div class="bg-slate-900 border border-slate-800 rounded-2xl p-8 shadow-2xl relative overflow-hidden">
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
async def list_recipes(request: Request, search: str = "", limit: int = 60, offset: int = 0):
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

    # Update in-memory
    all_recipes = get_recipes_data()
    all_recipes.insert(0, new_recipe)
    recipes_cache["data"] = all_recipes
    
    # Push to GitHub
    try:
        gh_h = {"Authorization": f"token {CONFIG['GITHUB_TOKEN']}", "Accept": "application/vnd.github.v3+json", "Content-Type": "application/json"}
        req_c = urllib.request.Request(f"https://api.github.com/repos/{CONFIG['REPO_NAME']}/commits/main", headers=gh_h)
        with urllib.request.urlopen(req_c) as r_c:
            commit_info = json.loads(r_c.read().decode("utf-8"))
            latest_commit_sha = commit_info["sha"]

        full_json_str = json.dumps(all_recipes, ensure_ascii=False)
        blob_payload = {"content": full_json_str, "encoding": "utf-8"}
        req_b = urllib.request.Request(f"https://api.github.com/repos/{CONFIG['REPO_NAME']}/git/blobs", data=json.dumps(blob_payload).encode("utf-8"), headers=gh_h, method="POST")
        with urllib.request.urlopen(req_b) as r_b:
            blob_sha = json.loads(r_b.read().decode("utf-8"))["sha"]

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

        commit_payload = {
            "message": f"feat(recipes): publish recipe '{title.strip()}' via partner portal",
            "tree": tree_sha,
            "parents": [latest_commit_sha]
        }
        req_cm = urllib.request.Request(f"https://api.github.com/repos/{CONFIG['REPO_NAME']}/git/commits", data=json.dumps(commit_payload).encode("utf-8"), headers=gh_h, method="POST")
        with urllib.request.urlopen(req_cm) as r_cm:
            new_commit_sha = json.loads(r_cm.read().decode("utf-8"))["sha"]

        ref_payload = {"sha": new_commit_sha, "force": False}
        req_ref = urllib.request.Request(f"https://api.github.com/repos/{CONFIG['REPO_NAME']}/git/refs/heads/main", data=json.dumps(ref_payload).encode("utf-8"), headers=gh_h, method="PATCH")
        with urllib.request.urlopen(req_ref):
            pass

        # Trigger Coolify deployment
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
            "message": f"تم نشر المقال '{title}' بنجاح! / Recipe published successfully!"
        }
    except Exception as e:
        print("Error saving recipe to GitHub:", e)
        return {
            "success": False,
            "error": str(e)
        }

# ================= AI GENERATION & REWRITER API =================
@app.post("/api/ai/models")
async def fetch_ai_models(request: Request):
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    body = await request.json()
    provider = body.get("provider", "google")
    api_key = body.get("api_key", "").strip()
    
    if not api_key:
        raise HTTPException(status_code=400, detail="API Key is required")

    models = []
    try:
        if provider == "google":
            # Gemini models
            url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for m in data.get("models", []):
                    name = m.get("name", "")
                    if "gemini" in name and "generateContent" in m.get("supportedGenerationMethods", []):
                        m_id = name.replace("models/", "")
                        disp = m.get("displayName", m_id)
                        models.append({"id": m_id, "name": f"{disp} ({m_id})"})
        elif provider == "openrouter":
            # OpenRouter models
            url = "https://openrouter.ai/api/v1/models"
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"})
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for m in data.get("data", []):
                    models.append({"id": m.get("id"), "name": m.get("name", m.get("id"))})
                # Sort popular ones first
                models = sorted(models, key=lambda x: x["name"])
        return {"success": True, "provider": provider, "models": models}
    except Exception as e:
        return {"success": False, "error": f"Failed to fetch models: {str(e)}"}

@app.post("/api/ai/generate")
async def generate_recipe_ai(request: Request):
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    body = await request.json()
    provider = body.get("provider", "google")
    api_key = body.get("api_key", "").strip()
    model = body.get("model", "").strip()
    mode = body.get("mode", "name") # "name" or "rewrite"
    recipe_input = body.get("recipe_input", "").strip()
    category = body.get("category", "Dinner").strip()

    if not api_key or not recipe_input:
        raise HTTPException(status_code=400, detail="API Key and input text are required")

    system_instruction = """
    You are an expert chef, food blogger, and SEO copywriter for Make-Food.com. 
    You must create or rewrite a complete, original, appetizing, and SEO-optimized English recipe.
    You MUST return ONLY a raw JSON object (without markdown code blocks, without commentary) matching this schema:
    {
      "title": "Clear, appetizing recipe title",
      "slug": "recipe-title-lowercase-hyphens",
      "category": "Dinner",
      "prep_time": 15,
      "cook_time": 25,
      "servings": 4,
      "description": "2 appetizing sentences summarizing the dish.",
      "featured_image": "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?auto=format&fit=crop&w=1200&q=80",
      "ingredients": ["1 lb chicken breast, diced", "2 cloves garlic, minced", "1 tbsp olive oil"],
      "instructions": ["Heat olive oil in a skillet over medium heat.", "Add garlic and cook for 1 minute.", "Serve hot."],
      "article_html": "<p>Introductory story explaining why this recipe is delicious...</p><h3>Why You'll Love This Recipe</h3><ul><li>Quick and easy...</li></ul><h3>Chef's Secret Tips</h3><p>Tips for perfect results...</p><h3>Storage & Reheating</h3><p>Store in airtight container...</p>"
    }
    """

    user_prompt = ""
    if mode == "name":
        user_prompt = f"Create a full original recipe for the dish: '{recipe_input}'. Recommended category: {category}."
    else:
        user_prompt = f"Inspiration article/recipe to completely rewrite into a 100% unique original recipe for Make-Food.com:\n\n{recipe_input}"

    ai_response_text = ""
    try:
        if provider == "google":
            target_model = model if model else "gemini-2.5-flash"
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:generateContent?key={api_key}"
            payload = {
                "contents": [{"parts": [{"text": f"{system_instruction}\n\nTask:\n{user_prompt}"}]}],
                "generationConfig": {"responseMimeType": "application/json"}
            }
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=35) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                ai_response_text = data["candidates"][0]["content"]["parts"][0]["text"]
        elif provider == "openrouter":
            target_model = model if model else "openai/gpt-4o-mini"
            url = "https://openrouter.ai/api/v1/chat/completions"
            payload = {
                "model": target_model,
                "messages": [
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_prompt}
                ],
                "response_format": {"type": "json_object"}
            }
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=35) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                ai_response_text = data["choices"][0]["message"]["content"]

        # Parse cleaned JSON
        clean_json_str = ai_response_text.strip()
        if clean_json_str.startswith("```json"):
            clean_json_str = clean_json_str[7:]
        if clean_json_str.endswith("```"):
            clean_json_str = clean_json_str[:-3]
        clean_json_str = clean_json_str.strip()

        parsed = json.loads(clean_json_str)
        return {"success": True, "recipe": parsed}
    except Exception as e:
        print("AI generation error:", e)
        return {"success": False, "error": f"AI generation error: {str(e)}"}

# ================= DASHBOARD UI =================
@app.get("/", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=302)
    
    return """
    <!DOCTYPE html>
    <html lang="ar" dir="rtl" id="htmlRoot">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Make-Food.com — Portal الإدارة، المقالات والأرباح</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;800&family=Plus+Jakarta+Sans:wght@500;700;800&display=swap" rel="stylesheet">
        <style>
            body { font-family: 'Tajawal', 'Plus Jakarta Sans', sans-serif; }
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
                    <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-amber-500 to-emerald-500 flex items-center justify-center shadow-lg shadow-emerald-500/20 text-2xl flex-shrink-0">
                        🍲
                    </div>
                    <div>
                        <div class="flex items-center gap-2">
                            <h1 class="text-lg font-extrabold tracking-tight text-white font-num">Make-Food.com</h1>
                            <span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1 font-num">
                                <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                                LIVE
                            </span>
                            <span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20 font-num">
                                MAD (د.م.) 🇲🇦
                            </span>
                        </div>
                        <p id="topSubtitle" class="text-xs text-slate-400">لوحة التحكم، النشر والمداخيل الحصرية</p>
                    </div>
                </div>

                <!-- Tabs & Controls -->
                <div class="flex items-center gap-3">
                    <div class="bg-slate-900 border border-slate-800 rounded-xl p-1 flex items-center gap-1 text-xs">
                        <button onclick="switchTab('analytics')" id="tab-btn-analytics" class="px-3 py-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 font-bold border border-emerald-500/20 transition flex items-center gap-1.5">
                            <span>📊</span> <span id="tabNameAnalytics">الإحصائيات والأرباح</span>
                        </button>
                        <button onclick="switchTab('recipes')" id="tab-btn-recipes" class="px-3 py-1.5 rounded-lg text-slate-400 hover:text-white transition flex items-center gap-1.5">
                            <span>📝</span> <span id="tabNameRecipes">المقالات والوصفات</span>
                        </button>
                        <button onclick="switchTab('create')" id="tab-btn-create" class="px-3 py-1.5 rounded-lg text-slate-400 hover:text-white transition flex items-center gap-1.5">
                            <span>➕</span> <span id="tabNameCreate">نشر مقال جديد</span>
                        </button>
                        <button onclick="switchTab('settings')" id="tab-btn-settings" class="px-3 py-1.5 rounded-lg text-slate-400 hover:text-white transition flex items-center gap-1.5">
                            <span>⚙️</span> <span id="tabNameSettings">الإعدادات و الذكاء الاصطناعي</span>
                        </button>
                    </div>

                    <!-- Language Switcher Button -->
                    <button onclick="toggleLanguage()" id="langToggleBtn" class="px-3 py-1.5 text-xs font-bold bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-800 rounded-xl transition flex items-center gap-1.5">
                        <span>🌐</span> <span id="langBtnText">English</span>
                    </button>

                    <a href="/logout" title="تسجيل الخروج" class="px-3 py-1.5 text-xs font-bold text-slate-400 hover:text-rose-400 border border-slate-800 rounded-xl hover:border-rose-500/30 transition flex items-center gap-1">
                        <span id="logoutBtnText">خروج</span>
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
                        <h2 id="kpiSectionTitle" class="text-base font-bold text-white">مؤشرات الأداء والأرباح لـ make-food.com</h2>
                        <p id="kpiSectionSub" class="text-xs text-slate-400">مباشرة من Google AdSense Management API بعملة الدرهم المغربي (MAD)</p>
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
                        <div class="absolute top-0 right-0 w-24 h-24 bg-emerald-500/10 rounded-full blur-2xl"></div>
                        <div class="flex items-center justify-between text-slate-400 text-xs font-bold uppercase tracking-wider mb-2">
                            <span id="kpiTitleEarnings">إجمالي الأرباح</span>
                            <span class="text-emerald-400 font-bold font-num">MAD</span>
                        </div>
                        <div id="stat-earnings" class="text-3xl font-extrabold text-white tracking-tight font-num">0.00 د.م.</div>
                        <div class="text-[11px] text-slate-400 mt-2 flex items-center gap-1">
                            <span id="kpiSubEarnings" class="text-emerald-400 font-bold">100% مؤكد</span> من AdSense الرسمي
                        </div>
                    </div>

                    <!-- Pageviews -->
                    <div class="bg-slate-900 border border-slate-800/80 rounded-2xl p-5 relative overflow-hidden">
                        <div class="absolute top-0 right-0 w-24 h-24 bg-sky-500/10 rounded-full blur-2xl"></div>
                        <div class="flex items-center justify-between text-slate-400 text-xs font-bold uppercase tracking-wider mb-2">
                            <span id="kpiTitleViews">مشاهدات الصفحات</span>
                            <span class="text-sky-400 text-base">👁️</span>
                        </div>
                        <div id="stat-views" class="text-3xl font-extrabold text-white tracking-tight font-num">0</div>
                        <div id="kpiSubViews" class="text-[11px] text-slate-400 mt-2">
                            عدد قراءات المقالات
                        </div>
                    </div>

                    <!-- RPM in MAD -->
                    <div class="bg-slate-900 border border-slate-800/80 rounded-2xl p-5 relative overflow-hidden">
                        <div class="absolute top-0 right-0 w-24 h-24 bg-amber-500/10 rounded-full blur-2xl"></div>
                        <div class="flex items-center justify-between text-slate-400 text-xs font-bold uppercase tracking-wider mb-2">
                            <span id="kpiTitleRpm">معدل الربح (RPM)</span>
                            <span class="text-amber-400 text-base">📈</span>
                        </div>
                        <div id="stat-rpm" class="text-3xl font-extrabold text-white tracking-tight font-num">0.00 د.م.</div>
                        <div id="kpiSubRpm" class="text-[11px] text-slate-400 mt-2">
                            الربح لكل 1,000 مشاهدة
                        </div>
                    </div>

                    <!-- Impressions -->
                    <div class="bg-slate-900 border border-slate-800/80 rounded-2xl p-5 relative overflow-hidden">
                        <div class="absolute top-0 right-0 w-24 h-24 bg-purple-500/10 rounded-full blur-2xl"></div>
                        <div class="flex items-center justify-between text-slate-400 text-xs font-bold uppercase tracking-wider mb-2">
                            <span id="kpiTitleImps">ظهور الإعلانات</span>
                            <span class="text-purple-400 text-base">📊</span>
                        </div>
                        <div id="stat-impressions" class="text-3xl font-extrabold text-white tracking-tight font-num">0</div>
                        <div id="kpiSubImps" class="text-[11px] text-slate-400 mt-2">
                            مرات ظهور الإعلانات
                        </div>
                    </div>

                    <!-- Clicks & CTR -->
                    <div class="bg-slate-900 border border-slate-800/80 rounded-2xl p-5 relative overflow-hidden">
                        <div class="absolute top-0 right-0 w-24 h-24 bg-teal-500/10 rounded-full blur-2xl"></div>
                        <div class="flex items-center justify-between text-slate-400 text-xs font-bold uppercase tracking-wider mb-2">
                            <span id="kpiTitleClicks">النقرات (CTR)</span>
                            <span class="text-teal-400 text-base">🖱️</span>
                        </div>
                        <div id="stat-clicks" class="text-3xl font-extrabold text-white tracking-tight font-num">0 <span class="text-sm font-medium text-slate-400" id="stat-ctr">(0%)</span></div>
                        <div id="kpiSubClicks" class="text-[11px] text-slate-400 mt-2">
                            تفاعل الزوار مع الإعلانات
                        </div>
                    </div>
                </div>

                <!-- Charts Row -->
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <!-- Daily Revenue Chart -->
                    <div class="bg-slate-900 border border-slate-800/80 rounded-2xl p-6">
                        <div class="flex items-center justify-between mb-4">
                            <h2 id="chartTitleRevenue" class="text-base font-bold text-white flex items-center gap-2">
                                <span>💵 مسار الأرباح اليومية (بالدرهم المغربي)</span>
                            </h2>
                            <span class="text-xs text-slate-400 font-num">MAD</span>
                        </div>
                        <div class="h-64">
                            <canvas id="earningsChart"></canvas>
                        </div>
                    </div>

                    <!-- Traffic Chart -->
                    <div class="bg-slate-900 border border-slate-800/80 rounded-2xl p-6">
                        <div class="flex items-center justify-between mb-4">
                            <h2 id="chartTitleTraffic" class="text-base font-bold text-white flex items-center gap-2">
                                <span>📈 حركة المشاهدات والظهور اليومي</span>
                            </h2>
                            <span id="chartSubTraffic" class="text-xs text-slate-400">حجم الزيارات</span>
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
                            <h2 id="tableTitleCountries" class="text-base font-bold text-white">🌍 توزيع الأرباح حسب الدول</h2>
                            <span id="tableSubCountries" class="text-xs text-slate-400">مرتبة حسب العائد</span>
                        </div>
                        <div class="overflow-x-auto">
                            <table class="w-full text-right text-sm" id="countriesTableTag">
                                <thead class="text-xs uppercase text-slate-400 border-b border-slate-800">
                                    <tr>
                                        <th id="thCountry" class="py-3 px-3">الدولة</th>
                                        <th id="thViews" class="py-3 px-3 text-left">المشاهدات</th>
                                        <th id="thImps" class="py-3 px-3 text-left">الظهور</th>
                                        <th id="thEarn" class="py-3 px-3 text-left">الأرباح (د.م.)</th>
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
                                <h2 id="chartTitleDevices" class="text-base font-bold text-white">📱 توزيع الأجهزة</h2>
                                <span id="chartSubDevices" class="text-xs text-slate-400">الهاتف مقابل الحاسوب</span>
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
                        <h2 id="tableTitleDaily" class="text-base font-bold text-white">📅 السجل اليومي للأرباح والمشاهدات</h2>
                        <button onclick="exportCSV()" class="px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-bold transition flex items-center gap-1.5">
                            <span>📥</span> <span id="btnTextExport">تصدير ملف Excel / CSV</span>
                        </button>
                    </div>
                    <div class="overflow-x-auto max-h-96">
                        <table class="w-full text-right text-sm" id="dailyTableTag">
                            <thead class="text-xs uppercase text-slate-400 border-b border-slate-800 sticky top-0 bg-slate-900">
                                <tr>
                                    <th id="thDDate" class="py-3 px-4">التاريخ</th>
                                    <th id="thDEarn" class="py-3 px-4 text-left">الأرباح (د.م.)</th>
                                    <th id="thDViews" class="py-3 px-4 text-left">المشاهدات</th>
                                    <th id="thDRpm" class="py-3 px-4 text-left">الـ RPM (د.م.)</th>
                                    <th id="thDImps" class="py-3 px-4 text-left">الظهور</th>
                                    <th id="thDClicks" class="py-3 px-4 text-left">النقرات</th>
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
                            <h2 id="recipesListTitle" class="text-base font-bold text-white">جميع مقالات ووصفات make-food.com</h2>
                            <span id="recipes-count-badge" class="px-2 py-0.5 rounded-full text-xs font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-num">
                                1,181
                            </span>
                        </div>
                        <p id="recipesListSub" class="text-xs text-slate-400 mt-1">تصفح، ابحث وشاهد المقالات المنشورة حياً على الموقع</p>
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
                                <label id="lblPostTitle" class="block text-xs font-bold text-slate-300 mb-2">عنوان الوصفة / المقال *</label>
                                <input type="text" id="postTitle" required onkeyup="autoSlug()"
                                    placeholder="e.g. Crispy Garlic Parmesan Chicken Wings"
                                    class="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-xl text-white text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 transition font-num text-left" dir="ltr">
                            </div>
                            <div>
                                <label id="lblPostSlug" class="block text-xs font-bold text-slate-300 mb-2">رابط المقال (Slug) *</label>
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
                                <label id="lblPostCategory" class="block text-xs font-bold text-slate-300 mb-2">التصنيف (Category)</label>
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
                                <label id="lblPostAuthor" class="block text-xs font-bold text-slate-300 mb-2">اسم الكاتب (Author)</label>
                                <input type="text" id="postAuthor" value="Maria"
                                    class="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-xl text-white text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 transition font-num text-left" dir="ltr">
                            </div>
                            <div>
                                <label id="lblPostImage" class="block text-xs font-bold text-slate-300 mb-2">رابط الصورة البارزة (Image URL)</label>
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
                                <label id="lblPrepTime" class="block text-xs font-bold text-slate-300 mb-1">وقت التحضير (بالدقائق)</label>
                                <input type="number" id="postPrepTime" value="15" min="1"
                                    class="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm font-num text-center">
                            </div>
                            <div>
                                <label id="lblCookTime" class="block text-xs font-bold text-slate-300 mb-1">وقت الطهي (بالدقائق)</label>
                                <input type="number" id="postCookTime" value="25" min="0"
                                    class="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm font-num text-center">
                            </div>
                            <div>
                                <label id="lblServings" class="block text-xs font-bold text-slate-300 mb-1">عدد الحصص (Servings)</label>
                                <input type="number" id="postServings" value="4" min="1"
                                    class="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm font-num text-center">
                            </div>
                        </div>

                        <!-- Short Description -->
                        <div>
                            <label id="lblPostDesc" class="block text-xs font-bold text-slate-300 mb-2">مقدمة ووصف مختصر للوصفة (Excerpt / Description) *</label>
                            <textarea id="postDescription" rows="2" required
                                placeholder="اكتب وصفاً جذاباً ومختصراً يصف هذه الوصفة..."
                                class="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-xl text-white text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 transition"></textarea>
                        </div>

                        <!-- Ingredients Builder -->
                        <div>
                            <div class="flex items-center justify-between mb-2">
                                <label id="lblPostIngs" class="text-xs font-bold text-slate-300">المكونات (Ingredients) — سطر لكل مكون *</label>
                                <span class="text-[11px] text-slate-400">مثال: 500g Chicken breast, sliced</span>
                            </div>
                            <textarea id="postIngredients" rows="4" required dir="ltr"
                                placeholder="2 tbsp olive oil&#10;1 tsp smoked paprika&#10;3 cloves garlic, minced&#10;Salt and freshly cracked black pepper"
                                class="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-xl text-white text-xs focus:outline-none focus:ring-2 focus:ring-emerald-500 transition font-num text-left"></textarea>
                        </div>

                        <!-- Instructions Builder -->
                        <div>
                            <div class="flex items-center justify-between mb-2">
                                <label id="lblPostSteps" class="text-xs font-bold text-slate-300">خطوات التحضير (Instructions / Steps) — سطر لكل خطوة *</label>
                                <span id="lblPostStepsSub" class="text-[11px] text-slate-400">يتم ترقيمها تلقائياً</span>
                            </div>
                            <textarea id="postInstructions" rows="4" required dir="ltr"
                                placeholder="Preheat the oven to 400°F (200°C) and line a baking sheet.&#10;In a large bowl, toss the ingredients until evenly coated.&#10;Spread evenly on the baking sheet and bake for 25 minutes until golden brown."
                                class="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-xl text-white text-xs focus:outline-none focus:ring-2 focus:ring-emerald-500 transition font-num text-left"></textarea>
                        </div>

                        <!-- Article Body HTML -->
                        <div>
                            <label id="lblPostHtml" class="block text-xs font-bold text-slate-300 mb-2">نص المقال الكامل (Article Body / HTML) [اختياري]</label>
                            <textarea id="postArticleHtml" rows="5" dir="ltr"
                                placeholder="<p>This easy chicken recipe is perfect for busy weeknights...</p><h3>Why You Will Love This Recipe</h3><p>...</p>"
                                class="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-xl text-white text-xs focus:outline-none focus:ring-2 focus:ring-emerald-500 transition font-mono text-left"></textarea>
                        </div>

                        <!-- Submit Button -->
                        <div class="pt-4 border-t border-slate-800 flex items-center justify-between">
                            <p class="text-xs text-slate-400 flex items-center gap-1.5">
                                <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                                <span id="publishNoteText">سيتم نشر المقال فورياً وتحديث النطاق الحي</span>
                            </p>
                            <button type="submit" id="btnPublish"
                                class="py-3 px-8 bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-slate-950 font-extrabold rounded-xl shadow-lg shadow-emerald-500/25 transition duration-200 text-sm flex items-center gap-2">
                                <span>🚀</span> <span id="btnTextPublish">نشر المقال في make-food.com</span>
                            </button>
                        </div>
                    </form>
                </div>
            </div>

            <!-- ================= TAB 4: SETTINGS (AI & PROVIDERS) ================= -->
            <div id="tab-settings" class="hidden space-y-6">
                <div class="bg-slate-900 border border-slate-800/80 rounded-2xl p-6 sm:p-8 max-w-3xl mx-auto space-y-6">
                    <div class="border-b border-slate-800 pb-4 flex items-center justify-between">
                        <div>
                            <h2 id="settingsTitle" class="text-lg font-bold text-white">⚙️ إعدادات الذكاء الاصطناعي (AI Provider Settings)</h2>
                            <p id="settingsSub" class="text-xs text-slate-400 mt-1">اختر مزود الذكاء الاصطناعي (Google Gemini أو OpenRouter) وقم بجلب النماذج لكتابة المقالات</p>
                        </div>
                        <span class="text-2xl">🤖</span>
                    </div>

                    <!-- Provider Selector -->
                    <div>
                        <label id="lblProvider" class="block text-xs font-bold text-slate-300 mb-2">مزود الخدمة (AI Provider)</label>
                        <div class="grid grid-cols-2 gap-4">
                            <label class="flex items-center gap-3 p-3.5 bg-slate-800/80 border border-slate-700 rounded-xl cursor-pointer hover:border-emerald-500/50 transition">
                                <input type="radio" name="aiProvider" value="google" checked onchange="onProviderChange()" class="text-emerald-500 focus:ring-emerald-500">
                                <div>
                                    <div class="text-sm font-bold text-white">Google Gemini API</div>
                                    <div class="text-[11px] text-slate-400">Gemini 2.5 Flash / Pro (سريع ودقيق)</div>
                                </div>
                            </label>
                            <label class="flex items-center gap-3 p-3.5 bg-slate-800/80 border border-slate-700 rounded-xl cursor-pointer hover:border-emerald-500/50 transition">
                                <input type="radio" name="aiProvider" value="openrouter" onchange="onProviderChange()" class="text-emerald-500 focus:ring-emerald-500">
                                <div>
                                    <div class="text-sm font-bold text-white">OpenRouter API</div>
                                    <div class="text-[11px] text-slate-400">Claude 3.5, GPT-4o, DeepSeek, Llama</div>
                                </div>
                            </label>
                        </div>
                    </div>

                    <!-- API Key Input -->
                    <div>
                        <label id="lblApiKey" class="block text-xs font-bold text-slate-300 mb-2">مفتاح الـ API (API Key) *</label>
                        <div class="relative">
                            <input type="password" id="inputApiKey" dir="ltr"
                                placeholder="AIzaSy... or sk-or-v1-..."
                                class="w-full px-4 py-3 bg-slate-800 border border-slate-700 rounded-xl text-white text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 text-left font-num">
                            <button type="button" onclick="toggleApiKeyVisibility()" class="absolute right-3 top-3 text-xs text-slate-400 hover:text-white">
                                👁️
                            </button>
                        </div>
                        <p class="text-[11px] text-slate-400 mt-1.5">
                            🔒 <span id="apiKeySafetyNote">يتم حفظ المفتاح بأمان في متصفحك ولا يتم مشاركته مع أي طرف خارجي.</span>
                        </p>
                    </div>

                    <!-- Fetch Models Button & Dropdown -->
                    <div class="p-4 bg-slate-800/40 rounded-xl border border-slate-800 space-y-4">
                        <div class="flex items-center justify-between">
                            <div>
                                <h4 id="fetchModelsTitle" class="text-xs font-bold text-white">النماذج المتاحة (Available Models)</h4>
                                <p id="fetchModelsSub" class="text-[11px] text-slate-400">اضغط على جلب النماذج لاسترداد القائمة الكاملة المتاحة لحسابك</p>
                            </div>
                            <button type="button" onclick="fetchModelsFromApi()" id="btnFetchModels"
                                class="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-xl text-xs font-bold transition flex items-center gap-1.5">
                                <span>🔄</span> <span id="btnTextFetchModels">جلب النماذج (Fetch Models)</span>
                            </button>
                        </div>

                        <div>
                            <select id="selectModel" class="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-xl text-white text-xs font-num focus:outline-none focus:ring-2 focus:ring-emerald-500">
                                <option value="gemini-2.5-flash">Gemini 2.5 Flash (افتراضي موصى به)</option>
                                <option value="gemini-1.5-pro">Gemini 1.5 Pro</option>
                                <option value="gemini-1.5-flash">Gemini 1.5 Flash</option>
                            </select>
                        </div>
                    </div>

                    <!-- Save Settings Button -->
                    <div class="pt-4 border-t border-slate-800 flex items-center justify-between">
                        <span id="saveStatusMsg" class="text-xs text-emerald-400 font-bold"></span>
                        <button type="button" onclick="saveAiSettings()"
                            class="py-3 px-8 bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-slate-950 font-extrabold rounded-xl shadow-lg shadow-emerald-500/25 transition text-sm">
                            <span id="btnTextSaveSettings">💾 حفظ الإعدادات</span>
                        </button>
                    </div>
                </div>
            </div>
        </main>

        <footer class="border-t border-slate-800/80 py-6 mt-12 text-center text-xs text-slate-500">
            Make-Food.com Partner Portal • أرباح AdSense بالدرهم المغربي MAD 🇲🇦 • محرك كتابة الوصفات بالذكاء الاصطناعي
        </footer>

        <!-- JS Logic with i18n Dictionary -->
        <script>
            let currentLang = localStorage.getItem('portal_lang') || 'ar';
            let currentRange = 'last30';
            let earningsChart, trafficChart, platformChart;
            let rawDailyData = [];
            let allRecipesData = [];
            let currentAiMode = 'name';

            // Translations
            const dict = {
                ar: {
                    topSubtitle: "لوحة التحكم، النشر والمداخيل الحصرية",
                    tabAnalytics: "الإحصائيات والأرباح",
                    tabRecipes: "المقالات والوصفات",
                    tabCreate: "نشر مقال جديد",
                    tabSettings: "الإعدادات و الذكاء الاصطناعي",
                    logout: "خروج",
                    langBtn: "English",
                    kpiTitle: "مؤشرات الأداء والأرباح لـ make-food.com",
                    kpiSub: "مباشرة من Google AdSense Management API بعملة الدرهم المغربي (MAD)",
                    earnings: "إجمالي الأرباح",
                    earningsSub: "100% مؤكد من AdSense الرسمي",
                    views: "مشاهدات الصفحات",
                    viewsSub: "عدد قراءات المقالات",
                    rpm: "معدل الربح (RPM)",
                    rpmSub: "الربح لكل 1,000 مشاهدة",
                    impressions: "ظهور الإعلانات",
                    impressionsSub: "مرات ظهور الإعلانات",
                    clicks: "النقرات (CTR)",
                    clicksSub: "تفاعل الزوار مع الإعلانات",
                    chartRevenue: "💵 مسار الأرباح اليومية (بالدرهم المغربي)",
                    chartTraffic: "📈 حركة المشاهدات والظهور اليومي",
                    chartTrafficSub: "حجم الزيارات",
                    countriesTitle: "🌍 توزيع الأرباح حسب الدول",
                    countriesSub: "مرتبة حسب العائد",
                    thCountry: "الدولة",
                    thViews: "المشاهدات",
                    thImps: "الظهور",
                    thEarn: "الأرباح (د.م.)",
                    devicesTitle: "📱 توزيع الأجهزة",
                    devicesSub: "الهاتف مقابل الحاسوب",
                    dailyTitle: "📅 السجل اليومي للأرباح والمشاهدات",
                    btnExport: "تصدير ملف Excel / CSV",
                    recipesTitle: "جميع مقالات ووصفات make-food.com",
                    recipesSub: "تصفح، ابحث وشاهد المقالات المنشورة حياً على الموقع",
                    searchPlaceholder: "🔍 ابحث عن أي وصفة أو تصنيف...",
                    aiTitle: "المساعد الذكي لكتابة وإعادة صياغة الوصفات (AI Recipe Studio)",
                    modeName: "💡 فقط باسم الوصفة",
                    modeRewrite: "🔄 إعادة صياغة مقال / إلهام",
                    lblAiName: "اكتب اسم الوصفة بالإنجليزية (مثال: Tuscan Garlic Butter Salmon):",
                    lblAiRewrite: "ضع رابط أو نص المقال الخارجي لإعادة صياغته بطريقة حصرية واحترافية:",
                    btnGenerateAi: "توليد الوصفة بالذكاء الاصطناعي",
                    aiNote: "يقوم الذكاء الاصطناعي بتوليد العنوان، المكونات، الخطوات، وقت الطهي، ومقالة SEO كاملة.",
                    formTitle: "تفاصيل المقال والوصفة لـ make-food.com",
                    formSub: "راجع البيانات ثم اضغط نشر لتظهر فورياً على الموقع الحي",
                    btnPublish: "نشر المقال في make-food.com",
                    settingsTitle: "⚙️ إعدادات الذكاء الاصطناعي (AI Provider Settings)",
                    settingsSub: "اختر مزود الذكاء الاصطناعي (Google Gemini أو OpenRouter) وقم بجلب النماذج لكتابة المقالات",
                    lblProvider: "مزود الخدمة (AI Provider)",
                    lblApiKey: "مفتاح الـ API (API Key) *",
                    apiKeyNote: "يتم حفظ المفتاح بأمان في متصفحك ولا يتم مشاركته مع أي طرف خارجي.",
                    fetchTitle: "النماذج المتاحة (Available Models)",
                    fetchSub: "اضغط على جلب النماذج لاسترداد القائمة الكاملة المتاحة لحسابك",
                    btnFetch: "جلب النماذج (Fetch Models)",
                    btnSaveSettings: "💾 حفظ الإعدادات"
                },
                en: {
                    topSubtitle: "Make-Food.com Partner Management & Revenue Portal",
                    tabAnalytics: "Revenue & Analytics",
                    tabRecipes: "Articles & Recipes",
                    tabCreate: "Create New Post",
                    tabSettings: "Settings & AI Models",
                    logout: "Logout",
                    langBtn: "العربية",
                    kpiTitle: "Performance & Revenue Metrics for make-food.com",
                    kpiSub: "Directly from Google AdSense Management API in Moroccan Dirhams (MAD)",
                    earnings: "Total Revenue",
                    earningsSub: "100% verified from official AdSense",
                    views: "Page Views",
                    viewsSub: "Direct recipe article reads",
                    rpm: "Page RPM",
                    rpmSub: "Revenue per 1,000 views",
                    impressions: "Ad Impressions",
                    impressionsSub: "Ad impressions served",
                    clicks: "Clicks (CTR)",
                    clicksSub: "User ad engagement",
                    chartRevenue: "💵 Daily Revenue Trend (in MAD)",
                    chartTraffic: "📈 Daily Views & Impressions",
                    chartTrafficSub: "Traffic volume",
                    countriesTitle: "🌍 Top Countries by Performance",
                    countriesSub: "Ranked by earnings",
                    thCountry: "Country",
                    thViews: "Pageviews",
                    thImps: "Impressions",
                    thEarn: "Earnings (MAD)",
                    devicesTitle: "📱 Device Breakdown",
                    devicesSub: "Mobile vs Desktop share",
                    dailyTitle: "📅 Daily Detailed Revenue & Traffic Log",
                    btnExport: "Export CSV / Excel",
                    recipesTitle: "All Articles & Recipes for make-food.com",
                    recipesSub: "Search, filter and view live articles on the website",
                    searchPlaceholder: "🔍 Search recipes or categories...",
                    aiTitle: "AI Recipe Authoring & Rewriting Studio",
                    modeName: "💡 From Recipe Name",
                    modeRewrite: "🔄 Rewrite from Inspiration",
                    lblAiName: "Enter recipe name in English (e.g. Tuscan Garlic Butter Salmon):",
                    lblAiRewrite: "Paste external article text or URL to rewrite into a unique recipe:",
                    btnGenerateAi: "Generate Recipe with AI",
                    aiNote: "AI will automatically generate the Title, Ingredients, Steps, Timings, and complete SEO story.",
                    formTitle: "Recipe & Article Details for make-food.com",
                    formSub: "Review generated content and click publish to deploy live instantly",
                    btnPublish: "Publish to make-food.com Live",
                    settingsTitle: "⚙️ AI Provider Settings & Model Selector",
                    settingsSub: "Configure Google Gemini or OpenRouter API to fetch models and power recipe writing",
                    lblProvider: "AI Provider",
                    lblApiKey: "API Key *",
                    apiKeyNote: "Your key is stored securely in your browser and used only for recipe generation.",
                    fetchTitle: "Available Models",
                    fetchSub: "Click Fetch Models to pull the latest models available for your account",
                    btnFetch: "Fetch Models",
                    btnSaveSettings: "💾 Save Settings"
                }
            };

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
                document.getElementById('chartSubTraffic').innerText = t.chartTrafficSub;
                document.getElementById('tableTitleCountries').innerText = t.countriesTitle;
                document.getElementById('tableSubCountries').innerText = t.countriesSub;
                document.getElementById('thCountry').innerText = t.thCountry;
                document.getElementById('thViews').innerText = t.thViews;
                document.getElementById('thImps').innerText = t.thImps;
                document.getElementById('thEarn').innerText = t.thEarn;

                document.getElementById('chartTitleDevices').innerText = t.devicesTitle;
                document.getElementById('chartSubDevices').innerText = t.devicesSub;
                document.getElementById('tableTitleDaily').innerText = t.dailyTitle;
                document.getElementById('btnTextExport').innerText = t.btnExport;

                document.getElementById('recipesListTitle').innerText = t.recipesTitle;
                document.getElementById('recipesListSub').innerText = t.recipesSub;
                document.getElementById('recipeSearchInput').placeholder = t.searchPlaceholder;

                document.getElementById('aiStudioTitle').innerText = t.aiTitle;
                document.getElementById('aiModeBtnName').innerText = t.modeName;
                document.getElementById('aiModeBtnRewrite').innerText = t.modeRewrite;
                document.getElementById('lblAiName').innerText = t.lblAiName;
                document.getElementById('lblAiRewrite').innerText = t.lblAiRewrite;
                document.getElementById('btnTextGenerateAi').innerText = t.btnGenerateAi;
                document.getElementById('aiNoteText').innerText = t.aiNote;

                document.getElementById('formSectionTitle').innerText = t.formTitle;
                document.getElementById('formSectionSub').innerText = t.formSub;
                document.getElementById('btnTextPublish').innerText = t.btnPublish;

                document.getElementById('settingsTitle').innerText = t.settingsTitle;
                document.getElementById('settingsSub').innerText = t.settingsSub;
                document.getElementById('lblProvider').innerText = t.lblProvider;
                document.getElementById('lblApiKey').innerText = t.lblApiKey;
                document.getElementById('apiKeySafetyNote').innerText = t.apiKeyNote;
                document.getElementById('fetchModelsTitle').innerText = t.fetchTitle;
                document.getElementById('fetchModelsSub').innerText = t.fetchSub;
                document.getElementById('btnTextFetchModels').innerText = t.btnFetch;
                document.getElementById('btnTextSaveSettings').innerText = t.btnSaveSettings;
            }

            function toggleLanguage() {
                applyLanguage(currentLang === 'ar' ? 'en' : 'ar');
            }

            function switchTab(tabId) {
                ['analytics', 'recipes', 'create', 'settings'].forEach(t => {
                    document.getElementById('tab-' + t).classList.add('hidden');
                    const btn = document.getElementById('tab-btn-' + t);
                    btn.className = "px-3 py-1.5 rounded-lg text-slate-400 hover:text-white transition flex items-center gap-1.5";
                });
                document.getElementById('tab-' + tabId).classList.remove('hidden');
                document.getElementById('tab-btn-' + tabId).className = "px-3 py-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 font-bold border border-emerald-500/20 transition flex items-center gap-1.5";

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
                document.getElementById('stat-earnings').innerText = t.earnings.toFixed(2) + ' MAD';
                document.getElementById('stat-views').innerText = t.views.toLocaleString();
                document.getElementById('stat-rpm').innerText = t.rpm.toFixed(2) + ' MAD';
                document.getElementById('stat-impressions').innerText = t.impressions.toLocaleString();
                document.getElementById('stat-clicks').innerText = t.clicks.toLocaleString();
                document.getElementById('stat-ctr').innerText = `(${t.ctr}%)`;

                rawDailyData = data.daily || [];
                const labels = rawDailyData.map(d => d.date);
                const earnings = rawDailyData.map(d => d.earnings);
                const views = rawDailyData.map(d => d.pageviews);
                const impressions = rawDailyData.map(d => d.impressions);

                // 1. Earnings Chart (Always in MAD)
                if (earningsChart) earningsChart.destroy();
                const ctxE = document.getElementById('earningsChart').getContext('2d');
                earningsChart = new Chart(ctxE, {
                    type: 'line',
                    data: {
                        labels: labels,
                        datasets: [{
                            label: currentLang === 'ar' ? 'الأرباح (د.م.)' : 'Earnings (MAD)',
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
                            tooltip: { callbacks: { label: c => c.parsed.y.toFixed(2) + ' MAD' } }
                        },
                        scales: {
                            x: { grid: { color: 'rgba(51, 65, 85, 0.3)' }, ticks: { color: '#94a3b8', font: { size: 10 } } },
                            y: { grid: { color: 'rgba(51, 65, 85, 0.3)' }, ticks: { color: '#94a3b8', callback: v => v + ' MAD' } }
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
                                label: currentLang === 'ar' ? 'مشاهدات المقالات' : 'Pageviews',
                                data: views,
                                backgroundColor: '#38bdf8',
                                borderRadius: 4
                            },
                            {
                                label: currentLang === 'ar' ? 'ظهور الإعلانات' : 'Impressions',
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
                const pLabels = plats.map(p => {
                    if (currentLang === 'ar') return p.platform.replace('High-end mobile devices', 'الهواتف').replace('Desktop', 'الحواسيب').replace('Tablets', 'التابليت');
                    return p.platform.replace('High-end mobile devices', 'Mobile').replace('Tablets', 'Tablet');
                });
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
                            tooltip: { callbacks: { label: c => `${c.label}: ${c.parsed.toFixed(2)} MAD` } }
                        }
                    }
                });

                // Platform Cards
                document.getElementById('platformCards').innerHTML = plats.map(p => {
                    const shortName = currentLang === 'ar' 
                        ? p.platform.replace('High-end mobile devices', 'الهواتف').replace('Desktop', 'الحواسيب').replace('Tablets', 'التابليت')
                        : p.platform.replace('High-end mobile devices', 'Mobile').replace('Tablets', 'Tablet');
                    return `
                        <div class="bg-slate-800/50 p-2 rounded-xl">
                            <div class="text-[10px] text-slate-400">${shortName}</div>
                            <div class="text-sm font-bold text-white font-num">${p.earnings.toFixed(2)} MAD</div>
                            <div class="text-[10px] text-slate-400 font-num">${p.pageviews} views</div>
                        </div>
                    `;
                }).join('');

                // Countries Table
                const cTbody = document.getElementById('countryTableBody');
                if (!data.countries || data.countries.length === 0) {
                    cTbody.innerHTML = '<tr><td colspan="4" class="py-4 text-center text-slate-500">No data available</td></tr>';
                } else {
                    cTbody.innerHTML = data.countries.map(c => `
                        <tr class="hover:bg-slate-800/30 transition">
                            <td class="py-2.5 px-3 font-medium text-white">${c.country}</td>
                            <td class="py-2.5 px-3 font-num ${currentLang === 'en' ? 'text-left' : 'text-left'}">${c.pageviews.toLocaleString()}</td>
                            <td class="py-2.5 px-3 font-num ${currentLang === 'en' ? 'text-left' : 'text-left'}">${c.impressions.toLocaleString()}</td>
                            <td class="py-2.5 px-3 font-bold text-emerald-400 font-num ${currentLang === 'en' ? 'text-left' : 'text-left'}">${c.earnings.toFixed(2)} MAD</td>
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
                            <td class="py-2.5 px-4 font-bold text-emerald-400 ${currentLang === 'en' ? 'text-left' : 'text-left'}">${d.earnings.toFixed(2)} MAD</td>
                            <td class="py-2.5 px-4 ${currentLang === 'en' ? 'text-left' : 'text-left'}">${d.pageviews.toLocaleString()}</td>
                            <td class="py-2.5 px-4 text-amber-400 ${currentLang === 'en' ? 'text-left' : 'text-left'}">${d.rpm.toFixed(2)} MAD</td>
                            <td class="py-2.5 px-4 ${currentLang === 'en' ? 'text-left' : 'text-left'}">${d.impressions.toLocaleString()}</td>
                            <td class="py-2.5 px-4 ${currentLang === 'en' ? 'text-left' : 'text-left'}">${d.clicks}</td>
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
                    document.getElementById('recipes-count-badge').innerText = `${data.total.toLocaleString()} recipes`;
                    renderRecipesGrid(allRecipesData);
                } catch (e) {
                    console.error("Failed to load recipes:", e);
                }
            }

            function renderRecipesGrid(recipes) {
                const container = document.getElementById('recipesGrid');
                if (!recipes.length) {
                    container.innerHTML = '<div class="col-span-3 text-center py-12 text-slate-500">No recipes found matching your query.</div>';
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
                                <a href="${r.url}" target="_blank" class="text-xs font-bold text-emerald-400 hover:text-emerald-300 flex items-center gap-1 font-num">
                                    <span>${currentLang === 'ar' ? 'مشاهدة حية ↗' : 'View Live ↗'}</span>
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

            // ================= AI STUDIO LOGIC =================
            function setAiMode(mode) {
                currentAiMode = mode;
                if (mode === 'name') {
                    document.getElementById('aiModeBtnName').className = "flex-1 py-1.5 rounded-lg bg-emerald-500/20 text-emerald-300 font-bold transition";
                    document.getElementById('aiModeBtnRewrite').className = "flex-1 py-1.5 rounded-lg text-slate-400 hover:text-white transition";
                    document.getElementById('aiNameInputBox').classList.remove('hidden');
                    document.getElementById('aiRewriteInputBox').classList.add('hidden');
                } else {
                    document.getElementById('aiModeBtnRewrite').className = "flex-1 py-1.5 rounded-lg bg-emerald-500/20 text-emerald-300 font-bold transition";
                    document.getElementById('aiModeBtnName').className = "flex-1 py-1.5 rounded-lg text-slate-400 hover:text-white transition";
                    document.getElementById('aiRewriteInputBox').classList.remove('hidden');
                    document.getElementById('aiNameInputBox').classList.add('hidden');
                }
            }

            async function triggerAiGeneration() {
                const provider = localStorage.getItem('ai_provider') || 'google';
                const apiKey = localStorage.getItem('ai_api_key') || '';
                const model = localStorage.getItem('ai_model') || (provider === 'google' ? 'gemini-2.5-flash' : 'openai/gpt-4o-mini');

                if (!apiKey) {
                    alert(currentLang === 'ar' ? 'يرجى إدخال وحفظ مفتاح الـ API في تبويب (الإعدادات) أولاً!' : 'Please enter and save your API Key in the Settings tab first!');
                    switchTab('settings');
                    return;
                }

                const inputVal = currentAiMode === 'name' 
                    ? document.getElementById('aiRecipeName').value.trim() 
                    : document.getElementById('aiSourceContent').value.trim();

                if (!inputVal) {
                    alert(currentLang === 'ar' ? 'يرجى كتابة اسم الوصفة أو وضع نص المقال أولاً!' : 'Please provide recipe name or source text first!');
                    return;
                }

                const btn = document.getElementById('btnGenerateAi');
                btn.disabled = true;
                btn.innerHTML = `<span>⏳</span> <span>${currentLang === 'ar' ? 'جاري التوليد بالذكاء الاصطناعي...' : 'Generating with AI...'}</span>`;

                try {
                    const res = await fetch('/api/ai/generate', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            provider: provider,
                            api_key: apiKey,
                            model: model,
                            mode: currentAiMode,
                            recipe_input: inputVal,
                            category: document.getElementById('postCategory').value
                        })
                    });
                    const data = await res.json();
                    if (data.success && data.recipe) {
                        const r = data.recipe;
                        document.getElementById('postTitle').value = r.title || '';
                        document.getElementById('postSlug').value = r.slug || '';
                        if (r.category) document.getElementById('postCategory').value = r.category;
                        document.getElementById('postPrepTime').value = r.prep_time || 15;
                        document.getElementById('postCookTime').value = r.cook_time || 25;
                        document.getElementById('postServings').value = r.servings || 4;
                        document.getElementById('postDescription').value = r.description || '';
                        if (r.featured_image) {
                            document.getElementById('postImage').value = r.featured_image;
                            previewImage();
                        }
                        if (Array.isArray(r.ingredients)) {
                            document.getElementById('postIngredients').value = r.ingredients.join('\\n');
                        }
                        if (Array.isArray(r.instructions)) {
                            document.getElementById('postInstructions').value = r.instructions.join('\\n');
                        }
                        document.getElementById('postArticleHtml').value = r.article_html || '';

                        // Scroll down to form
                        document.getElementById('createRecipeForm').scrollIntoView({ behavior: 'smooth' });
                    } else {
                        alert('Error: ' + (data.error || 'Failed to generate recipe'));
                    }
                } catch (e) {
                    alert('Request error: ' + e);
                } finally {
                    btn.disabled = false;
                    btn.innerHTML = `<span>✨</span> <span>${dict[currentLang].btnGenerateAi}</span>`;
                }
            }

            // ================= SETTINGS LOGIC =================
            function onProviderChange() {
                const provider = document.querySelector('input[name="aiProvider"]:checked').value;
                const select = document.getElementById('selectModel');
                if (provider === 'google') {
                    select.innerHTML = `
                        <option value="gemini-2.5-flash">Gemini 2.5 Flash (Recommended)</option>
                        <option value="gemini-1.5-pro">Gemini 1.5 Pro</option>
                        <option value="gemini-1.5-flash">Gemini 1.5 Flash</option>
                    `;
                } else {
                    select.innerHTML = `
                        <option value="openai/gpt-4o-mini">GPT-4o Mini (Fast & Cheap)</option>
                        <option value="anthropic/claude-3.5-sonnet">Claude 3.5 Sonnet</option>
                        <option value="deepseek/deepseek-chat">DeepSeek Chat V3</option>
                        <option value="meta-llama/llama-3.3-70b-instruct">Llama 3.3 70B</option>
                    `;
                }
            }

            function toggleApiKeyVisibility() {
                const inp = document.getElementById('inputApiKey');
                inp.type = inp.type === 'password' ? 'text' : 'password';
            }

            async function fetchModelsFromApi() {
                const provider = document.querySelector('input[name="aiProvider"]:checked').value;
                const apiKey = document.getElementById('inputApiKey').value.trim();
                if (!apiKey) {
                    alert(currentLang === 'ar' ? 'يرجى إدخال مفتاح الـ API أولاً لجلب النماذج!' : 'Please enter API Key first to fetch models!');
                    return;
                }

                const btn = document.getElementById('btnFetchModels');
                btn.disabled = true;
                btn.innerHTML = `<span>⏳ Fetching...</span>`;

                try {
                    const res = await fetch('/api/ai/models', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ provider: provider, api_key: apiKey })
                    });
                    const data = await res.json();
                    if (data.success && data.models && data.models.length > 0) {
                        const select = document.getElementById('selectModel');
                        select.innerHTML = data.models.map(m => `<option value="${m.id}">${m.name}</option>`).join('');
                        alert(currentLang === 'ar' ? `تم جلب ${data.models.length} نموذج متاح بنجاح!` : `Successfully fetched ${data.models.length} available models!`);
                    } else {
                        alert('Could not fetch models: ' + (data.error || 'Unknown error'));
                    }
                } catch (e) {
                    alert('Connection error: ' + e);
                } finally {
                    btn.disabled = false;
                    btn.innerHTML = `<span>🔄</span> <span>${dict[currentLang].btnFetch}</span>`;
                }
            }

            function saveAiSettings() {
                const provider = document.querySelector('input[name="aiProvider"]:checked').value;
                const apiKey = document.getElementById('inputApiKey').value.trim();
                const model = document.getElementById('selectModel').value;

                localStorage.setItem('ai_provider', provider);
                if (apiKey) localStorage.setItem('ai_api_key', apiKey);
                localStorage.setItem('ai_model', model);

                document.getElementById('activeAiModelBadge').innerText = `${provider.toUpperCase()}: ${model}`;
                const msg = document.getElementById('saveStatusMsg');
                msg.innerText = currentLang === 'ar' ? '✓ تم حفظ الإعدادات بنجاح!' : '✓ Settings saved successfully!';
                setTimeout(() => { msg.innerText = ''; }, 3000);
            }

            function loadAiSettings() {
                const provider = localStorage.getItem('ai_provider') || 'google';
                const apiKey = localStorage.getItem('ai_api_key') || '';
                const model = localStorage.getItem('ai_model') || (provider === 'google' ? 'gemini-2.5-flash' : 'openai/gpt-4o-mini');

                const rad = document.querySelector(`input[name="aiProvider"][value="${provider}"]`);
                if (rad) rad.checked = true;
                onProviderChange();

                if (apiKey) document.getElementById('inputApiKey').value = apiKey;
                const sel = document.getElementById('selectModel');
                if (sel) {
                    let opt = sel.querySelector(`option[value="${model}"]`);
                    if (!opt) {
                        const newOpt = document.createElement('option');
                        newOpt.value = model;
                        newOpt.innerText = model;
                        sel.appendChild(newOpt);
                    }
                    sel.value = model;
                }
                document.getElementById('activeAiModelBadge').innerText = `${provider.toUpperCase()}: ${model}`;
            }

            async function handleCreateRecipe(e) {
                e.preventDefault();
                const btn = document.getElementById('btnPublish');
                btn.disabled = true;
                btn.innerHTML = `<span>⏳</span> <span>${currentLang === 'ar' ? 'جاري النشر وتحديث make-food.com...' : 'Publishing & rebuilding make-food.com...'}</span>`;

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
                        alert(`🎉 ${result.message}\\n\\nLive URL:\\n${result.live_url}`);
                        document.getElementById('createRecipeForm').reset();
                        document.getElementById('imagePreviewBox').classList.add('hidden');
                        switchTab('recipes');
                        loadRecipesList();
                    } else {
                        alert('Publication error: ' + (result.error || 'Unknown error'));
                    }
                } catch (err) {
                    alert('Server error: ' + err);
                } finally {
                    btn.disabled = false;
                    btn.innerHTML = `<span>🚀</span> <span>${dict[currentLang].btnPublish}</span>`;
                }
            }

            // Init
            applyLanguage(currentLang);
            loadDashboardData();
            loadAiSettings();
        </script>
    </body>
    </html>
    """

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

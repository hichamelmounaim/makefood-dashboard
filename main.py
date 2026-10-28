import os
import json
import time
import hmac
import hashlib
import urllib.request
import urllib.parse
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Request, Response, Form, HTTPException, status, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uuid
import shutil
import base64

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

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

def get_template(name: str) -> str:
    path = os.path.join(TEMPLATES_DIR, name)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

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
    recipes_cache["data"] = all_recipes
    recipes_cache["last_loaded"] = time.time()

    gh_h = {
        "Authorization": f"token {CONFIG['GITHUB_TOKEN']}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json"
    }

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
        "message": commit_message,
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

    coolify_h = {"Authorization": f"Bearer {CONFIG['COOLIFY_TOKEN']}", "Content-Type": "application/json"}
    req_dep = urllib.request.Request(f"{CONFIG['COOLIFY_URL']}/api/v1/deploy?uuid={CONFIG['MAKEFOOD_COOLIFY_UUID']}", headers=coolify_h, method="POST")
    try:
        urllib.request.urlopen(req_dep)
    except Exception as e:
        print("Note: Coolify deploy trigger exception:", e)

# Rate limiting tracking for login
failed_login_attempts = {}

def sign_session(username: str) -> str:
    ts = str(int(time.time()))
    payload = f"{username}:{ts}"
    sig = hmac.new(CONFIG["SECRET_KEY"].encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{username}:{ts}:{sig}"

def verify_session(token: str) -> Optional[str]:
    try:
        parts = token.split(":")
        if len(parts) == 3:
            username, ts, sig = parts
            # Check 30 days expiration
            if int(ts) < int(time.time()) - (86400 * 30):
                return None
            payload = f"{username}:{ts}"
            expected = hmac.new(CONFIG["SECRET_KEY"].encode(), payload.encode(), hashlib.sha256).hexdigest()
            if hmac.compare_digest(sig, expected):
                return username
        elif len(parts) == 2:
            # Backwards compatibility for existing active sessions
            username, sig = parts
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
    return HTMLResponse(get_template("login.html"))

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    client_ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (request.client.host if request.client else "unknown")
    now = time.time()
    
    # Rate limit check (max 5 failed attempts within 15 minutes)
    if client_ip in failed_login_attempts:
        attempts, lock_until = failed_login_attempts[client_ip]
        if lock_until > now:
            remaining_mins = int((lock_until - now) / 60) + 1
            return HTMLResponse(f"""
                <script>
                    alert("تم حظر محاولات الدخول مؤقتاً لحماية الحساب. يرجى الانتظار {remaining_mins} دقيقة قبل المحاولة مجدداً.");
                    window.location.href = "/login";
                </script>
            """, status_code=429)
        elif now > lock_until and attempts >= 5:
            # Reset after lock expires
            del failed_login_attempts[client_ip]

    valid_user = hmac.compare_digest(username.strip(), CONFIG["DASH_USER"])
    valid_pass = hmac.compare_digest(password.strip(), CONFIG["DASH_PASS"])

    if valid_user and valid_pass:
        if client_ip in failed_login_attempts:
            del failed_login_attempts[client_ip]
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

    # Record failed attempt
    attempts, _ = failed_login_attempts.get(client_ip, (0, 0))
    attempts += 1
    lock_time = (now + 900) if attempts >= 5 else 0
    failed_login_attempts[client_ip] = (attempts, lock_time)

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


@app.post("/api/upload-image")
async def upload_image(request: Request, image: UploadFile = File(...)):
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    ext = os.path.splitext(image.filename)[1].lower() if image.filename else ".jpg"
    if ext not in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"]:
        raise HTTPException(status_code=400, detail="Invalid image extension. Allowed: jpg, jpeg, png, webp, gif, avif")
        
    # Enforce maximum 15MB file size limit
    image.file.seek(0, 2)
    file_size = image.file.tell()
    image.file.seek(0)
    if file_size > 15 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image file exceeds maximum allowed size (15MB).")

    safe_name = f"{uuid.uuid4().hex[:12]}{ext}"
    file_path = os.path.join(UPLOADS_DIR, safe_name)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)
        
    partner_url = f"https://partner.make-food.com/uploads/{safe_name}"
    makefood_url = f"https://make-food.com/uploads/{safe_name}"
    cdn_url = f"https://media.themagicrecipe.com/uploads/{safe_name}"
    
    # 1. Upload to Cloudflare R2 Global CDN
    try:
        import boto3
        from botocore.config import Config
        s3 = boto3.client(
            's3',
            endpoint_url='https://b13e9d704d273ebc42675122e41a9726.r2.cloudflarestorage.com',
            aws_access_key_id='1d26713429e1a23c991f2ac06e242f75',
            aws_secret_access_key='69d11c7fe169ece537ab0569842d8def7c8a739d9b308da97bacc6a3c0501248',
            region_name='auto',
            config=Config(signature_version='s3v4', s3={'addressing_style': 'path'})
        )
        content_type = "image/jpeg" if ext in [".jpg", ".jpeg"] else ("image/png" if ext == ".png" else "image/webp")
        with open(file_path, "rb") as f_r2:
            s3.put_object(
                Bucket='recipe-media',
                Key=f'uploads/{safe_name}',
                Body=f_r2.read(),
                ContentType=content_type
            )
    except Exception as e_r2:
        print("Note: R2 upload fallback:", e_r2)

    # 2. Also push image to GitHub make-food.com public/uploads/ if token configured
    if CONFIG.get("GITHUB_TOKEN") and CONFIG.get("REPO_NAME"):
        try:
            with open(file_path, "rb") as f_img:
                img_b64 = base64.b64encode(f_img.read()).decode("utf-8")
            gh_h = {
                "Authorization": f"token {CONFIG['GITHUB_TOKEN']}",
                "Accept": "application/vnd.github.v3+json",
                "Content-Type": "application/json"
            }
            gh_payload = {
                "message": f"upload: add recipe image {safe_name}",
                "content": img_b64,
                "branch": "main"
            }
            req_gh = urllib.request.Request(
                f"https://api.github.com/repos/{CONFIG['REPO_NAME']}/contents/public/uploads/{safe_name}",
                data=json.dumps(gh_payload).encode("utf-8"),
                headers=gh_h,
                method="PUT"
            )
            with urllib.request.urlopen(req_gh):
                pass
        except Exception as e:
            print("Note: GitHub direct content push skipped, fallback to partner upload URL:", e)

    return {
        "success": True,
        "filename": safe_name,
        "url": makefood_url,
        "fallback_url": partner_url,
        "cdn_url": cdn_url
    }

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
        "month": "MONTH_TO_DATE"
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
        ("filters", f"DOMAIN_NAME=={CONFIG['TARGET_DOMAIN']}"),
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

    country_params = [
        ("dateRange", date_range),
        ("metrics", "PAGE_VIEWS"),
        ("metrics", "ESTIMATED_EARNINGS"),
        ("dimensions", "COUNTRY_NAME"),
        ("filters", f"DOMAIN_NAME=={CONFIG['TARGET_DOMAIN']}"),
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

    plat_params = [
        ("dateRange", date_range),
        ("metrics", "PAGE_VIEWS"),
        ("dimensions", "PLATFORM_TYPE_NAME"),
        ("filters", f"DOMAIN_NAME=={CONFIG['TARGET_DOMAIN']}"),
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
            "ratings": {"average": 5.0, "count": 1, "average_rating": 5.0, "total_reviews": 1}
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
    return HTMLResponse(get_template("dashboard.html"))


# ================= DYNAMIC LIVE RECIPE FALLBACK RENDERER =================
# Enables 0-second live publishing! If Astro SSG is still compiling in background,
# this endpoint renders the recipe instantly with full CSS, Schema.org and AdSense.
@app.get("/public-render/{slug:path}", response_class=HTMLResponse)
async def public_render_recipe(slug: str):
    clean_slug = slug.strip("/").split("/")[-1]
    recipes = get_recipes_data()
    found = None
    for r in recipes:
        if r.get("slug") == clean_slug or str(r.get("wp_post_id")) == clean_slug:
            found = r
            break
            
    if not found:
        raise HTTPException(status_code=404, detail="Recipe not found")

    title = found.get("title", "")
    card_title = found.get("recipe_card_title") or title
    rec = found.get("recipe", {})
    desc = rec.get("description") or found.get("seo", {}).get("meta_description", "")
    author_name = found.get("author", {}).get("name", "Maria") if isinstance(found.get("author"), dict) else "Maria"
    pub_date = found.get("published_at", "")[:10]
    
    img_url = found.get("featured_image", {}).get("url", "") if isinstance(found.get("featured_image"), dict) else ""
    if not img_url:
        img_url = "https://images.unsplash.com/photo-1495521821757-a1efb6729352?auto=format&fit=crop&w=1200&q=80"
        
    category_name = "Dinner"
    if found.get("categories") and len(found["categories"]) > 0:
        c0 = found["categories"][0]
        category_name = c0.get("name", "Dinner") if isinstance(c0, dict) else str(c0)

    prep_time = rec.get("prep_time", "15 min")
    cook_time = rec.get("cook_time", "25 min")
    total_time = rec.get("total_time", "40 min")
    servings = rec.get("yield", "4 servings")
    cuisine = rec.get("cuisine", "American")
    
    # Ingredients list
    ings_html = ""
    for ing in rec.get("ingredients", []):
        raw = ing.get("raw") if isinstance(ing, dict) else str(ing)
        if raw:
            ings_html += f'''
            <li class="flex items-start gap-3 py-2 border-b border-stone-100 last:border-none">
                <input type="checkbox" class="mt-1 w-4 h-4 rounded text-amber-600 focus:ring-amber-500 border-stone-300 cursor-pointer">
                <span class="text-stone-700 text-sm leading-relaxed">{raw}</span>
            </li>
            '''

    # Instructions list
    steps_html = ""
    for idx, step in enumerate(rec.get("instructions", [])):
        text = step.get("text") if isinstance(step, dict) else str(step)
        if text:
            steps_html += f'''
            <li class="flex items-start gap-4 py-3">
                <span class="w-7 h-7 rounded-full bg-amber-500 text-white font-bold text-xs flex items-center justify-center flex-shrink-0 shadow-sm">{idx + 1}</span>
                <p class="text-stone-700 text-sm sm:text-base leading-relaxed pt-0.5">{text}</p>
            </li>
            '''

    article_html = found.get("article_html", f"<p>{desc}</p>")

    # Schema JSON-LD
    schema_json = json.dumps({
        "@context": "https://schema.org",
        "@type": "Recipe",
        "name": card_title,
        "headline": title,
        "description": desc,
        "image": [img_url],
        "author": {"@type": "Person", "name": author_name},
        "publisher": {"@type": "Organization", "name": "Make-Food", "url": "https://make-food.com"},
        "datePublished": found.get("published_at", datetime.now().strftime("%Y-%m-%d")),
        "prepTime": "PT15M",
        "cookTime": "PT25M",
        "totalTime": "PT40M",
        "recipeYield": servings,
        "recipeCategory": category_name,
        "recipeCuisine": cuisine,
        "recipeIngredient": [ing.get("raw", "") if isinstance(ing, dict) else str(ing) for ing in rec.get("ingredients", [])],
        "aggregateRating": {
            "@type": "AggregateRating",
            "ratingValue": 5.0,
            "reviewCount": 1
        }
    }, ensure_ascii=False)

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} — Make-Food</title>
    <meta name="description" content="{desc}">
    <link rel="canonical" href="https://make-food.com/{clean_slug}/">
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Playfair+Display:wght@700;900&display=swap" rel="stylesheet">
    <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-9077963246978786" crossorigin="anonymous"></script>
    <script type="application/ld+json">{schema_json}</script>
    <style>
        body {{ font-family: 'Plus Jakarta Sans', sans-serif; }}
        h1, h2, h3, .font-serif {{ font-family: 'Playfair Display', Georgia, serif; }}
        .prose p {{ margin-bottom: 1.25rem; line-height: 1.8; color: #44403c; }}
        .prose h2 {{ font-size: 1.5rem; font-weight: 700; color: #1c1917; margin-top: 2rem; margin-bottom: 0.75rem; }}
        .prose ul {{ list-style-type: disc; padding-left: 1.5rem; margin-bottom: 1.25rem; color: #44403c; }}
    </style>
</head>
<body class="bg-stone-50 text-stone-900 min-h-screen flex flex-col">

    <!-- Header Navigation -->
    <header class="bg-white border-b border-stone-200 sticky top-0 z-40 shadow-sm">
        <div class="max-w-5xl mx-auto px-4 h-20 flex items-center justify-between">
            <a href="/" class="flex items-center gap-3">
                <span class="w-10 h-10 rounded-full bg-amber-500 text-white flex items-center justify-center font-serif font-black text-xl shadow-md">✦</span>
                <span class="font-serif text-2xl font-black text-stone-900 tracking-tight">Make-Food</span>
            </a>
            <div class="flex items-center gap-3">
                <a href="/" class="px-4 py-2 rounded-full text-xs font-bold text-stone-700 hover:bg-stone-100 transition">← Back to Recipes</a>
            </div>
        </div>
    </header>

    <!-- Main Content -->
    <main class="flex-1 max-w-4xl mx-auto px-4 py-8 w-full">
        <!-- Breadcrumbs -->
        <nav class="flex items-center gap-2 text-xs text-stone-400 font-semibold mb-6">
            <a href="/" class="hover:text-amber-600">Home</a>
            <span>›</span>
            <span class="text-stone-600">{category_name}</span>
            <span>›</span>
            <span class="text-stone-800 truncate">{title}</span>
        </nav>

        <!-- Article Header -->
        <div class="space-y-4 mb-8">
            <span class="inline-block px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-amber-100 text-amber-800">
                {category_name}
            </span>
            <h1 class="text-3xl sm:text-5xl font-serif font-black text-stone-900 leading-tight">
                {title}
            </h1>
            <div class="flex items-center gap-4 text-xs text-stone-500 pt-1">
                <span>By <strong class="text-stone-800">{author_name}</strong></span>
                <span>•</span>
                <span>{pub_date}</span>
                <span>•</span>
                <span>⏱ {total_time}</span>
            </div>
        </div>

        <!-- Featured Image -->
        <div class="rounded-3xl overflow-hidden shadow-lg mb-10 max-h-[480px] bg-stone-200">
            <img src="{img_url}" alt="{title}" class="w-full h-full object-cover">
        </div>

        <!-- Article Intro & Story Content -->
        <article class="prose max-w-none text-stone-700 text-base sm:text-lg mb-12">
            {article_html}
        </article>

        <!-- Recipe Card Box -->
        <div id="recipe-card" class="bg-white border-2 border-amber-200/80 rounded-3xl p-6 sm:p-10 shadow-xl mb-12">
            <div class="border-b border-stone-200 pb-6 mb-6">
                <span class="px-2.5 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-amber-500 text-white inline-block mb-2">Recipe Card</span>
                <h2 class="text-2xl sm:text-3xl font-serif font-black text-stone-900">{card_title}</h2>
                <p class="text-stone-500 text-sm mt-1">{desc}</p>
                <div class="flex items-center gap-2 text-amber-500 text-sm mt-3">
                    <span>★★★★★</span>
                    <span class="text-xs font-bold text-stone-700">5.0 (1 rating)</span>
                </div>
            </div>

            <!-- Times & Servings Grid -->
            <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 p-4 rounded-2xl bg-amber-50/60 border border-amber-100 mb-8 text-center text-xs">
                <div>
                    <span class="block text-stone-400 font-medium">Prep Time</span>
                    <strong class="text-stone-800 text-sm font-bold">{prep_time}</strong>
                </div>
                <div>
                    <span class="block text-stone-400 font-medium">Cook Time</span>
                    <strong class="text-stone-800 text-sm font-bold">{cook_time}</strong>
                </div>
                <div>
                    <span class="block text-stone-400 font-medium">Total Time</span>
                    <strong class="text-stone-800 text-sm font-bold">{total_time}</strong>
                </div>
                <div>
                    <span class="block text-stone-400 font-medium">Servings</span>
                    <strong class="text-stone-800 text-sm font-bold">{servings}</strong>
                </div>
            </div>

            <!-- Ingredients -->
            <div class="mb-8">
                <h3 class="text-xl font-bold text-stone-900 mb-4 flex items-center gap-2">
                    <span>🛒</span> Ingredients
                </h3>
                <ul class="space-y-1">
                    {ings_html}
                </ul>
            </div>

            <!-- Instructions -->
            <div>
                <h3 class="text-xl font-bold text-stone-900 mb-4 flex items-center gap-2">
                    <span>👩‍🍳</span> Step-by-Step Instructions
                </h3>
                <ol class="space-y-2">
                    {steps_html}
                </ol>
            </div>
        </div>
    </main>

    <!-- Footer -->
    <footer class="bg-white border-t border-stone-200 py-8 text-center text-xs text-stone-500">
        <p>© 2026 Make-Food.com — All Rights Reserved.</p>
    </footer>

</body>
</html>'''
    return HTMLResponse(html)

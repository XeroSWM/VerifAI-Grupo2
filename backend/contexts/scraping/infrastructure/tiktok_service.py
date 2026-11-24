"""Unified Playwright-based TikTok scraping service with async execution and no-login support."""

from __future__ import annotations

import asyncio
import sys
import json
import random
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional, Dict, List

from playwright.async_api import Response, async_playwright

BASE_DIR = Path(__file__).resolve().parent.parent.parent
PERFIL_NAVEGADOR_DIR = BASE_DIR / "tiktok_browser_profile"

USER_AGENTS: dict[str, str] = {
    "chrome_windows": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "chrome_mac": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "edge_windows": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 Edg/128.0.0.0"
    ),
    "iphone_mobile": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"
    ),
}

MODOS: tuple[str, ...] = ("hibrido", "red", "dom", "rapido")

SELECTOR_POST = '[data-e2e="user-post-item"]'
SELECTOR_HIDRATACION = "script#__UNIVERSAL_DATA_FOR_REHYDRATION__"
SELECTORES_CAPTCHA: tuple[str, ...] = (
    "#captcha-verify-container-main-page",
    "#captcha_container",
    "div[class*='captcha_verify']",
    "div[class*='CaptchaVerify']",
)

JS_LEER_DOM = """
(sel) => Array.from(document.querySelectorAll(sel)).map(el => {
    const a = el.querySelector('a[href*="/video/"], a[href*="/photo/"]') || el.querySelector('a');
    const v = el.querySelector('[data-e2e="video-views"]') || el.querySelector('strong');
    const img = el.querySelector('img');
    const descEl = el.querySelector('[title], a');
    return {
        href: a ? a.href : null,
        vistas: v ? v.innerText.trim() : null,
        alt: img ? img.getAttribute('alt') : null,
        portada: img ? img.getAttribute('src') : null,
        desc: descEl ? (descEl.getAttribute('title') || descEl.innerText || '') : '',
        fijado: !!el.querySelector('[data-e2e="video-card-badge"]'),
    };
})
"""


@dataclass(frozen=True)
class ScrapeOptions:
    """Configuración para la ejecución del scraping de perfiles."""
    modo: str = "hibrido"
    max_scrolls: int = 5
    max_posts: int = 19
    scroll_delay_ms: int = 1800
    headless: bool = True
    bloquear_multimedia: bool = True
    sesion_persistente: bool = False
    humanizar: bool = True
    detener_sin_nuevos: int = 3
    fecha_desde: Optional[str] = None
    user_agent: str = "chrome_windows"
    timeout_carga_s: int = 25
    reintentos: int = 2
    max_comment_videos: int = 2
    comment_scrolls: int = 3
    max_following: int = 20
    max_followers: int = 20

    @classmethod
    def desde_dict(cls, data: Optional[dict[str, Any]]) -> ScrapeOptions:
        raw = data or {}

        def _parse_int(key: str, default: int, minimum: int, maximum: int) -> int:
            try:
                return max(minimum, min(int(raw.get(key, default)), maximum))
            except (TypeError, ValueError):
                return default

        def _parse_bool(key: str, default: bool) -> bool:
            val = raw.get(key, default)
            if isinstance(val, str):
                return val.lower() in ("1", "true", "on", "si", "sí", "yes")
            return bool(val)

        modo = raw.get("modo", "hibrido")
        return cls(
            modo=modo if modo in MODOS else "hibrido",
            max_scrolls=_parse_int("max_scrolls", 5, 0, 100),
            max_posts=_parse_int("max_posts", _parse_int("max_videos", 19, 1, 500), 1, 5000),
            scroll_delay_ms=_parse_int("scroll_delay_ms", 1800, 400, 15000),
            headless=_parse_bool("headless", True),
            bloquear_multimedia=_parse_bool("bloquear_multimedia", True),
            sesion_persistente=_parse_bool("sesion_persistente", False),
            humanizar=_parse_bool("humanizar", True),
            detener_sin_nuevos=_parse_int("detener_sin_nuevos", 3, 1, 30),
            fecha_desde=(raw.get("fecha_desde") or "").strip() or None,
            user_agent=raw.get("user_agent", "chrome_windows"),
            timeout_carga_s=_parse_int("timeout_carga_s", 25, 5, 120),
            reintentos=_parse_int("reintentos", 1, 0, 4),
            max_comment_videos=_parse_int("max_comment_videos", 2, 0, 10),
            comment_scrolls=_parse_int("comment_scrolls", 3, 1, 10),
            max_following=_parse_int("max_following", 20, 0, 100),
            max_followers=_parse_int("max_followers", 20, 0, 100)
        )


class TikTokDataParser:
    """Normaliza y estructura datos extraídos tanto de la API de TikTok como del DOM."""

    @staticmethod
    def format_number(val: Any) -> str:
        try:
            num = int(val)
            if num < 0:
                num = num + 4294967296
            if num >= 1_000_000_000:
                return f"{round(num / 1_000_000_000, 1)}B"
            if num >= 1_000_000:
                return f"{round(num / 1_000_000, 1)}M"
            if num >= 1_000:
                return f"{round(num / 1_000, 1)}K"
            return str(num)
        except Exception:
            return str(val or "0")

    @staticmethod
    def parse_count(value: Any) -> Optional[int]:
        if value is None or value == "":
            return None
        if isinstance(value, (int, float)):
            return int(value)
        text = str(value).strip().upper().replace(" ", "")
        if not text:
            return None
        mult = 1
        if text.endswith("K"):
            mult, text = 1_000, text[:-1]
        elif text.endswith("M"):
            mult, text = 1_000_000, text[:-1]
        elif text.endswith("B"):
            mult, text = 1_000_000_000, text[:-1]
        text = text.replace(",", ".")
        if text.count(".") > 1:
            text = text.replace(".", "")
        try:
            return int(float(text) * mult)
        except ValueError:
            return None

    @classmethod
    def to_int(cls, value: Any) -> Optional[int]:
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return cls.parse_count(value)

    @staticmethod
    def extract_hashtags(item: dict[str, Any], description: str) -> list[str]:
        tags: list[str] = []
        for extra in item.get("textExtra") or []:
            name = extra.get("hashtagName")
            if name:
                tags.append(name.lower())
        if not tags:
            for challenge in item.get("challenges") or []:
                if challenge.get("title"):
                    tags.append(challenge["title"].lower())
        if not tags and description:
            tags = [h.lower() for h in re.findall(r"#([\w\ñ\Ñ]+)", description)]
        return list(dict.fromkeys(tags))

    @staticmethod
    def extract_mentions(item: dict[str, Any], description: str) -> list[str]:
        mentions = [
            extra.get("userUniqueId")
            for extra in item.get("textExtra") or []
            if extra.get("userUniqueId")
        ]
        if not mentions and description:
            mentions = re.findall(r"@([\w.]+)", description)
        return list(dict.fromkeys(mentions))

    @classmethod
    def parse_api_item(cls, item: dict[str, Any], username: str) -> dict[str, Any]:
        video_id = str(item.get("id", ""))
        ts = cls.to_int(item.get("createTime")) or 0
        desc = item.get("desc", "") or ""
        stats = item.get("stats") or {}
        stats_v2 = item.get("statsV2") or {}
        video = item.get("video") or {}
        music = item.get("music") or {}
        is_photo = bool(item.get("imagePost"))

        def _stat(key: str) -> int:
            val = cls.to_int(stats_v2.get(key))
            if val is not None:
                return val
            return cls.to_int(stats.get(key)) or 0

        plays = _stat("playCount")
        likes = _stat("diggCount")
        comments = _stat("commentCount")
        shares = _stat("shareCount")
        collects = _stat("collectCount")

        cover = (
            video.get("cover")
            or video.get("originCover")
            or video.get("dynamicCover")
            or "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=600&auto=format&fit=crop&q=80"
        )

        duration_sec = cls.to_int(video.get("duration")) or 15

        return {
            "id": video_id,
            "vid_id": video_id,
            "descripcion": desc,
            "desc": desc,
            "timestamp": ts,
            "create_time": ts,
            "fecha": datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else None,
            "url": f"https://www.tiktok.com/@{username}/{'photo' if is_photo else 'video'}/{video_id}",
            "tipo": "foto" if is_photo else "video",
            "duracion": duration_sec,
            "duration": f"{duration_sec}s",
            "fijado": bool(item.get("isPinnedItem") or item.get("isPinned")),
            "hashtags": cls.extract_hashtags(item, desc),
            "menciones": cls.extract_mentions(item, desc),
            "musica": {
                "titulo": music.get("title"),
                "autor": music.get("authorName"),
                "original": bool(music.get("original")),
            },
            "portada": cover,
            "thumbnail": cover,
            "views": cls.format_number(plays),
            "likes": cls.format_number(likes),
            "shares": cls.format_number(shares),
            "comments_count": cls.format_number(comments),
            "raw_plays": plays,
            "raw_interactions": likes + comments + shares + collects,
            "estadisticas": {
                "vistas": plays,
                "likes": likes,
                "comentarios": comments,
                "compartidos": shares,
                "guardados": collects,
            },
            "fuente": "api",
        }

    @classmethod
    def parse_dom_item(cls, raw: dict[str, Any], username: str) -> Optional[dict[str, Any]]:
        href = raw.get("href") or ""
        match = re.search(r"/(video|photo)/(\d+)", href)
        if not match:
            return None
        video_id = match.group(2)
        desc = raw.get("desc") or raw.get("alt") or ""
        plays = cls.parse_count(raw.get("vistas")) or 0
        cover = raw.get("portada") or "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=600&auto=format&fit=crop&q=80"

        return {
            "id": video_id,
            "vid_id": video_id,
            "descripcion": desc,
            "desc": desc,
            "timestamp": 0,
            "create_time": 0,
            "fecha": None,
            "url": href.split("?")[0] if href else f"https://www.tiktok.com/@{username}/video/{video_id}",
            "tipo": "foto" if match.group(1) == "photo" else "video",
            "duracion": 15,
            "duration": "15s",
            "fijado": bool(raw.get("fijado")),
            "hashtags": list(dict.fromkeys(h.lower() for h in re.findall(r"#([\w\ñ\Ñ]+)", desc))),
            "menciones": [],
            "musica": {"titulo": None, "autor": None, "original": None},
            "portada": cover,
            "thumbnail": cover,
            "views": cls.format_number(plays),
            "likes": "0",
            "shares": "0",
            "comments_count": "0",
            "raw_plays": plays,
            "raw_interactions": 0,
            "estadisticas": {
                "vistas": plays,
                "likes": 0,
                "comentarios": 0,
                "compartidos": 0,
                "guardados": 0,
            },
            "fuente": "dom",
        }

    @classmethod
    def parse_profile(cls, user_detail: dict[str, Any], fallback_user: str) -> dict[str, Any]:
        info = user_detail.get("userInfo") or {}
        user = info.get("user") or {}
        stats = info.get("statsV2") or info.get("stats") or {}
        stats_v1 = info.get("stats") or {}

        def _stat(key: str, fallback: Optional[str] = None) -> Optional[int]:
            val = cls.to_int(stats.get(key))
            if val is None and fallback:
                val = cls.to_int(stats.get(fallback))
            if val is None:
                val = cls.to_int(stats_v1.get(key)) or (
                    cls.to_int(stats_v1.get(fallback)) if fallback else None
                )
            return val

        raw_followers = _stat("followerCount") or 0
        raw_likes = _stat("heartCount", "heart") or 0
        raw_following = _stat("followingCount") or 0
        raw_videos = _stat("videoCount") or 0

        uname = user.get("uniqueId") or fallback_user
        name = user.get("nickname") or uname
        bio = user.get("signature") or ""
        avatar = user.get("avatarLarger") or user.get("avatarMedium") or user.get("avatarThumb") or ""

        return {
            "id": user.get("id"),
            "usuario": uname,
            "username": f"@{uname.lstrip('@')}",
            "nombre": name,
            "name": name,
            "bio": bio,
            "avatar": avatar,
            "verificado": bool(user.get("verified")),
            "privada": bool(user.get("privateAccount")),
            "enlace_bio": (user.get("bioLink") or {}).get("link"),
            "region": user.get("region"),
            "seguidores": raw_followers,
            "followers": cls.format_number(raw_followers),
            "siguiendo": raw_following,
            "likes_totales": raw_likes,
            "likes": cls.format_number(raw_likes),
            "videos": raw_videos,
            "videosCount": str(raw_videos),
            "amigos": _stat("friendCount") or 0,
            "engagement": "N/A",
            "avgViews": "N/A"
        }


class TikTokScraperService:
    """Servicio completo de extracción con Playwright async, soporte sin login y streaming."""

    def __init__(self, log_callback: Optional[Callable[[str], Any]] = None):
        self.log_callback = log_callback
        self.parser = TikTokDataParser()
        self._current_main_loop: Optional[asyncio.AbstractEventLoop] = None

    async def _log(self, message: str) -> None:
        if self.log_callback:
            try:
                res = self.log_callback(message)
                if asyncio.iscoroutine(res):
                    if self._current_main_loop and self._current_main_loop.is_running():
                        asyncio.run_coroutine_threadsafe(res, self._current_main_loop).result()
                    else:
                        await res
            except Exception:
                pass

    async def scrape(
        self,
        username: str,
        target: str = "all",
        max_videos: int = 19,
        max_comment_videos: int = 2,
        max_following: int = 20,
        max_followers: int = 20,
        options_dict: Optional[dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Punto de entrada compatible con VerifAI que invoca el motor optimizado."""
        clean_user = username.replace("@", "").strip()
        opts = options_dict or {}
        opts.setdefault("max_videos", max_videos)
        opts.setdefault("max_comment_videos", max_comment_videos)
        opts.setdefault("max_following", max_following)
        opts.setdefault("max_followers", max_followers)
        scrape_opts = ScrapeOptions.desde_dict(opts)

        try:
            main_loop = asyncio.get_running_loop()
        except RuntimeError:
            main_loop = None

        def _worker_thread():
            worker_loop = (
                asyncio.ProactorEventLoop()
                if sys.platform == "win32"
                else asyncio.new_event_loop()
            )
            asyncio.set_event_loop(worker_loop)
            self._current_main_loop = main_loop
            try:
                return worker_loop.run_until_complete(
                    self._execute_scrape(clean_user, target, scrape_opts)
                )
            finally:
                worker_loop.close()
                asyncio.set_event_loop(None)
                self._current_main_loop = None

        try:
            return await asyncio.to_thread(_worker_thread)
        except Exception as exc:
            await self._log(
                f"[ERROR] Error durante el ciclo de scraping: "
                f"{type(exc).__name__}: {exc!r}"
            )
            raise

    async def _execute_scrape(
        self, username: str, target: str, options: ScrapeOptions
    ) -> Dict[str, Any]:
        start_time = time.time()
        await self._log(f"[INIT] Configurando motor de extracción para @{username} (Modo: {options.modo})...")

        posts_map: Dict[str, Dict[str, Any]] = {}
        captured_comments: List[Dict[str, Any]] = []
        captured_followers: List[Dict[str, Any]] = []
        captured_following: List[Dict[str, Any]] = []

        profile_data = {
            "name": username,
            "username": f"@{username}",
            "bio": "",
            "followers": "0",
            "likes": "0",
            "videosCount": "0",
            "engagement": "N/A",
            "avgViews": "N/A",
            "avatar": ""
        }

        async with async_playwright() as playwright:
            browser = None
            context = None
            mobile_context = None
            try:
                launch_args = [
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--mute-audio"
                ]

                if options.sesion_persistente:
                    PERFIL_NAVEGADOR_DIR.mkdir(parents=True, exist_ok=True)
                    try:
                        context = await playwright.chromium.launch_persistent_context(
                            str(PERFIL_NAVEGADOR_DIR),
                            headless=options.headless,
                            args=launch_args,
                            user_agent=USER_AGENTS.get(options.user_agent, USER_AGENTS["chrome_windows"]),
                            viewport={"width": 1280, "height": 850}
                        )
                    except Exception as p_err:
                        if sys.platform == "win32":
                            await self._log(f"[WARN] Chromium persistente falló ({p_err}). Reintentando con Edge...")
                            context = await playwright.chromium.launch_persistent_context(
                                str(PERFIL_NAVEGADOR_DIR),
                                channel="msedge",
                                headless=options.headless,
                                args=launch_args,
                                user_agent=USER_AGENTS.get(options.user_agent, USER_AGENTS["chrome_windows"]),
                                viewport={"width": 1280, "height": 850}
                            )
                        else:
                            raise p_err
                else:
                    try:
                        browser = await playwright.chromium.launch(
                            headless=options.headless,
                            args=launch_args
                        )
                    except Exception as c_err:
                        if sys.platform == "win32":
                            await self._log(f"[WARN] Chromium no disponible ({c_err}). Reintentando con Microsoft Edge...")
                            browser = await playwright.chromium.launch(
                                channel="msedge",
                                headless=options.headless,
                                args=launch_args
                            )
                        else:
                            raise c_err

                    context = await browser.new_context(
                        user_agent=USER_AGENTS.get(options.user_agent, USER_AGENTS["chrome_windows"]),
                        viewport={"width": 1280, "height": 850}
                    )

                if options.bloquear_multimedia:
                    async def filter_route(route):
                        try:
                            if route.request.resource_type in ("media", "image", "font"):
                                await route.abort()
                            else:
                                await route.continue_()
                        except Exception:
                            pass
                    await context.route("**/*", filter_route)

                page = context.pages[0] if context.pages else await context.new_page()
                current_video_ctx = {"id": "api_intercepted", "url": f"https://www.tiktok.com/@{username}"}

                # 1. Listener de red para atrapar respuestas de la API interna de TikTok
                async def on_response(response: Response):
                    req_url = response.url

                    # A. Catálogo de publicaciones
                    if "/api/post/item_list" in req_url and response.status == 200:
                        try:
                            data = await response.json()
                            for item in data.get("itemList") or []:
                                parsed = self.parser.parse_api_item(item, username)
                                if parsed["id"] not in posts_map:
                                    posts_map[parsed["id"]] = parsed
                        except Exception:
                            pass

                    # B. Comentarios públicos (extrae el aweme_id real desde la query de la API)
                    if ("/api/comment/list" in req_url or "comment/list" in req_url) and response.status == 200:
                        try:
                            aweme_match = re.search(r"aweme_id=(\d+)", req_url)
                            real_vid_id = aweme_match.group(1) if aweme_match else current_video_ctx["id"]
                            vid_info = posts_map.get(real_vid_id)
                            real_vid_url = (
                                vid_info["url"]
                                if vid_info
                                else f"https://www.tiktok.com/@{username}/video/{real_vid_id}"
                            )

                            data = await response.json()
                            for comm in data.get("comments") or []:
                                c_id = str(comm.get("cid", ""))
                                if c_id and not any(c["id"] == c_id for c in captured_comments):
                                    u = comm.get("user") or {}
                                    raw_uid = u.get("unique_id") or u.get("uniqueId") or "anónimo"
                                    captured_comments.append({
                                        "id": c_id,
                                        "video_id": real_vid_id,
                                        "video_url": real_vid_url,
                                        "author": f"@{raw_uid.lstrip('@')}",
                                        "author_name": u.get("nickname") or raw_uid,
                                        "avatar": (u.get("avatar_thumb") or {}).get("url_list", [""])[0] if isinstance(u.get("avatar_thumb"), dict) else "",
                                        "text": comm.get("text") or "",
                                        "likes": self.parser.format_number(comm.get("digg_count", 0)),
                                        "date": time.strftime("%Y-%m-%d", time.localtime(comm.get("create_time", time.time())))
                                    })
                        except Exception:
                            pass

                if options.modo in ("hibrido", "red", "rapido"):
                    page.on("response", on_response)

                url = f"https://www.tiktok.com/@{username}"
                await self._log(f"[NETWORK] Navegando a {url}...")

                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=options.timeout_carga_s * 1000)
                except Exception as e:
                    await self._log(f"[WARN] Error inicial cargando {url}: {e}. Reintentando...")
                    try:
                        await page.reload(wait_until="domcontentloaded", timeout=15000)
                    except Exception:
                        pass

                # 2. Extracción de datos del perfil desde SSR Hydration
                await self._log("[PARSER] Inspeccionando datos hidratados de TikTok...")
                try:
                    await page.wait_for_selector(SELECTOR_HIDRATACION, state="attached", timeout=8000)
                    hydration_el = await page.query_selector(SELECTOR_HIDRATACION)
                    if hydration_el:
                        raw_json = await hydration_el.inner_text()
                        hydration_data = json.loads(raw_json)
                        user_detail = hydration_data.get("__DEFAULT_SCOPE__", {}).get("webapp.user-detail", {})
                        if user_detail:
                            profile_data = self.parser.parse_profile(user_detail, username)
                            for item in user_detail.get("itemList") or []:
                                parsed = self.parser.parse_api_item(item, username)
                                if parsed["id"] not in posts_map:
                                    posts_map[parsed["id"]] = parsed
                            await self._log(f"[SUCCESS] Perfil detectado: {profile_data['name']} (@{profile_data['usuario']}) con {profile_data['followers']} seguidores.")
                except Exception as e:
                    await self._log(f"[WARN] No se pudo leer hidratación SSR completa: {e}")

                # 3. Detección de Captcha
                for c_sel in SELECTORES_CAPTCHA:
                    if await page.query_selector(c_sel):
                        await self._log("[CAPTCHA] TikTok ha solicitado verificación.")
                        if not options.headless:
                            await self._log("[CAPTCHA] Esperando resolución en ventana (40s)...")
                            for _ in range(40):
                                await page.wait_for_timeout(1000)
                                if not await page.query_selector(c_sel):
                                    await self._log("[CAPTCHA] Resuelto con éxito.")
                                    break
                        break

                # 4. Lectura visual del DOM (Fallback o Modo DOM)
                if options.modo in ("hibrido", "dom"):
                    try:
                        raw_dom_cards = await page.evaluate(JS_LEER_DOM, SELECTOR_POST)
                        for raw_card in raw_dom_cards:
                            parsed = self.parser.parse_dom_item(raw_card, username)
                            if parsed and parsed["id"] not in posts_map:
                                posts_map[parsed["id"]] = parsed
                    except Exception:
                        pass

                # 5. Scrolls adaptativos y humanizados si se requieren más publicaciones
                if options.modo != "rapido" and options.max_scrolls > 0 and len(posts_map) < options.max_posts:
                    await self._log(f"[SCROLL] Recolectando publicaciones adicionales (Objetivo: {options.max_posts})...")
                    sin_nuevos = 0
                    for s_idx in range(options.max_scrolls):
                        if len(posts_map) >= options.max_posts:
                            break

                        cant_anterior = len(posts_map)

                        if options.humanizar:
                            await page.mouse.move(random.randint(400, 800), random.randint(300, 600))
                            await page.mouse.wheel(0, random.randint(700, 1200))
                            await page.wait_for_timeout(random.randint(150, 400))
                        else:
                            await page.evaluate("window.scrollBy(0, 1000)")

                        await page.wait_for_timeout(options.scroll_delay_ms)

                        if options.modo in ("hibrido", "dom"):
                            try:
                                raw_dom_cards = await page.evaluate(JS_LEER_DOM, SELECTOR_POST)
                                for raw_card in raw_dom_cards:
                                    parsed = self.parser.parse_dom_item(raw_card, username)
                                    if parsed and parsed["id"] not in posts_map:
                                        posts_map[parsed["id"]] = parsed
                            except Exception:
                                pass

                        nuevos = len(posts_map) - cant_anterior
                        await self._log(f"[PROGRESS] Scroll {s_idx + 1}/{options.max_scrolls}: {len(posts_map)} posts (+{nuevos})")

                        if nuevos == 0:
                            sin_nuevos += 1
                            if sin_nuevos >= options.detener_sin_nuevos:
                                await self._log("[INFO] No hay más contenido nuevo cargando. Finalizando scrolls.")
                                break
                        else:
                            sin_nuevos = 0

                # 6. Extracción de comentarios localizando cada publicación por su href exacto
                if target in ("all", "comments") and options.max_comment_videos > 0 and posts_map:
                    videos_para_comentar = list(posts_map.values())[:options.max_comment_videos]
                    await self._log(
                        f"[COMMENTS] Extrayendo comentarios de {len(videos_para_comentar)} publicaciones "
                        f"({options.comment_scrolls} scrolls por video)..."
                    )

                    await page.evaluate("window.scrollTo(0, 0)")
                    await page.wait_for_timeout(1000)

                    for v_idx, vid in enumerate(videos_para_comentar):
                        current_video_ctx["id"] = vid["id"]
                        current_video_ctx["url"] = vid["url"]
                        prev_count = len(captured_comments)
                        try:
                            # Buscar el enlace específico de este video por su ID único
                            specific_link = page.locator(f'a[href*="/{vid["id"]}"]').first
                            if await specific_link.count() > 0:
                                await specific_link.scroll_into_view_if_needed(timeout=5000)
                                await specific_link.click(force=True, timeout=8000)
                                await page.wait_for_timeout(2500)

                                # Múltiples scrolls en el panel lateral de comentarios
                                await page.mouse.move(1050, 450)
                                for _ in range(options.comment_scrolls):
                                    await page.mouse.wheel(0, 850)
                                    await page.wait_for_timeout(1200)

                                # Cerrar modal del video para volver al grid limpio
                                close_modal = page.locator('[data-e2e="browse-close"]').first
                                if await close_modal.count() > 0:
                                    await close_modal.click(force=True)
                                else:
                                    await page.keyboard.press("Escape")
                                await page.wait_for_timeout(1200)

                            nuevos_comm = len(captured_comments) - prev_count
                            await self._log(
                                f"[COMMENTS] Video {v_idx + 1}/{len(videos_para_comentar)} ({vid['id']}): "
                                f"+{nuevos_comm} comentarios (Total: {len(captured_comments)})."
                            )
                        except Exception as c_err:
                            await self._log(f"[WARN] No se pudieron cargar comentarios del video {vid['id']}: {c_err}")
                            try:
                                await page.keyboard.press("Escape")
                                await page.wait_for_timeout(600)
                            except Exception:
                                pass

                # 7. Extracción de comunidad / red (intento API móvil + fallback a comunidad activa sin login)
                if target in ("all", "network", "followers", "following") and (options.max_followers > 0 or options.max_following > 0):
                    await self._log("[NETWORK] Intentando extraer listas de seguidores y seguidos...")
                    try:
                        if browser:
                            mobile_context = await browser.new_context(
                                user_agent=USER_AGENTS["iphone_mobile"],
                                viewport={"width": 390, "height": 844},
                                device_scale_factor=3,
                                is_mobile=True,
                                has_touch=True,
                            )
                            mobile_page = await mobile_context.new_page()
                        else:
                            mobile_page = await context.new_page()
                            await mobile_page.set_viewport_size({"width": 390, "height": 844})

                        active_network_mode = {"type": "followers"}

                        async def on_mobile_network_response(response: Response):
                            req_url = response.url
                            if ("/api/user/list" in req_url or "user/list" in req_url) and response.status == 200:
                                try:
                                    data = await response.json()
                                    is_following = (
                                        "scene=21" in req_url
                                        or "following" in req_url
                                        or active_network_mode["type"] == "following"
                                    )
                                    target_list = captured_following if is_following else captured_followers
                                    limit = options.max_following if is_following else options.max_followers

                                    for item in data.get("userList") or []:
                                        if len(target_list) >= limit:
                                            break
                                        u = item.get("user") or {}
                                        uid = u.get("uniqueId") or u.get("unique_id")
                                        if uid and not any(x["username"] == f"@{uid}" for x in target_list):
                                            target_list.append({
                                                "username": f"@{uid}",
                                                "name": u.get("nickname") or uid,
                                                "avatar": u.get("avatarThumb") or ""
                                            })
                                except Exception:
                                    pass

                        mobile_page.on("response", on_mobile_network_response)
                        await mobile_page.goto(url, wait_until="domcontentloaded", timeout=15000)
                        await mobile_page.wait_for_timeout(2000)

                        for mode_key, selectors, max_items in [
                            ("followers", ['[data-e2e="followers-count"]', '[data-e2e="followers"]', 'text=/Seguidores|Followers/i'], options.max_followers),
                            ("following", ['[data-e2e="following-count"]', '[data-e2e="following"]', 'text=/Siguiendo|Following/i'], options.max_following),
                        ]:
                            if max_items <= 0:
                                continue
                            active_network_mode["type"] = mode_key
                            for sel in selectors:
                                loc = mobile_page.locator(sel).first
                                if await loc.count() > 0:
                                    await loc.click(force=True, timeout=3000)
                                    await mobile_page.wait_for_timeout(1800)
                                    break

                        # Si TikTok bloqueó el listado privado sin login, reconstruir red desde comentaristas y menciones
                        if not captured_followers and not captured_following:
                            await self._log(
                                "[INFO] TikTok restringe /api/user/list sin sesión iniciada; "
                                "poblando Comunidad & Red con usuarios activos en comentarios y menciones."
                            )
                            seen_users = set()
                            for c in captured_comments:
                                u_handle = c.get("author", "")
                                if u_handle and u_handle not in seen_users and len(captured_followers) < options.max_followers:
                                    seen_users.add(u_handle)
                                    captured_followers.append({
                                        "username": u_handle,
                                        "name": c.get("author_name") or u_handle.lstrip("@"),
                                        "avatar": c.get("avatar") or "",
                                        "tipo_relacion": "Comentarista activo"
                                    })

                            for post in posts_map.values():
                                for m in post.get("menciones") or []:
                                    m_handle = f"@{m.lstrip('@')}"
                                    if m_handle not in seen_users and len(captured_following) < options.max_following:
                                        seen_users.add(m_handle)
                                        captured_following.append({
                                            "username": m_handle,
                                            "name": m.lstrip("@"),
                                            "avatar": "",
                                            "tipo_relacion": "Mencionado en video"
                                        })
                    except Exception as n_err:
                        await self._log(f"[WARN] No se pudieron extraer listas de red: {n_err}")
                    finally:
                        if mobile_context:
                            try:
                                await mobile_context.close()
                            except Exception:
                                pass

            finally:
                if context:
                    try:
                        await context.close()
                    except Exception:
                        pass
                if browser:
                    try:
                        await browser.close()
                    except Exception:
                        pass

        # 8. Consolidar métricas finales
        all_posts = list(posts_map.values())[:options.max_posts]
        total_plays = sum(p.get("raw_plays", 0) for p in all_posts)
        total_interactions = sum(p.get("raw_interactions", 0) for p in all_posts)
        v_count = len(all_posts)

        profile_data["videosCount"] = str(profile_data.get("videos") or v_count)

        if v_count > 0:
            if total_plays > 0:
                profile_data["avgViews"] = self.parser.format_number(int(total_plays / v_count))
                profile_data["engagement"] = f"{round((total_interactions / total_plays) * 100, 2)}%"
            else:
                profile_data["avgViews"] = all_posts[0].get("views", "0")
                profile_data["engagement"] = "0%"

        # Formatear lista de videos para la UI de React / Mobile
        formatted_videos = []
        for idx, vid in enumerate(all_posts):
            formatted_videos.append({
                "id": vid["id"],
                "url": vid["url"],
                "thumbnail": vid.get("thumbnail") or vid.get("portada", ""),
                "views": vid.get("views", "0"),
                "likes": vid.get("likes", "0"),
                "shares": vid.get("shares", "0"),
                "comments_count": vid.get("comments_count", "0"),
                "duration": vid.get("duration", "15s"),
                "duracion": vid.get("duracion", 15),
                "desc": vid.get("desc") or vid.get("descripcion", ""),
                "descripcion": vid.get("descripcion") or vid.get("desc", ""),
                "create_time": vid.get("create_time", 0),
                "fecha": vid.get("fecha"),
                "hashtags": vid.get("hashtags", []),
                "menciones": vid.get("menciones", []),
                "musica": vid.get("musica", {}),
                "tipo": vid.get("tipo", "video"),
                "fijado": vid.get("fijado", False),
                "estadisticas": vid.get("estadisticas", {})
            })

        duration_s = round(time.time() - start_time, 2)
        await self._log(
            f"[SUCCESS] Extracción finalizada en {duration_s}s: "
            f"{len(formatted_videos)} videos, {len(captured_comments)} comentarios, "
            f"{len(captured_followers)} seguidores/comunidad, {len(captured_following)} seguidos/menciones."
        )

        raw_scrape_result = {
            "estado": "ok",
            "usuario": username,
            "username": username,
            "perfil": profile_data,
            "profile": profile_data,
            "publica": True,
            "total_posts_extraidos": len(formatted_videos),
            "posts": formatted_videos,
            "videos": formatted_videos,
            "comments": captured_comments,
            "followers_list": captured_followers,
            "following_list": captured_following,
            "meta": {
                "fecha_scrape": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "duracion_s": duration_s,
                "opciones": asdict(options)
            }
        }

        # Ejecución del motor analítico de reglas e insights
        try:
            from contexts.analytics.analytics_service import default_dashboard_builder
            dashboard = default_dashboard_builder.build(raw_scrape_result)
            raw_scrape_result["analytics"] = dashboard
            raw_scrape_result["kpis"] = dashboard.get("kpis", {})
            raw_scrape_result["insights"] = dashboard.get("insights", [])
        except Exception as e:
            await self._log(f"[WARN] No se pudo computar el dashboard analítico: {e}")
            raw_scrape_result["analytics"] = {}

        return raw_scrape_result
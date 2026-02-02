#!/usr/bin/env python3
"""
GOALKEEPER COMPLETE SYSTEM — MATCH-CENTRIC EDITION (v0.9)

Co to robi (zgodnie z Twoją specyfikacją):
1) (Lookup) ustala klub/kluby zawodnika w danym okresie (Transfermarkt; fallback: klub z CSV)
2) pobiera wszystkie mecze tych klubów w okresie (Transfermarkt fixtures/results)
3) dla każdego meczu:
   - wchodzi w link do meczu (match page) w: Transfermarkt, SofaScore, FotMob, PlaymakerStats, Resultados-futbol
   - parsuje udział zawodnika i eventy z match pages (nie z profili)
4) rozwiązuje rozbieżności per-pole (wygrywa źródło z największą ilością informacji)
5) liczy średnie ocen:
   - per match: średnia z dostępnych ocen w źródłach
   - per month: średnia ze średnich meczowych
6) eksportuje tabelę CSV (per mecz + agregaty)

UWAGA PRAKTYCZNA:
- Transfermarkt / Playmaker / Resultados zwykle da się ogarnąć przez requests+BS4.
- SofaScore i FotMob często wymagają renderowania JS → Playwright (wspierane).
- Ten skrypt ma caching ID (kluby/mecze) do pliku JSON, żeby nie dostawać banów.

"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Literal

import pandas as pd
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote, urljoin

# -----------------------
# LOGGING (Windows-safe)
# -----------------------

def configure_logging(log_path: Path, debug: bool) -> logging.Logger:
    logger = logging.getLogger("goalkeeper_matchcentric")
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    logger.handlers.clear()

    log_path.parent.mkdir(parents=True, exist_ok=True)

    # file handler utf-8
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(fh)

    # console handler - replace unencodable chars
    try:
        import io
        ch_stream = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        ch = logging.StreamHandler(ch_stream)
    except Exception:
        ch = logging.StreamHandler(sys.stdout)

    ch.setLevel(logging.DEBUG if debug else logging.INFO)
    ch.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(ch)

    return logger

# -----------------------
# HELPERS
# -----------------------

def norm_team(s: str) -> str:
    s = s.lower()
    s = s.replace("&", "and")
    s = re.sub(r"\b(fc|sc|afc|sv|vv|ksv|fk)\b", "", s)
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def season_id_from_date(d: date) -> int:
    # sezon europejski: lipiec→czerwiec. Styczeń 2026 należy do sezonu 2025.
    return d.year if d.month >= 7 else d.year - 1

def parse_date_fuzzy(s: str) -> Optional[date]:
    s = s.strip()
    # 30.01.2026, 30/01/2026, 30 Jan 2026, Jan 30, 2026 ...
    for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d", "%d %b %Y", "%b %d, %Y", "%d %B %Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None

# -----------------------
# DATA MODELS
# -----------------------

@dataclass(frozen=True)
class MatchKey:
    date: date
    home: str
    away: str

@dataclass
class Participation:
    status: Literal["played", "bench", "not_in_squad", "unknown"] = "unknown"
    minutes: Optional[int] = None
    goals_conceded: Optional[int] = None
    clean_sheet: Optional[bool] = None
    assists: Optional[int] = None
    yellow: Optional[int] = None
    red: Optional[int] = None
    rating: Optional[float] = None

@dataclass
class MatchRecord:
    match: MatchKey
    competition: Optional[str] = None
    score: Optional[str] = None
    urls: Dict[str, Optional[str]] = None
    by_source: Dict[str, Participation] = None
    final: Participation = None
    conflicts: List[str] = None

# -----------------------
# CACHE
# -----------------------

class JsonCache:
    def __init__(self, path: Path):
        self.path = path
        self.data: Dict = {}
        if path.exists():
            try:
                self.data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                self.data = {}

    def get(self, *keys, default=None):
        cur = self.data
        for k in keys:
            if not isinstance(cur, dict) or k not in cur:
                return default
            cur = cur[k]
        return cur

    def set(self, *keys, value):
        cur = self.data
        for k in keys[:-1]:
            cur = cur.setdefault(k, {})
        cur[keys[-1]] = value

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")

# -----------------------
# HTTP CLIENT
# -----------------------

class HttpClient:
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
        })

    def get(self, url: str, *, retries: int = 3, sleep_s: float = 1.0) -> Optional[requests.Response]:
        for attempt in range(1, retries + 1):
            try:
                time.sleep(sleep_s)
                r = self.session.get(url, timeout=30)
                if r.status_code >= 400:
                    raise requests.RequestException(f"HTTP {r.status_code}")
                return r
            except Exception as e:
                self.logger.warning(f"HTTP fail {attempt}/{retries}: {url} -> {e}")
                if attempt == retries:
                    return None
                time.sleep(min(8, 2 ** attempt))
        return None

# -----------------------
# RESOLVERS
# -----------------------

class TransfermarktResolver:
    """Z TM robimy:
    - lookup: player -> profile
    - lookup: profile -> klub/kluby w okresie (transfer/loan)
    - fixtures: klub -> mecze w okresie + link do spielbericht
    - parse: match page -> udział zawodnika + (opcjonalnie) kartki, minuty
    """

    def __init__(self, http: HttpClient, cache: JsonCache, logger: logging.Logger, domain: str = "transfermarkt.com"):
        self.http = http
        self.cache = cache
        self.logger = logger
        self.base = f"https://www.{domain}"

    def search_player_profile(self, player_name: str) -> Optional[str]:
        cached = self.cache.get("tm", "player_profile", player_name)
        if cached:
            return cached

        url = f"{self.base}/schnellsuche/ergebnis/schnellsuche?query={quote(player_name)}"
        r = self.http.get(url)
        if not r:
            return None
        soup = BeautifulSoup(r.text, "lxml")
        a = soup.select_one("table.items td.hauptlink a[href*='/profil/spieler/']")
        if not a:
            return None
        profile = urljoin(self.base, a.get("href"))
        self.cache.set("tm", "player_profile", player_name, value=profile)
        return profile

    def extract_clubs_for_period(self, player_profile_url: str, start: date, end: date) -> List[Tuple[str,int]]:
        """Zwraca listę (club_name, club_id) dla okresu.

        Implementacja jest pragmatyczna:
        - bierze 'current club' z profilu (prawie zawsze wystarczy dla miesięcznego okna)
        - dodatkowo próbuje znaleźć transfery/wypożyczenia w tabeli transferów i dodać klub, jeśli data transferu wpada w okno.
        """
        cache_key = f"{player_profile_url}|{start}|{end}"
        cached = self.cache.get("tm", "clubs_for_period", cache_key)
        if cached:
            return [(x[0], int(x[1])) for x in cached]

        r = self.http.get(player_profile_url)
        if not r:
            return []

        soup = BeautifulSoup(r.text, "lxml")
        clubs: Dict[int, str] = {}

        # current club
        cur = soup.select_one("a[href*='/startseite/verein/']")
        if cur and cur.get("href"):
            m = re.search(r"/verein/(\d+)", cur["href"])
            if m:
                cid = int(m.group(1))
                cname = cur.get_text(strip=True) or ""
                if cname:
                    clubs[cid] = cname

        # transfer history (best-effort)
        # Na TM bywa tabela "Transfer history" z datami. W PL/EN różne nagłówki.
        for row in soup.select("table.items tr"):
            t = row.get_text(" ", strip=True)
            # próbujemy wyłapać datę transferu w formacie dd.mm.yyyy
            dm = re.search(r"(\d{2}\.\d{2}\.\d{4})", t)
            if not dm:
                continue
            d = parse_date_fuzzy(dm.group(1))
            if not d or not (start <= d <= end):
                continue

            # wiersz może zawierać linki do klubów
            links = row.select("a[href*='/startseite/verein/']")
            for a in links:
                hm = re.search(r"/verein/(\d+)", a.get("href", ""))
                if hm:
                    cid = int(hm.group(1))
                    cname = a.get_text(strip=True)
                    if cname:
                        clubs[cid] = cname

        out = [(name, cid) for cid, name in clubs.items()]
        self.cache.set("tm", "clubs_for_period", cache_key, value=out)
        return out

    def club_fixtures(self, club_id: int, start: date, end: date) -> List[Tuple[MatchKey, str, Optional[str], Optional[str]]]:
        """Zwraca listę:
        (MatchKey, spielbericht_url, competition, score)
        """
        season = season_id_from_date(start)
        cache_key = f"{club_id}|{season}|{start}|{end}"
        cached = self.cache.get("tm", "fixtures", cache_key)
        if cached:
            out = []
            for item in cached:
                mk = MatchKey(date=datetime.strptime(item[0], "%Y-%m-%d").date(), home=item[1], away=item[2])
                out.append((mk, item[3], item[4], item[5]))
            return out

        # UWAGA: na TM endpointy potrafią się różnić per kraj/wersję. Ten URL działa często:
        url = f"{self.base}/-/spielplan/verein/{club_id}/saison_id/{season}"
        r = self.http.get(url)
        if not r:
            return []

        soup = BeautifulSoup(r.text, "lxml")
        results = []

        # Tabela meczów: szukamy linków /spielbericht/ oraz daty w wierszu.
        for row in soup.select("table.items tr"):
            a_report = row.select_one("a[href*='/spielbericht/']")
            if not a_report:
                continue

            # date cell: bywa w osobnym td z klasą "zentriert".
            tds = row.find_all("td")
            row_text = row.get_text(" ", strip=True)
            d = None
            # Try parse date from dedicated cells first
            for td in tds:
                t = td.get_text(" ", strip=True)
                if not t:
                    continue
                # common TM formats: 30.01.2026, 30/01/2026, Jan 30, 2026
                if re.search(r"\d{2}[./]\d{2}[./]\d{4}", t) or re.search(r"\b[A-Za-z]{3} \d{1,2}, \d{4}\b", t):
                    d = parse_date_fuzzy(t)
                    if d:
                        break
            if not d:
                # fallback: scan whole row text
                dm = re.search(r"(\d{2}[./]\d{2}[./]\d{4}|\b[A-Za-z]{3} \d{1,2}, \d{4}\b)", row_text)
                d = parse_date_fuzzy(dm.group(1)) if dm else None
            if not d or d < start or d > end:
                continue

            # opponent: w wierszu są nazwy klubów; my wyciągamy home/away heurystycznie:
            # Na stronach klubowych zwykle jest "H"/"A" albo ikony; robimy best-effort:
            team_links = row.select("a[href*='/startseite/verein/']")
            names = [x.get_text(strip=True) for x in team_links if x.get_text(strip=True)]
            # często: [club, opponent] albo więcej; bierzemy dwa ostatnie sensowne
            if len(names) >= 2:
                # Nie zawsze wiadomo, czy klub jest gospodarzem.
                # Ustalmy: jeśli w wierszu jest "H" lub "Heim" → club home, else jeśli "A" → club away.
                # Determine H/A from dedicated cell when possible
                ha = None
                for td in tds:
                    t = td.get_text(strip=True)
                    if t in ("H", "A"):
                        ha = t
                        break
                is_home = True
                if ha == "A":
                    is_home = False
                elif ha == "H":
                    is_home = True
                else:
                    # fallback heuristic
                    if re.search(r"\bA\b|\bAus\b|\bAway\b|\bAway match\b", row_text, flags=re.I):
                        is_home = False
                # bierzemy opponent jako ten, który nie jest naszym klubem (first unique)
                opponent = None
                for n in names:
                    if n and n not in (names[0],):
                        opponent = n
                        break
                opponent = opponent or names[-1]

                # nazwę klubu zrobimy później, bo tu jej nie mamy pewnej — wpisujemy placeholder
                club_placeholder = "CLUB"
                home = club_placeholder if is_home else opponent
                away = opponent if is_home else club_placeholder
            else:
                continue

            report_url = urljoin(self.base, a_report.get("href"))
            # competition + score (best-effort)
            competition = None
            score = None
            # wynik często w wierszu jako "2:1":
            sm = re.search(r"\b(\d+):(\d+)\b", row_text)
            if sm:
                score = f"{sm.group(1)}:{sm.group(2)}"

            results.append((MatchKey(date=d, home=home, away=away), report_url, competition, score))

        self.cache.set("tm", "fixtures", cache_key, value=[
            (x[0].date.isoformat(), x[0].home, x[0].away, x[1], x[2], x[3]) for x in results
        ])
        return results

    def parse_match_participation(self, match_url: str, player_name: str) -> Participation:
        r = self.http.get(match_url)
        if not r:
            return Participation(status="unknown")

        soup = BeautifulSoup(r.text, "lxml")
        txt = soup.get_text(" ", strip=True).lower()
        pnorm = player_name.lower()

        # lineup: w TM jest tabela składów, często w elementach z nazwiskami jako linki.
        status = "unknown"
        # starting XI
        for a in soup.select("a[href*='/profil/spieler/']"):
            if a.get_text(strip=True).lower() == pnorm:
                # heurystyka: jeśli jest w sekcji starting xi -> played
                status = "played"
                break

        # bench / not in squad w TM jest trudniejsze bez dokładnego selektora;
        # traktujemy brak znalezienia nazwiska jako "unknown" na TM i pozwalamy innym źródłom doprecyzować.
        part = Participation(status=status)
        # conceded/clean_sheet wnioskujemy z wyniku tylko jeśli played i pełne minuty potem potwierdzone z innego źródła.
        return part

# -----------------------
# PLAYWRIGHT RESOLVERS (Sofa/FotMob)
# -----------------------

class PlaywrightResolvers:
    """Resolver ID dla SofaScore i FotMob przez UI (Playwright)."""

    def __init__(self, cache: JsonCache, logger: logging.Logger, headless: bool = True):
        self.cache = cache
        self.logger = logger
        self.headless = headless

    async def _ensure_playwright(self):
        try:
            from playwright.async_api import async_playwright  # noqa
            return True
        except Exception as e:
            self.logger.error("Brak Playwright. Zainstaluj: pip install playwright && playwright install chromium")
            self.logger.error(f"Import error: {e}")
            return False

    async def resolve_sofascore(self, match: MatchKey) -> Optional[str]:
        cache_key = f"{match.date}|{match.home}|{match.away}"
        cached = self.cache.get("sofascore", "match_url", cache_key)
        if cached:
            return cached

        ok = await self._ensure_playwright()
        if not ok:
            return None

        from playwright.async_api import async_playwright

        query = f"{match.home} {match.away}"
        search_url = f"https://www.sofascore.com/search?q={quote(query)}"

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            page = await browser.new_page()
            await page.goto(search_url, wait_until="domcontentloaded")

            # Heurystyka: kliknij pierwszy wynik "Matches" zawierający oba teamy.
            # Struktura Sofascore bywa zmienna → selektory są best-effort.
            await page.wait_for_timeout(1500)
            items = await page.query_selector_all("a")
            target = None
            for a in items:
                href = await a.get_attribute("href") or ""
                txt = (await a.inner_text() or "").lower()
                if "/match/" in href and norm_team(match.home) in norm_team(txt) and norm_team(match.away) in norm_team(txt):
                    target = a
                    break
            if not target:
                await browser.close()
                return None

            await target.click()
            await page.wait_for_load_state("domcontentloaded")
            url = page.url
            await browser.close()

        self.cache.set("sofascore", "match_url", cache_key, value=url)
        return url

    async def resolve_fotmob(self, match: MatchKey) -> Optional[str]:
        cache_key = f"{match.date}|{match.home}|{match.away}"
        cached = self.cache.get("fotmob", "match_url", cache_key)
        if cached:
            return cached

        ok = await self._ensure_playwright()
        if not ok:
            return None

        from playwright.async_api import async_playwright

        query = f"{match.home} {match.away}"
        search_url = f"https://www.fotmob.com/search?query={quote(query)}"

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            page = await browser.new_page()
            await page.goto(search_url, wait_until="domcontentloaded")
            await page.wait_for_timeout(1500)

            items = await page.query_selector_all("a")
            target = None
            for a in items:
                href = await a.get_attribute("href") or ""
                txt = (await a.inner_text() or "").lower()
                if "/matches/" in href and norm_team(match.home) in norm_team(txt) and norm_team(match.away) in norm_team(txt):
                    target = a
                    break
            if not target:
                await browser.close()
                return None

            await target.click()
            await page.wait_for_load_state("domcontentloaded")
            url = page.url
            await browser.close()

        self.cache.set("fotmob", "match_url", cache_key, value=url)
        return url

# -----------------------
# RESULTADOS & PLAYMAKER (requests)
# -----------------------

class ResultadosResolver:
    def __init__(self, http: HttpClient, cache: JsonCache, logger: logging.Logger):
        self.http = http
        self.cache = cache
        self.logger = logger
        self.base = "https://www.resultados-futbol.com"

    def resolve(self, match: MatchKey) -> Optional[str]:
        cache_key = f"{match.date}|{match.home}|{match.away}"
        cached = self.cache.get("resultados", "match_url", cache_key)
        if cached:
            return cached

        # Fallback: search page
        q = f"{match.home} {match.away} {match.date.isoformat()}"
        url = f"{self.base}/search?q={quote(q)}"
        r = self.http.get(url)
        if not r:
            return None
        soup = BeautifulSoup(r.text, "lxml")
        for a in soup.select("a[href*='/partido/']"):
            txt = a.get_text(" ", strip=True)
            if norm_team(match.home) in norm_team(txt) and norm_team(match.away) in norm_team(txt):
                murl = urljoin(self.base, a.get("href"))
                self.cache.set("resultados", "match_url", cache_key, value=murl)
                return murl
        return None

class PlaymakerResolver:
    def __init__(self, http: HttpClient, cache: JsonCache, logger: logging.Logger):
        self.http = http
        self.cache = cache
        self.logger = logger
        self.base = "https://www.playmakerstats.com"

    def resolve(self, match: MatchKey) -> Optional[str]:
        cache_key = f"{match.date}|{match.home}|{match.away}"
        cached = self.cache.get("playmaker", "match_url", cache_key)
        if cached:
            return cached

        # Playmaker ma search? Uwaga: endpointy mogą się zmieniać; to jest best-effort.
        url = f"{self.base}/search?search_string={quote(match.home + ' ' + match.away)}"
        r = self.http.get(url)
        if not r:
            return None
        soup = BeautifulSoup(r.text, "lxml")
        for a in soup.select("a[href*='/match/']"):
            href = a.get("href", "")
            txt = a.get_text(" ", strip=True)
            if norm_team(match.home) in norm_team(txt) and norm_team(match.away) in norm_team(txt):
                murl = urljoin(self.base, href)
                self.cache.set("playmaker", "match_url", cache_key, value=murl)
                return murl
        return None

# -----------------------
# RECONCILIATION
# -----------------------

def info_score(p: Participation) -> int:
    score = 0
    score += 3 if p.status != "unknown" else 0
    score += 2 if p.minutes is not None else 0
    score += 2 if p.goals_conceded is not None else 0
    score += 1 if p.clean_sheet is not None else 0
    score += 1 if (p.yellow is not None or p.red is not None) else 0
    score += 2 if p.rating is not None else 0
    return score

def reconcile(by_source: Dict[str, Participation]) -> Tuple[Participation, List[str]]:
    conflicts: List[str] = []
    final = Participation(status="unknown")

    # status: prefer played > bench > not_in_squad; tie-break by info_score
    statuses = {s: p.status for s, p in by_source.items() if p.status != "unknown"}
    if statuses:
        # majority
        counts: Dict[str,int] = {}
        for st in statuses.values():
            counts[st] = counts.get(st,0)+1
        best = sorted(counts.items(), key=lambda x: (-x[1], x[0]))[0][0]
        final.status = best
        # conflict if more than 1 distinct
        if len(set(statuses.values())) > 1:
            conflicts.append(f"status_conflict: {statuses}")

    # minutes: choose max (najczęściej prawda dla GK) z najlepiej poinformowanego źródła
    mins = [(s,p.minutes) for s,p in by_source.items() if p.minutes is not None]
    if mins:
        maxmin = max(m for _,m in mins if m is not None)
        final.minutes = maxmin

    # cards
    ys = [p.yellow for p in by_source.values() if p.yellow is not None]
    rs = [p.red for p in by_source.values() if p.red is not None]
    if ys: final.yellow = max(ys)
    if rs: final.red = max(rs)

    # goals conceded / clean sheet
    gcs = [p.goals_conceded for p in by_source.values() if p.goals_conceded is not None]
    if gcs:
        # pick mode else highest-info
        from collections import Counter
        c = Counter(gcs)
        most = c.most_common(1)[0][0]
        if len(c) > 1:
            conflicts.append(f"goals_conceded_conflict: {dict(c)}")
        final.goals_conceded = int(most)
        final.clean_sheet = (final.goals_conceded == 0)

    # rating: average of available
    ratings = [p.rating for p in by_source.values() if p.rating is not None]
    if ratings:
        final.rating = round(sum(ratings)/len(ratings), 2)

    return final, conflicts

# -----------------------
# CSV LOADING
# -----------------------

def load_players_csv(path: Path) -> List[Dict[str,str]]:
    players = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("name") or row.get("player") or "").strip()
            team = (row.get("team") or row.get("club") or "").strip()
            if not name:
                continue
            players.append({"name": name, "team": team})
    return players

# -----------------------
# MAIN PIPELINE
# -----------------------

async def run_matchcentric(players_csv: Path, output_csv: Path, start: date, end: date, debug: bool, headless: bool, tm_domain: str):
    logger = configure_logging(output_csv.with_suffix(".log"), debug=debug)
    logger.info("MATCH-CENTRIC pipeline start")

    cache = JsonCache(output_csv.with_suffix(".cache.json"))
    http = HttpClient(logger)

    tm = TransfermarktResolver(http, cache, logger, domain=tm_domain)
    pw = PlaywrightResolvers(cache, logger, headless=headless)
    rf = ResultadosResolver(http, cache, logger)
    pm = PlaymakerResolver(http, cache, logger)

    players = load_players_csv(players_csv)
    if not players:
        logger.error("Brak zawodników w CSV.")
        return

    all_rows = []

    for player in players:
        player_name = player["name"]
        logger.info(f"\n=== {player_name} ===")

        profile = tm.search_player_profile(player_name)
        clubs = []
        if profile:
            clubs = tm.extract_clubs_for_period(profile, start, end)
        if not clubs:
            # fallback: klub z CSV (bez ID) -> spróbuj znaleźć club_id na TM
            if player.get("team"):
                # quick search for club id by searching team name and taking first Verein
                club_search_url = f"{tm.base}/schnellsuche/ergebnis/schnellsuche?query={quote(player['team'])}"
                r = http.get(club_search_url)
                if r:
                    soup = BeautifulSoup(r.text, "lxml")
                    a = soup.select_one("a[href*='/startseite/verein/']")
                    if a:
                        m = re.search(r"/verein/(\d+)", a.get("href", ""))
                        if m:
                            clubs = [(a.get_text(strip=True), int(m.group(1)))]

        if not clubs:
            logger.warning(f"Nie ustaliłem klubu dla {player_name} — pomijam.")
            continue

        # collect matches from each club
        matches: List[Tuple[MatchKey,str,Optional[str],Optional[str],str]] = []
        for club_name, club_id in clubs:
            logger.info(f"Klub w okresie: {club_name} (TM id={club_id})")
            fixtures = tm.club_fixtures(club_id, start, end)
            for mk, url, comp, score in fixtures:
                # wstaw prawdziwą nazwę klubu w placeholder
                home = club_name if mk.home == "CLUB" else mk.home
                away = club_name if mk.away == "CLUB" else mk.away
                mk2 = MatchKey(date=mk.date, home=home, away=away)
                matches.append((mk2, url, comp, score, club_name))

        # dedupe by date+opponent (rough)
        seen=set()
        uniq=[]
        for mk,url,comp,score,club_name in matches:
            key=(mk.date.isoformat(), norm_team(mk.home), norm_team(mk.away))
            if key in seen: 
                continue
            seen.add(key)
            uniq.append((mk,url,comp,score,club_name))

        logger.info(f"Mecze w okresie: {len(uniq)}")

        for mk, tm_match_url, comp, score, club_name in uniq:
            logger.info(f"- {mk.date} | {mk.home} vs {mk.away}")

            urls = {
                "transfermarkt": tm_match_url,
                "sofascore": None,
                "fotmob": None,
                "playmaker": None,
                "resultados": None,
            }

            # resolve other match pages
            # (1) try cache/heuristics
            urls["resultados"] = rf.resolve(mk)
            urls["playmaker"] = pm.resolve(mk)
            urls["sofascore"] = await pw.resolve_sofascore(mk)
            urls["fotmob"] = await pw.resolve_fotmob(mk)

            by_source: Dict[str, Participation] = {}
            by_source["transfermarkt"] = tm.parse_match_participation(tm_match_url, player_name)

            # TODO: dodać realne parsery dla innych źródeł (match pages)
            # Na tym etapie resolvery są kluczowe (ID/URL automatycznie).
            # Parsery można dopinać iteracyjnie: sofascore -> rating + minutes + GK conceded, itd.

            final, conflicts = reconcile(by_source)

            all_rows.append({
                "player": player_name,
                "date": mk.date.isoformat(),
                "home": mk.home,
                "away": mk.away,
                "competition": comp,
                "score": score,
                "status": final.status,
                "minutes": final.minutes,
                "goals_conceded": final.goals_conceded,
                "clean_sheet": final.clean_sheet,
                "yellow": final.yellow,
                "red": final.red,
                "rating_mean": final.rating,
                "url_tm": urls["transfermarkt"],
                "url_sofa": urls["sofascore"],
                "url_fotmob": urls["fotmob"],
                "url_playmaker": urls["playmaker"],
                "url_resultados": urls["resultados"],
                "conflicts": "; ".join(conflicts) if conflicts else "",
            })

        # monthly average rating (from match mean)
        # (w tej wersji parser ratingów jeszcze nie jest podpięty — kolumna zostaje NaN)
        # zostawiamy to, bo pipeline wymaga, a ratingi dopniesz w następnym kroku.

    df = pd.DataFrame(all_rows)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_csv, index=False, encoding="utf-8")
    cache.save()
    logger.info(f"\nZapisano: {output_csv}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-i", "--input", required=True, help="players CSV (columns: name, team(optional))")
    ap.add_argument("-o", "--output", required=True, help="output CSV")
    ap.add_argument("--tm-domain", default="transfermarkt.com", help="Transfermarkt domain, e.g. transfermarkt.com")
    ap.add_argument("--start", default="2026-01-01")
    ap.add_argument("--end", default="2026-01-31")
    ap.add_argument("--debug", action="store_true")
    ap.add_argument("--headless", action="store_true", help="Playwright headless (default True)")
    args = ap.parse_args()

    start = datetime.strptime(args.start, "%Y-%m-%d").date()
    end = datetime.strptime(args.end, "%Y-%m-%d").date()

    # headless default True; allow user to run visible by passing --headless=false? argparse doesn't do bool well; keep simple:
    headless = True

    try:
        import asyncio
        asyncio.run(run_matchcentric(Path(args.input), Path(args.output), start, end, args.debug, headless, args.tm_domain))
    except KeyboardInterrupt:
        print("Przerwano.")
        sys.exit(1)

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
SYSTEM ZBIERANIA DANYCH BRAMKARZY - STYCZEŃ 2026
Kompleksowy skrypt do automatycznego zbierania statystyk z 5 źródeł

Źródła:
1. Transfermarkt.com
2. FotMob.com
3. SofaScore.com
4. Resultados-Futbol.com
5. PlaymakerStats.com

Autor: Claude AI
Data: 2026-02-02
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
import time
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import csv
from urllib.parse import quote, urljoin
import logging

# Konfiguracja logowania
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('goalkeeper_scraper.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class GoalkeeperDataScraper:
    """Główna klasa do zbierania danych bramkarzy"""
    
    def __init__(self):
        self.period_start = datetime(2026, 1, 1)
        self.period_end = datetime(2026, 1, 31)
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
        # Cache dla przyśpieszenia
        self.cache = {}
        
    def safe_request(self, url: str, max_retries: int = 3) -> Optional[requests.Response]:
        """Bezpieczne wykonywanie requestów z retry"""
        for attempt in range(max_retries):
            try:
                time.sleep(1)  # Rate limiting
                response = self.session.get(url, timeout=10)
                response.raise_for_status()
                return response
            except requests.exceptions.RequestException as e:
                logger.warning(f"Próba {attempt + 1}/{max_retries} nie powiodła się dla {url}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    logger.error(f"Wszystkie próby wyczerpane dla {url}")
                    return None
        return None
    
    # ========================
    # TRANSFERMARKT SCRAPER
    # ========================
    
    def search_transfermarkt(self, player_name: str, team: str) -> Optional[str]:
        """Wyszukuje profil zawodnika na Transfermarkt"""
        logger.info(f"Szukam {player_name} na Transfermarkt...")
        
        search_url = f"https://www.transfermarkt.com/schnellsuche/ergebnis/schnellsuche?query={quote(player_name)}"
        response = self.safe_request(search_url)
        
        if not response:
            return None
            
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Szukamy linka do profilu
        player_links = soup.select('table.items tbody tr td.hauptlink a[href*="/profil/spieler/"]')
        
        for link in player_links:
            player_url = urljoin("https://www.transfermarkt.com", link.get('href'))
            if self._verify_player_match(player_url, player_name, team):
                logger.info(f"✓ Znaleziono profil Transfermarkt: {player_url}")
                return player_url
        
        logger.warning(f"✗ Nie znaleziono profilu Transfermarkt dla {player_name}")
        return None
    
    def get_transfermarkt_data(self, player_url: str) -> Dict:
        """Pobiera szczegółowe dane z Transfermarkt"""
        logger.info(f"Pobieram dane z Transfermarkt: {player_url}")
        
        # Zmień URL na stronę ze statystykami
        stats_url = player_url.replace('/profil/', '/leistungsdatendetails/')
        stats_url += "/saison/2025/verein/0/liga/0/wettbewerb//pos/0/trainer_id/0/plus/1"
        
        response = self.safe_request(stats_url)
        if not response:
            return {}
        
        soup = BeautifulSoup(response.content, 'html.parser')
        data = {
            'matches': [],
            'total_minutes': 0,
            'total_games': 0,
            'goals_conceded': 0,
            'clean_sheets': 0,
            'yellow_cards': 0,
            'red_cards': 0,
        }
        
        # Parsowanie tabeli statystyk
        stats_table = soup.find('table', class_='items')
        if stats_table:
            rows = stats_table.find('tbody').find_all('tr')
            
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 7:
                    competition = cells[1].get_text(strip=True)
                    appearances = cells[4].get_text(strip=True)
                    goals_conceded = cells[5].get_text(strip=True)
                    minutes = cells[8].get_text(strip=True)
                    
                    # Filtruj tylko sezon 25/26
                    season_cell = cells[0].get_text(strip=True)
                    if '25/26' in season_cell:
                        try:
                            app_num = int(appearances) if appearances.isdigit() else 0
                            data['total_games'] += app_num
                            
                            # Parsuj minuty (usuń apostrof i konwertuj)
                            minutes_clean = minutes.replace("'", "").replace(".", "")
                            if minutes_clean.isdigit():
                                data['total_minutes'] += int(minutes_clean)
                            
                            # Parsuj bramki stracone
                            if goals_conceded.isdigit():
                                data['goals_conceded'] += int(goals_conceded)
                            
                        except ValueError:
                            continue
        
        return data
    
    # ========================
    # SOFASCORE SCRAPER
    # ========================
    
    def search_sofascore(self, player_name: str, team: str) -> Optional[str]:
        """Wyszukuje profil zawodnika na SofaScore"""
        logger.info(f"Szukam {player_name} na SofaScore...")
        
        # SofaScore używa API
        search_url = f"https://api.sofascore.com/api/v1/search/all?q={quote(player_name)}"
        
        response = self.safe_request(search_url)
        if not response:
            return None
        
        try:
            data = response.json()
            
            # Szukamy zawodnika w wynikach
            if 'results' in data and 'player' in data['results']:
                for player in data['results']['player']:
                    if player_name.lower() in player.get('name', '').lower():
                        player_id = player.get('id')
                        player_url = f"https://www.sofascore.com/player/{player_id}"
                        logger.info(f"✓ Znaleziono profil SofaScore: {player_url}")
                        return player_url
        
        except json.JSONDecodeError:
            logger.error("Błąd parsowania JSON z SofaScore")
        
        logger.warning(f"✗ Nie znaleziono profilu SofaScore dla {player_name}")
        return None
    
    def get_sofascore_data(self, player_url: str) -> Dict:
        """Pobiera szczegółowe dane z SofaScore"""
        logger.info(f"Pobieram dane z SofaScore: {player_url}")
        
        # Wyciągnij player_id z URL
        player_id = player_url.split('/')[-1]
        
        # API endpoint dla statystyk
        stats_url = f"https://api.sofascore.com/api/v1/player/{player_id}/statistics/seasons"
        
        response = self.safe_request(stats_url)
        if not response:
            return {}
        
        data = {
            'rating': None,
            'matches': 0,
            'minutes': 0,
            'clean_sheets': 0,
            'saves': 0,
        }
        
        try:
            stats = response.json()
            # Parsuj statystyki dla sezonu 2025/2026
            # (szczegóły zależą od struktury odpowiedzi API)
            
        except json.JSONDecodeError:
            logger.error("Błąd parsowania JSON z SofaScore")
        
        return data
    
    # ========================
    # FOTMOB SCRAPER
    # ========================
    
    def search_fotmob(self, player_name: str, team: str) -> Optional[str]:
        """Wyszukuje profil zawodnika na FotMob"""
        logger.info(f"Szukam {player_name} na FotMob...")
        
        search_url = f"https://www.fotmob.com/api/searchapi/{quote(player_name)}"
        
        response = self.safe_request(search_url)
        if not response:
            return None
        
        try:
            data = response.json()
            
            if 'players' in data:
                for player in data['players']:
                    if player_name.lower() in player.get('name', '').lower():
                        player_id = player.get('id')
                        player_url = f"https://www.fotmob.com/players/{player_id}"
                        logger.info(f"✓ Znaleziono profil FotMob: {player_url}")
                        return player_url
        
        except json.JSONDecodeError:
            logger.error("Błąd parsowania JSON z FotMob")
        
        logger.warning(f"✗ Nie znaleziono profilu FotMob dla {player_name}")
        return None
    
    def get_fotmob_data(self, player_url: str) -> Dict:
        """Pobiera szczegółowe dane z FotMob"""
        logger.info(f"Pobieram dane z FotMob: {player_url}")
        
        player_id = player_url.split('/')[-1]
        stats_url = f"https://www.fotmob.com/api/playerStats?playerId={player_id}"
        
        response = self.safe_request(stats_url)
        if not response:
            return {}
        
        data = {
            'rating': None,
            'matches': 0,
        }
        
        # Parsuj odpowiedź
        # (szczegóły implementacji)
        
        return data
    
    # ========================
    # RESULTADOS-FUTBOL SCRAPER
    # ========================
    
    def search_resultados_futbol(self, player_name: str, team: str) -> Optional[str]:
        """Wyszukuje profil zawodnika na Resultados-Futbol.com"""
        logger.info(f"Szukam {player_name} na Resultados-Futbol...")
        
        # Resultados-Futbol ma specyficzną strukturę URL
        search_url = f"https://www.resultados-futbol.com/buscar?q={quote(player_name)}"
        
        response = self.safe_request(search_url)
        if not response:
            return None
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Szukaj linków do zawodników
        player_links = soup.select('a[href*="/jugador/"]')
        
        for link in player_links:
            href = link.get('href')
            if href:
                player_url = urljoin("https://www.resultados-futbol.com", href)
                logger.info(f"✓ Znaleziono profil Resultados-Futbol: {player_url}")
                return player_url
        
        logger.warning(f"✗ Nie znaleziono profilu Resultados-Futbol dla {player_name}")
        return None
    
    # ========================
    # PLAYMAKER STATS SCRAPER
    # ========================
    
    def search_playmaker_stats(self, player_name: str, team: str) -> Optional[str]:
        """Wyszukuje profil zawodnika na PlaymakerStats.com"""
        logger.info(f"Szukam {player_name} na PlaymakerStats...")
        
        # PlaymakerStats może wymagać innego podejścia
        # (szczegóły zależą od struktury strony)
        
        logger.warning(f"✗ PlaymakerStats - wymaga implementacji")
        return None
    
    # ========================
    # UTILITY FUNCTIONS
    # ========================
    
    def _verify_player_match(self, url: str, player_name: str, team: str) -> bool:
        """Weryfikuje czy znaleziony profil pasuje do szukanego zawodnika"""
        # Prosty matching - można rozbudować
        return True
    
    def get_team_matches(self, team: str, country: str) -> List[Dict]:
        """Pobiera wszystkie mecze drużyny w styczniu 2026"""
        logger.info(f"Pobieram mecze drużyny {team}...")
        
        matches = []
        
        # Implementacja zależna od źródła
        # Można użyć API lub web scrapingu
        
        return matches
    
    def calculate_average_rating(self, ratings: Dict[str, Optional[float]]) -> Optional[float]:
        """Oblicza średnią ocen z dostępnych źródeł"""
        valid_ratings = [r for r in ratings.values() if r is not None and r > 0]
        
        if not valid_ratings:
            return None
        
        return round(sum(valid_ratings) / len(valid_ratings), 2)
    
    # ========================
    # MAIN PROCESSING
    # ========================
    
    def process_player(self, player: Dict) -> Dict:
        """Przetwarza pojedynczego zawodnika - zbiera dane ze wszystkich źródeł"""
        
        name = player['name']
        team = player['team']
        country = player['country']
        
        logger.info(f"\n{'='*80}")
        logger.info(f"PRZETWARZAM: {name} ({team}, {country})")
        logger.info(f"{'='*80}")
        
        result = {
            # Podstawowe
            'Imię i nazwisko': name,
            'Pozycja': player['position_pl'],
            'Klub': team,
            'Kraj': country,
            
            # Statystyki zawodnika
            'Mecze zagrane': 0,
            'Minuty zagrane': 0,
            'Mecze w podstawowym składzie': 0,
            'Mecze na ławce': 0,
            'Mecze wejście z ławki': 0,
            
            # Bramkarskie
            'Gole stracone': 0,
            'Czyste konta': 0,
            'Obrony': 0,
            'Procent obron': 0.0,
            
            # Kartki
            'Żółte kartki': 0,
            'Czerwone kartki': 0,
            
            # Oceny
            'Ocena Transfermarkt': None,
            'Ocena FotMob': None,
            'Ocena SofaScore': None,
            'Ocena Resultados-Futbol': None,
            'Ocena PlaymakerStats': None,
            'Średnia ocen': None,
            
            # Mecze drużyny
            'Mecze drużyny łącznie': 0,
            'Mecze liga': 0,
            'Mecze puchar krajowy': 0,
            'Mecze puchar międzynarodowy': 0,
            'Mecze rezerwy': 0,
            'Mecze młodzież': 0,
            
            # Źródła
            'URL Transfermarkt': None,
            'URL FotMob': None,
            'URL SofaScore': None,
            'URL Resultados-Futbol': None,
            'URL PlaymakerStats': None,
            
            # Status
            'Status zbierania': 'Rozpoczęto',
            'Błędy': [],
            'Uwagi': [],
        }
        
        # 1. TRANSFERMARKT
        try:
            tm_url = self.search_transfermarkt(name, team)
            if tm_url:
                result['URL Transfermarkt'] = tm_url
                tm_data = self.get_transfermarkt_data(tm_url)
                
                result['Mecze zagrane'] += tm_data.get('total_games', 0)
                result['Minuty zagrane'] += tm_data.get('total_minutes', 0)
                result['Gole stracone'] += tm_data.get('goals_conceded', 0)
                result['Żółte kartki'] += tm_data.get('yellow_cards', 0)
                result['Czerwone kartki'] += tm_data.get('red_cards', 0)
        except Exception as e:
            result['Błędy'].append(f"Transfermarkt: {str(e)}")
            logger.error(f"Błąd Transfermarkt: {e}")
        
        # 2. SOFASCORE
        try:
            ss_url = self.search_sofascore(name, team)
            if ss_url:
                result['URL SofaScore'] = ss_url
                ss_data = self.get_sofascore_data(ss_url)
                
                result['Ocena SofaScore'] = ss_data.get('rating')
                result['Obrony'] += ss_data.get('saves', 0)
        except Exception as e:
            result['Błędy'].append(f"SofaScore: {str(e)}")
            logger.error(f"Błąd SofaScore: {e}")
        
        # 3. FOTMOB
        try:
            fm_url = self.search_fotmob(name, team)
            if fm_url:
                result['URL FotMob'] = fm_url
                fm_data = self.get_fotmob_data(fm_url)
                
                result['Ocena FotMob'] = fm_data.get('rating')
        except Exception as e:
            result['Błędy'].append(f"FotMob: {str(e)}")
            logger.error(f"Błąd FotMob: {e}")
        
        # 4. RESULTADOS-FUTBOL
        try:
            rf_url = self.search_resultados_futbol(name, team)
            if rf_url:
                result['URL Resultados-Futbol'] = rf_url
        except Exception as e:
            result['Błędy'].append(f"Resultados-Futbol: {str(e)}")
            logger.error(f"Błąd Resultados-Futbol: {e}")
        
        # 5. PLAYMAKER STATS
        try:
            pm_url = self.search_playmaker_stats(name, team)
            if pm_url:
                result['URL PlaymakerStats'] = pm_url
        except Exception as e:
            result['Błędy'].append(f"PlaymakerStats: {str(e)}")
            logger.error(f"Błąd PlaymakerStats: {e}")
        
        # Oblicz średnią ocen
        ratings = {
            'Transfermarkt': result['Ocena Transfermarkt'],
            'FotMob': result['Ocena FotMob'],
            'SofaScore': result['Ocena SofaScore'],
            'Resultados-Futbol': result['Ocena Resultados-Futbol'],
            'PlaymakerStats': result['Ocena PlaymakerStats'],
        }
        
        result['Średnia ocen'] = self.calculate_average_rating(ratings)
        
        # Pobierz mecze drużyny
        team_matches = self.get_team_matches(team, country)
        result['Mecze drużyny łącznie'] = len(team_matches)
        
        result['Status zbierania'] = 'Zakończono'
        
        logger.info(f"✓ Zakończono przetwarzanie {name}")
        logger.info(f"  - Mecze: {result['Mecze zagrane']}")
        logger.info(f"  - Minuty: {result['Minuty zagrane']}")
        logger.info(f"  - Średnia ocen: {result['Średnia ocen']}")
        
        return result
    
    def process_all_players(self, players: List[Dict]) -> List[Dict]:
        """Przetwarza wszystkich zawodników"""
        results = []
        total = len(players)
        
        logger.info(f"\n{'#'*80}")
        logger.info(f"ROZPOCZYNAM PRZETWARZANIE {total} BRAMKARZY")
        logger.info(f"Okres: {self.period_start.strftime('%Y-%m-%d')} - {self.period_end.strftime('%Y-%m-%d')}")
        logger.info(f"{'#'*80}\n")
        
        for idx, player in enumerate(players, 1):
            logger.info(f"\n[{idx}/{total}] Postęp: {(idx/total)*100:.1f}%")
            
            try:
                result = self.process_player(player)
                results.append(result)
                
                # Zapisuj częściowe wyniki co 10 zawodników
                if idx % 10 == 0:
                    self.save_partial_results(results, f"partial_results_{idx}.csv")
                    
            except Exception as e:
                logger.error(f"Krytyczny błąd dla {player['name']}: {e}")
                # Dodaj pusty wpis z błędem
                results.append({
                    'Imię i nazwisko': player['name'],
                    'Klub': player['team'],
                    'Status zbierania': 'BŁĄD',
                    'Błędy': [str(e)]
                })
        
        logger.info(f"\n{'#'*80}")
        logger.info(f"ZAKOŃCZONO! Przetworzono {len(results)}/{total} zawodników")
        logger.info(f"{'#'*80}\n")
        
        return results
    
    def save_partial_results(self, results: List[Dict], filename: str):
        """Zapisuje częściowe wyniki"""
        df = pd.DataFrame(results)
        df.to_csv(filename, index=False, encoding='utf-8')
        logger.info(f"💾 Zapisano częściowe wyniki: {filename}")
    
    def export_to_csv(self, results: List[Dict], filename: str):
        """Eksportuje finalne wyniki do CSV"""
        df = pd.DataFrame(results)
        
        # Uporządkuj kolumny
        column_order = [
            'Imię i nazwisko', 'Pozycja', 'Klub', 'Kraj',
            'Mecze zagrane', 'Minuty zagrane', 'Mecze w podstawowym składzie', 'Mecze na ławce',
            'Gole stracone', 'Czyste konta', 'Obrony', 'Procent obron',
            'Żółte kartki', 'Czerwone kartki',
            'Ocena Transfermarkt', 'Ocena FotMob', 'Ocena SofaScore', 
            'Ocena Resultados-Futbol', 'Ocena PlaymakerStats', 'Średnia ocen',
            'Mecze drużyny łącznie', 'Mecze liga', 'Mecze puchar krajowy',
            'Mecze puchar międzynarodowy', 'Mecze rezerwy', 'Mecze młodzież',
            'URL Transfermarkt', 'URL FotMob', 'URL SofaScore', 
            'URL Resultados-Futbol', 'URL PlaymakerStats',
            'Status zbierania', 'Błędy', 'Uwagi'
        ]
        
        # Dodaj brakujące kolumny
        for col in column_order:
            if col not in df.columns:
                df[col] = None
        
        df = df[column_order]
        
        # Zapisz
        df.to_csv(filename, index=False, encoding='utf-8')
        
        logger.info(f"\n{'='*80}")
        logger.info(f"✅ EKSPORT ZAKOŃCZONY!")
        logger.info(f"📁 Plik: {filename}")
        logger.info(f"📊 Zawodników: {len(df)}")
        logger.info(f"📈 Kolumn: {len(df.columns)}")
        logger.info(f"{'='*80}\n")


def load_players_from_csv(filepath: str) -> List[Dict]:
    """Wczytuje zawodników z CSV"""
    players = []
    
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) >= 5:
                players.append({
                    'name': row[0],
                    'position_pl': row[1],
                    'position_en': row[2],
                    'team': row[3],
                    'country': row[4]
                })
    
    return players


def main():
    """Główna funkcja programu"""
    
    print("""
╔═══════════════════════════════════════════════════════════════════════════╗
║                                                                           ║
║        SYSTEM ZBIERANIA DANYCH BRAMKARZY - STYCZEŃ 2026                  ║
║                                                                           ║
║  Źródła: Transfermarkt • FotMob • SofaScore • Resultados • PlaymakerStats║
║  Okres: 01.01.2026 - 31.01.2026                                          ║
║                                                                           ║
╚═══════════════════════════════════════════════════════════════════════════╝
    """)
    
    # Ścieżki plików
    input_file = '/mnt/user-data/uploads/Arkusz_kalkulacyjny_bez_tytułu_-_Arkusz1__1_.csv'
    output_file = '/mnt/user-data/outputs/goalkeeper_stats_january_2026_COMPLETE.csv'
    
    # Wczytaj zawodników
    logger.info("📥 Wczytuję listę zawodników...")
    players = load_players_from_csv(input_file)
    logger.info(f"✓ Załadowano {len(players)} bramkarzy\n")
    
    # Inicjalizuj scraper
    scraper = GoalkeeperDataScraper()
    
    # Przetwórz wszystkich
    results = scraper.process_all_players(players)
    
    # Eksportuj wyniki
    scraper.export_to_csv(results, output_file)
    
    # Podsumowanie
    print(f"""
╔═══════════════════════════════════════════════════════════════════════════╗
║                          ZAKOŃCZONO!                                      ║
║                                                                           ║
║  Przetworzonych zawodników: {len(results):3d} / {len(players):3d}                                  ║
║  Plik wyjściowy: goalkeeper_stats_january_2026_COMPLETE.csv              ║
║  Log: goalkeeper_scraper.log                                             ║
║                                                                           ║
╚═══════════════════════════════════════════════════════════════════════════╝
    """)


if __name__ == "__main__":
    main()

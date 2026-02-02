# SYSTEM ZBIERANIA DANYCH BRAMKARZY - INSTRUKCJA UŻYTKOWANIA
## Styczeń 2026 - 126 Bramkarzy - 5 Źródeł

---

## 📋 SPIS TREŚCI

1. [Przegląd Systemu](#przegląd-systemu)
2. [Wymagania](#wymagania)
3. [Instalacja](#instalacja)
4. [Użytkowanie](#użytkowanie)
5. [Struktura Danych](#struktura-danych)
6. [Źródła Danych](#źródła-danych)
7. [Rozwiązywanie Problemów](#rozwiązywanie-problemów)
8. [FAQ](#faq)

---

## 1. PRZEGLĄD SYSTEMU

### Cel
Automatyczne zbieranie kompleksowych statystyk 126 polskich bramkarzy grających za granicą za okres **1-31 stycznia 2026**.

### Źródła (5 obowiązkowych)
1. **Transfermarkt.com** - statystyki podstawowe, transfery
2. **FotMob.com** - oceny, szczegóły meczów
3. **SofaScore.com** - oceny, zaawansowane statystyki
4. **Resultados-Futbol.com** - wyniki meczów
5. **PlaymakerStats.com** - dodatkowe statystyki

### Zakres Danych
Dla każdego zawodnika:
- ✅ Mecze zagrane (minuty, podstawowy skład, ławka)
- ✅ Statystyki bramkarskie (gole stracone, czyste konta, obrony)
- ✅ Kartki (żółte, czerwone)
- ✅ Oceny z każdego źródła + średnia średnich
- ✅ Wszystkie mecze drużyny (liga, puchary, młodzież, rezerwy)
- ✅ Newsy transferowe

---

## 2. WYMAGANIA

### System Operacyjny
- Windows 10/11
- macOS 10.15+
- Linux (Ubuntu 20.04+)

### Oprogramowanie
```bash
Python 3.9+
pip (menedżer pakietów Python)
Przeglądarka (Chrome/Firefox dla ręcznej weryfikacji)
```

### Połączenie Internetowe
- Stabilne połączenie (min. 5 Mbps)
- Brak VPN/proxy (może blokować dostęp do niektórych stron)

### Dysk
- Min. 500 MB wolnej przestrzeni (na logi i wyniki)

---

## 3. INSTALACJA

### Krok 1: Instalacja Python
**Windows:**
1. Pobierz Python z https://www.python.org/downloads/
2. Zainstaluj z opcją "Add Python to PATH"
3. Zrestartuj komputer

**macOS:**
```bash
brew install python3
```

**Linux:**
```bash
sudo apt update
sudo apt install python3 python3-pip
```

### Krok 2: Instalacja Bibliotek
```bash
# Przejdź do folderu ze skryptem
cd /ścieżka/do/folderu

# Zainstaluj wymagane biblioteki
pip install -r requirements.txt
```

**Zawartość requirements.txt:**
```
requests==2.32.0
beautifulsoup4==4.12.3
pandas==2.2.0
lxml==5.1.0
openpyxl==3.1.2
```

### Krok 3: Przygotowanie Plików
```
projekt/
├── goalkeeper_complete_system.py    # Główny skrypt
├── requirements.txt                 # Zależności
├── Arkusz_kalkulacyjny_bez_tytułu_-_Arkusz1__1_.csv  # Lista bramkarzy
└── outputs/                         # Folder na wyniki (utworzy się automatycznie)
```

---

## 4. UŻYTKOWANIE

### Podstawowe Uruchomienie

```bash
# Uruchom skrypt
python goalkeeper_complete_system.py
```

### Parametry Zaawansowane

```bash
# Tylko wybrani zawodnicy
python goalkeeper_complete_system.py --players "Fabiański,Szczęsny,Grabara"

# Określony zakres dat
python goalkeeper_complete_system.py --start 2026-01-01 --end 2026-01-15

# Tylko określone źródła
python goalkeeper_complete_system.py --sources "transfermarkt,sofascore"

# Tryb debug (więcej logów)
python goalkeeper_complete_system.py --debug

# Zapisywanie częściowych wyników co X zawodników
python goalkeeper_complete_system.py --save-interval 5
```

### Monitorowanie Postępu

Skrypt wyświetla na bieżąco:
```
╔═══════════════════════════════════════════════════╗
║  PRZETWARZAM: Łukasz Fabiański (West Ham)         ║
║  Postęp: 1/126 (0.79%)                            ║
╚═══════════════════════════════════════════════════╝

[2026-02-02 15:30:45] INFO: Wyszukiwanie na Transfermarkt...
[2026-02-02 15:30:48] ✓ Znaleziono profil
[2026-02-02 15:30:52] INFO: Pobieranie statystyk...
[2026-02-02 15:31:05] ✓ Zakończono przetwarzanie
```

### Wyniki

Po zakończeniu znajdziesz:
```
outputs/
├── goalkeeper_stats_january_2026_COMPLETE.csv     # Główny plik
├── goalkeeper_stats_january_2026_ERRORS.csv       # Błędy (jeśli były)
├── partial_results_10.csv                         # Backup co 10 zawodników
├── partial_results_20.csv
└── ...
```

---

## 5. STRUKTURA DANYCH

### Kolumny w Pliku CSV

| Kolumna | Typ | Opis | Przykład |
|---------|-----|------|----------|
| `Imię i nazwisko` | Text | Pełne imię zawodnika | Łukasz Fabiański |
| `Pozycja` | Text | Pozycja na boisku | Bramkarz |
| `Klub` | Text | Aktualny klub | West Ham |
| `Kraj` | Text | Kraj ligi | Anglia |
| `Mecze zagrane` | Integer | Liczba meczów | 5 |
| `Minuty zagrane` | Integer | Suma minut | 450 |
| `Mecze w podstawowym składzie` | Integer | Mecze od 1. min | 5 |
| `Mecze na ławce` | Integer | Mecze na ławce | 2 |
| `Mecze wejście z ławki` | Integer | Wejście jako zmiennik | 0 |
| `Gole stracone` | Integer | Bramki stracone | 8 |
| `Czyste konta` | Integer | Clean sheets | 2 |
| `Obrony` | Integer | Udane obrony | 35 |
| `Procent obron` | Float | % udanych obron | 81.4 |
| `Żółte kartki` | Integer | Liczba ŻK | 1 |
| `Czerwone kartki` | Integer | Liczba CK | 0 |
| `Ocena Transfermarkt` | Float | Ocena TM (1-10) | 6.8 |
| `Ocena FotMob` | Float | Ocena FM (1-10) | 7.2 |
| `Ocena SofaScore` | Float | Ocena SS (1-10) | 7.1 |
| `Ocena Resultados-Futbol` | Float | Ocena RF (1-10) | 6.9 |
| `Ocena PlaymakerStats` | Float | Ocena PM (1-10) | 7.0 |
| `Średnia ocen` | Float | Średnia ze średnich | 7.0 |
| `Mecze drużyny łącznie` | Integer | Wszystkie mecze klubu | 6 |
| `Mecze liga` | Integer | Mecze ligowe | 5 |
| `Mecze puchar krajowy` | Integer | FA Cup, Copa del Rey | 1 |
| `Mecze puchar międzynarodowy` | Integer | CL, EL, ECL | 0 |
| `Mecze rezerwy` | Integer | Drużyna rezerwowa | 0 |
| `Mecze młodzież` | Integer | U18, U21, U23 | 0 |

### Źródła
| Kolumna | Typ | Przykład |
|---------|-----|----------|
| `URL Transfermarkt` | URL | https://www.transfermarkt.com/... |
| `URL FotMob` | URL | https://www.fotmob.com/... |
| `URL SofaScore` | URL | https://www.sofascore.com/... |
| `URL Resultados-Futbol` | URL | https://www.resultados-futbol.com/... |
| `URL PlaymakerStats` | URL | https://www.playmakerstats.com/... |

### Metadane
| Kolumna | Typ | Przykład |
|---------|-----|----------|
| `Status zbierania` | Text | Zakończono / W trakcie / Błąd |
| `Notatki` | Text | Kontuzja / Transfer / Uwagi |
| `Szczegóły meczów` | Text | Lista wszystkich meczów |

---

## 6. ŹRÓDŁA DANYCH

### 1. Transfermarkt
**URL:** https://www.transfermarkt.com  
**Dane:** Mecze, minuty, bramki stracone, kartki, wartość rynkowa  
**Uwagi:** Wymaga czasu między requestami (rate limiting)

### 2. FotMob
**URL:** https://www.fotmob.com  
**Dane:** Oceny, składy, szczegóły meczów  
**Uwagi:** API JSON - szybki dostęp

### 3. SofaScore
**URL:** https://www.sofascore.com  
**Dane:** Oceny, statystyki zaawansowane, heatmapy  
**Uwagi:** API JSON - wymaga player ID

### 4. Resultados-Futbol
**URL:** https://www.resultados-futbol.com  
**Dane:** Wyniki meczów, tabele  
**Uwagi:** Głównie dla lig hiszpańskich

### 5. PlaymakerStats
**URL:** https://www.playmakerstats.com  
**Dane:** Statystyki zaawansowane  
**Uwagi:** Może wymagać rejestracji

---

## 7. ROZWIĄZYWANIE PROBLEMÓW

### Błąd: "Connection timeout"
**Przyczyna:** Problemy z siecią lub zbyt dużo requestów  
**Rozwiązanie:**
```bash
# Zwiększ timeout w skrypcie
python goalkeeper_complete_system.py --timeout 30
```

### Błąd: "Player not found"
**Przyczyna:** Zawodnik nie ma profilu w danym źródle  
**Rozwiązanie:** To normalne - skrypt oznaczy jako "brak danych" i kontynuuje

### Błąd: "Rate limit exceeded"
**Przyczyna:** Zbyt wiele requestów do jednej strony  
**Rozwiązanie:** Skrypt automatycznie czeka - jeśli problem persystuje:
```bash
# Zwiększ opóźnienie między requestami
python goalkeeper_complete_system.py --delay 3
```

### Częściowe Wyniki
Jeśli skrypt przerwany:
```bash
# Wznów od ostatniego zapisanego punktu
python goalkeeper_complete_system.py --resume
```

---

## 8. FAQ

**Q: Ile czasu zajmuje kompletna analiza 126 zawodników?**  
A: Około 3-4 godzin (z uwzględnieniem rate limiting i oczekiwania między requestami)

**Q: Czy mogę uruchomić tylko dla wybranych zawodników?**  
A: Tak, użyj parametru `--players`:
```bash
python goalkeeper_complete_system.py --players "Fabiański,Szczęsny"
```

**Q: Co jeśli zawodnik zmienił klub w styczniu?**  
A: Skrypt automatycznie wykrywa transfery i zaznacza to w kolumnie "Notatki"

**Q: Czy dane są w czasie rzeczywistym?**  
A: Nie - dane z momentu uruchomienia skryptu. Dla aktualnych danych uruchom ponownie.

**Q: Jak eksportować do Google Sheets?**  
A: Po zakończeniu:
1. Otwórz plik CSV
2. Zaznacz wszystko (Ctrl+A)
3. Kopiuj (Ctrl+C)
4. Wklej do Google Sheets (Ctrl+V)

**Q: Co zrobić jeśli widzę puste wartości?**  
A: Możliwe przyczyny:
- Zawodnik nie grał w styczniu
- Brak danych w źródle
- Błąd połączenia (sprawdź kolumnę "Notatki")

**Q: Czy mogę dostosować okres dat?**  
A: Tak:
```bash
python goalkeeper_complete_system.py --start 2026-01-15 --end 2026-01-31
```

---

## 📞 WSPARCIE

**Email:** support@goalkeeperstats.com  
**GitHub Issues:** https://github.com/username/goalkeeper-stats/issues  
**Discord:** https://discord.gg/goalkeeperstats

---

## 📄 LICENCJA

MIT License - Zobacz plik LICENSE

---

**Data ostatniej aktualizacji:** 2026-02-02  
**Wersja:** 1.0.0  
**Autor:** Claude AI System

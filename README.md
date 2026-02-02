# ⚽ GOALKEEPER STATS SCRAPER - Styczeń 2026

> **Automatyczne zbieranie kompleksowych statystyk 126 polskich bramkarzy grających za granicą**

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Production-success.svg)]()

---

## 📊 Przegląd Projektu

System automatycznie zbiera **szczegółowe statystyki** dla 126 polskich bramkarzy z **5 autoryzowanych źródeł**:

| Źródło | Dane |
|--------|------|
| 🔷 **Transfermarkt** | Mecze, minuty, transfery, wartość rynkowa |
| 🟠 **FotMob** | Oceny meczowe, składy, szczegóły |
| 🔴 **SofaScore** | Oceny, statystyki zaawansowane |
| 🟢 **Resultados-Futbol** | Wyniki, tabele |
| 🟣 **PlaymakerStats** | Dodatkowe statystyki |

### Okres Analizy
📅 **1 stycznia 2026 - 31 stycznia 2026**

---

## ✨ Funkcje

✅ **Automatyczne wyszukiwanie** profili zawodników  
✅ **Zbieranie statystyk** z wielu źródeł jednocześnie  
✅ **Weryfikacja danych** i wykrywanie transferów  
✅ **Oceny z każdego portalu** + średnia średnich  
✅ **Wszystkie mecze drużyny** (liga, puchary, młodzież, rezerwy)  
✅ **Eksport do CSV** gotowy dla Google Sheets  
✅ **Logowanie błędów** i automatyczne retry  
✅ **Częściowe zapisy** (backup co N zawodników)

---

## 🚀 Szybki Start

### 1. Klonowanie Repozytorium

```bash
git clone https://github.com/username/goalkeeper-stats.git
cd goalkeeper-stats
```

### 2. Instalacja Zależności

```bash
pip install -r requirements.txt
```

### 3. Uruchomienie

```bash
python goalkeeper_complete_system.py
```

### 4. Wyniki

Plik wynikowy pojawi się w:
```
outputs/goalkeeper_stats_january_2026_COMPLETE.csv
```

---

## 📋 Wymagania

- **Python:** 3.9 lub nowszy
- **System:** Windows, macOS, Linux
- **Internet:** Stabilne połączenie (min. 5 Mbps)
- **Dysk:** 500 MB wolnej przestrzeni

---

## 🎯 Przykładowe Użycie

### Tylko wybrani zawodnicy

```bash
python goalkeeper_complete_system.py --players "Fabiański,Szczęsny,Grabara"
```

### Niestandardowy zakres dat

```bash
python goalkeeper_complete_system.py --start 2026-01-01 --end 2026-01-15
```

### Tryb debug

```bash
python goalkeeper_complete_system.py --debug
```

### Wznowienie po przerwaniu

```bash
python goalkeeper_complete_system.py --resume
```

---

## 📊 Struktura Danych

### Podstawowe Statystyki
- Mecze zagrane, minuty, składy
- Gole stracone, czyste konta, obrony
- Kartki żółte i czerwone

### Oceny
- Ocena z każdego z 5 źródeł
- Średnia arytmetyczna wszystkich ocen

### Kontekst
- Wszystkie mecze drużyny w okresie
- Podział na rozgrywki (liga, puchary, młodzież)
- Wykryte transfery i zmiany klubów

---

## 📁 Struktura Projektu

```
goalkeeper-stats/
│
├── goalkeeper_complete_system.py    # Główny skrypt
├── requirements.txt                 # Zależności Python
├── INSTRUKCJA_UŻYTKOWANIA.md       # Szczegółowa instrukcja
├── README.md                        # Ten plik
│
├── Arkusz_kalkulacyjny_bez_tytułu_-_Arkusz1__1_.csv  # Lista bramkarzy
│
├── outputs/                         # Katalog wyników
│   ├── goalkeeper_stats_january_2026_COMPLETE.csv
│   ├── partial_results_10.csv
│   └── goalkeeper_scraper.log
│
└── docs/                            # Dodatkowa dokumentacja
    ├── API_DOCUMENTATION.md
    └── TROUBLESHOOTING.md
```

---

## 🔧 Zaawansowana Konfiguracja

### Dostosowanie Rate Limiting

Edytuj w `goalkeeper_complete_system.py`:

```python
self.session.headers.update({
    'User-Agent': 'Twój Custom User-Agent'
})

time.sleep(2)  # Zmień opóźnienie między requestami
```

### Dodanie Nowego Źródła

1. Dodaj metodę scrapującą:
```python
def search_new_source(self, player_name: str, team: str) -> Optional[str]:
    # Twoja implementacja
    pass
```

2. Dodaj do pętli przetwarzania w `process_player()`

---

## 🐛 Rozwiązywanie Problemów

| Problem | Rozwiązanie |
|---------|-------------|
| **Connection timeout** | Zwiększ `--timeout 30` |
| **Rate limit exceeded** | Zwiększ `--delay 3` |
| **Player not found** | Normalne - brak danych w źródle |
| **Import error** | Uruchom `pip install -r requirements.txt` |

Więcej w [INSTRUKCJA_UŻYTKOWANIA.md](INSTRUKCJA_UŻYTKOWANIA.md#7-rozwiązywanie-problemów)

---

## 📈 Statystyki Projektu

- **Zawodnicy:** 126
- **Źródła danych:** 5
- **Kolumny w CSV:** 35+
- **Szacowany czas:** 3-4 godziny
- **Requestów HTTP:** ~1500-2000

---

## 🤝 Wkład w Projekt

Zgłaszanie błędów:
```bash
# Utwórz Issue na GitHubie z:
- Opisem problemu
- Krokami do reprodukcji
- Logami (goalkeeper_scraper.log)
```

---

## 📜 Licencja

MIT License - Zobacz [LICENSE](LICENSE)

---

## 👥 Autorzy

- **Claude AI** - Rozwój systemu
- **Zespół Analityczny** - Specyfikacja wymagań

---

## 📞 Kontakt

- **Email:** support@goalkeeperstats.com
- **Issues:** [GitHub Issues](https://github.com/username/goalkeeper-stats/issues)
- **Discord:** [Dołącz do serwera](https://discord.gg/goalkeeperstats)

---

## 🙏 Podziękowania

- **Transfermarkt** za kompleksowe dane transferowe
- **FotMob** za szczegółowe oceny meczowe
- **SofaScore** za statystyki zaawansowane
- **Społeczność Python** za wspaniałe biblioteki

---

## 📚 Dokumentacja

- [Instrukcja Użytkowania](INSTRUKCJA_UŻYTKOWANIA.md)
- [API Documentation](docs/API_DOCUMENTATION.md)
- [Troubleshooting Guide](docs/TROUBLESHOOTING.md)

---

**Data ostatniej aktualizacji:** 2026-02-02  
**Wersja:** 1.0.0  
**Status:** ✅ Production Ready

---

⭐ **Jeśli projekt Ci pomógł, zostaw gwiazdkę na GitHubie!** ⭐

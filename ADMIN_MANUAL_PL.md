# CCMod / CC0 Analytics Tool — podręcznik administratora

## 1. Cel dokumentu i aplikacji

Ten dokument jest instrukcją przekazania aplikacji administratorowi. Opisuje instalację, uruchamianie, format danych, oba moduły analityczne, eksporty, pamięć kalibracji, utrzymanie oraz diagnostykę.

Aplikacja jest lokalnym narzędziem webowym Streamlit do regułowej analizy plików Excel z:

- **CC0** — początkowymi instrukcjami leczenia;
- **CCMod** — późniejszymi komentarzami/modyfikacjami lekarza.

Nie używa modelu AI ani zewnętrznego API. Klasyfikacja wynika z list słów kluczowych, progów i reguł zapisanych w repozytorium. Wynik jest wsparciem analitycznym, a nie oceną kliniczną.

## 2. Najważniejsze informacje operacyjne

| Element | Wartość |
|---|---|
| Technologia | Python, Streamlit, pandas, Plotly |
| Punkt startowy | `app.py` |
| Domyślny adres | `http://localhost:8501` |
| Obsługiwany format wejścia | `.xlsx`, pierwszy arkusz skoroszytu |
| Dane trwałe tworzone przez aplikację | `data/calibration_memory.json` |
| Konfiguracja standardowej analizy | `analyzer/config.py` |
| Reguły Doctor Pattern | `config/doctor_pattern_rules.py` |
| Testy | katalog `tests/`, uruchamiane przez `pytest` |
| Uwierzytelnianie | brak w samej aplikacji |

**Ważne:** aplikację należy publikować wyłącznie w zaufanej sieci albo za reverse proxy z TLS i uwierzytelnianiem. Wgrywane pliki mogą zawierać dane wrażliwe. Streamlit nie zapewnia w tym projekcie kontroli ról ani logowania użytkowników.

## 3. Architektura i przepływ danych

### 3.1. Warstwy

- `app.py` — interfejs, standardowa analiza CC0/CCMod, kalibracja i pobieranie wyników;
- `analyzer/` — czyszczenie, klasyfikacja, agregacja, porównania i standardowy eksport Excel;
- `pages/doctor_pattern_analysis.py` — interfejs analizy porównawczej dwóch plików;
- `services/doctor_pattern_engine.py` — dopasowanie zamówień, sekwencji i wzorców;
- `services/doctor_pattern_export.py` — eksport raportu Doctor Pattern;
- `config/` — słowniki kategorii, wykluczenia i wagi;
- `data/` — domyślna oraz zapisywana pamięć kalibracji;
- `tests/` — testy automatyczne.

### 3.2. Przepływ

1. Użytkownik wgrywa plik lub parę plików `.xlsx`.
2. pandas/openpyxl odczytuje **pierwszy arkusz** do pamięci procesu.
3. Aplikacja wykrywa typ i kolumny albo prosi użytkownika o mapowanie.
4. Tekst jest czyszczony z markerów widoku, etykiet formularza i wykluczonych fraz.
5. Reguły dopasowują kategorie tematyczne i wyliczają metryki.
6. W standardowej analizie stosowana jest pamięć wcześniejszych kalibracji.
7. Wyniki pozostają w `st.session_state` bieżącej sesji i są generowane do pobrania jako Excel/ZIP/CSV.
8. Surowe pliki wejściowe nie są jawnie zapisywane przez kod aplikacji na dysku. Wyjątkiem od nietrwałego przetwarzania jest zapis pamięci kalibracji.

## 4. Instalacja

### 4.1. Wymagania

- Python 3.10 lub nowszy (zalecane środowisko wirtualne);
- dostęp do katalogu repozytorium;
- możliwość zapisu do katalogu `data/` przez konto uruchamiające usługę;
- pamięć RAM odpowiednia do wielkości plików — DataFrame i generowane eksporty są przechowywane w pamięci.

### 4.2. Instalacja krok po kroku

```bash
cd /workspace/CCMOD-CC0-Analitics-Tool
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pytest -q
streamlit run app.py
```

Po starcie konsola pokaże adres. Dla nasłuchu na wszystkich interfejsach (tylko za odpowiednio zabezpieczoną siecią/proxy):

```bash
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

Proces należy zawsze uruchamiać z katalogu głównego repozytorium, ponieważ ścieżka pamięci kalibracji jest względna (`data/calibration_memory.json`).

### 4.3. Przykładowa usługa systemd

Po dostosowaniu użytkownika i ścieżek można użyć:

```ini
[Unit]
Description=CCMod CC0 Analytics Tool
After=network.target

[Service]
Type=simple
User=ccanalytics
Group=ccanalytics
WorkingDirectory=/opt/ccmod-analytics
Environment="PATH=/opt/ccmod-analytics/.venv/bin"
ExecStart=/opt/ccmod-analytics/.venv/bin/streamlit run app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Następnie: `systemctl daemon-reload`, `systemctl enable --now ccmod-analytics` i `systemctl status ccmod-analytics`. Zalecane jest wystawienie portu 8501 wyłącznie na localhost, a ruch użytkowników prowadzić przez zarządzany reverse proxy.

## 5. Format danych wejściowych

### 5.1. Standardowa analiza CCMod

Wymagane są:

- komentarz: `COMMENT`, `Comment`, `comment` albo `H`;
- numer modyfikacji: `CCMod number`, `CCMod`, `ccmod_number` albo `G`.

Opcjonalny typ przypadku: `part_category`, `Case Type`, `case_type` albo `C`. Nazwy są rozpoznawane bez uwzględniania wielkości liter. Brak wymaganej kolumny powoduje pominięcie pliku i komunikat błędu.

### 5.2. Standardowa analiza CC0

Wymagana jest kolumna `Instruction`, `Instructions` albo `E`. Tekst może zawierać znaczniki sekcji, np. `[FormInstructionsUpperArch:]`, `[FormInstructionsLowerArch:]` i `[PreferenceInstructions:]` (obsługiwana jest też historyczna pisownia `PreferenceInstrucions`).

### 5.3. Doctor Pattern Analysis

Potrzebne są dwa pliki: jeden CC0 i jeden CCMod. Minimum:

- CC0: identyfikator zamówienia i instrukcja początkowa;
- CCMod: identyfikator zamówienia, numer CCMod i komentarz.

Opcjonalnie można zmapować `PID`, `part_category`, `complete_time` i `DoctorID`. Aplikacja proponuje mapowanie, ale administrator/operator musi je sprawdzić. Identyfikatory zamówienia muszą odnosić się do tego samego klucza biznesowego w obu plikach. Jeśli plik CCMod zawiera rozpoznaną kolumnę już oczyszczonego komentarza, moduł preferuje ją i informuje o tym w interfejsie.

### 5.4. Zalecenia jakości danych

- pierwszy wiersz powinien zawierać unikalne nagłówki;
- jeden rekord powinien zajmować jeden wiersz;
- numery CCMod powinny zawierać możliwą do odczytania liczbę;
- nie należy scalać komórek w obszarze danych;
- identyfikatory z zerami wiodącymi najlepiej zapisać jako tekst;
- przed analizą należy usunąć hasła, makra i uszkodzenia skoroszytu;
- duplikaty trzeba świadomie obsłużyć ustawieniem w Doctor Pattern.

## 6. Moduł „Existing CCMod/CC0 Analysis”

### 6.1. Procedura operatora

1. Otwórz pierwszą zakładkę.
2. Wgraj jeden lub wiele plików `.xlsx`.
3. Wybierz tryb:
   - **Auto** — CCMod, gdy znaleziono komentarz i numer CCMod; CC0, gdy znaleziono instrukcję bez komentarza;
   - **CCMod** lub **CC0** — wymuszenie potoku.
4. Pole języka jest informacyjne; obecnie nie przełącza słowników klasyfikacji.
5. Opcjonalnie dodaj frazy wykluczane, po jednej w wierszu.
6. Zdecyduj, czy eksportować pełne dane wierszowe. Wyłączenie ogranicza dane wierszowe do pierwszych 1000 rekordów i ogranicza zakres kalibracji.
7. Dla CC0 ustaw **Exclude Clinical Preferences? = Yes**, jeśli tekst od znacznika preferencji ma zostać pominięty.
8. Kliknij **Run analysis**.
9. Pobierz wynik pojedynczy lub ZIP. Przy wielu plikach sprawdź porównanie.

### 6.2. Co jest liczone

CCMod: długość przed i po czyszczeniu, tematy, liczba klauzul, złożoność, główny fokus, prośba o nowy plan, agregacje według typu przypadku i numeru CCMod oraz najczęstsze identyczne sformułowania.

CC0: długości, sekcje formularza, tematy, liczba linii, złożoność oraz najczęstsze instrukcje.

Złożoność jest regułowa:

- CCMod **Low**: maks. 80 znaków, 1 temat i 1 klauzula; **Medium**: maks. 250 znaków, 2 tematy i 2 klauzule; przekroczenie warunków Medium daje **High**;
- CC0 **Low**: maks. 100 znaków, 1 temat, 1 sekcja i 2 linie; **Medium**: maks. 300 znaków, 2 tematy, 2 sekcje i 5 linii; przekroczenie daje **High**;
- pusty tekst otrzymuje kategorię **Empty**.

To miara długości/struktury tekstu, nie trudności klinicznej.

### 6.3. Arkusze eksportu

CCMod zawiera: `00_Summary`, średnie według kategorii/numeru, `04_Topic_counts`, `05_Focus_counts`, `06_Complexity`, `07_Top_Formulations`, `08_New_Plan_Requests`, audyt usuniętych fraz i `10_Row_Level`.

CC0 zawiera: `00_Overview`, `01_Sections`, `02_Topic_counts`, `03_Complexity`, `04_Top_Formulations` i `05_Row_Level`.

## 7. Kalibracja i własne kategorie

### 7.1. Własna kategoria Treatment Area Footprint

W sekcji **Custom Treatment Area Footprint categories** podaj nazwę oraz frazy rozpoznające (po jednej w linii), a następnie zapisz. Reguła działa w przyszłych standardowych analizach CC0 i CCMod. Nazwy i frazy powinny być jednoznaczne; zbyt ogólne słowo zwiększy liczbę fałszywych dopasowań.

### 7.2. Korekta po analizie

W **Post-analysis calibration** można zmieniać:

- CCMod: tematy, fokus, złożoność i flagę nowego planu;
- CC0: sekcje, tematy i złożoność.

Pobranie „calibrated result” uwzględnia bieżące edycje. Przycisk zapisania nauki utrwala reguły dla identycznego oczyszczonego tekstu oraz tej samej globalnej pozycji wiersza. Ta druga reguła działa niezależnie od nazwy pliku, dlatego przed zapisaniem trzeba szczególnie dokładnie zweryfikować korektę.

### 7.3. Trwałość, backup i wycofanie

- ustawienia fabryczne: `data/default_calibration_memory.json` (wersjonowane w Git);
- zmiany użytkowników: `data/calibration_memory.json` (tworzony podczas pracy);
- backup: zatrzymaj zapis lub usługę i skopiuj `data/calibration_memory.json` do chronionej lokalizacji;
- odtworzenie: zatrzymaj usługę, podmień plik na poprawną kopię, ustaw właściciela i uruchom usługę;
- reset zmian lokalnych: zarchiwizuj, a następnie usuń `data/calibration_memory.json`; po restarcie pozostaną reguły domyślne.

Plik zawiera fragmenty/klucze tekstowe wynikające z analiz, więc należy go traktować zgodnie z polityką ochrony danych i nie publikować bez przeglądu.

## 8. Moduł „Doctor Pattern Analysis”

### 8.1. Procedura

1. Wgraj dwa pliki `.xlsx` w dowolnej kolejności.
2. Sprawdź wykryte role i wskaż, który plik jest CC0.
3. Zweryfikuj wszystkie wymagane mapowania kolumn.
4. W **Text Cleaning Settings** pozostaw domyślne wykluczenia, wyłącz wybrane albo dodaj własne.
5. W **Advanced Settings** wybierz obsługę duplikatów:
   - `exclude_duplicate_clinical` — domyślne; usuwa kliniczne duplikaty dla zamówienia, iteracji i znormalizowanego komentarza;
   - `keep_all_rows` — zachowuje wszystko;
   - `exclude_exact_source_duplicates` — usuwa tylko identyczne rekordy źródłowe.
6. Opcjonalnie wyklucz preferencje CC0, ustaw wagi findings i ukryj identyfikatory w widoku.
7. Kliknij **Run Pattern Analysis**.
8. Zweryfikuj jakość danych, unmatched orders i dowody wierszowe przed interpretacją.

Ukrycie identyfikatorów działa w prezentacji ekranowej. Nie należy zakładać, że anonimizuje źródło lub każdy eksport — przed przekazaniem plików trzeba je sprawdzić zgodnie z polityką organizacji.

### 8.2. Znaczenie kluczowych flag

- `present_upfront` — kategoria z CCMod była w części CC0 dotyczącej konkretnego przypadku;
- `preference_only` — była tylko w ogólnej sekcji preferencji CC0;
- `missing_upfront` — wystąpiła w CCMod 1, ale nie w instrukcji CC0 dla przypadku;
- `late_emerging` — pierwszy raz wystąpiła w CCMod 2 lub później;
- `repeated_request` — ta sama kategoria występuje w co najmniej dwóch iteracjach;
- `consecutively_repeated` — występuje w kolejnych numerach CCMod;
- `persistent_unresolved_request` — powtarza się z takim samym wykrytym podpisem klinicznym;
- `changed_decision` — powtarza się, lecz zmieniły się wykryte wartości, szczegóły lub kierunek działania;
- `added_detail` — podpis się zmienił, ale reguła nie uznała tego za zmianę decyzji.

`missing_upfront` nie dowodzi błędu lekarza, a `SO without CCMod` nie oznacza akceptacji ani sukcesu. Obie wartości opisują wyłącznie zawartość przesłanych plików.

### 8.3. Zakładki wyniku

- **Executive Summary** — pokrycie danych, najważniejsze findings, jakość danych i najczęstsze kategorie;
- **Frequent Requests** — kategorie, dokładnie powtarzane teksty i klastry komentarzy;
- **CC0 vs CCMod** — luki, wykresy, Sankey i audyt `Missing upfront evidence`;
- **Iteration Patterns** — powtórzenia, późne prośby oraz zmienione decyzje;
- **Primary vs Secondary** — porównanie typów przypadków;
- **Order Explorer** — historia wskazanego zamówienia;
- **Detailed Data** — tabele szczegółowe i osobne CSV;
- **Export** — audyt boilerplate oraz pełny Excel.

Pełny raport Excel zawiera słownik zmiennych i arkusze m.in. pokrycia, frequent requests, exact comments, CC0 vs CCMod, dowodów missing upfront, powtórzeń, późnych próśb, zmian decyzji, sekwencji, danych oczyszczonych, niedopasowanych rekordów, audytu wykluczeń i użytych reguł.

### 8.4. Findings i wagi

Ranking problemów jest wskaźnikiem ważności, nie prawdopodobieństwem. Domyślne składniki to: pokrycie unikalnych zamówień 0,30; częstość komentarzy 0,20; powtórzenia 0,20; późne pojawienie 0,15; zmiana decyzji 0,10; średni maksymalny CCMod 0,05. Zmiana wag wpływa na priorytety, dlatego wartości użyte w cyklicznych raportach należy standaryzować i dokumentować.

## 9. Bezpieczeństwo i ochrona danych

Administrator powinien:

1. ograniczyć dostęp sieciowo i przez uwierzytelniający reverse proxy;
2. zakończyć TLS na proxy i nie wystawiać portu Streamlit publicznie;
3. uruchamiać usługę z konta bez uprawnień administracyjnych;
4. ograniczyć prawa do repozytorium i `data/`;
5. ustalić limity rozmiaru uploadu na proxy/Streamlit, czas sesji i retencję logów;
6. nie logować treści wgrywanych danych;
7. chronić backup pamięci kalibracji;
8. aktualizować zależności po testach regresyjnych;
9. traktować pobrane raporty jako potencjalnie zawierające dane identyfikujące;
10. restartować proces przy podejrzeniu pozostania danych w pamięci lub po incydencie.

Projekt nie ma bazy użytkowników, audytu logowań, mechanizmu uprawnień, szyfrowania plików ani automatycznej retencji. Te wymagania muszą być zrealizowane w warstwie infrastruktury i procedur organizacyjnych.

## 10. Utrzymanie i zmiany reguł

Przed wdrożeniem aktualizacji:

```bash
git status --short
git pull --ff-only
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```

Następnie zrestartuj usługę i wykonaj test akceptacyjny na zanonimizowanych plikach referencyjnych. Kopię `data/calibration_memory.json` wykonaj przed aktualizacją.

Zmiany standardowych słów kluczowych i progów wykonuje się w `analyzer/config.py`; reguły Doctor Pattern w `config/doctor_pattern_rules.py`. Po każdej zmianie należy dodać test, uruchomić pełny `pytest`, porównać raport referencyjny i zatwierdzić zmianę merytorycznie. Reguły obu modułów są osobne: własna kategoria zapisana w pamięci kalibracji standardowego modułu nie rozszerza automatycznie słownika Doctor Pattern.

## 11. Diagnostyka

### „Cannot detect the file format”

Sprawdź pierwszy arkusz i dokładne nagłówki z rozdziału 5. Wymuś tryb tylko wtedy, gdy struktura rzeczywiście mu odpowiada.

### „Required column … not detected” / brak możliwości uruchomienia Doctor Pattern

Wybierz kolumnę ręcznie. Sprawdź, czy zawiera tekst/liczby, a nie same puste wartości, oraz czy numer CCMod daje się sparsować.

### Niski match rate lub wiele unmatched orders

Porównaj typ, zera wiodące, spacje i znaczenie identyfikatorów w obu źródłach. Upewnij się, że zestawy obejmują zgodny okres.

### Za dużo „General or unclassified” albo brak tematów

Sprawdź język i słowniki. Dodaj precyzyjną kategorię w standardowej analizie albo, po przeglądzie kodu i testach, rozszerz reguły Doctor Pattern.

### Wyniki zmieniły się bez zmiany pliku

Sprawdź `data/calibration_memory.json`, własne wykluczenia, opcję preferencji, politykę duplikatów, mapowanie kolumn i wagi. Standardowa analiza automatycznie stosuje zapamiętane kalibracje.

### Brak zapisu kalibracji

Sprawdź bieżący katalog procesu, właściciela oraz prawa zapisu do `data/`. Przejrzyj log usługi. Nie uruchamiaj wielu niezależnych replik zapisujących do jednego pliku bez dodatkowej synchronizacji/współdzielonego mechanizmu trwałości.

### Wolne działanie lub brak pamięci

Przetwarzaj mniejsze partie, wyłącz pełny eksport wierszowy w standardowej analizie, ogranicz rozmiar uploadu i monitoruj RAM. Eksport Excel oraz ZIP są budowane w pamięci.

### Błąd odczytu Excel

Otwórz i zapisz plik ponownie jako `.xlsx`, usuń hasło/makra, sprawdź pierwszy arkusz oraz integralność pliku. W logach procesu będzie pełny wyjątek.

## 12. Checklista przekazania administratorowi

- [ ] Python i zależności zainstalowane w osobnym środowisku.
- [ ] `pytest -q` przechodzi.
- [ ] Usługa działa z dedykowanego konta i właściwego `WorkingDirectory`.
- [ ] Reverse proxy, TLS, uwierzytelnianie i reguły sieciowe są skonfigurowane.
- [ ] Prawa do `data/` umożliwiają zapis tylko właściwemu kontu.
- [ ] Backup i retencja `data/calibration_memory.json` są ustalone.
- [ ] Uzgodniono limit i klasyfikację danych wejściowych/raportów.
- [ ] Operator zna wymagane kolumny i procedurę weryfikacji mapowania.
- [ ] Istnieje zanonimizowany zestaw do testu akceptacyjnego.
- [ ] Ustalono właściciela merytorycznego słowników i wag.
- [ ] Ustalono procedurę aktualizacji, rollbacku i obsługi incydentów.

## 13. Ograniczenia, które trzeba komunikować odbiorcom

- dopasowanie jest oparte na słowach i wyrażeniach, więc możliwe są wyniki fałszywie dodatnie i ujemne;
- negacja i kontekst kliniczny nie zawsze są rozumiane;
- języki są obsługiwane tylko w zakresie wpisanych fraz;
- podobieństwo tekstów i `changed_decision` są heurystykami;
- jakość wniosków zależy od kompletności, spójności identyfikatorów i poprawnego mapowania;
- aplikacja analizuje dostarczony wycinek danych, nie pełną historię kliniczną;
- raport musi zostać zweryfikowany przez osobę znającą proces i znaczenie danych.

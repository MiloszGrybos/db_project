# Football Card Shop

**System sprzedaży kart piłkarskich (sklep online + panel admina)**

**Autor:** Miłosz Gryboś
**Wersja:** 1.0 (2026)  
**Technologie (propozycja):** Python 3.10+, SQLite 3.x

---

## Spis treści

1. [Architektura i filozofia projektu](#architektura-i-filozofia-projektu)
2. [Przykładowe scenariusze użycia](#przykladowe-scenariusze-uzycia)
3. [Wymagania funkcjonalne](#wymagania-funkcjonalne)
4. [Schemat bazy danych](#schemat-bazy-danych)
5. [Opis tabel](#opis-tabel)
6. [Relacje między tabelami](#relacje-miedzy-tabelami)
7. [Normalizacja bazy danych](#normalizacja-bazy-danych)
8. [Prawa dostępu](#prawa-dostepu)
9. [Triggery SQL](#triggery-sql)
10. [Transakcje i spójność](#transakcje-i-spojnosc)
11. [Bezpieczeństwo](#bezpieczenstwo)
12. [Instrukcja uruchomienia](#instrukcja-uruchomienia)
13. [Możliwości rozbudowy](#mozliwosci-rozbudowy)

---

## Architektura i filozofia projektu

Projekt realizuje prosty sklep internetowy sprzedający **karty piłkarskie**.

Kluczowe założenia:
- **Rozdzielenie ról:** administrator zarządza ofertą, klient kupuje.
- **Kontrola dostępu:** dodawanie do koszyka i zakup tylko po zalogowaniu.
- **Spójność danych:** zakup działa atomowo (transakcja), stan magazynu nie może spaść poniżej zera.
- **Bezpieczeństwo:** hasła hashowane, zapytania parametryzowane.

## Przykładowe scenariusze użycia

Poniżej opis typowych przepływów użytkownika.

### Rejestracja konta klienta
1. Klient podaje: `username`, `email`, `password`.
2. System tworzy konto z rolą `user`.

### Logowanie
1. Klient podaje `username` i `password`.
2. System weryfikuje hash hasła i tworzy sesję (lub ustawia `current_user`).

### Przeglądanie dostępnych kart (dla wszystkich)
- Lista kart z ceną i stanem (np. filtr: klub, sezon, rzadkość).

### Dodawanie do koszyka (tylko zalogowany klient)
1. Klient wybiera kartę i ilość.
2. System dodaje/aktualizuje pozycję w koszyku użytkownika.

### Zakup (checkout) (tylko zalogowany klient)
1. Klient potwierdza koszyk.
2. System:
   - tworzy zamówienie,
   - przenosi pozycje koszyka do pozycji zamówienia,
   - zmniejsza stany magazynowe,
   - czyści koszyk.

### Panel administratora
- Admin może dodawać karty (nazwa/opis/cena/stan) oraz edytować/usunąć ofertę.

---

## Wymagania funkcjonalne

### Wymagania dla Administratora

| ID | Wymaganie |
|----|-----------|
| A1 | Dodawanie nowej karty piłkarskiej (nazwa, opis, cena, stan magazynowy) |
| A2 | Edycja danych karty (np. zmiana ceny, opis, stan) |
| A3 | Usuwanie karty z oferty (soft-delete lub hard-delete) |
| A4 | Przeglądanie wszystkich zamówień i ich statusów |
| A5 | Dostęp do panelu administracyjnego (rola `admin`) |

### Wymagania dla Klienta

| ID | Wymaganie |
|----|-----------|
| K1 | Rejestracja konta |
| K2 | Logowanie do systemu z weryfikacją hasła |
| K3 | Przeglądanie dostępnych kart (bez logowania) |
| K4 | Dodawanie kart do koszyka (wymaga logowania) |
| K5 | Podgląd i edycja koszyka (zmiana ilości/usunięcie pozycji) |
| K6 | Złożenie zamówienia i zakup (wymaga logowania) |
| K7 | Podgląd historii swoich zamówień |

### Wymagania niefunkcjonalne

| ID | Wymaganie | Opis |
|----|-----------|------|
| N1 | Bezpieczeństwo haseł | Hashowanie SHA-256 |
| N2 | Ochrona przed SQL Injection | Parametryzowane zapytania SQLite |
| N3 | Transakcyjność zakupu | Checkout jako operacja atomowa |
| N4 | Audyt zmian cen | Trigger logujący zmianę ceny |
| N5 | Kontrola dostępu | Role `admin`/`user`, koszyk tylko dla zalogowanych |

---

## Schemat bazy danych

### Diagram ERD (propozycja)

```
┌──────────────────────┐
│        users         │
│──────────────────────│
│ id (PK)              │
│ username UNIQUE      │
│ email UNIQUE         │
│ password_hash        │
│ role CHECK           │ ('admin'/'user')
│ created_at           │
└─────────┬────────────┘
          │ 1:N
          ▼
┌──────────────────────┐
│        carts         │
│──────────────────────│
│ id (PK)              │
│ user_id (FK) UNIQUE  │  (1 aktywny koszyk na użytkownika)
│ created_at           │
│ updated_at           │
└─────────┬────────────┘
          │ 1:N
          ▼
┌──────────────────────┐        ┌──────────────────────┐
│      cart_items      │        │        cards         │
│──────────────────────│        │──────────────────────│
│ id (PK)              │        │ id (PK)              │
│ cart_id (FK)         │   N:1  │ name                 │
│ card_id (FK)─────────┼───────▶│ description          │
│ quantity             │        │ price_cents          │
│ unit_price_cents     │        │ stock_qty            │
│ added_at             │        │ is_active            │
└──────────────────────┘        │ created_at           │
                                │ updated_at           │
                                └─────────┬────────────┘
                                          │ 1:N
                                          ▼
                                ┌──────────────────────┐
                                │   price_audit_logs   │
                                │──────────────────────│
                                │ id (PK)              │
                                │ card_id (FK)         │
                                │ old_price_cents      │
                                │ new_price_cents      │
                                │ changed_at           │
                                │ changed_by_user_id   │ (FK -> users.id)
                                └──────────────────────┘

┌──────────────────────┐
│        orders        │
│──────────────────────│
│ id (PK)              │
│ user_id (FK)         │
│ status               │ ('created','paid','cancelled')
│ total_cents          │
│ created_at           │
└─────────┬────────────┘
          │ 1:N
          ▼
┌──────────────────────┐
│     order_items      │
│──────────────────────│
│ id (PK)              │
│ order_id (FK)        │
│ card_id (FK)         │
│ quantity             │
│ unit_price_cents     │ (cena w momencie zakupu)
│ line_total_cents     │
└──────────────────────┘
```

---

## Opis tabel

Poniżej opis głównych tabel.

### 1) `users` (użytkownicy)
| Kolumna | Typ | Opis |
|---------|-----|------|
| id | INTEGER (PK) | Klucz główny |
| username | TEXT UNIQUE | Login |
| email | TEXT UNIQUE | E-mail |
| password_hash | TEXT | Hash hasła |
| role | TEXT CHECK | `admin` lub `user` |
| created_at | TEXT/TIMESTAMP | Data utworzenia |

### 2) `cards` (produkty)
| Kolumna | Typ | Opis |
|---------|-----|------|
| id | INTEGER (PK) | Klucz główny |
| name | TEXT | Nazwa karty |
| description | TEXT | Opis |
| price_cents | INTEGER | Cena w groszach (unika float) |
| stock_qty | INTEGER | Stan magazynowy |
| is_active | INTEGER/BOOLEAN | Czy karta jest w sprzedaży |
| created_at | TEXT/TIMESTAMP | Data dodania |
| updated_at | TEXT/TIMESTAMP | Data aktualizacji |

### 3) `carts` (koszyki)
| Kolumna | Typ | Opis |
|---------|-----|------|
| id | INTEGER (PK) | Klucz główny |
| user_id | INTEGER (FK) UNIQUE | Właściciel koszyka |
| created_at | TEXT/TIMESTAMP | Data utworzenia |
| updated_at | TEXT/TIMESTAMP | Data modyfikacji |

### 4) `cart_items` (pozycje koszyka)
| Kolumna | Typ | Opis |
|---------|-----|------|
| id | INTEGER (PK) | Klucz główny |
| cart_id | INTEGER (FK) | Koszyk |
| card_id | INTEGER (FK) | Karta |
| quantity | INTEGER | Ilość |
| unit_price_cents | INTEGER | Cena w momencie dodania do koszyka (opcjonalnie) |
| added_at | TEXT/TIMESTAMP | Data dodania |

### 5) `orders` (zamówienia)
| Kolumna | Typ | Opis |
|---------|-----|------|
| id | INTEGER (PK) | Klucz główny |
| user_id | INTEGER (FK) | Kupujący |
| status | TEXT | Status zamówienia |
| total_cents | INTEGER | Suma |
| created_at | TEXT/TIMESTAMP | Data utworzenia |

### 6) `order_items` (pozycje zamówienia)
| Kolumna | Typ | Opis |
|---------|-----|------|
| id | INTEGER (PK) | Klucz główny |
| order_id | INTEGER (FK) | Zamówienie |
| card_id | INTEGER (FK) | Karta |
| quantity | INTEGER | Ilość |
| unit_price_cents | INTEGER | Cena w momencie zakupu |
| line_total_cents | INTEGER | quantity * unit_price_cents |

### 7) `price_audit_logs` (audyt zmian cen)
| Kolumna | Typ | Opis |
|---------|-----|------|
| id | INTEGER (PK) | Klucz główny |
| card_id | INTEGER (FK) | Karta |
| old_price_cents | INTEGER | Poprzednia cena |
| new_price_cents | INTEGER | Nowa cena |
| changed_at | TEXT/TIMESTAMP | Kiedy zmieniono |
| changed_by_user_id | INTEGER (FK) | Kto zmienił (admin) |

---

## Relacje między tabelami

1. `users → carts` (1:1)
   - użytkownik ma dokładnie jeden aktywny koszyk
2. `carts → cart_items` (1:N)
   - koszyk ma wiele pozycji
3. `cards → cart_items` (1:N)
   - karta może wystąpić w wielu koszykach
4. `users → orders` (1:N)
   - użytkownik może mieć wiele zamówień
5. `orders → order_items` (1:N)
   - zamówienie ma wiele pozycji
6. `cards → order_items` (1:N)
   - karta może wystąpić w wielu zamówieniach
7. `cards → price_audit_logs` (1:N)
   - historia zmian cen dla danej karty

---

## Normalizacja bazy danych

Baza danych spełnia założenia **3NF**:
- Dane użytkownika trzymane są w `users`, bez duplikacji w koszyku/zamówieniach.
- Produkty są w `cards`, a pozycje koszyka/zamówienia są relacjami (nie listami w jednym polu).
- `order_items` przechowuje cenę z momentu zakupu (denormalizacja kontrolowana), aby historia zamówień była niezmienna nawet po zmianie ceny produktu.

---

## Prawa dostępu

### Role
- `admin` – zarządza produktami i widzi wszystkie zamówienia.
- `user` – przegląda ofertę, zarządza własnym koszykiem i zamówieniami.

### Tabela uprawnień

| Komponent | Administrator | Użytkownik |
|----------|----------------|-----------|
| Rejestracja / logowanie | ✓ | ✓ |
| `cards` | CRUD | Read |
| `carts`, `cart_items` | Read/Support | CRUD tylko własne |
| `orders`, `order_items` | Read wszystkie | Read tylko własne + Create |
| `price_audit_logs` | Read | Brak dostępu |

Wymuszenie wymagania: **dodawanie do koszyka i zakup wymaga logowania**.

---

## Triggery SQL

### Trigger 1: logowanie zmian ceny karty
Cel: każda zmiana `price_cents` dopisuje wpis do `price_audit_logs`.

```sql
CREATE TRIGGER IF NOT EXISTS log_card_price_change
AFTER UPDATE OF price_cents ON cards
WHEN OLD.price_cents != NEW.price_cents
BEGIN
  INSERT INTO price_audit_logs (card_id, old_price_cents, new_price_cents, changed_at, changed_by_user_id)
  VALUES (OLD.id, OLD.price_cents, NEW.price_cents, CURRENT_TIMESTAMP, NULL);
END;
```

### Trigger 2: ochrona przed ujemnym stanem
Cel: nie pozwolić zejść `stock_qty` poniżej 0.

```sql
CREATE TRIGGER IF NOT EXISTS prevent_negative_stock
BEFORE UPDATE OF stock_qty ON cards
WHEN NEW.stock_qty < 0
BEGIN
  SELECT RAISE(ABORT, 'Stan nie może być ujemny');
END;
```

---

## Transakcje i spójność

Najważniejsza transakcja w systemie to **checkout** (zakup).

### Cel
Zapewnić, że zamówienie powstaje tylko wtedy, gdy:
- wszystkie pozycje z koszyka da się kupić (stan magazynowy wystarczający),
- stany magazynowe zostaną zaktualizowane,
- koszyk zostanie wyczyszczony.

### Przykładowy pseudokod (Python + sqlite3)

```python
def checkout(user_id):
    conn = get_db_connection()
    try:
        c = conn.cursor()
        conn.execute('BEGIN')

        c.execute('SELECT id FROM carts WHERE user_id = ?', (user_id,))
        cart_id = c.fetchone()[0]

        c.execute('SELECT card_id, quantity FROM cart_items WHERE cart_id = ?', (cart_id,))
        items = c.fetchall()
        if not items:
            raise ValueError('Koszyk jest pusty')
        for card_id, qty in items:
            c.execute('SELECT stock_qty, price_cents FROM cards WHERE id = ? AND is_active = 1', (card_id,))
            row = c.fetchone()
            if row is None:
                raise ValueError('Produkt niedostępny')
            stock_qty, price = row
            if stock_qty < qty:
                raise ValueError('Brak wystarczającego stanu magazynowego')

        c.execute('INSERT INTO orders (user_id, status, total_cents, created_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)',
                  (user_id, 'created', 0))
        order_id = c.lastrowid

        total = 0
        for card_id, qty in items:
            c.execute('SELECT price_cents FROM cards WHERE id = ?', (card_id,))
            unit_price = c.fetchone()[0]
            line_total = unit_price * qty
            total += line_total

            c.execute('INSERT INTO order_items (order_id, card_id, quantity, unit_price_cents, line_total_cents)
                       VALUES (?, ?, ?, ?, ?)',
                      (order_id, card_id, qty, unit_price, line_total))

            c.execute('UPDATE cards SET stock_qty = stock_qty - ? WHERE id = ?', (qty, card_id))

        c.execute('UPDATE orders SET total_cents = ? WHERE id = ?', (total, order_id))
        c.execute('DELETE FROM cart_items WHERE cart_id = ?', (cart_id,))

        conn.commit()
        return order_id

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
```

---

## Bezpieczeństwo

### Hashowanie haseł
Minimalnie: **SHA-256**.

```python
import hashlib

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def verify_password(stored_hash: str, password: str) -> bool:
    return stored_hash == hash_password(password)
```

### Ochrona przed SQL Injection
- Zawsze używać zapytań parametryzowanych:

```python
c.execute('SELECT id FROM users WHERE username = ? AND email = ?', (username, email))
```

### Kontrola dostępu
- Po zalogowaniu system trzyma `current_user`/sesję.
- Dodanie do koszyka i zakup: tylko gdy `current_user` istnieje.
- Panel admina: tylko gdy `role == 'admin'`.

---

## Instrukcja uruchomienia

### Wymagania
- Python 3.10+
- SQLite 3.x

### Instalacja (wariant minimalny)

```bash
python3 setup_db.py
python3 main.py
```

### Struktura projektu

```
lab5/
├── main.py           # CLI
├── database.py       # operacje na bazie danych
├── setup_db.py       # tworzenie tabel + dane testowe
├── shop.db           # baza SQLite (tworzona automatycznie)
└── README.md         # ta dokumentacja
```

### Konta testowe (opcjonalnie)

| Login | Hasło | Rola |
|-------|-------|------|
| admin | adminpass | Administrator |
| klient | user123 | Użytkownik |

---

## Możliwości rozbudowy

- Płatności (symulacja / integracja z bramką)
- Statusy zamówień: `paid`, `sent`, `delivered`, `cancelled`
- Adresy wysyłki i dane do faktury
- Promocje/kupony rabatowe
- Upload zdjęć kart i galerie
- Full-text search + filtry (klub, liga, sezon, rzadkość)
- REST API + frontend (React/Vue)

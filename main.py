from __future__ import annotations

import getpass
import sys

import database as db


def fmt_money(cents: int) -> str:
    return f"{cents / 100:.2f} zł"


def prompt_password(label: str) -> str:
    if sys.stdin is not None and sys.stdin.isatty():
        try:
            return getpass.getpass(label)
        except (EOFError, OSError):
            pass
    return input(label)


def prompt_int(label: str) -> int:
    while True:
        raw = input(label).strip()
        try:
            return int(raw)
        except ValueError:
            print("Podaj liczbę całkowitą")


def show_cards() -> None:
    cards = db.list_active_cards()
    if not cards:
        print("Brak kart w ofercie")
        return

    print("\nDostępne karty:")
    print("ID | Nazwa | Cena | Stan")
    for c in cards:
        print(f"{c.id} | {c.name} | {fmt_money(c.price_cents)} | {c.stock_qty}")


def register_flow() -> None:
    print("\n=== Rejestracja ===")
    username = input("Login: ").strip()
    password = prompt_password("Hasło: ")
    password2 = prompt_password("Powtórz hasło: ")
    if password != password2:
        print("Hasła nie są identyczne")
        return

    try:
        user_id = db.create_user(username, password, role="user")
        print(f"OK: utworzono konto (id={user_id}). Możesz się zalogować.")
    except Exception as e:
        print(f"Błąd rejestracji: {e}")


def login_flow() -> db.User | None:
    print("\n=== Logowanie ===")
    username = input("Login: ").strip()
    password = prompt_password("Hasło: ")
    user = db.authenticate(username, password)
    if not user:
        print("Błędny login lub hasło")
        return None
    print(f"Zalogowano jako {user.username} ({user.role})")
    return user


def user_menu(user: db.User) -> None:
    while True:
        print("\n=== MENU UŻYTKOWNIKA ===")
        print("1. Przeglądaj karty")
        print("2. Dodaj kartę do koszyka")
        print("3. Pokaż koszyk")
        print("4. Kup (checkout)")
        print("5. Moje zamówienia")
        print("0. Wyloguj")
        choice = input("> ").strip()

        if choice == "1":
            show_cards()

        elif choice == "2":
            show_cards()
            card_id = prompt_int("ID karty: ")
            qty = prompt_int("Ilość: ")
            try:
                db.add_to_cart(user.id, card_id, qty)
                print("OK: dodano do koszyka")
            except Exception as e:
                print(f"Błąd: {e}")

        elif choice == "3":
            items = db.get_cart_items(user.id)
            if not items:
                print("Koszyk jest pusty")
                continue
            total = 0
            print("\nKoszyk:")
            print("ID | Nazwa | Cena | Ilość | Suma")
            for it in items:
                total += int(it["line_total"])
                print(
                    f"{it['card_id']} | {it['name']} | {fmt_money(int(it['price_cents']))} | {it['quantity']} | {fmt_money(int(it['line_total']))}"
                )
            print(f"Razem: {fmt_money(total)}")

        elif choice == "4":
            try:
                order_id = db.checkout(user.id)
                print(f"OK: zakup zakończony. ID zamówienia: {order_id}")
            except Exception as e:
                print(f"Błąd checkout: {e}")

        elif choice == "5":
            orders = db.list_my_orders(user.id)
            if not orders:
                print("Brak zamówień")
                continue
            print("\nMoje zamówienia:")
            print("ID | Status | Suma | Data")
            for o in orders:
                print(
                    f"{o['id']} | {o['status']} | {fmt_money(int(o['total_cents']))} | {o['created_at']}"
                )

        elif choice == "0":
            return
        else:
            print("Nieznana opcja")


def admin_menu(user: db.User) -> None:
    while True:
        print("\n=== PANEL ADMINA ===")
        print("1. Lista kart")
        print("2. Dodaj kartę")
        print("3. Zmień cenę karty")
        print("4. Zmień stan magazynowy")
        print("5. Aktywuj/dezaktywuj kartę")
        print("6. Lista zamówień")
        print("0. Wyloguj")
        choice = input("> ").strip()

        if choice == "1":
            show_cards()

        elif choice == "2":
            print("\nDodawanie karty")
            name = input("Nazwa: ").strip()
            description = input("Opis: ").strip()
            price_cents = prompt_int("Cena (w groszach, np. 1999): ")
            stock_qty = prompt_int("Stan: ")
            try:
                card_id = db.admin_add_card(name, description, price_cents, stock_qty)
                print(f"OK: dodano kartę (id={card_id})")
            except Exception as e:
                print(f"Błąd: {e}")

        elif choice == "3":
            show_cards()
            card_id = prompt_int("ID karty: ")
            new_price = prompt_int("Nowa cena (grosze): ")
            try:
                db.admin_update_card_price(card_id, new_price)
                print("OK: zaktualizowano cenę")
            except Exception as e:
                print(f"Błąd: {e}")

        elif choice == "4":
            show_cards()
            card_id = prompt_int("ID karty: ")
            new_stock = prompt_int("Nowy stan: ")
            try:
                db.admin_update_card_stock(card_id, new_stock)
                print("OK: zaktualizowano stan")
            except Exception as e:
                print(f"Błąd: {e}")

        elif choice == "5":
            show_cards()
            card_id = prompt_int("ID karty: ")
            raw = input("Aktywna? (t/n): ").strip().lower()
            is_active = raw == "t"
            try:
                db.admin_set_card_active(card_id, is_active)
                print("OK: zaktualizowano aktywność")
            except Exception as e:
                print(f"Błąd: {e}")

        elif choice == "6":
            orders = db.admin_list_orders()
            if not orders:
                print("Brak zamówień")
                continue
            print("\nZamówienia:")
            print("ID | Użytkownik | Status | Suma | Data")
            for o in orders:
                print(
                    f"{o['id']} | {o['username']} | {o['status']} | {fmt_money(int(o['total_cents']))} | {o['created_at']}"
                )

        elif choice == "0":
            return
        else:
            print("Nieznana opcja")


def main() -> None:
    try:
        db.ensure_db_exists()
    except FileNotFoundError as e:
        print(e)
        print("Uruchom: python setup_db.py")
        return

    # wstaw domyślne dane (admin + kilka kart), jeśli trzeba
    db.admin_seed_defaults()

    current_user: db.User | None = None

    while True:
        print("\n============================")
        print("   FOOTBALL CARD SHOP CLI")
        print("============================")
        print("1. Rejestracja")
        print("2. Logowanie")
        print("3. Przeglądaj karty")
        print("0. Wyjście")
        choice = input("> ").strip()

        if choice == "1":
            register_flow()

        elif choice == "2":
            current_user = login_flow()
            if not current_user:
                continue
            if current_user.role == "admin":
                admin_menu(current_user)
            else:
                user_menu(current_user)
            current_user = None

        elif choice == "3":
            show_cards()
            print("\nAby dodać do koszyka/kupić, musisz się zalogować.")

        elif choice == "0":
            print("Do zobaczenia!")
            return

        else:
            print("Nieznana opcja")


if __name__ == "__main__":
    main()

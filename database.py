import hashlib
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

DB_PATH = Path(__file__).with_name("shop.db")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class User:
    id: int
    username: str
    role: str


@dataclass(frozen=True)
class Card:
    id: int
    name: str
    price_cents: int
    stock_qty: int
    is_active: int


def ensure_db_exists() -> None:
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Brak bazy danych {DB_PATH}. Uruchom najpierw: python setup_db.py"
        )


def create_user(username: str, password: str, role: str = "user") -> int:
    if not username.strip():
        raise ValueError("Username nie może być pusty")
    if len(password) < 3:
        raise ValueError("Hasło za krótkie")

    pw_hash = hash_password(password)

    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (username.strip(), pw_hash, role),
        )
        user_id = int(cur.lastrowid)
        cur.execute("INSERT INTO carts (user_id) VALUES (?)", (user_id,))
        conn.commit()
        return user_id
    finally:
        conn.close()


def authenticate(username: str, password: str) -> Optional[User]:
    pw_hash = hash_password(password)
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, username, role FROM users WHERE username = ? AND password_hash = ?",
            (username.strip(), pw_hash),
        )
        row = cur.fetchone()
        if not row:
            return None
        return User(id=int(row["id"]), username=row["username"], role=row["role"])
    finally:
        conn.close()


def list_active_cards() -> list[Card]:
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, name, price_cents, stock_qty, is_active FROM cards WHERE is_active = 1 ORDER BY id"
        )
        rows = cur.fetchall()
        return [
            Card(
                id=int(r["id"]),
                name=r["name"],
                price_cents=int(r["price_cents"]),
                stock_qty=int(r["stock_qty"]),
                is_active=int(r["is_active"]),
            )
            for r in rows
        ]
    finally:
        conn.close()


def admin_add_card(name: str, description: str, price_cents: int, stock_qty: int) -> int:
    if not name.strip():
        raise ValueError("Nazwa karty nie może być pusta")
    if price_cents < 0:
        raise ValueError("Cena nie może być ujemna")
    if stock_qty < 0:
        raise ValueError("Stan nie może być ujemny")

    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO cards (name, description, price_cents, stock_qty, is_active) VALUES (?, ?, ?, ?, 1)",
            (name.strip(), description.strip(), price_cents, stock_qty),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def admin_update_card_price(card_id: int, new_price_cents: int) -> None:
    if new_price_cents < 0:
        raise ValueError("Cena nie może być ujemna")

    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE cards SET price_cents = ? WHERE id = ?", (new_price_cents, card_id))
        if cur.rowcount == 0:
            raise ValueError("Nie znaleziono karty")
        conn.commit()
    finally:
        conn.close()


def admin_update_card_stock(card_id: int, new_stock_qty: int) -> None:
    #if new_stock_qty < 0:
        #raise ValueError("Stan nie może być ujemny")

    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE cards SET stock_qty = ? WHERE id = ?", (new_stock_qty, card_id))
        if cur.rowcount == 0:
            raise ValueError("Nie znaleziono karty")
        conn.commit()
    finally:
        conn.close()


def admin_set_card_active(card_id: int, is_active: bool) -> None:
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE cards SET is_active = ? WHERE id = ?", (1 if is_active else 0, card_id))
        if cur.rowcount == 0:
            raise ValueError("Nie znaleziono karty")
        conn.commit()
    finally:
        conn.close()


def get_cart_id(user_id: int) -> int:
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM carts WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        if not row:
            cur.execute("INSERT INTO carts (user_id) VALUES (?)", (user_id,))
            conn.commit()
            return int(cur.lastrowid)
        return int(row["id"])
    finally:
        conn.close()


def add_to_cart(user_id: int, card_id: int, quantity: int) -> None:
    if quantity <= 0:
        raise ValueError("Ilość musi być > 0")

    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM carts WHERE user_id = ?", (user_id,))
        cart_row = cur.fetchone()
        if not cart_row:
            cur.execute("INSERT INTO carts (user_id) VALUES (?)", (user_id,))
            cart_id = int(cur.lastrowid)
        else:
            cart_id = int(cart_row["id"])

        cur.execute(
            "SELECT stock_qty, is_active FROM cards WHERE id = ?",
            (card_id,),
        )
        card = cur.fetchone()
        if not card or int(card["is_active"]) != 1:
            raise ValueError("Karta niedostępna")

        cur.execute(
            "INSERT INTO cart_items (cart_id, card_id, quantity) VALUES (?, ?, ?) "
            "ON CONFLICT(cart_id, card_id) DO UPDATE SET quantity = quantity + excluded.quantity",
            (cart_id, card_id, quantity),
        )
        cur.execute("UPDATE carts SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (cart_id,))
        conn.commit()
    finally:
        conn.close()


def get_cart_items(user_id: int) -> list[sqlite3.Row]:
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT ci.card_id, c.name, c.price_cents, ci.quantity, (c.price_cents * ci.quantity) AS line_total "
            "FROM carts ca "
            "JOIN cart_items ci ON ci.cart_id = ca.id "
            "JOIN cards c ON c.id = ci.card_id "
            "WHERE ca.user_id = ? "
            "ORDER BY ci.id",
            (user_id,),
        )
        return cur.fetchall()
    finally:
        conn.close()


def clear_cart(user_id: int) -> None:
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM carts WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        if not row:
            return
        cart_id = int(row["id"])
        cur.execute("DELETE FROM cart_items WHERE cart_id = ?", (cart_id,))
        cur.execute("UPDATE carts SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (cart_id,))
        conn.commit()
    finally:
        conn.close()


def checkout(user_id: int) -> int:
    conn = connect()
    try:
        cur = conn.cursor()
        conn.execute("BEGIN")

        cur.execute("SELECT id FROM carts WHERE user_id = ?", (user_id,))
        cart_row = cur.fetchone()
        if not cart_row:
            raise ValueError("Brak koszyka")
        cart_id = int(cart_row["id"])

        cur.execute("SELECT card_id, quantity FROM cart_items WHERE cart_id = ?", (cart_id,))
        items = cur.fetchall()
        if not items:
            raise ValueError("Koszyk jest pusty")

        for it in items:
            card_id = int(it["card_id"])
            qty = int(it["quantity"])
            cur.execute(
                "SELECT stock_qty, is_active FROM cards WHERE id = ?",
                (card_id,),
            )
            row = cur.fetchone()
            if not row or int(row["is_active"]) != 1:
                raise ValueError("Jedna z kart jest niedostępna")
            if int(row["stock_qty"]) < qty:
                raise ValueError("Brak stanu magazynowego dla jednej z kart")

        cur.execute(
            "INSERT INTO orders (user_id, status, total_cents) VALUES (?, 'paid', 0)",
            (user_id,),
        )
        order_id = int(cur.lastrowid)

        total = 0
        for it in items:
            card_id = int(it["card_id"])
            qty = int(it["quantity"])

            cur.execute("SELECT price_cents FROM cards WHERE id = ?", (card_id,))
            unit_price = int(cur.fetchone()["price_cents"])
            line_total = unit_price * qty
            total += line_total

            cur.execute(
                "INSERT INTO order_items (order_id, card_id, quantity, unit_price_cents, line_total_cents) "
                "VALUES (?, ?, ?, ?, ?)",
                (order_id, card_id, qty, unit_price, line_total),
            )
            cur.execute(
                "UPDATE cards SET stock_qty = stock_qty - ? WHERE id = ?",
                (qty, card_id),
            )

        cur.execute("UPDATE orders SET total_cents = ? WHERE id = ?", (total, order_id))
        cur.execute("DELETE FROM cart_items WHERE cart_id = ?", (cart_id,))
        cur.execute("UPDATE carts SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (cart_id,))

        conn.commit()
        return order_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def list_my_orders(user_id: int) -> list[sqlite3.Row]:
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, status, total_cents, created_at FROM orders WHERE user_id = ? ORDER BY id DESC",
            (user_id,),
        )
        return cur.fetchall()
    finally:
        conn.close()


def admin_list_orders() -> list[sqlite3.Row]:
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT o.id, u.username, o.status, o.total_cents, o.created_at "
            "FROM orders o JOIN users u ON u.id = o.user_id "
            "ORDER BY o.id DESC"
        )
        return cur.fetchall()
    finally:
        conn.close()


def admin_seed_defaults() -> None:
    conn = connect()
    try:
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) AS cnt FROM users")
        if int(cur.fetchone()["cnt"]) == 0:
            cur.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, 'admin')",
                ("admin", hash_password("adminpass")),
            )
            admin_id = int(cur.lastrowid)
            cur.execute("INSERT INTO carts (user_id) VALUES (?)", (admin_id,))

        cur.execute("SELECT COUNT(*) AS cnt FROM cards")
        if int(cur.fetchone()["cnt"]) == 0:
            cur.execute(
                "INSERT INTO cards (name, description, price_cents, stock_qty, is_active) VALUES (?, ?, ?, ?, 1)",
                ("Karta: Lionel Messi", "Sezon 2022/23", 1999, 5),
            )
            cur.execute(
                "INSERT INTO cards (name, description, price_cents, stock_qty, is_active) VALUES (?, ?, ?, ?, 1)",
                ("Karta: Robert Lewandowski", "Sezon 2023/24", 1499, 10),
            )
            cur.execute(
                "INSERT INTO cards (name, description, price_cents, stock_qty, is_active) VALUES (?, ?, ?, ?, 1)",
                ("Karta: Kylian Mbappé", "Edycja limitowana", 2999, 3),
            )

        conn.commit()
    finally:
        conn.close()

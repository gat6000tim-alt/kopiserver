import sqlite3
import os
import secrets
import hashlib
import time
from typing import Optional, Dict, Any, List

DB_PATH = os.path.join(os.path.dirname(__file__), "bank.db")
SUPER_ADMIN_EMAIL = "alexpochmak@gmail.com"

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def generate_phone_number() -> str:
    part1 = secrets.randbelow(900) + 100
    part2 = secrets.randbelow(90) + 10
    part3 = secrets.randbelow(90) + 10
    return f"+7 (999) {part1}-{part2}-{part3}"

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        card_number TEXT UNIQUE NOT NULL,
        account_number TEXT UNIQUE NOT NULL,
        phone_number TEXT,
        balance REAL DEFAULT 0.0,
        full_name TEXT DEFAULT 'Клиент Копи Банка',
        is_frozen INTEGER DEFAULT 0,
        is_admin INTEGER DEFAULT 0,
        avatar_url TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_id INTEGER,
        recipient_id INTEGER,
        sender_name TEXT,
        recipient_name TEXT,
        amount REAL NOT NULL,
        type TEXT NOT NULL, -- 'transfer', 'nfc', 'qr', 'admin_credit', 'admin_debit'
        status TEXT DEFAULT 'completed',
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (sender_id) REFERENCES users (id),
        FOREIGN KEY (recipient_id) REFERENCES users (id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS nfc_tokens (
        token TEXT PRIMARY KEY,
        sender_id INTEGER NOT NULL,
        max_amount REAL DEFAULT 50000.0,
        status TEXT DEFAULT 'active',
        transaction_id INTEGER,
        amount REAL,
        recipient_name TEXT,
        created_at INTEGER NOT NULL,
        expires_at INTEGER NOT NULL,
        FOREIGN KEY (sender_id) REFERENCES users (id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS split_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        creator_id INTEGER NOT NULL,
        payer_id INTEGER NOT NULL,
        creator_name TEXT NOT NULL,
        payer_name TEXT NOT NULL,
        amount REAL NOT NULL,
        total_amount REAL NOT NULL,
        description TEXT,
        status TEXT DEFAULT 'pending', -- 'pending', 'paid', 'declined'
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (creator_id) REFERENCES users (id),
        FOREIGN KEY (payer_id) REFERENCES users (id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS business_accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        company_name TEXT NOT NULL,
        business_type TEXT NOT NULL, -- 'ИП' or 'ООО'
        inn TEXT NOT NULL,
        account_number TEXT NOT NULL,
        tax_rate REAL DEFAULT 13.0,
        balance REAL DEFAULT 0.0,
        status TEXT DEFAULT 'pending', -- 'pending', 'approved', 'rejected', 'frozen'
        admin_comment TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS credits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        amount REAL NOT NULL,
        remaining_amount REAL NOT NULL,
        monthly_payment REAL NOT NULL,
        interest_rate REAL NOT NULL,
        term_months INTEGER NOT NULL,
        status TEXT DEFAULT 'pending', -- 'pending', 'active', 'frozen', 'paid', 'rejected'
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS deposits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        amount REAL NOT NULL,
        interest_rate REAL NOT NULL,
        term_months INTEGER NOT NULL,
        earned_amount REAL DEFAULT 0.0,
        status TEXT DEFAULT 'pending', -- 'pending', 'active', 'frozen', 'closed', 'rejected'
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    """)
    
    cursor.execute("PRAGMA table_info(users)")
    user_columns = [row[1] for row in cursor.fetchall()]
    
    if "phone_number" not in user_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN phone_number TEXT")
    if "is_frozen" not in user_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN is_frozen INTEGER DEFAULT 0")
    if "is_admin" not in user_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
    if "avatar_url" not in user_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN avatar_url TEXT")
    if "pin_code" not in user_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN pin_code TEXT")
    if "is_pin_enabled" not in user_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN is_pin_enabled INTEGER DEFAULT 0")

    if "last_finance_at" not in user_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN last_finance_at REAL")
    if "credit_score" not in user_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN credit_score INTEGER DEFAULT 650")
    if "history_cleared_at" not in user_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN history_cleared_at TIMESTAMP")

    cursor.execute("PRAGMA table_info(credits)")
    credit_columns = [row[1] for row in cursor.fetchall()]
    if "overdue_since" not in credit_columns:
        cursor.execute("ALTER TABLE credits ADD COLUMN overdue_since REAL")
    if "payment_type" not in credit_columns:
        cursor.execute("ALTER TABLE credits ADD COLUMN payment_type TEXT DEFAULT 'annuity'")
    if "business_id" not in credit_columns:
        cursor.execute("ALTER TABLE credits ADD COLUMN business_id INTEGER")

    cursor.execute("PRAGMA table_info(deposits)")
    deposit_columns = [row[1] for row in cursor.fetchall()]
    if "last_accrual_at" not in deposit_columns:
        cursor.execute("ALTER TABLE deposits ADD COLUMN last_accrual_at REAL")
        
    cursor.execute("PRAGMA table_info(transactions)")
    tx_columns = [row[1] for row in cursor.fetchall()]
    
    if "sender_name" not in tx_columns:
        cursor.execute("ALTER TABLE transactions ADD COLUMN sender_name TEXT")
    if "recipient_name" not in tx_columns:
        cursor.execute("ALTER TABLE transactions ADD COLUMN recipient_name TEXT")
    if "tax_amount" not in tx_columns:
        cursor.execute("ALTER TABLE transactions ADD COLUMN tax_amount REAL DEFAULT 0.0")
    if "commission_amount" not in tx_columns:
        cursor.execute("ALTER TABLE transactions ADD COLUMN commission_amount REAL DEFAULT 0.0")
    if "is_tax_payment" not in tx_columns:
        cursor.execute("ALTER TABLE transactions ADD COLUMN is_tax_payment INTEGER DEFAULT 0")
    if "business_id" not in tx_columns:
        cursor.execute("ALTER TABLE transactions ADD COLUMN business_id INTEGER")
        
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS credit_history_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        event_type TEXT NOT NULL,
        score_delta INTEGER NOT NULL,
        new_score INTEGER NOT NULL,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    """)
        
    cursor.execute("PRAGMA table_info(nfc_tokens)")
    nfc_columns = [row[1] for row in cursor.fetchall()]
    if "short_code" not in nfc_columns:
        cursor.execute("ALTER TABLE nfc_tokens ADD COLUMN short_code TEXT")
    if "business_id" not in nfc_columns:
        cursor.execute("ALTER TABLE nfc_tokens ADD COLUMN business_id INTEGER")
        
    cursor.execute("""
    UPDATE users SET is_admin = 1 WHERE lower(trim(email)) = ?
    """, (SUPER_ADMIN_EMAIL.lower(),))
    
    cursor.execute("SELECT id, phone_number FROM users WHERE phone_number IS NULL OR phone_number = ''")
    missing_phones = cursor.fetchall()
    for row in missing_phones:
        new_phone = generate_phone_number()
        cursor.execute("UPDATE users SET phone_number = ? WHERE id = ?", (new_phone, row["id"]))
    
    conn.commit()
    conn.close()

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    ).hex()
    return f"{salt}${key}"

def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, key = stored_hash.split('$')
        new_key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000
        ).hex()
        return secrets.compare_digest(key, new_key)
    except Exception:
        return False

def generate_sber_card_number() -> str:
    random_part = "".join([str(secrets.randbelow(10)) for _ in range(12)])
    raw = f"2202{random_part}"
    return f"{raw[0:4]} {raw[4:8]} {raw[8:12]} {raw[12:16]}"

def generate_account_number() -> str:
    suffix = "".join([str(secrets.randbelow(10)) for _ in range(12)])
    return f"40817810{suffix}"

def create_user(email: str, password: str, full_name: Optional[str] = None, phone_number: Optional[str] = None) -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    
    pwd_hash = hash_password(password)
    card_number = generate_sber_card_number()
    account_number = generate_account_number()
    phone = phone_number.strip() if phone_number and phone_number.strip() else generate_phone_number()
    name = full_name.strip() if full_name and full_name.strip() else email.split("@")[0].capitalize()
    is_admin = 1 if email.lower().strip() == SUPER_ADMIN_EMAIL.lower() else 0
    
    cursor.execute("""
    INSERT INTO users (email, password_hash, card_number, account_number, phone_number, balance, full_name, is_frozen, is_admin)
    VALUES (?, ?, ?, ?, ?, 0.0, ?, 0, ?)
    """, (email.lower().strip(), pwd_hash, card_number, account_number, phone, name, is_admin))
    
    user_id = cursor.lastrowid
    conn.commit()
    
    cursor.execute("""
    SELECT id, email, card_number, account_number, phone_number, balance, full_name, is_frozen, is_admin, avatar_url, created_at,
           is_pin_enabled, CASE WHEN pin_code IS NOT NULL AND pin_code != '' THEN 1 ELSE 0 END as has_pin,
           COALESCE(credit_score, 650) as credit_score, history_cleared_at
    FROM users WHERE id = ?
    """, (user_id,))
    user = dict(cursor.fetchone())
    conn.close()
    return user

def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE lower(trim(email)) = ?", (email.lower().strip(),))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, email, card_number, account_number, phone_number, balance, full_name, is_frozen, is_admin, avatar_url, created_at,
           is_pin_enabled, CASE WHEN pin_code IS NOT NULL AND pin_code != '' THEN 1 ELSE 0 END as has_pin,
           COALESCE(credit_score, 650) as credit_score, history_cleared_at
    FROM users WHERE id = ?
    """, (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def clean_digits(val: str) -> str:
    return "".join(c for c in val if c.isdigit())

def find_user_by_target(target: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    clean_target = target.strip()
    digits = clean_digits(clean_target)
    
    user_select = """
    SELECT id, email, card_number, account_number, phone_number, balance, full_name, is_frozen, is_admin, avatar_url, created_at,
           is_pin_enabled, CASE WHEN pin_code IS NOT NULL AND pin_code != '' THEN 1 ELSE 0 END as has_pin,
           COALESCE(credit_score, 650) as credit_score, history_cleared_at
    FROM users
    """
    
    cursor.execute(f"{user_select} WHERE lower(trim(email)) = ?", (clean_target.lower(),))
    row = cursor.fetchone()
    if row:
        conn.close()
        return dict(row)
        
    cursor.execute(f"{user_select} WHERE replace(card_number, ' ', '') = ? OR card_number = ?", (digits, clean_target))
    row = cursor.fetchone()
    if row:
        conn.close()
        return dict(row)
        
    cursor.execute(f"{user_select} WHERE account_number = ? OR replace(account_number, ' ', '') = ?", (clean_target, digits))
    row = cursor.fetchone()
    if row:
        conn.close()
        return dict(row)
        
    if len(digits) >= 7:
        cursor.execute(user_select)
        rows = cursor.fetchall()
        for r in rows:
            p_digits = clean_digits(r["phone_number"] or "")
            if p_digits == digits or (len(p_digits) >= 10 and len(digits) >= 10 and p_digits[-10:] == digits[-10:]):
                conn.close()
                return dict(r)

    if clean_target or digits:
        cursor.execute(
            "SELECT * FROM business_accounts WHERE (account_number = ? OR inn = ? OR replace(account_number, ' ', '') = ?) AND status = 'approved'",
            (clean_target, digits, digits)
        )
        b_row = cursor.fetchone()
        if b_row:
            b_dict = dict(b_row)
            cursor.execute(f"{user_select} WHERE id = ?", (b_dict["user_id"],))
            u_row = cursor.fetchone()
            if u_row:
                u_dict = dict(u_row)
                u_dict["recipient_business_id"] = b_dict["id"]
                u_dict["recipient_business_name"] = b_dict["company_name"]
                u_dict["recipient_business_type"] = b_dict["business_type"]
                conn.close()
                return u_dict
                
    conn.close()
    return None

def get_all_users() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, email, card_number, account_number, phone_number, balance, full_name, is_frozen, is_admin, avatar_url, created_at,
           is_pin_enabled, CASE WHEN pin_code IS NOT NULL AND pin_code != '' THEN 1 ELSE 0 END as has_pin,
           COALESCE(credit_score, 650) as credit_score, history_cleared_at
    FROM users
    ORDER BY is_admin DESC, id ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_bank_stats() -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COALESCE(SUM(balance), 0) FROM users")
    total_balance = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM users WHERE is_frozen = 1")
    total_frozen = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM transactions")
    total_transactions = cursor.fetchone()[0]
    
    conn.close()
    return {
        "total_bank_balance": float(total_balance),
        "total_users": int(total_users),
        "total_frozen": int(total_frozen),
        "total_transactions": int(total_transactions),
    }

def set_user_frozen(user_id: int, is_frozen: bool) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_frozen = ? WHERE id = ?", (1 if is_frozen else 0, user_id))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0

def delete_user_by_id(user_id: int) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM transactions WHERE sender_id = ? OR recipient_id = ?", (user_id, user_id))
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0

def update_user_fields(user_id: int, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    allowed = {"full_name", "phone_number", "card_number", "account_number", "email", "balance", "avatar_url"}
    filtered = {k: v for k, v in updates.items() if k in allowed and v is not None}
    if not filtered:
        return get_user_by_id(user_id)
        
    set_clauses = [f"{k} = ?" for k in filtered.keys()]
    values = list(filtered.values())
    values.append(user_id)
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"UPDATE users SET {', '.join(set_clauses)} WHERE id = ?", values)
    conn.commit()
    conn.close()
    return get_user_by_id(user_id)

def update_user_avatar(user_id: int, avatar_url: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET avatar_url = ? WHERE id = ?", (avatar_url, user_id))
    conn.commit()
    conn.close()
    return get_user_by_id(user_id)

def admin_credit_user(user_id: int, amount: float, sender_name: str, description: Optional[str] = None) -> Dict[str, Any]:
    if amount <= 0:
        raise ValueError("Сумма начисления должна быть больше 0.")
        
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, full_name, balance FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        conn.close()
        raise ValueError("Пользователь не найден.")
        
    new_balance = user["balance"] + amount
    cursor.execute("UPDATE users SET balance = ? WHERE id = ?", (new_balance, user_id))
    
    cursor.execute("""
    INSERT INTO transactions (sender_id, recipient_id, sender_name, recipient_name, amount, type, status, description)
    VALUES (NULL, ?, ?, ?, ?, 'admin_credit', 'completed', ?)
    """, (user_id, sender_name.strip(), user["full_name"], amount, description or "Начисление средств"))
    
    tx_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return {
        "transaction_id": tx_id,
        "user_id": user_id,
        "amount": amount,
        "new_balance": new_balance,
        "sender_name": sender_name,
        "description": description,
    }

def admin_debit_user(user_id: int, amount: float, reason: Optional[str] = None) -> Dict[str, Any]:
    if amount <= 0:
        raise ValueError("Сумма списания должна быть больше 0.")
        
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, full_name, balance FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        conn.close()
        raise ValueError("Пользователь не найден.")
        
    new_balance = max(0.0, user["balance"] - amount)
    cursor.execute("UPDATE users SET balance = ? WHERE id = ?", (new_balance, user_id))
    
    cursor.execute("""
    INSERT INTO transactions (sender_id, recipient_id, sender_name, recipient_name, amount, type, status, description)
    VALUES (?, NULL, ?, 'Банк (Списание)', ?, 'admin_debit', 'completed', ?)
    """, (user_id, user["full_name"], amount, reason or "Списание средств"))
    
    tx_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return {
        "transaction_id": tx_id,
        "user_id": user_id,
        "amount": amount,
        "new_balance": new_balance,
        "reason": reason,
    }

def transfer_funds(
    sender_id: int,
    target: str,
    amount: float,
    tx_type: str = "transfer",
    description: Optional[str] = None,
    custom_sender_name: Optional[str] = None,
    custom_recipient_name: Optional[str] = None,
    is_salary: bool = False,
    tax_rate: float = 0.0,
    business_id: Optional[int] = None,
) -> Dict[str, Any]:
    if amount <= 0:
        raise ValueError("Сумма перевода должна быть больше 0.")
        
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users WHERE id = ?", (sender_id,))
    sender = cursor.fetchone()
    if not sender:
        conn.close()
        raise ValueError("Отправитель не найден.")
        
    if sender["is_frozen"]:
        conn.close()
        raise ValueError("Ваш счёт заморожен банком. Расходные операции приостановлены.")

    if sender["balance"] < 0:
        conn.close()
        raise ValueError(f"Перевод заблокирован: на вашем счете отрицательный баланс ({sender['balance']:.2f} ₽). Пополните счёт для разблокировки.")

    cursor.execute("SELECT COUNT(*), SUM(remaining_amount) FROM credits WHERE user_id = ? AND overdue_since IS NOT NULL", (sender_id,))
    overdue_row = cursor.fetchone()
    if overdue_row and overdue_row[0] and overdue_row[0] > 0:
        overdue_amt = float(overdue_row[1]) if overdue_row[1] else 0.0
        conn.close()
        raise ValueError(f"Перевод заблокирован: у вас имеется просроченная задолженность по кредиту на сумму {overdue_amt:.2f} ₽. Погасите задолженность перед банком.")
        
    commission_rate = 0.0
    if tx_type == "qr":
        commission_rate = 1.0
    elif tx_type == "nfc":
        if amount <= 1000.0:
            commission_rate = 0.0
        elif amount <= 10000.0:
            commission_rate = 1.0
        elif amount <= 50000.0:
            commission_rate = 2.0
        else:
            commission_rate = 3.0

    commission_amount = round(amount * (commission_rate / 100.0), 2) if commission_rate > 0 else 0.0
    total_sender_charge = round(amount + commission_amount, 2)

    sender_biz = None
    deducted_from_biz = False
    if business_id:
        cursor.execute("SELECT * FROM business_accounts WHERE id = ? AND user_id = ?", (business_id, sender_id))
        b_row = cursor.fetchone()
        if not b_row:
            conn.close()
            raise ValueError("Указанный бизнес-счёт не найден.")
        sender_biz = dict(b_row)
        if sender_biz["status"] != "approved":
            conn.close()
            raise ValueError(f"Бизнес-счёт «{sender_biz['company_name']}» {sender_biz['status']}. Переводы не разрешены.")
        is_salary = True
        if sender_biz["balance"] >= total_sender_charge:
            deducted_from_biz = True
        elif sender["balance"] < total_sender_charge:
            conn.close()
            raise ValueError(f"Недостаточно средств с учётом комиссии ({commission_amount:.2f} ₽). Доступно на бизнес-счёте: {sender_biz['balance']:.2f} ₽, на карте: {sender['balance']:.2f} ₽")

    if not deducted_from_biz and sender["balance"] < total_sender_charge:
        conn.close()
        raise ValueError(f"Недостаточно средств для перевода и комиссии ({commission_amount:.2f} ₽). Всего требуется: {total_sender_charge:.2f} ₽, доступно: {sender['balance']:.2f} ₽")
        
    recipient = find_user_by_target(target)
    if not recipient:
        conn.close()
        raise ValueError("Получатель с указанными реквизитами не найден.")
        
    if recipient["id"] == sender_id:
        conn.close()
        raise ValueError("Нельзя перевести деньги самому себе.")
        
    if recipient["is_frozen"]:
        conn.close()
        raise ValueError("Счёт получателя заблокирован банком. Перевод невозможен.")

    effective_tax_rate = tax_rate if tax_rate > 0 else (13.0 if (is_salary or business_id) else 0.0)
    tax_amount = round(amount * (effective_tax_rate / 100.0), 2) if effective_tax_rate > 0 else 0.0
    recipient_credit = round(amount - tax_amount, 2)
        
    recipient_new_balance = recipient["balance"] + recipient_credit
    
    s_name = custom_sender_name or (
        f"{sender_biz['business_type']} «{sender_biz['company_name']}»" if sender_biz else sender["full_name"]
    )
    recipient_biz_id = recipient.get("recipient_business_id")
    if recipient_biz_id:
        r_name = custom_recipient_name or f"{recipient.get('recipient_business_type', 'Организация')} «{recipient.get('recipient_business_name', recipient['full_name'])}»"
    else:
        r_name = custom_recipient_name or recipient["full_name"]
    
    desc = description.strip() if description and description.strip() else (
        ("Выплата заработной платы" if is_salary else "Перевод с бизнес-счёта") if business_id else (
            ("Оплата услуг/товаров " + r_name) if recipient_biz_id else (
                "Выплата заработной платы" if is_salary else (
                    "NFC Оплата" if tx_type == "nfc" else (
                        "Оплата по QR-коду" if tx_type == "qr" else "Перевод клиенту Копи Банка"
                    )
                )
            )
        )
    )
    if commission_amount > 0 and "комиссия" not in desc.lower():
        desc += f" (Комиссия {commission_rate:.1f}%: {commission_amount:.2f} ₽)"
    if tax_amount > 0 and "налог" not in desc.lower() and "ндфл" not in desc.lower():
        desc += f" (Удержан НДФЛ {effective_tax_rate:.0f}%: {tax_amount:.2f} ₽)"
    
    try:
        if deducted_from_biz:
            cursor.execute("UPDATE business_accounts SET balance = balance - ? WHERE id = ?", (total_sender_charge, business_id))
            sender_new_balance = sender["balance"]
        else:
            sender_new_balance = sender["balance"] - total_sender_charge
            cursor.execute("UPDATE users SET balance = ? WHERE id = ?", (sender_new_balance, sender_id))
            
        if recipient_biz_id:
            cursor.execute("UPDATE business_accounts SET balance = balance + ? WHERE id = ?", (recipient_credit, recipient_biz_id))
        else:
            cursor.execute("UPDATE users SET balance = ? WHERE id = ?", (recipient_new_balance, recipient["id"]))
        
        tx_biz_id = recipient_biz_id or business_id
        cursor.execute("""
        INSERT INTO transactions (sender_id, recipient_id, sender_name, recipient_name, amount, type, status, description, tax_amount, commission_amount, business_id)
        VALUES (?, ?, ?, ?, ?, ?, 'completed', ?, ?, ?, ?)
        """, (sender_id, recipient["id"], s_name, r_name, amount, tx_type, desc, tax_amount, commission_amount, tx_biz_id))
        
        tx_id = cursor.lastrowid
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        raise e
        
    conn.close()
    
    return {
        "transaction_id": tx_id,
        "sender_id": sender_id,
        "recipient_id": recipient["id"],
        "sender_name": s_name,
        "recipient_name": r_name,
        "amount": amount,
        "commission_amount": commission_amount,
        "total_debited": total_sender_charge,
        "tax_amount": tax_amount,
        "recipient_received": recipient_credit,
        "sender_new_balance": sender_new_balance,
        "type": tx_type,
        "description": desc,
    }

def get_user_transactions(user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT history_cleared_at FROM users WHERE id = ?", (user_id,))
    u = cursor.fetchone()
    cleared_at = u["history_cleared_at"] if u else None

    query = """
    SELECT id, sender_id, recipient_id, sender_name, recipient_name, amount, type, status, description, tax_amount, commission_amount, business_id, created_at
    FROM transactions
    WHERE (sender_id = ? OR recipient_id = ?)
    """
    params: List[Any] = [user_id, user_id]
    if cleared_at:
        query += " AND created_at > ?"
        params.append(cleared_at)
    query += " ORDER BY created_at DESC, id DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    res = []
    for r in rows:
        d = dict(r)
        d["direction"] = "incoming" if d["recipient_id"] == user_id else "outgoing"
        res.append(d)
    return res

def clear_user_history(user_id: int) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET history_cleared_at = CURRENT_TIMESTAMP WHERE id = ?", (user_id,))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0

def admin_get_user_full_transactions(user_id: int, limit: int = 200) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT history_cleared_at FROM users WHERE id = ?", (user_id,))
    u = cursor.fetchone()
    cleared_at = u["history_cleared_at"] if u else None

    cursor.execute("""
    SELECT id, sender_id, recipient_id, sender_name, recipient_name, amount, type, status, description, tax_amount, commission_amount, business_id, created_at
    FROM transactions
    WHERE sender_id = ? OR recipient_id = ?
    ORDER BY created_at DESC, id DESC
    LIMIT ?
    """, (user_id, user_id, limit))
    rows = cursor.fetchall()
    conn.close()

    res = []
    for r in rows:
        d = dict(r)
        d["direction"] = "incoming" if d["recipient_id"] == user_id else "outgoing"
        d["hidden_by_user"] = bool(cleared_at and d.get("created_at") and d["created_at"] <= cleared_at)
        res.append(d)
    return res

def create_nfc_token(sender_id: int, max_amount: float = 50000.0, ttl_seconds: int = 120, business_id: Optional[int] = None) -> Dict[str, Any]:
    sender = get_user_by_id(sender_id)
    if not sender:
        raise ValueError("Пользователь-плательщик не найден.")
    if sender["is_frozen"]:
        raise ValueError("Счёт заморожен банком. Бесконтактная NFC-оплата недоступна.")

    sender_biz = None
    if business_id:
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM business_accounts WHERE id = ? AND user_id = ?", (business_id, sender_id))
        brow = c.fetchone()
        conn.close()
        if not brow:
            raise ValueError("Указанный бизнес-счёт не найден.")
        sender_biz = dict(brow)
        if sender_biz["status"] != "approved":
            raise ValueError(f"Бизнес-счёт «{sender_biz['company_name']}» не активен.")

    token = f"sber_nfc_{secrets.token_hex(16)}"
    short_code = secrets.token_hex(3).upper()
    now = int(time.time())
    expires_at = now + ttl_seconds

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE nfc_tokens SET status = 'cancelled' WHERE sender_id = ? AND status = 'active'", (sender_id,))
    cursor.execute("""
    INSERT INTO nfc_tokens (token, short_code, sender_id, max_amount, status, created_at, expires_at, business_id)
    VALUES (?, ?, ?, ?, 'active', ?, ?, ?)
    """, (token, short_code, sender_id, max_amount, now, expires_at, business_id))
    conn.commit()
    conn.close()

    return {
        "token": token,
        "short_code": short_code,
        "sender_id": sender_id,
        "sender_name": f"{sender_biz['business_type']} «{sender_biz['company_name']}»" if sender_biz else sender["full_name"],
        "card_number": sender_biz["account_number"] if sender_biz else sender["card_number"],
        "business_id": business_id,
        "max_amount": max_amount,
        "expires_in": ttl_seconds,
        "expires_at": expires_at,
    }

def get_nfc_token(identifier: str) -> Optional[Dict[str, Any]]:
    clean_id = identifier.strip()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM nfc_tokens WHERE token = ? OR upper(short_code) = upper(?)", (clean_id, clean_id))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    now = int(time.time())
    if d["status"] == "active" and now > d["expires_at"]:
        conn = get_connection()
        c = conn.cursor()
        c.execute("UPDATE nfc_tokens SET status = 'expired' WHERE token = ?", (d["token"],))
        conn.commit()
        conn.close()
        d["status"] = "expired"
    return d

def cancel_nfc_token(token: str, sender_id: int) -> bool:
    clean_id = token.strip()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE nfc_tokens SET status = 'cancelled' WHERE (token = ? OR upper(short_code) = upper(?)) AND sender_id = ? AND status = 'active'",
        (clean_id, clean_id, sender_id)
    )
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0

def mark_nfc_token_used(token: str, transaction_id: int, amount: float, recipient_name: str) -> bool:
    clean_id = token.strip()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE nfc_tokens 
    SET status = 'completed', transaction_id = ?, amount = ?, recipient_name = ?
    WHERE (token = ? OR upper(short_code) = upper(?)) AND status = 'active'
    """, (transaction_id, amount, recipient_name, clean_id, clean_id))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0

def create_split_requests(
    creator_id: int,
    payer_ids: List[int],
    amount_per_person: float,
    total_amount: float,
    description: Optional[str] = "Сплит чека"
) -> List[Dict[str, Any]]:
    creator = get_user_by_id(creator_id)
    if not creator:
        raise ValueError("Создатель сплита не найден.")
    
    conn = get_connection()
    cursor = conn.cursor()
    created_requests = []
    
    for pid in payer_ids:
        if pid == creator_id:
            continue
        payer = get_user_by_id(pid)
        if not payer:
            continue
            
        desc = description or "Сплит чека"
        cursor.execute("""
        INSERT INTO split_requests (creator_id, payer_id, creator_name, payer_name, amount, total_amount, description, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
        """, (creator_id, pid, creator["full_name"], payer["full_name"], amount_per_person, total_amount, desc))
        split_id = cursor.lastrowid
        created_requests.append({
            "id": split_id,
            "creator_id": creator_id,
            "payer_id": pid,
            "creator_name": creator["full_name"],
            "payer_name": payer["full_name"],
            "amount": amount_per_person,
            "total_amount": total_amount,
            "description": desc,
            "status": "pending",
        })
        
    conn.commit()
    conn.close()
    return created_requests

def get_pending_split_requests(user_id: int) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT s.*, u.avatar_url as creator_avatar, u.phone_number as creator_phone
    FROM split_requests s
    JOIN users u ON s.creator_id = u.id
    WHERE s.payer_id = ? AND s.status = 'pending'
    ORDER BY s.created_at DESC, s.id DESC
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def pay_split_request(split_id: int, payer_id: int) -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM split_requests WHERE id = ?", (split_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise ValueError("Запрос на сплит не найден.")
    
    req = dict(row)
    if req["payer_id"] != payer_id:
        conn.close()
        raise ValueError("У вас нет прав для оплаты этого сплита.")
    if req["status"] != "pending":
        conn.close()
        raise ValueError(f"Этот сплит уже обработан (статус: {req['status']}).")
    
    conn.close()
    
    creator = get_user_by_id(req["creator_id"])
    if not creator:
        raise ValueError("Получатель средств не найден.")
        
    tx_desc = f"Оплата сплита чека: {req.get('description') or 'Сплит'}"
    tx = transfer_funds(
        sender_id=payer_id,
        target=creator["card_number"],
        amount=req["amount"],
        tx_type="split",
        description=tx_desc
    )
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE split_requests SET status = 'paid' WHERE id = ?", (split_id,))
    conn.commit()
    conn.close()
    
    return {
        "success": True,
        "split_id": split_id,
        "message": f"Сплит на сумму {req['amount']:.2f} ₽ успешно оплачен!",
        "transaction": tx
    }

def decline_split_request(split_id: int, payer_id: int) -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM split_requests WHERE id = ?", (split_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise ValueError("Запрос на сплит не найден.")
    req = dict(row)
    if req["payer_id"] != payer_id:
        conn.close()
        raise ValueError("У вас нет прав для отклонения этого сплита.")
    if req["status"] != "pending":
        conn.close()
        raise ValueError("Запрос уже обработан.")
        
    cursor.execute("UPDATE split_requests SET status = 'declined' WHERE id = ?", (split_id,))
    conn.commit()
    conn.close()
    return {"success": True, "message": "Запрос на сплит отклонён."}



def set_user_pin(user_id: int, pin: str, enabled: bool = True) -> bool:
    clean_pin = pin.strip()
    if len(clean_pin) < 4 or len(clean_pin) > 6 or not clean_pin.isdigit():
        raise ValueError("Пин-код должен состоять из 4-6 цифр.")
    pin_hash = hash_password(clean_pin)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET pin_code = ?, is_pin_enabled = ? WHERE id = ?", (pin_hash, 1 if enabled else 0, user_id))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0

def verify_user_pin(user_id: int, pin: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT pin_code, is_pin_enabled FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if not row or not row["pin_code"]:
        return False
    return verify_password(pin.strip(), row["pin_code"])

def set_pin_enabled(user_id: int, enabled: bool) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_pin_enabled = ? WHERE id = ?", (1 if enabled else 0, user_id))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0

def admin_reset_user_pin(user_id: int) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET pin_code = NULL, is_pin_enabled = 0 WHERE id = ?", (user_id,))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0

def admin_factory_reset_user(user_id: int) -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        conn.close()
        raise ValueError("Пользователь не найден.")
    user = dict(user)
    if user["email"].lower().strip() == SUPER_ADMIN_EMAIL.lower():
        conn.close()
        raise ValueError("Нельзя выполнить сброс аккаунта Главного администратора банка.")

    cursor.execute("DELETE FROM business_accounts WHERE user_id = ?", (user_id,))
    cursor.execute("DELETE FROM credits WHERE user_id = ?", (user_id,))
    cursor.execute("DELETE FROM deposits WHERE user_id = ?", (user_id,))
    cursor.execute("DELETE FROM transactions WHERE sender_id = ? OR recipient_id = ?", (user_id, user_id))
    cursor.execute("DELETE FROM split_requests WHERE creator_id = ? OR payer_id = ?", (user_id, user_id))
    cursor.execute("DELETE FROM nfc_tokens WHERE sender_id = ?", (user_id,))

    new_card = generate_sber_card_number()
    new_account = generate_account_number()

    cursor.execute("""
    UPDATE users 
    SET balance = 0.0, 
        card_number = ?, 
        account_number = ?, 
        pin_code = NULL, 
        is_pin_enabled = 0, 
        is_frozen = 0
    WHERE id = ?
    """, (new_card, new_account, user_id))

    conn.commit()

    cursor.execute("""
    SELECT id, email, card_number, account_number, phone_number, balance, full_name, is_frozen, is_admin, avatar_url, created_at,
           is_pin_enabled, CASE WHEN pin_code IS NOT NULL AND pin_code != '' THEN 1 ELSE 0 END as has_pin
    FROM users WHERE id = ?
    """, (user_id,))
    updated_user = dict(cursor.fetchone())
    conn.close()
    return updated_user



def generate_inn(business_type: str) -> str:
    length = 12 if business_type.upper() == "ИП" else 10
    digits = "".join([str(secrets.randbelow(10)) for _ in range(length - 1)])
    return f"7{digits}"

def generate_business_account_number() -> str:
    suffix = "".join([str(secrets.randbelow(10)) for _ in range(12)])
    return f"40702810{suffix}"

def apply_business_account(user_id: int, company_name: str, business_type: str, tax_rate: float = 13.0) -> Dict[str, Any]:
    name = company_name.strip()
    if not name:
        raise ValueError("Укажите название организации.")
    b_type = business_type.strip().upper()
    if b_type not in ["ИП", "ООО"]:
        b_type = "ИП"
        
    fee = 800.0 if b_type == "ИП" else 4000.0
    user = get_user_by_id(user_id)
    if not user:
        raise ValueError("Пользователь не найден.")
    if user.get("is_frozen", 0):
        raise ValueError("Ваш счёт заморожен банком. Регистрация бизнеса невозможна.")
    if user["balance"] < fee:
        raise ValueError(
            f"Недостаточно средств для оплаты госпошлины за открытие {b_type} ({fee:,.0f} ₽). "
            f"Текущий баланс: {user['balance']:,.2f} ₽. Пополните счёт карты."
        )

    inn = generate_inn(b_type)
    account_number = generate_business_account_number()
    rate = float(tax_rate) if tax_rate > 0 else 13.0

    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (fee, user_id))
    cursor.execute("""
    INSERT INTO transactions (sender_id, recipient_id, sender_name, recipient_name, amount, type, status, description)
    VALUES (?, NULL, ?, 'ФНС России (Госпошлина)', ?, 'transfer', 'completed', ?)
    """, (user_id, user["full_name"], fee, f"Госпошлина за регистрацию {b_type} «{name}»"))

    cursor.execute("""
    INSERT INTO business_accounts (user_id, company_name, business_type, inn, account_number, tax_rate, balance, status)
    VALUES (?, ?, ?, ?, ?, ?, 0.0, 'pending')
    """, (user_id, name, b_type, inn, account_number, rate))
    b_id = cursor.lastrowid
    conn.commit()
    cursor.execute("SELECT * FROM business_accounts WHERE id = ?", (b_id,))
    row = dict(cursor.fetchone())
    conn.close()
    return row

def close_business(user_id: int, business_id: int) -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM business_accounts WHERE id = ? AND user_id = ?", (business_id, user_id))
    biz = cursor.fetchone()
    if not biz:
        conn.close()
        raise ValueError("Бизнес-аккаунт не найден или не принадлежит вам.")
    biz = dict(biz)
    if biz["status"] == "closed":
        conn.close()
        raise ValueError("Организация уже ликвидирована (закрыта).")
    if biz["status"] == "pending_close":
        conn.close()
        raise ValueError("Заявка на закрытие уже находится на рассмотрении у администратора.")

    cursor.execute("UPDATE business_accounts SET status = 'pending_close' WHERE id = ?", (business_id,))
    conn.commit()
    conn.close()
    return {
        "success": True,
        "business_id": business_id,
        "status": "pending_close",
        "refund_amount": float(biz["balance"]),
        "message": f"Заявка на ликвидацию {biz['business_type']} «{biz['company_name']}» успешно передана администратору на рассмотрение."
    }

def admin_approve_business_closure(business_id: int, admin_comment: Optional[str] = None) -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM business_accounts WHERE id = ?", (business_id,))
    biz = cursor.fetchone()
    if not biz:
        conn.close()
        raise ValueError("Организация не найдена.")
    biz = dict(biz)
    user_id = biz["user_id"]
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        conn.close()
        raise ValueError("Владелец бизнеса не найден.")
    user = dict(user)

    rem_balance = float(biz["balance"])
    if rem_balance > 0:
        cursor.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (rem_balance, user_id))
        cursor.execute("UPDATE business_accounts SET balance = 0.0, status = 'closed', admin_comment = ? WHERE id = ?", (admin_comment or "Ликвидация одобрена администратором", business_id))
        cursor.execute("""
        INSERT INTO transactions (sender_id, recipient_id, sender_name, recipient_name, amount, type, status, description, business_id)
        VALUES (?, ?, ?, ?, ?, 'transfer', 'completed', ?, ?)
        """, (
            user_id,
            user_id,
            f"{biz['business_type']} «{biz['company_name']}»",
            user["full_name"],
            rem_balance,
            f"Возврат остатка средств при ликвидации {biz['business_type']} на карту",
            business_id
        ))
    else:
        cursor.execute("UPDATE business_accounts SET status = 'closed', admin_comment = ? WHERE id = ?", (admin_comment or "Ликвидация одобрена администратором", business_id))

    conn.commit()
    conn.close()
    return {
        "success": True,
        "business_id": business_id,
        "refunded_amount": rem_balance,
        "message": f"Ликвидация «{biz['company_name']}» одобрена. Остаток средств ({rem_balance:,.2f} ₽) возвращён на карту владельца." if rem_balance > 0 else f"Ликвидация «{biz['company_name']}» одобрена."
    }

def admin_reject_business_closure(business_id: int, admin_comment: Optional[str] = None) -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE business_accounts SET status = 'approved', admin_comment = ? WHERE id = ?", (admin_comment or "В закрытии отказано администратором", business_id))
    conn.commit()
    conn.close()
    return {
        "success": True,
        "business_id": business_id,
        "status": "approved",
        "message": "Заявка на закрытие отклонена. Организация остаётся активной."
    }

def get_user_business_accounts(user_id: int) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM business_accounts WHERE user_id = ? ORDER BY id DESC", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def admin_get_all_businesses() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT b.*, u.full_name as owner_name, u.email as owner_email, u.phone_number as owner_phone
    FROM business_accounts b
    JOIN users u ON b.user_id = u.id
    ORDER BY CASE b.status WHEN 'pending' THEN 0 ELSE 1 END, b.id DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def admin_update_business_status(business_id: int, status: str, admin_comment: Optional[str] = None) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE business_accounts SET status = ?, admin_comment = ? WHERE id = ?", (status, admin_comment, business_id))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0

def admin_update_business_details(
    business_id: int,
    company_name: Optional[str] = None,
    tax_rate: Optional[float] = None,
    balance: Optional[float] = None,
    status: Optional[str] = None,
) -> bool:
    updates = {}
    if company_name is not None: updates["company_name"] = company_name.strip()
    if tax_rate is not None: updates["tax_rate"] = tax_rate
    if balance is not None: updates["balance"] = balance
    if status is not None: updates["status"] = status
    if not updates: return True
    
    set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
    vals = list(updates.values())
    vals.append(business_id)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"UPDATE business_accounts SET {set_clause} WHERE id = ?", vals)
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0

def admin_delete_business(business_id: int) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM business_accounts WHERE id = ?", (business_id,))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0

def admin_create_business(user_id: int, company_name: str, business_type: str, tax_rate: float = 13.0, balance: float = 0.0) -> Dict[str, Any]:
    name = company_name.strip()
    if not name:
        raise ValueError("Укажите название организации.")
    b_type = business_type.strip().upper()
    if b_type not in ["ИП", "ООО"]:
        b_type = "ИП"
    inn = generate_inn(b_type)
    account_number = generate_business_account_number()
    rate = float(tax_rate) if tax_rate > 0 else 13.0

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO business_accounts (user_id, company_name, business_type, inn, account_number, tax_rate, balance, status)
    VALUES (?, ?, ?, ?, ?, ?, ?, 'approved')
    """, (user_id, name, b_type, inn, account_number, rate, float(initial_balance)))
    b_id = cursor.lastrowid
    conn.commit()
    cursor.execute("SELECT * FROM business_accounts WHERE id = ?", (b_id,))
    row = dict(cursor.fetchone())
    conn.close()
    return row


def adjust_user_credit_score_internal(cursor: sqlite3.Cursor, user_id: int, delta: int, description: str) -> int:
    cursor.execute("SELECT credit_score FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    current_score = row["credit_score"] if row and row["credit_score"] is not None else 650
    new_score = max(300, min(850, current_score + delta))
    cursor.execute("UPDATE users SET credit_score = ? WHERE id = ?", (new_score, user_id))
    cursor.execute("""
    INSERT INTO credit_history_events (user_id, event_type, score_delta, new_score, description)
    VALUES (?, ?, ?, ?, ?)
    """, (user_id, "score_adjustment" if delta != 0 else "info", delta, new_score, description))
    return new_score

def get_credit_score_category(score: int) -> Dict[str, Any]:
    if score >= 750:
        return {"category": "Отличная", "code": "excellent", "is_allowed": True, "color": "#15803D"}
    elif score >= 650:
        return {"category": "Хорошая", "code": "good", "is_allowed": True, "color": "#2563EB"}
    elif score >= 500:
        return {"category": "Средняя", "code": "fair", "is_allowed": True, "color": "#D97706"}
    else:
        return {"category": "Плохая", "code": "poor", "is_allowed": False, "color": "#DC2626"}

def get_user_credit_history(user_id: int) -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT credit_score, full_name FROM users WHERE id = ?", (user_id,))
    u = cursor.fetchone()
    if not u:
        conn.close()
        raise ValueError("Пользователь не найден.")
    score = u["credit_score"] if u["credit_score"] is not None else 650
    cursor.execute("""
    SELECT id, user_id, event_type, score_delta, new_score, description, created_at
    FROM credit_history_events
    WHERE user_id = ?
    ORDER BY created_at DESC, id DESC
    LIMIT 100
    """, (user_id,))
    events = [dict(r) for r in cursor.fetchall()]
    conn.close()
    cat = get_credit_score_category(score)
    return {
        "user_id": user_id,
        "score": score,
        "category": cat["category"],
        "category_code": cat["code"],
        "is_credit_allowed": cat["is_allowed"],
        "color": cat["color"],
        "events": events
    }

def admin_adjust_user_credit_score(admin_id: int, user_id: int, score_delta: int, description: str) -> Dict[str, Any]:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        new_score = adjust_user_credit_score_internal(cursor, user_id, score_delta, f"Ручная корректировка: {description}")
        conn.commit()
        cat = get_credit_score_category(new_score)
        return {"success": True, "new_score": new_score, "category": cat["category"]}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def apply_credit(
    user_id: int,
    title: str,
    amount: float,
    interest_rate: float = 14.9,
    term_months: int = 12,
    payment_type: str = "annuity",
    business_id: Optional[int] = None,
) -> dict:
    if amount <= 0:
        raise ValueError("Сумма кредита должна быть больше 0.")
    if term_months <= 0:
        raise ValueError("Срок кредитования должен превышать 0 месяцев.")
    
    r = (interest_rate / 100.0) / 12.0
    normalized_type = "differentiated" if payment_type.lower() == "differentiated" else "annuity"
    if normalized_type == "differentiated":
        monthly = round((amount / term_months) + (amount * r), 2)
        total_interest = sum((amount - (k * amount / term_months)) * r for k in range(term_months))
        total_to_repay = round(amount + total_interest, 2)
    else:
        if r > 0:
            factor = (1 + r) ** term_months
            monthly = round(amount * (r * factor) / (factor - 1), 2)
            total_to_repay = round(monthly * term_months, 2)
        else:
            monthly = round(amount / term_months, 2)
            total_to_repay = round(amount, 2)
    
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        
        cursor.execute("SELECT id, full_name, balance, credit_score FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        if not user:
            raise ValueError("Пользователь не найден.")
            
        score = user["credit_score"] if user["credit_score"] is not None else 650
        if score < 500:
            raise ValueError(f"Кредитование заблокировано: у вас плохая кредитная история (рейтинг: {score} из 850). Для разблокировки погасите задолженности.")

        # Строгие лимиты по скорингу (предотвращение взятия миллиардов и мультиаккаунтов)
        if business_id:
            max_allowed = 5000000.0
        elif score < 600:
            max_allowed = 150000.0
        elif score < 700:
            max_allowed = 500000.0
        elif score < 750:
            max_allowed = 1500000.0
        elif score < 800:
            max_allowed = 2000000.0
        else:
            max_allowed = 3000000.0

        if amount > max_allowed:
            raise ValueError(f"Запрошенная сумма ({amount:,.0f} ₽) превышает кредитный лимит для вашего рейтинга ({score} баллов). Максимально доступно: {max_allowed:,.0f} ₽.")

        # Проверка просроченной задолженности
        cursor.execute("SELECT COUNT(*), SUM(remaining_amount) FROM credits WHERE user_id = ? AND overdue_since IS NOT NULL", (user_id,))
        od = cursor.fetchone()
        if od and od[0] and od[0] > 0:
            raise ValueError(f"Кредитование отклонено: у вас имеется непогашенная просроченная задолженность ({od[1]:.2f} ₽).")

        # Проверка суммарной кредитной нагрузки (DTI)
        cursor.execute("SELECT SUM(remaining_amount) FROM credits WHERE user_id = ? AND status IN ('active', 'pending')", (user_id,))
        current_debt = cursor.fetchone()[0] or 0.0
        if current_debt + total_to_repay > max_allowed * 1.3:
            raise ValueError(f"Превышен совокупный лимит кредитной нагрузки ({max_allowed:,.0f} ₽). Ваши текущие обязательства: {current_debt:,.2f} ₽.")
            
        cursor.execute("""
        INSERT INTO credits (user_id, title, amount, remaining_amount, monthly_payment, interest_rate, term_months, status, payment_type, business_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
        """, (user_id, title.strip() or ("Кредит для бизнеса" if business_id else "Кредит наличными"), amount, total_to_repay, monthly, interest_rate, term_months, normalized_type, business_id))
        c_id = cursor.lastrowid
        
        cursor.execute("""
        INSERT INTO credit_history_events (user_id, event_type, score_delta, new_score, description)
        VALUES (?, 'credit_applied', 0, ?, ?)
        """, (user_id, score, f"Подана заявка на кредит «{title.strip() or 'Кредит'}» на {amount:.0f} ₽ (ожидает одобрения администратора)"))
        
        conn.commit()
        cursor.execute("SELECT * FROM credits WHERE id = ?", (c_id,))
        row = dict(cursor.fetchone())
        return row
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_user_credits(user_id: int) -> list:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM credits WHERE user_id = ? ORDER BY id DESC", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def admin_get_all_credits() -> list:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT c.*, u.full_name as owner_name, u.email as owner_email, u.credit_score as owner_credit_score
    FROM credits c
    JOIN users u ON c.user_id = u.id
    ORDER BY CASE c.status WHEN 'pending' THEN 0 ELSE 1 END, c.id DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def admin_update_credit(
    credit_id: int,
    remaining_amount: Optional[float] = None,
    interest_rate: Optional[float] = None,
    monthly_payment: Optional[float] = None,
    status: Optional[str] = None,
) -> bool:
    updates = {}
    if remaining_amount is not None: updates["remaining_amount"] = remaining_amount
    if interest_rate is not None: updates["interest_rate"] = interest_rate
    if monthly_payment is not None: updates["monthly_payment"] = monthly_payment
    if status is not None: updates["status"] = status
    if not updates: return True
    
    set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
    vals = list(updates.values())
    vals.append(credit_id)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"UPDATE credits SET {set_clause} WHERE id = ?", vals)
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0

def admin_delete_credit(credit_id: int) -> bool:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute("SELECT * FROM credits WHERE id = ?", (credit_id,))
        credit = cursor.fetchone()
        if not credit:
            conn.close()
            return False

        user_id = int(credit["user_id"])
        status = credit["status"]
        remaining = float(credit["remaining_amount"])
        biz_id = credit["business_id"] if "business_id" in credit.keys() else None

        if status in ("active", "frozen"):
            cursor.execute("SELECT balance, full_name FROM users WHERE id = ?", (user_id,))
            user = cursor.fetchone()
            user_name = user["full_name"] if user else "Клиент"
            
            disbursed = float(credit["amount"])
            amt_to_deduct = min(disbursed, remaining)

            if biz_id:
                cursor.execute("UPDATE business_accounts SET balance = balance - ? WHERE id = ?", (amt_to_deduct, biz_id))
            else:
                cursor.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (amt_to_deduct, user_id))
                cursor.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
                post_user = cursor.fetchone()
                if post_user and post_user["balance"] < 0:
                    cursor.execute("UPDATE users SET is_frozen = 1 WHERE id = ?", (user_id,))
                    adjust_user_credit_score_internal(
                        cursor,
                        user_id,
                        -100,
                        f"Санкция: аннулирование кредита «{credit['title']}» при отсутствии средств (баланс: {post_user['balance']:.2f} ₽)"
                    )

            cursor.execute("""
            INSERT INTO transactions (sender_id, recipient_id, sender_name, recipient_name, amount, type, status, description, business_id)
            VALUES (?, NULL, ?, 'Копи Банк', ?, 'credit_revoked', 'completed', ?, ?)
            """, (user_id, user_name, amt_to_deduct, f"Списание долга при аннулировании кредита: {credit['title']}", biz_id))

        cursor.execute("DELETE FROM credits WHERE id = ?", (credit_id,))
        affected = cursor.rowcount
        conn.commit()
        return affected > 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def repay_user_credit(user_id: int, credit_id: int, repay_amount: Optional[float] = None) -> Dict[str, Any]:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute("SELECT * FROM credits WHERE id = ? AND user_id = ?", (credit_id, user_id))
        credit = cursor.fetchone()
        if not credit:
            raise ValueError("Кредит не найден.")
        if credit["status"] not in ("active", "frozen"):
            raise ValueError(f"Операция невозможна для кредита в статусе «{credit['status']}».")

        remaining = float(credit["remaining_amount"])
        actual_pay = round(repay_amount if repay_amount is not None and repay_amount > 0 else remaining, 2)
        if actual_pay > remaining:
            actual_pay = remaining

        cursor.execute("SELECT balance, full_name FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        if not user or user["balance"] < actual_pay:
            raise ValueError(f"Недостаточно средств на основном счете. Доступно: {user['balance'] if user else 0:.2f} ₽, требуется: {actual_pay:.2f} ₽")

        new_remaining = round(remaining - actual_pay, 2)
        new_status = "paid" if new_remaining <= 0.01 else credit["status"]
        if new_remaining <= 0.01:
            new_remaining = 0.0

        cursor.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (actual_pay, user_id))
        cursor.execute("UPDATE credits SET remaining_amount = ?, status = ?, overdue_since = NULL WHERE id = ?", (new_remaining, new_status, credit_id))

        cursor.execute("""
        INSERT INTO transactions (sender_id, recipient_id, sender_name, recipient_name, amount, type, status, description)
        VALUES (?, NULL, ?, 'Копи Банк', ?, 'credit_repayment', 'completed', ?)
        """, (user_id, user["full_name"], actual_pay, f"Погашение кредита «{credit['title']}»{' (досрочно закрыт)' if new_status == 'paid' else ''}"))

        if new_status == "paid":
            adjust_user_credit_score_internal(cursor, user_id, 35, f"Полное погашение кредита «{credit['title']}» (+35 баллов)")
        else:
            adjust_user_credit_score_internal(cursor, user_id, 10, f"Частичное погашение кредита «{credit['title']}»")

        conn.commit()
        cursor.execute("SELECT * FROM credits WHERE id = ?", (credit_id,))
        res = dict(cursor.fetchone())
        return res
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def admin_create_credit(user_id: int, title: str, amount: float, interest_rate: float = 14.9, term_months: int = 12) -> Dict[str, Any]:
    title = title.strip() or "Кредит наличными"
    c = apply_credit(user_id, title, amount, interest_rate, term_months)
    credit_id = int(c["id"])

    conn = get_connection()
    try:
        res = issue_pending_credit(credit_id, conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return res


def issue_pending_credit(credit_id: int, conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    """Issues funds for an already registered credit in one database transaction."""
    own_connection = conn is None
    if conn is None:
        conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM credits WHERE id = ?", (credit_id,))
    credit = cursor.fetchone()
    if not credit:
        raise ValueError("Кредит не найден.")
    if credit["status"] in ("approved", "active"):
        res = dict(credit)
        if own_connection:
            conn.close()
        return res
    if credit["status"] in ("rejected", "paid"):
        raise ValueError("Операция недоступна для кредита в текущем состоянии.")

    now = time.time()
    user_id = int(credit["user_id"])
    biz_id = credit["business_id"] if "business_id" in credit.keys() else None
    amt = float(credit["amount"])

    cursor.execute(
        "UPDATE credits SET status = 'active', overdue_since = NULL WHERE id = ?",
        (credit_id,),
    )
    if biz_id:
        cursor.execute(
            "UPDATE business_accounts SET balance = balance + ? WHERE id = ?",
            (amt, biz_id),
        )
    else:
        cursor.execute(
            "UPDATE users SET balance = balance + ?, last_finance_at = COALESCE(last_finance_at, ?) WHERE id = ?",
            (amt, now, user_id),
        )

    cursor.execute(
        """
        INSERT INTO transactions
            (sender_id, recipient_id, sender_name, recipient_name, amount, type, status, description, business_id)
        VALUES
            (NULL, ?, 'Копи Банк', (SELECT full_name FROM users WHERE id = ?), ?,
             'credit_disbursement', 'completed', ?, ?)
        """,
        (
            user_id,
            user_id,
            amt,
            f"Выдача кредита: {credit['title']}",
            biz_id,
        ),
    )

    adjust_user_credit_score_internal(cursor, user_id, 15, f"Одобрение кредита «{credit['title']}» банком")

    cursor.execute("SELECT * FROM credits WHERE id = ?", (credit_id,))
    res = dict(cursor.fetchone())
    if own_connection:
        conn.commit()
        conn.close()
    return res


def apply_deposit(user_id: int, title: str, amount: float, interest_rate: float = 16.0, term_months: int = 6) -> Dict[str, Any]:
    if amount <= 0:
        raise ValueError("Сумма вклада должна быть больше 0.")
    if term_months <= 0:
        raise ValueError("Срок размещения средств должен быть не менее 1 месяца.")

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute("SELECT balance, full_name, credit_score FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        if not user:
            raise ValueError("Пользователь не найден.")
        if user["balance"] < amount:
            raise ValueError(f"Недостаточно средств для открытия вклада на {amount:.2f} ₽. Доступно на счете: {user['balance']:.2f} ₽")

        now = time.time()
        cursor.execute(
            """
            INSERT INTO deposits
                (user_id, title, amount, interest_rate, term_months, earned_amount, status, last_accrual_at)
            VALUES (?, ?, ?, ?, ?, 0.0, 'pending', ?)
            """,
            (user_id, title.strip() or "КопиВклад", float(amount), float(interest_rate), int(term_months), now)
        )
        deposit_id = int(cursor.lastrowid)
        conn.commit()
        cursor.execute("SELECT * FROM deposits WHERE id = ?", (deposit_id,))
        row = dict(cursor.fetchone())
        return row
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def close_user_deposit(user_id: int, deposit_id: int) -> Dict[str, Any]:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute("SELECT * FROM deposits WHERE id = ? AND user_id = ?", (deposit_id, user_id))
        dep = cursor.fetchone()
        if not dep:
            raise ValueError("Вклад не найден.")
        if dep["status"] != "active":
            raise ValueError(f"Невозможно закрыть вклад в статусе «{dep['status']}».")

        amount = float(dep["amount"])
        earned = float(dep["earned_amount"])
        total_refund = round(amount + earned, 2)

        cursor.execute("UPDATE deposits SET status = 'closed' WHERE id = ?", (deposit_id,))
        cursor.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (total_refund, user_id))
        cursor.execute("SELECT full_name FROM users WHERE id = ?", (user_id,))
        u = cursor.fetchone()
        user_name = u["full_name"] if u else "Клиент"

        cursor.execute("""
        INSERT INTO transactions (sender_id, recipient_id, sender_name, recipient_name, amount, type, status, description)
        VALUES (NULL, ?, 'Копи Банк', ?, ?, 'deposit_closed', 'completed', ?)
        """, (user_id, user_name, total_refund, f"Досрочное закрытие вклада «{dep['title']}» (тело: {amount:.2f} ₽, доход: {earned:.2f} ₽)"))

        conn.commit()
        cursor.execute("SELECT * FROM deposits WHERE id = ?", (deposit_id,))
        res = dict(cursor.fetchone())
        return res
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def open_deposit_transactional(
    user_id: int,
    title: str,
    amount: float,
    interest_rate: float,
    term_months: int,
    default_title: str,
    conn: Optional[sqlite3.Connection] = None,
) -> Dict[str, Any]:
    """Debits the principal and creates an active deposit atomically."""
    own_connection = conn is None
    if conn is None:
        conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("BEGIN IMMEDIATE")

    cursor.execute("SELECT balance, last_finance_at FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        raise ValueError("Пользователь не найден.")
    if user["balance"] < amount:
        raise ValueError("Недостаточно средств для открытия вклада на указанную сумму.")

    now = time.time()
    cursor.execute(
        """
        INSERT INTO deposits
            (user_id, title, amount, interest_rate, term_months, earned_amount, status, last_accrual_at)
        VALUES (?, ?, ?, ?, ?, 0.0, 'active', ?)
        """,
        (
            user_id,
            title.strip() or default_title,
            amount,
            interest_rate,
            term_months,
            now,
        ),
    )
    deposit_id = int(cursor.lastrowid)
    cursor.execute(
        "UPDATE users SET balance = balance - ?, last_finance_at = COALESCE(last_finance_at, ?) WHERE id = ?",
        (amount, now, user_id),
    )
    cursor.execute(
        """
        INSERT INTO transactions
            (sender_id, recipient_id, sender_name, recipient_name, amount, type, status, description)
        VALUES
            (?, NULL, (SELECT full_name FROM users WHERE id = ?), 'Копи Банк', ?,
             'deposit_open', 'completed', ?)
        """,
        (
            user_id,
            user_id,
            amount,
            f"Открытие вклада: {title.strip() or default_title}",
        ),
    )
    cursor.execute("SELECT * FROM deposits WHERE id = ?", (deposit_id,))
    row = dict(cursor.fetchone())
    if own_connection:
        conn.commit()
        conn.close()
    return row


def fund_pending_deposit(deposit_id: int) -> Dict[str, Any]:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute("SELECT * FROM deposits WHERE id = ?", (deposit_id,))
        deposit = cursor.fetchone()
        if not deposit:
            raise ValueError("Вклад не найден.")
        if deposit["status"] in ("active", "closed"):
            return dict(deposit)
        if deposit["status"] in ("rejected", "frozen"):
            raise ValueError("Операция недоступна для вклада в текущем состоянии.")

        cursor.execute("SELECT balance FROM users WHERE id = ?", (int(deposit["user_id"]),))
        user = cursor.fetchone()
        if not user or user["balance"] < deposit["amount"]:
            raise ValueError(f"Недостаточно средств у пользователя для открытия вклада. Доступно: {user['balance'] if user else 0:.2f} ₽")

        now = time.time()
        cursor.execute(
            "UPDATE deposits SET status = 'active', last_accrual_at = ? WHERE id = ?",
            (now, deposit_id),
        )
        cursor.execute(
            "UPDATE users SET balance = balance - ?, last_finance_at = ? WHERE id = ?",
            (float(deposit["amount"]), now, int(deposit["user_id"])),
        )
        cursor.execute(
            """
            INSERT INTO transactions
                (sender_id, recipient_id, sender_name, recipient_name, amount, type, status, description)
            VALUES
                (?, NULL, (SELECT full_name FROM users WHERE id = ?), 'Копи Банк', ?,
                 'deposit_open', 'completed', ?)
            """,
            (
                int(deposit["user_id"]),
                int(deposit["user_id"]),
                float(deposit["amount"]),
                f"Открытие вклада: {deposit['title']}",
            ),
        )
        cursor.execute("SELECT * FROM deposits WHERE id = ?", (deposit_id,))
        res = dict(cursor.fetchone())
        conn.commit()
        return res
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def get_user_deposits(user_id: int) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM deposits WHERE user_id = ? ORDER BY id DESC", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def admin_get_all_deposits() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT d.*, u.full_name as owner_name, u.email as owner_email, u.credit_score as owner_credit_score
    FROM deposits d
    JOIN users u ON d.user_id = u.id
    ORDER BY CASE d.status WHEN 'pending' THEN 0 ELSE 1 END, d.id DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def admin_update_deposit(
    deposit_id: int,
    amount: Optional[float] = None,
    interest_rate: Optional[float] = None,
    earned_amount: Optional[float] = None,
    status: Optional[str] = None,
) -> bool:
    updates = {}
    if amount is not None: updates["amount"] = amount
    if interest_rate is not None: updates["interest_rate"] = interest_rate
    if earned_amount is not None: updates["earned_amount"] = earned_amount
    if status is not None: updates["status"] = status
    if not updates: return True
    
    set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
    vals = list(updates.values())
    vals.append(deposit_id)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"UPDATE deposits SET {set_clause} WHERE id = ?", vals)
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0

def admin_delete_deposit(deposit_id: int) -> bool:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute("SELECT * FROM deposits WHERE id = ?", (deposit_id,))
        dep = cursor.fetchone()
        if not dep:
            conn.close()
            return False

        user_id = int(dep["user_id"])
        status = dep["status"]
        amount = float(dep["amount"])
        earned = float(dep["earned_amount"])
        total_refund = round(amount + earned, 2)

        if status in ("active", "frozen"):
            cursor.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (total_refund, user_id))
            cursor.execute("SELECT full_name FROM users WHERE id = ?", (user_id,))
            u = cursor.fetchone()
            user_name = u["full_name"] if u else "Клиент"
            cursor.execute("""
            INSERT INTO transactions (sender_id, recipient_id, sender_name, recipient_name, amount, type, status, description)
            VALUES (NULL, ?, 'Копи Банк', ?, ?, 'deposit_refund', 'completed', ?)
            """, (user_id, user_name, total_refund, f"Возврат вклада и дохода при удалении: {dep['title']}"))

        cursor.execute("DELETE FROM deposits WHERE id = ?", (deposit_id,))
        affected = cursor.rowcount
        conn.commit()
        return affected > 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def get_business_analytics(business_id: int) -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM business_accounts WHERE id = ?", (business_id,))
    biz = cursor.fetchone()
    if not biz:
        conn.close()
        raise ValueError("Бизнес-аккаунт не найден.")
    
    cursor.execute("""
    SELECT COALESCE(SUM(amount), 0.0) as income
    FROM transactions
    WHERE business_id = ? AND recipient_id = ?
    """, (business_id, biz["user_id"]))
    income = float(cursor.fetchone()["income"])

    cursor.execute("""
    SELECT COALESCE(SUM(amount), 0.0) as expenses, COALESCE(SUM(tax_amount), 0.0) as taxes
    FROM transactions
    WHERE business_id = ? AND sender_id = ?
    """, (business_id, biz["user_id"]))
    exp_row = cursor.fetchone()
    expenses = float(exp_row["expenses"])
    taxes = float(exp_row["taxes"])

    cursor.execute("""
    SELECT COALESCE(SUM(amount), 0.0) as tax_payments
    FROM transactions
    WHERE business_id = ? AND is_tax_payment = 1
    """, (business_id,))
    tax_payments = float(cursor.fetchone()["tax_payments"])
    total_taxes = round(taxes + tax_payments, 2)

    cursor.execute("""
    SELECT id, sender_name, recipient_name, amount, type, status, description, tax_amount, commission_amount, created_at
    FROM transactions
    WHERE business_id = ?
    ORDER BY created_at DESC, id DESC
    LIMIT 30
    """, (business_id,))
    txs = [dict(r) for r in cursor.fetchall()]
    conn.close()

    return {
        "business_id": business_id,
        "company_name": biz["company_name"],
        "business_type": biz["business_type"],
        "balance": float(biz["balance"]),
        "tax_rate": float(biz["tax_rate"]),
        "total_income": round(income, 2),
        "total_expenses": round(expenses, 2),
        "total_taxes_paid": total_taxes,
        "transactions": txs,
    }

def pay_business_tax(user_id: int, business_id: int, amount: float, description: Optional[str] = None) -> Dict[str, Any]:
    if amount <= 0:
        raise ValueError("Сумма налога должна быть больше 0.")
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute("SELECT * FROM business_accounts WHERE id = ? AND user_id = ?", (business_id, user_id))
        biz = cursor.fetchone()
        if not biz:
            raise ValueError("Бизнес-аккаунт не найден.")
        if biz["balance"] < amount:
            raise ValueError(f"Недостаточно средств на бизнес-счёте для уплаты налога. Доступно: {biz['balance']:.2f} ₽")

        cursor.execute("UPDATE business_accounts SET balance = balance - ? WHERE id = ?", (amount, business_id))
        desc = description or f"Уплата налогов/сборов: {biz['company_name']}"
        cursor.execute("""
        INSERT INTO transactions (sender_id, recipient_id, sender_name, recipient_name, amount, type, status, description, is_tax_payment, business_id)
        VALUES (?, NULL, ?, 'Федеральная налоговая служба (ФНС)', ?, 'tax_payment', 'completed', ?, 1, ?)
        """, (user_id, f"{biz['business_type']} «{biz['company_name']}»", amount, desc, business_id))
        tx_id = cursor.lastrowid
        conn.commit()
        return {"success": True, "transaction_id": tx_id, "amount": amount, "new_balance": round(biz["balance"] - amount, 2)}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def apply_business_credit(
    user_id: int,
    business_id: int,
    title: str,
    amount: float,
    interest_rate: float = 12.5,
    term_months: int = 12,
) -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM business_accounts WHERE id = ? AND user_id = ?", (business_id, user_id))
    biz = cursor.fetchone()
    conn.close()
    if not biz:
        raise ValueError("Бизнес-счёт не найден.")
    if biz["status"] != "approved":
        raise ValueError("Кредитование доступно только для подтвержденных организаций.")

    full_title = f"{title.strip() or 'Кредит на развитие бизнеса'} ({biz['company_name']})"
    return apply_credit(
        user_id=user_id,
        title=full_title,
        amount=amount,
        interest_rate=interest_rate,
        term_months=term_months,
        business_id=business_id,
    )

def admin_create_deposit(user_id: int, title: str, amount: float, interest_rate: float = 16.0, term_months: int = 6) -> Dict[str, Any]:
    conn = get_connection()
    try:
        res = open_deposit_transactional(
            user_id,
            title,
            float(amount),
            float(interest_rate),
            int(term_months),
            "КопиВклад Премиум",
            conn,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    conn.close()
    return res


FISCAL_YEAR_SECONDS = 3600.0
FISCAL_MONTH_SECONDS = 300.0


def _finance_rows(conn: sqlite3.Connection, user_id: int) -> Dict[str, Any]:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        raise ValueError("Пользователь не найден.")
    cursor.execute("SELECT * FROM credits WHERE user_id = ? ORDER BY id ASC", (user_id,))
    credits = cursor.fetchall()
    cursor.execute("SELECT * FROM deposits WHERE user_id = ? ORDER BY id ASC", (user_id,))
    deposits = cursor.fetchall()
    return {
        "user": dict(user),
        "credits": [dict(row) for row in credits],
        "deposits": [dict(row) for row in deposits],
    }


def run_finance_tick(user_id: int) -> Dict[str, Any]:
    """Accrues fiscal interest and applies repayments without allowing negative balances."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        state = _finance_rows(conn, user_id)
        now = time.time()
        last = state["user"].get("last_finance_at")
        last = float(last) if last is not None else now
        elapsed = max(0.0, min(now - last, 24.0 * FISCAL_YEAR_SECONDS))

        if elapsed > 0:
            for deposit in state["deposits"]:
                if deposit["status"] != "active":
                    continue
                deposit_last = deposit.get("last_accrual_at")
                deposit_last = float(deposit_last) if deposit_last is not None else now
                accrual_elapsed = max(0.0, min(now - deposit_last, 24.0 * FISCAL_YEAR_SECONDS))
                if accrual_elapsed <= 0:
                    continue
                monthly_rate = float(deposit["interest_rate"]) / 100.0 / 12.0
                months = accrual_elapsed / FISCAL_MONTH_SECONDS
                earned = float(deposit["amount"]) * monthly_rate * months
                cursor.execute(
                    "UPDATE deposits SET earned_amount = earned_amount + ?, last_accrual_at = ? WHERE id = ?",
                    (round(earned, 2), now, int(deposit["id"])),
                )

            balance = float(state["user"]["balance"])
            for credit in state["credits"]:
                if credit["status"] != "active":
                    continue
                remaining = float(credit["remaining_amount"])
                if remaining <= 0.01:
                    cursor.execute(
                        "UPDATE credits SET remaining_amount = 0, status = 'paid', overdue_since = NULL WHERE id = ?",
                        (int(credit["id"]),),
                    )
                    continue

                payment_type = credit.get("payment_type") or "annuity"
                term_months = int(credit["term_months"]) if credit.get("term_months") else 12
                interest_rate = float(credit["interest_rate"])
                monthly_rate = (interest_rate / 100.0) / 12.0
                principal_portion = round(float(credit["amount"]) / max(1, term_months), 2)
                due_cycles = int(elapsed / FISCAL_MONTH_SECONDS)

                for _ in range(due_cycles):
                    if remaining <= 0.01:
                        break

                    if payment_type == "differentiated":
                        current_payment = min(remaining, round(principal_portion + (remaining * monthly_rate), 2))
                    else:
                        current_payment = float(credit["monthly_payment"])

                    # Guardrail: balance can never go below 0.0
                    available_balance = max(0.0, balance)
                    payable = min(current_payment, remaining, available_balance)

                    if payable > 0:
                        balance = max(0.0, balance - payable)
                        remaining = max(0.0, remaining - payable)
                        cursor.execute(
                            "UPDATE users SET balance = ? WHERE id = ?",
                            (round(balance, 2), user_id),
                        )
                        cursor.execute(
                            "UPDATE credits SET remaining_amount = ? WHERE id = ?",
                            (round(remaining, 2), int(credit["id"])),
                        )
                        cursor.execute(
                            """
                            INSERT INTO transactions
                                (sender_id, recipient_id, sender_name, recipient_name, amount, type, status, description)
                            VALUES
                                (?, NULL, (SELECT full_name FROM users WHERE id = ?), 'Копи Банк', ?,
                                 'credit_repayment', 'completed', ?)
                            """,
                            (
                                user_id,
                                user_id,
                                round(payable, 2),
                                f"Плановый платеж по кредиту: {credit['title']}",
                            ),
                        )

                    # Overdraft guardrail: if payment could not be completed, flag overdue without debiting into negative
                    if remaining > 0.01 and payable + 0.01 < current_payment:
                        unpaid_amount = current_payment - payable
                        penalty = round(unpaid_amount * monthly_rate, 2)
                        remaining += penalty
                        cursor.execute(
                            "UPDATE credits SET remaining_amount = ?, overdue_since = COALESCE(overdue_since, ?) WHERE id = ?",
                            (round(remaining, 2), now, int(credit["id"])),
                        )
                        break
                    elif remaining > 0.01 and credit.get("overdue_since") is not None:
                        cursor.execute(
                            "UPDATE credits SET overdue_since = NULL WHERE id = ?",
                            (int(credit["id"]),),
                        )

                if remaining <= 0.01:
                    cursor.execute(
                        "UPDATE credits SET remaining_amount = 0, status = 'paid', overdue_since = NULL WHERE id = ?",
                        (int(credit["id"]),),
                    )

            cursor.execute("UPDATE users SET last_finance_at = ? WHERE id = ?", (now, user_id))

        conn.commit()
        return _finance_rows(conn, user_id)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def withdraw_business_to_personal(
    user_id: int,
    business_id: int,
    amount: float,
    commission_rate: float = 2.0,
) -> Dict[str, Any]:
    if amount <= 0:
        raise ValueError("Сумма вывода должна быть больше 0.")
    if amount < 100.0:
        raise ValueError("Минимальная сумма вывода со счёта организации составляет 100 ₽.")

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")

        cursor.execute("SELECT * FROM business_accounts WHERE id = ? AND user_id = ?", (business_id, user_id))
        biz = cursor.fetchone()
        if not biz:
            raise ValueError("Бизнес-счёт не найден или не принадлежит вам.")

        if biz["status"] != "approved":
            raise ValueError(f"Вывод невозможен: счёт организации находится в статусе «{biz['status']}».")

        if biz["balance"] < amount:
            raise ValueError(f"Недостаточно средств на счёте организации. Доступно: {biz['balance']:.2f} ₽, запрошено: {amount:.2f} ₽")

        cursor.execute("SELECT id, full_name, balance, is_frozen FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        if not user:
            raise ValueError("Пользователь не найден.")
        if user["is_frozen"]:
            raise ValueError("Ваш личный счёт заморожен банком. Вывод средств невозможен.")

        commission_amount = round(amount * (commission_rate / 100.0), 2)
        net_amount = round(amount - commission_amount, 2)
        if net_amount <= 0:
            raise ValueError("Сумма перевода слишком мала для покрытия банковской комиссии.")

        new_biz_balance = round(biz["balance"] - amount, 2)
        new_user_balance = round(user["balance"] + net_amount, 2)

        cursor.execute("UPDATE business_accounts SET balance = ? WHERE id = ?", (new_biz_balance, business_id))
        cursor.execute("UPDATE users SET balance = ? WHERE id = ?", (new_user_balance, user_id))

        biz_name = f"{biz['business_type']} «{biz['company_name']}»"
        user_name = user["full_name"]

        # Запись в историю операций по счёту бизнеса
        desc_biz = f"Вывод средств на личную карту (Комиссия {commission_rate:.1f}%: {commission_amount:.2f} ₽)"
        cursor.execute("""
        INSERT INTO transactions (sender_id, recipient_id, sender_name, recipient_name, amount, commission_amount, type, status, description, business_id)
        VALUES (?, ?, ?, ?, ?, ?, 'business_withdrawal', 'completed', ?, ?)
        """, (user_id, user_id, biz_name, user_name, amount, commission_amount, desc_biz, business_id))
        biz_tx_id = cursor.lastrowid

        # Запись в историю операций физлица
        desc_user = f"Поступление со счёта организации {biz_name} (за вычетом комиссии {commission_rate:.1f}%)"
        cursor.execute("""
        INSERT INTO transactions (sender_id, recipient_id, sender_name, recipient_name, amount, commission_amount, type, status, description)
        VALUES (?, ?, ?, ?, ?, 0, 'transfer', 'completed', ?)
        """, (user_id, user_id, biz_name, user_name, net_amount, desc_user))

        conn.commit()
        return {
            "success": True,
            "business_id": business_id,
            "amount_withdrawn": amount,
            "commission_rate": commission_rate,
            "commission_amount": commission_amount,
            "net_amount": net_amount,
            "new_business_balance": new_biz_balance,
            "new_user_balance": new_user_balance,
            "transaction_id": biz_tx_id,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


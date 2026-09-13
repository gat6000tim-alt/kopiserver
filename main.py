from fastapi import FastAPI, HTTPException, status, Query, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import re
from contextlib import asynccontextmanager

from db import (
    init_db,
    create_user,
    get_user_by_email,
    get_user_by_id,
    verify_password,
    get_all_users,
    get_bank_stats,
    set_user_frozen,
    delete_user_by_id,
    update_user_fields,
    admin_credit_user,
    admin_debit_user,
    transfer_funds,
    find_user_by_target,
    get_user_transactions,
    update_user_avatar,
    create_nfc_token,
    get_nfc_token,
    cancel_nfc_token,
    mark_nfc_token_used,
    create_split_requests,
    get_pending_split_requests,
    pay_split_request,
    decline_split_request,
    set_user_pin,
    verify_user_pin,
    set_pin_enabled,
    admin_reset_user_pin,
    admin_factory_reset_user,
    apply_business_account,
    close_business,
    get_user_business_accounts,
    admin_get_all_businesses,
    admin_update_business_status,
    admin_update_business_details,
    admin_delete_business,
    admin_create_business,
    admin_approve_business_closure,
    admin_reject_business_closure,
    apply_credit,
    get_user_credits,
    admin_get_all_credits,
    admin_update_credit,
    admin_delete_credit,
    admin_create_credit,
    issue_pending_credit,
    apply_deposit,
    get_user_deposits,
    admin_get_all_deposits,
    admin_update_deposit,
    admin_delete_deposit,
    admin_create_deposit,
    fund_pending_deposit,
    run_finance_tick,
    SUPER_ADMIN_EMAIL,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    print(" [Kopi Bank Server] SQLite Database & migrations initialized successfully.")
    yield

app = FastAPI(
    title="Kopi Bank Server - God Edition",
    description="Backend for Kopi Bank with Superadmin God Mode, QR and NFC Payments",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=6, description="Минимум 6 символов")
    confirm_password: str
    full_name: Optional[str] = None
    phone_number: Optional[str] = None

class LoginRequest(BaseModel):
    email: str
    password: str

class UserResponse(BaseModel):
    id: int
    email: str
    card_number: str
    account_number: str
    phone_number: Optional[str] = None
    balance: float
    full_name: str
    is_frozen: int = 0
    is_admin: int = 0
    avatar_url: Optional[str] = None
    created_at: str
    is_pin_enabled: int = 0
    has_pin: int = 0

class AvatarUploadRequest(BaseModel):
    avatar_url: str

class SplitRequest(BaseModel):
    sender_id: int
    participant_ids: Optional[List[int]] = None
    participant_names: Optional[List[str]] = None
    total_amount: float
    amount_per_person: float
    description: Optional[str] = "Сплит чека"

class SplitActionRequest(BaseModel):
    split_id: int
    payer_id: int

class AuthResponse(BaseModel):
    success: bool
    message: str
    user: Optional[UserResponse] = None

class AdminFreezeRequest(BaseModel):
    admin_id: Optional[int] = None
    admin_email: Optional[str] = None
    user_id: int
    is_frozen: bool

class AdminCreditRequest(BaseModel):
    admin_id: Optional[int] = None
    admin_email: Optional[str] = None
    user_id: int
    amount: float
    sender_name: str = Field(..., description="Название компании / отправителя")
    description: Optional[str] = None

class AdminDebitRequest(BaseModel):
    admin_id: Optional[int] = None
    admin_email: Optional[str] = None
    user_id: int
    amount: float
    reason: Optional[str] = None

class AdminUpdateUserRequest(BaseModel):
    admin_id: Optional[int] = None
    admin_email: Optional[str] = None
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    card_number: Optional[str] = None
    account_number: Optional[str] = None
    email: Optional[str] = None
    balance: Optional[float] = None

class TransferRequest(BaseModel):
    sender_id: int
    target: str = Field(..., description="Номер карты, счёта или телефона")
    amount: float
    description: Optional[str] = None
    is_salary: Optional[bool] = False
    tax_rate: Optional[float] = 0.0
    business_id: Optional[int] = None

class SetPinRequest(BaseModel):
    user_id: int
    pin: str
    enabled: Optional[bool] = True

class VerifyPinRequest(BaseModel):
    user_id: int
    pin: str

class TogglePinRequest(BaseModel):
    user_id: int
    enabled: bool

class AdminResetPinRequest(BaseModel):
    admin_id: Optional[int] = None
    admin_email: Optional[str] = None
    user_id: int

class BusinessApplyRequest(BaseModel):
    user_id: int
    company_name: str
    business_type: str = "ИП"
    tax_rate: Optional[float] = 13.0

class AdminBusinessActionRequest(BaseModel):
    admin_id: Optional[int] = None
    admin_email: Optional[str] = None
    business_id: Optional[int] = None
    user_id: Optional[int] = None
    action: str
    business_type: Optional[str] = "ИП"
    status: Optional[str] = None
    company_name: Optional[str] = None
    tax_rate: Optional[float] = None
    balance: Optional[float] = None
    admin_comment: Optional[str] = None

class CreditApplyRequest(BaseModel):
    user_id: int
    title: Optional[str] = "Кредит наличными"
    amount: float
    interest_rate: Optional[float] = 14.9
    term_months: Optional[int] = 12
    payment_type: Optional[str] = "annuity"

class AdminCreditActionRequest(BaseModel):
    admin_id: Optional[int] = None
    admin_email: Optional[str] = None
    credit_id: Optional[int] = None
    user_id: Optional[int] = None
    action: str
    title: Optional[str] = None
    amount: Optional[float] = None
    remaining_amount: Optional[float] = None
    interest_rate: Optional[float] = None
    monthly_payment: Optional[float] = None
    term_months: Optional[int] = None
    status: Optional[str] = None

class DepositApplyRequest(BaseModel):
    user_id: int
    title: Optional[str] = "КопиВклад"
    amount: float
    interest_rate: Optional[float] = 16.0
    term_months: Optional[int] = 6

class AdminDepositActionRequest(BaseModel):
    admin_id: Optional[int] = None
    admin_email: Optional[str] = None
    deposit_id: Optional[int] = None
    user_id: Optional[int] = None
    action: str

    amount: Optional[float] = None
    interest_rate: Optional[float] = None
    earned_amount: Optional[float] = None
    term_months: Optional[int] = None
    title: Optional[str] = None
    status: Optional[str] = None

class FinanceTickRequest(BaseModel):
    user_id: int

class SplitBillCreateRequest(BaseModel):
    creator_id: int
    payer_target: str
    amount: float
    total_amount: Optional[float] = None
    description: Optional[str] = "Сплит чека"

class SplitBillActionRequest(BaseModel):
    request_id: int
    sender_id: int

class QrPayRequest(BaseModel):
    sender_id: int
    target: str = Field(..., description="Номер карты или счёта из QR")
    amount: float
    description: Optional[str] = None

class NfcGenerateTokenRequest(BaseModel):
    sender_id: int
    max_amount: Optional[float] = 50000.0
    business_id: Optional[int] = None

class CloseBusinessRequest(BaseModel):
    user_id: int
    business_id: int

class AdminFactoryResetRequest(BaseModel):
    admin_id: Optional[int] = None
    admin_email: Optional[str] = None
    user_id: int

class NfcCancelTokenRequest(BaseModel):
    token: str
    sender_id: int

class NfcPayRequest(BaseModel):
    token: str = Field(..., description="Одноразовый защищённый токен из NFC метки клиента")
    target: str = Field(..., description="Номер карты или счёта терминала/продавца")
    amount: float
    terminal_name: Optional[str] = "Терминал КопиPay POS"
    description: Optional[str] = None

EMAIL_REGEX = re.compile(r"^[\w\.-]+@[\w\.-]+\.\w+$")

def verify_is_admin(admin_id: Optional[int] = None, admin_email: Optional[str] = None):
    if admin_id is not None:
        admin = get_user_by_id(admin_id)
        if admin:
            if admin["email"].lower().strip() == SUPER_ADMIN_EMAIL.lower() or admin.get("is_admin", 0) == 1:
                return admin
    if admin_email is not None and admin_email.lower().strip() == SUPER_ADMIN_EMAIL.lower():
        admin = get_user_by_email(admin_email)
        if admin:
            return admin
    super_admin = get_user_by_email(SUPER_ADMIN_EMAIL)
    if super_admin:
        return super_admin
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Доступ запрещён: требуются права Управляющего Банком."
    )

@app.get("/")
def root():
    return {
        "status": "online",
        "service": "Kopi Bank Server - God Edition",
        "version": "2.0.0",
        "docs": "/docs",
        "health": "/health"
    }

@app.get("/health")
def health_check():
    stats = get_bank_stats()
    return {
        "status": "ok",
        "service": "Kopi Bank Server - God Edition",
        "version": "2.0.0",
        "stats": stats
    }

@app.post("/api/auth/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(req: RegisterRequest):
    email = req.email.strip().lower()
    
    if not EMAIL_REGEX.match(email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Некорректный формат адреса электронной почты."
        )
    
    if req.password != req.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пароли не совпадают."
        )
    
    if len(req.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пароль должен содержать не менее 6 символов."
        )
    
    existing = get_user_by_email(email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь с таким email уже зарегистрирован."
        )
    
    try:
        user = create_user(
            email=email,
            password=req.password,
            full_name=req.full_name,
            phone_number=req.phone_number
        )
        return AuthResponse(
            success=True,
            message="Вы успешно зарегистрированы в Копи Банке!",
            user=UserResponse(**user)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка сервера при регистрации: {str(e)}"
        )

@app.post("/api/auth/login", response_model=AuthResponse)
def login(req: LoginRequest):
    email = req.email.strip().lower()
    user = get_user_by_email(email)
    
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль."
        )
        
    user_data = {
        "id": user["id"],
        "email": user["email"],
        "card_number": user["card_number"],
        "account_number": user["account_number"],
        "phone_number": user.get("phone_number"),
        "balance": user["balance"],
        "full_name": user["full_name"],
        "is_frozen": user.get("is_frozen", 0),
        "is_admin": user.get("is_admin", 0),
        "avatar_url": user.get("avatar_url"),
        "created_at": user["created_at"]
    }
    
    return AuthResponse(
        success=True,
        message="Вход успешно выполнен.",
        user=UserResponse(**user_data)
    )

@app.get("/api/users/lookup")
def lookup_recipient(target: str = Query(..., description="Номер карты, счёта, телефона или email")):
    user = find_user_by_target(target)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Получатель не найден."
        )
    biz_name = user.get("recipient_business_name")
    biz_type = user.get("recipient_business_type")
    full_title = f"{biz_type} «{biz_name}»" if biz_name else user["full_name"]

    return {
        "id": user["id"],
        "full_name": full_title,
        "business_name": biz_name,
        "business_type": biz_type,
        "business_id": user.get("recipient_business_id"),
        "card_number": user["card_number"],
        "account_number": user["account_number"],
        "phone_number": user.get("phone_number"),
        "avatar_url": user.get("avatar_url"),
        "is_frozen": user.get("is_frozen", 0)
    }

@app.get("/api/users/{user_id}", response_model=UserResponse)
def get_user(user_id: int):
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден."
        )
    return UserResponse(**user)

@app.post("/api/users/{user_id}/avatar", response_model=UserResponse)
def update_avatar_api(user_id: int, req: AvatarUploadRequest):
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден."
        )
    updated = update_user_avatar(user_id, req.avatar_url)
    return UserResponse(**updated)

@app.post("/api/transactions/split/create")
def create_split_api(req: SplitRequest):
    user = get_user_by_id(req.sender_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден.")
    
    payer_ids = []
    if req.participant_ids:
        payer_ids.extend([pid for pid in req.participant_ids if pid != req.sender_id])
    
    if req.participant_names:
        all_u = get_all_users()
        for name in req.participant_names:
            clean = name.strip().lower()
            for u in all_u:
                if u["id"] != req.sender_id and (u["full_name"].strip().lower() == clean or u["email"].strip().lower() == clean):
                    if u["id"] not in payer_ids:
                        payer_ids.append(u["id"])
                    break
                    
    if not payer_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Не выбраны участники сплита.")

    try:
        created = create_split_requests(
            creator_id=req.sender_id,
            payer_ids=payer_ids,
            amount_per_person=req.amount_per_person,
            total_amount=req.total_amount,
            description=req.description or "Сплит чека"
        )
        return {
            "success": True,
            "message": f"Запрос на разделение счёта ({req.amount_per_person:.2f} ₽ на человека) успешно отправлен {len(created)} участникам!",
            "sender_name": user["full_name"],
            "total_amount": req.total_amount,
            "amount_per_person": req.amount_per_person,
            "participant_names": req.participant_names or [c["payer_name"] for c in created],
            "requests": created
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@app.get("/api/transactions/split/pending")
def get_pending_splits_api(user_id: int = Query(..., description="ID пользователя")):
    return get_pending_split_requests(user_id)

@app.post("/api/transactions/split/pay")
def pay_split_api(req: SplitActionRequest):
    try:
        res = pay_split_request(split_id=req.split_id, payer_id=req.payer_id)
        return res
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@app.post("/api/transactions/split/decline")
def decline_split_api(req: SplitActionRequest):
    try:
        res = decline_split_request(split_id=req.split_id, payer_id=req.payer_id)
        return res
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@app.post("/api/transactions/transfer")
def transfer_api(req: TransferRequest):
    try:
        res = transfer_funds(
            sender_id=req.sender_id,
            target=req.target,
            amount=req.amount,
            tx_type="transfer",
            description=req.description,
            is_salary=req.is_salary or False,
            tax_rate=req.tax_rate or 0.0,
            business_id=req.business_id,
        )
        return {"success": True, "transaction": res}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.post("/api/transactions/qr/pay")
def qr_pay_api(req: QrPayRequest):
    try:
        res = transfer_funds(
            sender_id=req.sender_id,
            target=req.target,
            amount=req.amount,
            tx_type="qr",
            description=req.description or "Оплата по QR-коду"
        )
        return {"success": True, "transaction": res}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.post("/api/transactions/nfc/generate-token")
def nfc_generate_token_api(req: NfcGenerateTokenRequest):
    try:
        res = create_nfc_token(
            sender_id=req.sender_id,
            max_amount=req.max_amount or 50000.0,
            ttl_seconds=120,
            business_id=req.business_id
        )
        return {"success": True, **res}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.get("/api/transactions/nfc/token-status/{token}")
def nfc_token_status_api(token: str):
    token_info = get_nfc_token(token)
    if not token_info:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NFC токен не найден.")
    return {
        "success": True,
        "token": token_info["token"],
        "status": token_info["status"],
        "amount": token_info.get("amount"),
        "recipient_name": token_info.get("recipient_name"),
        "transaction_id": token_info.get("transaction_id"),
        "expires_at": token_info["expires_at"]
    }

@app.post("/api/transactions/nfc/cancel-token")
def nfc_cancel_token_api(req: NfcCancelTokenRequest):
    cancelled = cancel_nfc_token(req.token, req.sender_id)
    return {"success": True, "cancelled": cancelled}

@app.post("/api/transactions/nfc/pay")
def nfc_pay_api(req: NfcPayRequest):
    try:
        if req.amount <= 0:
            raise ValueError("Сумма платежа должна быть больше 0 ₽.")

        token_info = get_nfc_token(req.token)
        if not token_info:
            raise ValueError("NFC токен недействителен или не существует.")

        if token_info["status"] == "expired":
            raise ValueError("Время действия платёжной NFC-сессии истекло. Создайте новый платёж.")

        if token_info["status"] == "completed":
            raise ValueError("Этот NFC токен уже был использован для оплаты.")

        if token_info["status"] != "active":
            raise ValueError(f"NFC токен недоступен для оплаты (статус: {token_info['status']}).")

        if req.amount > token_info["max_amount"]:
            raise ValueError(f"Сумма превышает установленный лимит NFC ({token_info['max_amount']:.0f} ₽).")

        sender_id = token_info["sender_id"]
        sender_biz_id = token_info.get("business_id")

        desc = req.description.strip() if req.description and req.description.strip() else (
            f"Бесконтактная оплата NFC ({req.terminal_name})" if req.terminal_name else "Оплата КопиPay NFC"
        )
        res = transfer_funds(
            sender_id=sender_id,
            target=req.target,
            amount=req.amount,
            tx_type="nfc",
            description=desc,
            business_id=sender_biz_id
        )

        mark_nfc_token_used(
            token=req.token,
            transaction_id=res["transaction_id"],
            amount=req.amount,
            recipient_name=res["recipient_name"]
        )

        return {"success": True, "transaction": res}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.get("/api/transactions/history/{user_id}")
def transaction_history_api(user_id: int, limit: int = Query(50, ge=1, le=200)):
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден.")
    txs = get_user_transactions(user_id, limit=limit)
    return {"success": True, "transactions": txs}

@app.get("/api/admin/stats")
def admin_stats(admin_id: Optional[int] = Query(None), admin_email: Optional[str] = Query(None)):
    verify_is_admin(admin_id, admin_email)
    return get_bank_stats()

@app.get("/api/admin/users")
def admin_users_list(admin_id: Optional[int] = Query(None), admin_email: Optional[str] = Query(None)):
    verify_is_admin(admin_id, admin_email)
    users = get_all_users()
    return {"users": users}

@app.post("/api/admin/freeze")
def admin_freeze_user(req: AdminFreezeRequest):
    verify_is_admin(req.admin_id, req.admin_email)
    target_user = get_user_by_id(req.user_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден.")
    
    if target_user["email"].lower().strip() == SUPER_ADMIN_EMAIL.lower() and req.is_frozen:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нельзя заморозить счёт Управляющего Банком!")
        
    set_user_frozen(req.user_id, req.is_frozen)
    updated = get_user_by_id(req.user_id)
    return {
        "success": True,
        "message": f"Счёт {target_user['full_name']} {'заморожен' if req.is_frozen else 'разморожен'}.",
        "user": updated
    }

@app.post("/api/admin/credit")
def admin_credit_funds(req: AdminCreditRequest):
    verify_is_admin(req.admin_id, req.admin_email)
    try:
        res = admin_credit_user(
            user_id=req.user_id,
            amount=req.amount,
            sender_name=req.sender_name,
            description=req.description
        )
        return {
            "success": True,
            "message": f"Успешно начислено {req.amount:.2f} ₽ от «{req.sender_name}»",
            "result": res
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.post("/api/admin/debit")
def admin_debit_funds(req: AdminDebitRequest):
    verify_is_admin(req.admin_id, req.admin_email)
    try:
        res = admin_debit_user(
            user_id=req.user_id,
            amount=req.amount,
            reason=req.reason
        )
        return {
            "success": True,
            "message": f"Успешно списано {req.amount:.2f} ₽",
            "result": res
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.put("/api/admin/users/{user_id}")
def admin_update_user(user_id: int, req: AdminUpdateUserRequest):
    verify_is_admin(req.admin_id, req.admin_email)
    target_user = get_user_by_id(user_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден.")
        
    updates = {
        "full_name": req.full_name,
        "phone_number": req.phone_number,
        "card_number": req.card_number,
        "account_number": req.account_number,
        "email": req.email,
        "balance": req.balance,
    }
    updated = update_user_fields(user_id, updates)
    return {"success": True, "message": "Реквизиты успешно обновлены", "user": updated}

@app.delete("/api/admin/users/{user_id}")
def admin_delete_user(user_id: int, admin_id: Optional[int] = Query(None), admin_email: Optional[str] = Query(None)):
    verify_is_admin(admin_id, admin_email)
    target_user = get_user_by_id(user_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден.")
    if target_user["email"].lower().strip() == SUPER_ADMIN_EMAIL.lower():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нельзя удалить счёт главного Управляющего Банком!")
        
    deleted = delete_user_by_id(user_id)
    return {"success": deleted, "message": f"Счёт пользователя {target_user['full_name']} успешно удалён."}



@app.post("/api/user/pin")
def set_pin_api(req: SetPinRequest):
    try:
        success = set_user_pin(req.user_id, req.pin, enabled=req.enabled if req.enabled is not None else True)
        updated = get_user_by_id(req.user_id)
        return {"success": success, "message": "Пин-код успешно установлен!", "user": updated}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@app.post("/api/user/verify-pin")
def verify_pin_api(req: VerifyPinRequest):
    matched = verify_user_pin(req.user_id, req.pin)
    if not matched:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неверный пин-код.")
    return {"success": True, "message": "Пин-код подтверждён."}

@app.post("/api/user/toggle-pin")
def toggle_pin_api(req: TogglePinRequest):
    user = get_user_by_id(req.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден.")
    if req.enabled and not user.get("has_pin"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Сначала задайте пин-код.")
    if not req.enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Отключение защиты PIN-кодом возможно только через сброс администратором банка."
        )
    success = set_pin_enabled(req.user_id, req.enabled)
    updated = get_user_by_id(req.user_id)
    return {"success": success, "message": "Защита пин-кодом включена.", "user": updated}

@app.post("/api/admin/reset-pin")
def admin_reset_pin_api(req: AdminResetPinRequest):
    verify_is_admin(req.admin_id, req.admin_email)
    target_user = get_user_by_id(req.user_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден.")
    success = admin_reset_user_pin(req.user_id)
    updated = get_user_by_id(req.user_id)
    return {
        "success": success,
        "message": f"Пин-код пользователя {target_user['full_name']} успешно сброшен администратором.",
        "user": updated
    }

@app.post("/api/admin/user/factory-reset")
def admin_factory_reset_api(req: AdminFactoryResetRequest):
    verify_is_admin(req.admin_id, req.admin_email)
    try:
        res = admin_factory_reset_user(req.user_id)
        return {
            "success": True,
            "message": f"Счёт и профиль клиента {res['full_name']} полностью сброшены до заводских настроек.",
            "user": res
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))



@app.post("/api/business/apply")
def apply_business_api(req: BusinessApplyRequest):
    user = get_user_by_id(req.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден.")
    try:
        biz = apply_business_account(
            user_id=req.user_id,
            company_name=req.company_name,
            business_type=req.business_type,
            tax_rate=req.tax_rate or 13.0,
        )
        return {
            "success": True,
            "message": f"Госпошлина успешно оплачена! Заявка на регистрацию {req.business_type} «{req.company_name}» передана на рассмотрение управляющему.",
            "business": biz,
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@app.post("/api/business/close")
def close_business_api(req: CloseBusinessRequest):
    try:
        res = close_business(user_id=req.user_id, business_id=req.business_id)
        return res
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.get("/api/business/my")
def get_my_businesses_api(user_id: int = Query(...)):
    return get_user_business_accounts(user_id)

@app.get("/api/admin/businesses")
def admin_get_businesses_api(admin_id: Optional[int] = Query(None), admin_email: Optional[str] = Query(None)):
    verify_is_admin(admin_id, admin_email)
    return admin_get_all_businesses()

@app.post("/api/admin/business/action")
def admin_business_action_api(req: AdminBusinessActionRequest):
    verify_is_admin(req.admin_id, req.admin_email)
    act = req.action.lower()
    if act == "approve":
        admin_update_business_status(req.business_id, "approved", req.admin_comment or "Одобрено администратором")
        return {"success": True, "message": "Организация успешно зарегистрирована и активирована!"}
    elif act == "reject":
        admin_update_business_status(req.business_id, "rejected", req.admin_comment or "Отклонено администратором")
        return {"success": True, "message": "Заявка отклонена."}
    elif act == "approve_close":
        res = admin_approve_business_closure(req.business_id, req.admin_comment)
        return res
    elif act == "reject_close":
        res = admin_reject_business_closure(req.business_id, req.admin_comment)
        return res
    elif act == "freeze":
        admin_update_business_status(req.business_id, "frozen", req.admin_comment or "Заморожено администратором")
        return {"success": True, "message": "Счёт организации заморожен."}
    elif act == "unfreeze":
        admin_update_business_status(req.business_id, "approved", req.admin_comment or "Разморожено администратором")
        return {"success": True, "message": "Счёт организации разморожен."}
    elif act == "edit":
        admin_update_business_details(
            req.business_id,
            company_name=req.company_name,
            tax_rate=req.tax_rate,
            balance=req.balance,
            status=req.status,
        )
        return {"success": True, "message": "Параметры организации обновлены."}
    elif act == "delete":
        admin_delete_business(req.business_id)
        return {"success": True, "message": "Бизнес-аккаунт удалён."}
    elif act == "create":
        if not req.user_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Укажите ID владельца бизнеса.")
        biz = admin_create_business(
            user_id=req.user_id,
            company_name=req.company_name or "Новый бизнес",
            business_type=req.business_type or "ИП",
            tax_rate=req.tax_rate or 13.0,
            balance=req.balance or 0.0,
        )
        return {"success": True, "message": "Бизнес-аккаунт успешно открыт и одобрен администратором!", "business": biz}
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Неизвестное действие: {req.action}")



@app.post("/api/credits/apply")
def apply_credit_api(req: CreditApplyRequest):
    user = get_user_by_id(req.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден.")
    try:
        credit = apply_credit(
            user_id=req.user_id,
            title=req.title or "Кредит наличными",
            amount=req.amount,
            interest_rate=req.interest_rate or 14.9,
            term_months=req.term_months or 12,
            payment_type=req.payment_type or "annuity",
        )
        return {
            "success": True,
            "message": f"Кредит на сумму {req.amount:.0f} ₽ успешно выдан и зачислен на счет.",
            "credit": credit,
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@app.get("/api/credits/my")
def get_my_credits_api(user_id: int = Query(...)):
    return get_user_credits(user_id)

@app.get("/api/admin/credits")
def admin_get_credits_api(admin_id: Optional[int] = Query(None), admin_email: Optional[str] = Query(None)):
    verify_is_admin(admin_id, admin_email)
    return admin_get_all_credits()

@app.post("/api/admin/credit/action")
def admin_credit_action_api(req: AdminCreditActionRequest):
    verify_is_admin(req.admin_id, req.admin_email)
    act = req.action.lower()
    if act == "create":
        if not req.user_id or not req.amount:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Укажите пользователя и сумму кредита.")
        credit = admin_create_credit(
            user_id=req.user_id,
            title=req.title or "Кредит от Банка",
            amount=req.amount,
            interest_rate=req.interest_rate or 14.9,
            term_months=req.term_months or 12,
        )
        return {"success": True, "message": f"Кредит на сумму {req.amount:.0f} ₽ успешно выдан!", "credit": credit}
    
    if not req.credit_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Не указан ID кредита.")

    if act == "approve":
        credit = issue_pending_credit(req.credit_id)
        return {
            "success": True,
            "message": "Кредит одобрен и средства зачислены.",
            "credit": credit,
        }
    elif act == "reject":
        admin_update_credit(req.credit_id, status="rejected")
        return {"success": True, "message": "Заявка на кредит отклонена."}
    elif act == "freeze":
        admin_update_credit(req.credit_id, status="frozen")
        return {"success": True, "message": "Кредит заморожен."}
    elif act == "unfreeze":
        admin_update_credit(req.credit_id, status="active")
        return {"success": True, "message": "Кредит разморожен."}
    elif act == "edit":
        admin_update_credit(
            req.credit_id,
            remaining_amount=req.remaining_amount,
            interest_rate=req.interest_rate,
            monthly_payment=req.monthly_payment,
            status=req.status,
        )
        return {"success": True, "message": "Параметры кредита успешно обновлены."}
    elif act == "delete":
        admin_delete_credit(req.credit_id)
        return {"success": True, "message": "Кредит удалён."}
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Неизвестное действие: {req.action}")



@app.post("/api/deposits/apply")
def apply_deposit_api(req: DepositApplyRequest):
    user = get_user_by_id(req.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден.")
    try:
        deposit = apply_deposit(
            user_id=req.user_id,
            title=req.title or "КопиВклад",
            amount=req.amount,
            interest_rate=req.interest_rate or 16.0,
            term_months=req.term_months or 6,
        )
        return {
            "success": True,
            "message": f"Вклад на сумму {req.amount:.0f} ₽ успешно открыт. Средства списаны с основного счета.",
            "deposit": deposit,
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@app.get("/api/deposits/my")
def get_my_deposits_api(user_id: int = Query(...)):
    return get_user_deposits(user_id)

@app.get("/api/admin/deposits")
def admin_get_deposits_api(admin_id: Optional[int] = Query(None), admin_email: Optional[str] = Query(None)):
    verify_is_admin(admin_id, admin_email)
    return admin_get_all_deposits()

@app.post("/api/admin/deposit/action")
def admin_deposit_action_api(req: AdminDepositActionRequest):
    verify_is_admin(req.admin_id, req.admin_email)
    act = req.action.lower()
    if act == "create":
        if not req.user_id or not req.amount:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Укажите пользователя и сумму вклада.")
        deposit = admin_create_deposit(
            user_id=req.user_id,
            title=req.title or "КопиВклад Премиум",
            amount=req.amount,
            interest_rate=req.interest_rate or 16.0,
            term_months=req.term_months or 6,
        )
        return {"success": True, "message": f"Вклад на сумму {req.amount:.0f} ₽ успешно открыт!", "deposit": deposit}
        
    if not req.deposit_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Не указан ID вклада.")

    if act == "approve":
        deposit = fund_pending_deposit(req.deposit_id)
        return {
            "success": True,
            "message": "Вклад открыт, основная сумма списана.",
            "deposit": deposit,
        }
    elif act == "reject":
        admin_update_deposit(req.deposit_id, status="rejected")
        return {"success": True, "message": "Заявка на вклад отклонена."}
    elif act == "freeze":
        admin_update_deposit(req.deposit_id, status="frozen")
        return {"success": True, "message": "Вклад заморожен."}
    elif act == "unfreeze":
        admin_update_deposit(req.deposit_id, status="active")
        return {"success": True, "message": "Вклад разморожен."}
    elif act == "edit":
        admin_update_deposit(
            req.deposit_id,
            amount=req.amount,
            interest_rate=req.interest_rate,
            earned_amount=req.earned_amount,
            status=req.status,
        )
        return {"success": True, "message": "Параметры вклада обновлены."}
    elif act == "delete":
        admin_delete_deposit(req.deposit_id)
        return {"success": True, "message": "Вклад удалён."}
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Неизвестное действие: {req.action}")


@app.post("/api/finance/tick")
def finance_tick_api(req: FinanceTickRequest):
    user = get_user_by_id(req.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден.")
    try:
        snapshot = run_finance_tick(req.user_id)
        return {"success": True, **snapshot}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

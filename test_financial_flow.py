import os
import sys
import unittest

if "server" not in sys.path:
    sys.path.append("server")
import db

class TestFinancialFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.orig_db_path = db.DB_PATH
        cls.test_db_path = os.path.join(os.path.dirname(__file__), "test_financial_scratch.db")
        if os.path.exists(cls.test_db_path):
            try:
                os.remove(cls.test_db_path)
            except Exception:
                pass
        db.DB_PATH = cls.test_db_path
        db.init_db()

    @classmethod
    def tearDownClass(cls):
        db.DB_PATH = cls.orig_db_path
        if os.path.exists(cls.test_db_path):
            try:
                os.remove(cls.test_db_path)
            except Exception:
                pass

    def test_full_financial_lifecycle(self):
        test_email = f"tester_{os.urandom(4).hex()}@kopi.ru"
        user = db.create_user(
            email=test_email,
            password="testpassword123",
            full_name="Тестовый Клиент",
            phone_number=db.generate_phone_number()
        )
        user_id = user["id"]
        self.assertEqual(user["credit_score"], 650)
        
        db.admin_credit_user(user_id, 100000.0, "Стартовый капитал")
        user = db.get_user_by_id(user_id)
        self.assertEqual(user["balance"], 100000.0)

        # 1. Deposit lifecycle & Admin delete refund
        dep = db.apply_deposit(user_id, "Вклад", 20000.0, 16.0, 6)
        self.assertEqual(dep["status"], "pending")
        funded = db.fund_pending_deposit(dep["id"])
        self.assertEqual(funded["status"], "active")
        self.assertEqual(db.get_user_by_id(user_id)["balance"], 80000.0)

        # Admin delete deposit refund -> balance back to 100000
        db.admin_delete_deposit(dep["id"])
        self.assertEqual(db.get_user_by_id(user_id)["balance"], 100000.0)

        # 2. Credit lifecycle & Admin delete deduction
        cred = db.apply_credit(user_id, "Кредит", 50000.0, 15.0, 12)
        self.assertEqual(cred["status"], "pending")
        db.issue_pending_credit(cred["id"])
        self.assertEqual(db.get_user_by_id(user_id)["balance"], 150000.0)

        # Admin delete credit deduction -> balance back to 100000
        db.admin_delete_credit(cred["id"])
        self.assertEqual(db.get_user_by_id(user_id)["balance"], 100000.0)

        # 3. Early close deposit
        dep2 = db.apply_deposit(user_id, "Вклад 2", 30000.0, 16.0, 6)
        db.fund_pending_deposit(dep2["id"])
        db.close_user_deposit(user_id, dep2["id"])
        self.assertEqual(db.get_user_by_id(user_id)["balance"], 100000.0)

        # 4. Early repay credit with interest
        cred2 = db.apply_credit(user_id, "Кредит 2", 20000.0, 10.0, 6)
        db.issue_pending_credit(cred2["id"])
        db.repay_user_credit(user_id, cred2["id"])
        # Списана сумма кредита с процентами (20587.38 ₽ вместо 20000 ₽)
        self.assertEqual(db.get_user_by_id(user_id)["balance"], 99412.62)

        # 4.1 Business withdrawal with 2% commission
        biz = db.apply_business_account(user_id, "ООО Ромашка", "ООО", 13.0)
        db.admin_update_business_status(biz["id"], "approved")
        # Top up business
        conn = db.get_connection()
        conn.cursor().execute("UPDATE business_accounts SET balance = 50000 WHERE id = ?", (biz["id"],))
        conn.commit()
        conn.close()
        withdraw_res = db.withdraw_business_to_personal(user_id, biz["id"], 10000.0, 2.0)
        self.assertEqual(withdraw_res["commission_amount"], 200.0)
        self.assertEqual(withdraw_res["net_amount"], 9800.0)
        self.assertEqual(withdraw_res["new_business_balance"], 40000.0)
        # 99412.62 - 4000 (госпошлина ООО) + 9800 (вывод дохода) = 105212.62
        self.assertEqual(db.get_user_by_id(user_id)["balance"], round(99412.62 - 4000.0 + 9800.0, 2))

        # 5. Commissions
        recip = db.create_user(f"recip_{os.urandom(4).hex()}@kopi.ru", "testpassword123", "Получатель")
        qr_tx = db.transfer_funds(sender_id=user_id, target=recip["email"], amount=10000.0, tx_type="qr")
        self.assertEqual(qr_tx["commission_amount"], 100.0)

        nfc_tx = db.transfer_funds(sender_id=user_id, target=recip["email"], amount=20000.0, tx_type="nfc")
        self.assertEqual(nfc_tx["commission_amount"], 400.0)

        # 6. History clearing & Audit
        self.assertGreater(len(db.get_user_transactions(user_id)), 0)
        db.clear_user_history(user_id)
        self.assertEqual(len(db.get_user_transactions(user_id)), 0)
        self.assertGreater(len(db.admin_get_user_full_transactions(user_id)), 0)

        # 7. Credit block
        db.admin_adjust_user_credit_score(1, user_id, -300, "Штраф")
        with self.assertRaises(ValueError):
            db.apply_credit(user_id, "Блок", 10000.0)

        print("\n[+] ALL FINANCIAL FLOW TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    unittest.main()

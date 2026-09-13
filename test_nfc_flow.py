import unittest
from fastapi.testclient import TestClient
from main import app
from db import init_db, get_all_users, get_user_by_id, admin_credit_user

class TestNfcPaymentFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)
        users = get_all_users()
        if len(users) < 2:
            raise RuntimeError("Need at least 2 users in db for tests")
        cls.payer = users[0]
        cls.merchant = users[1]
        
        admin_credit_user(cls.payer["id"], 5000.0, "Центробанк")

    def test_full_nfc_flow_and_security(self):
        payer_id = self.payer["id"]
        merchant_card = self.merchant["card_number"]
        
        fake_pay_res = self.client.post("/api/transactions/nfc/pay", json={
            "token": "fake_stolen_token_12345",
            "target": merchant_card,
            "amount": 100.0,
            "terminal_name": "Test POS"
        })
        self.assertEqual(fake_pay_res.status_code, 400)
        self.assertIn("NFC токен недействителен", fake_pay_res.json()["detail"])
        print("[+] Negative Test Passed: Unauthorized deduction without valid token was rejected!")

        gen_res = self.client.post("/api/transactions/nfc/generate-token", json={
            "sender_id": payer_id,
            "max_amount": 2000.0
        })
        self.assertEqual(gen_res.status_code, 200)
        gen_data = gen_res.json()
        token = gen_data["token"]
        short_code = gen_data["short_code"]
        self.assertTrue(token.startswith("sber_nfc_"))
        self.assertEqual(len(short_code), 6)
        print(f"[+] Token Generated: {token} (Short Code: {short_code})")

        status_res = self.client.get(f"/api/transactions/nfc/token-status/{token}")
        self.assertEqual(status_res.status_code, 200)
        self.assertEqual(status_res.json()["status"], "active")
        print("[+] Token Status is Active")

        pay_amount = 350.0
        pay_res = self.client.post("/api/transactions/nfc/pay", json={
            "token": token,
            "target": merchant_card,
            "amount": pay_amount,
            "terminal_name": "SberPay POS • Тест",
            "description": "Тестовая покупка"
        })
        if pay_res.status_code != 200:
            print("PAY ERROR:", pay_res.status_code, pay_res.text)
        self.assertEqual(pay_res.status_code, 200)
        tx = pay_res.json()["transaction"]
        self.assertEqual(tx["amount"], pay_amount)
        print(f"[+] NFC Payment Succeeded! Transaction ID: {tx['transaction_id']}")

        replay_res = self.client.post("/api/transactions/nfc/pay", json={
            "token": token,
            "target": merchant_card,
            "amount": pay_amount,
            "terminal_name": "SberPay POS • Тест"
        })
        self.assertEqual(replay_res.status_code, 400)
        self.assertIn("уже был использован", replay_res.json()["detail"])
        print("[+] Negative Test Passed: Token replay attack was rejected!")

        status_after = self.client.get(f"/api/transactions/nfc/token-status/{token}")
        self.assertEqual(status_after.status_code, 200)
        self.assertEqual(status_after.json()["status"], "completed")
        self.assertEqual(status_after.json()["amount"], pay_amount)
        print("[+] Payer polling detected status = COMPLETED")

        gen2 = self.client.post("/api/transactions/nfc/generate-token", json={
            "sender_id": payer_id,
            "max_amount": 1000.0
        }).json()
        code2 = gen2["short_code"]
        pay2 = self.client.post("/api/transactions/nfc/pay", json={
            "token": code2,
            "target": merchant_card,
            "amount": 200.0,
            "terminal_name": "SberPay POS • Эмулятор"
        })
        self.assertEqual(pay2.status_code, 200)
        print("[+] Short code payment passed!")

if __name__ == "__main__":
    unittest.main()

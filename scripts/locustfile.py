import random
import time
import requests
from locust import HttpUser, task, between, tag, events

PAYMENT_METHODS = ["card", "kakaopay", "naverpay", "tosspay", "bank_transfer"]

class APIUser(HttpUser):
    host = "http://localhost:8000"
    wait_time = between(0.3, 1.0)
    shared_token = None

    def on_start(self):
        for _ in range(100):
            if APIUser.shared_token:
                break
            time.sleep(0.05)
        self.token = APIUser.shared_token

    def _auth(self):
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    def _extract_results(self, data):
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            results = data.get("results")
            if isinstance(results, list):
                return results
            return []
        return []

    def _rand_limit(self):
        return random.randint(1, 100)

    def _rand_offset(self, limit):
        return random.choice([0, limit, limit * 2, limit * 3])

    def _rand_page(self):
        candidates = list(range(1, 11)) + [50, 100, 200, 500, 1000, 2000, 5000, 7000, 9000]
        return random.choice(candidates)

    @tag("courses_list")
    @task
    def courses_list_default(self):
        if not self.token:
            return
        self.client.get("/courses", headers=self._auth(), name="courses:list:default")

    @tag("courses_available")
    @task
    def courses_list_available(self):
        if not self.token:
            return
        self.client.get("/courses?status=available", headers=self._auth(), name="courses:list:available")

    @tag("courses_popular")
    @task
    def courses_list_popular(self):
        if not self.token:
            return
        self.client.get("/courses?sort=popular", headers=self._auth(), name="courses:list:popular")

    @tag("courses_available_popular")
    @task
    def courses_list_available_popular(self):
        if not self.token:
            return
        self.client.get("/courses?status=available&sort=popular", headers=self._auth(), name="courses:list:available_popular")

    @tag("courses_paged")
    @task
    def courses_list_paged(self):
        if not self.token:
            return
        limit = self._rand_limit()
        page = self._rand_page()
        self.client.get(f"/courses?limit={limit}&page={page}", headers=self._auth(), name="courses:list:paged")

    @tag("courses_cursor_walk")
    @task
    def courses_cursor_walk(self):
        if not self.token:
            return
        limit = self._rand_limit()
        r = self.client.get(f"/courses?limit={limit}", headers=self._auth(), name="courses:list:cursor:first")
        if r.status_code != 200:
            return
        try:
            data = r.json()
            hops = 0
            next_url = data.get("next")
            while next_url and hops < 3:
                path = next_url.replace("http://localhost:8000", "")
                r = self.client.get(path, headers=self._auth(), name="courses:list:cursor:next")
                if r.status_code != 200:
                    break
                data = r.json()
                next_url = data.get("next")
                hops += 1
        except Exception:
            pass

    @tag("tests_list")
    @task
    def tests_list_default(self):
        if not self.token:
            return
        self.client.get("/tests", headers=self._auth(), name="tests:list:default")

    @tag("tests_available")
    @task
    def tests_list_available(self):
        if not self.token:
            return
        self.client.get("/tests?status=available", headers=self._auth(), name="tests:list:available")

    @tag("tests_popular")
    @task
    def tests_list_popular(self):
        if not self.token:
            return
        self.client.get("/tests?sort=popular", headers=self._auth(), name="tests:list:popular")

    @tag("tests_available_popular")
    @task
    def tests_list_available_popular(self):
        if not self.token:
            return
        self.client.get("/tests?status=available&sort=popular", headers=self._auth(), name="tests:list:available_popular")

    @tag("tests_paged")
    @task
    def tests_list_paged(self):
        if not self.token:
            return
        limit = self._rand_limit()
        page = self._rand_page()
        self.client.get(f"/tests?limit={limit}&page={page}", headers=self._auth(), name="tests:list:paged")

    @tag("tests_cursor_walk")
    @task
    def tests_cursor_walk(self):
        if not self.token:
            return
        limit = self._rand_limit()
        r = self.client.get(f"/tests?limit={limit}", headers=self._auth(), name="tests:list:cursor:first")
        if r.status_code != 200:
            return
        try:
            data = r.json()
            hops = 0
            next_url = data.get("next")
            while next_url and hops < 3:
                path = next_url.replace("http://localhost:8000", "")
                r = self.client.get(path, headers=self._auth(), name="tests:list:cursor:next")
                if r.status_code != 200:
                    break
                data = r.json()
                next_url = data.get("next")
                hops += 1
        except Exception:
            pass

    @events.test_start.add_listener
    def _get_shared_token(environment, **kwargs):
        base_url = getattr(environment, "host", None) or getattr(getattr(environment, "runner", None), "host", None)
        if not base_url:
            base_url = "http://localhost:8000"
        base_url = base_url.rstrip("/")

        if APIUser.shared_token:
            return

        email = f"lo_{random.randint(10_000_000,99_999_999)}@example.com"
        password = "Passw0rd!1"

        try:
            sr = requests.post(f"{base_url}/signup", json={"email": email, "password": password}, timeout=5)
            if sr.status_code >= 400 and sr.status_code not in (400, 409):
                print(f"[locust] signup failed {sr.status_code}: {sr.text}")
        except Exception as e:
            print(f"[locust] signup error: {e}")

        try:
            token = None
            for _ in range(10):
                r = requests.post(f"{base_url}/login", json={"email": email, "password": password}, timeout=5)
                if r.status_code == 200:
                    token = r.json().get("access")
                    break
                time.sleep(0.2)
            if token:
                APIUser.shared_token = token
                print("[locust] shared token acquired")
                try:
                    headers = {"Authorization": f"Bearer {token}"}
                    requests.get(f"{base_url}/courses", headers=headers, timeout=5)
                    requests.get(f"{base_url}/tests", headers=headers, timeout=5)
                except Exception:
                    pass
            else:
                print(f"[locust] login failed: status={r.status_code}")
        except Exception as e:
            print(f"[locust] login error: {e}")
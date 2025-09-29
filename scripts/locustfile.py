import random
from locust import HttpUser, task, between, tag

PAYMENT_METHODS = ["card", "kakaopay", "naverpay", "tosspay", "bank_transfer"]

class APIUser(HttpUser):
    host = "http://localhost:8000"
    wait_time = between(0.3, 1.0)

    def on_start(self):
        self.email = f"lo_{random.randint(10_000_000,99_999_999)}@example.com"
        self.password = "Passw0rd!1"
        self.token = None

        sr = self.client.post("/signup", json={"email": self.email, "password": self.password}, name="auth:signup:init")
        if sr.status_code >= 400:
            print(f"[locust] signup failed {sr.status_code}: {sr.text}")
        r = self.client.post("/login", json={"email": self.email, "password": self.password}, name="auth:login:init")
        if r.status_code == 200:
            self.token = r.json().get("access")
        else:
            print(f"[locust] login failed {r.status_code}: {r.text}")

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


    @tag("courses_list")
    @task
    def courses_list_default(self):
        self.client.get("/courses", headers=self._auth(), name="courses:list:default")

    @tag("courses_available")
    @task
    def courses_list_available(self):
        self.client.get("/courses?status=available", headers=self._auth(), name="courses:list:available")

    @tag("courses_popular")
    @task
    def courses_list_popular(self):
        self.client.get("/courses?sort=popular", headers=self._auth(), name="courses:list:popular")

    @tag("courses_available_popular")
    @task
    def courses_list_available_popular(self):
        self.client.get("/courses?status=available&sort=popular", headers=self._auth(), name="courses:list:available_popular")

    @tag("courses_paged")
    @task
    def courses_list_paged(self):
        limit = self._rand_limit()
        offset = self._rand_offset(limit)
        self.client.get(f"/courses?limit={limit}&offset={offset}", headers=self._auth(), name="courses:list:paged")
        
    @tag("tests_list")
    @task
    def tests_list_default(self):
        self.client.get("/tests", headers=self._auth(), name="tests:list:default")

    @tag("tests_available")
    @task
    def tests_list_available(self):
        self.client.get("/tests?status=available", headers=self._auth(), name="tests:list:available")

    @tag("tests_popular")
    @task
    def tests_list_popular(self):
        self.client.get("/tests?sort=popular", headers=self._auth(), name="tests:list:popular")

    @tag("tests_available_popular")
    @task
    def tests_list_available_popular(self):
        self.client.get("/tests?status=available&sort=popular", headers=self._auth(), name="tests:list:available_popular")

    @tag("tests_paged")
    @task
    def tests_list_paged(self):
        limit = self._rand_limit()
        offset = self._rand_offset(limit)
        self.client.get(f"/tests?limit={limit}&offset={offset}", headers=self._auth(), name="tests:list:paged")

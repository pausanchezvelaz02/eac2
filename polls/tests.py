import datetime
import shutil

from django.contrib.auth.models import User
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import TestCase
from django.utils import timezone
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.support.ui import Select, WebDriverWait

from .models import Question

QUESTION_ONE = "Quin es el millor sistema operatiu?"
QUESTION_TWO = "Quin es el millor llenguatge de programacio?"
PERMISSION_LABEL = "Polls | question | Can view question"
STAFF_USERNAME = "viewer"
STAFF_PASSWORD = "Zebra2026Pass!"


def create_webdriver():
    chrome_binary = (
        shutil.which("google-chrome")
        or shutil.which("google-chrome-stable")
        or shutil.which("chromium")
        or shutil.which("chromium-browser")
    )
    if chrome_binary:
        options = ChromeOptions()
        options.binary_location = chrome_binary
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1280,1024")
        return webdriver.Chrome(options=options)
    options = FirefoxOptions()
    options.add_argument("-headless")
    return webdriver.Firefox(options=options)


class QuestionModelTests(TestCase):

    def test_question_str(self):
        question = Question.objects.create(
            question_text="Prova", pub_date=timezone.now()
        )
        self.assertEqual(str(question), "Prova")

    def test_was_published_recently(self):
        recent = Question.objects.create(
            question_text="Recent", pub_date=timezone.now()
        )
        old = Question.objects.create(
            question_text="Antiga",
            pub_date=timezone.now() - datetime.timedelta(days=2),
        )
        self.assertTrue(recent.was_published_recently())
        self.assertFalse(old.was_published_recently())


class MySeleniumTests(StaticLiveServerTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.selenium = create_webdriver()
        cls.selenium.implicitly_wait(5)
        user = User.objects.create_user("isard", "isard@isardvdi.com", "pirineus")
        user.is_superuser = True
        user.is_staff = True
        user.save()

    @classmethod
    def tearDownClass(cls):
        cls.selenium.quit()
        super().tearDownClass()

    def login(self, username, password):
        self.selenium.get(f"{self.live_server_url}/admin/login/")
        self.selenium.find_element(By.ID, "id_username").send_keys(username)
        self.selenium.find_element(By.ID, "id_password").send_keys(password)
        self.selenium.find_element(By.CSS_SELECTOR, "input[type=submit]").click()
        WebDriverWait(self.selenium, 10).until(
            lambda driver: "/admin/login/" not in driver.current_url
        )

    def logout(self):
        selenium = self.selenium
        previous_url = selenium.current_url
        selenium.find_element(By.XPATH, "//button[text()='Log out']").click()
        WebDriverWait(selenium, 10).until(
            lambda driver: driver.current_url != previous_url
        )

    def create_question(self, text):
        selenium = self.selenium
        selenium.get(f"{self.live_server_url}/admin/polls/question/add/")
        selenium.find_element(By.ID, "id_question_text").send_keys(text)
        selenium.find_element(By.XPATH, "//summary[contains(., 'Date information')]"
        ).click()
        WebDriverWait(selenium, 10).until(
            lambda driver: driver.find_element(By.ID, "id_pub_date_0").is_displayed()
        )
        selenium.find_element(By.ID, "id_pub_date_0").send_keys("2026-11-04")
        selenium.find_element(By.ID, "id_pub_date_1").send_keys("12:00:00")
        selenium.find_element(By.ID, "id_choice_set-0-choice_text").send_keys(
            "Primera opcio"
        )
        selenium.find_element(By.ID, "id_choice_set-1-choice_text").send_keys(
            "Segona opcio"
        )
        selenium.find_element(By.NAME, "_save").click()
        WebDriverWait(selenium, 10).until(
            lambda driver: driver.current_url.endswith("/admin/polls/question/")
        )

    def create_staff_user(self):
        selenium = self.selenium
        selenium.get(f"{self.live_server_url}/admin/auth/user/add/")
        selenium.find_element(By.ID, "id_username").send_keys(STAFF_USERNAME)
        selenium.find_element(By.ID, "id_password1").send_keys(STAFF_PASSWORD)
        selenium.find_element(By.ID, "id_password2").send_keys(STAFF_PASSWORD)
        selenium.find_element(By.NAME, "_continue").click()
        WebDriverWait(selenium, 10).until(
            lambda driver: driver.current_url.endswith("/change/")
        )
        selenium.find_element(By.ID, "id_is_staff").click()
        permissions = Select(selenium.find_element(By.ID, "id_user_permissions_from"))
        permissions.select_by_visible_text(PERMISSION_LABEL)
        selenium.find_element(By.ID, "id_user_permissions_add").click()
        chosen = Select(selenium.find_element(By.ID, "id_user_permissions_to"))
        self.assertIn(PERMISSION_LABEL, [option.text for option in chosen.options])
        self.assertTrue(selenium.find_element(By.ID, "id_is_staff").is_selected())
        selenium.find_element(By.NAME, "_save").click()
        WebDriverWait(selenium, 10).until(
            lambda driver: driver.current_url.endswith("/admin/auth/user/")
        )
        selenium.find_element(By.XPATH, f"//a[text()='{STAFF_USERNAME}']")

    def test_staff_user_can_view_questions_but_cannot_create_or_delete(self):
        selenium = self.selenium
        self.login("isard", "pirineus")
        self.create_question(QUESTION_ONE)
        self.create_question(QUESTION_TWO)
        self.create_staff_user()
        self.logout()
        self.login(STAFF_USERNAME, STAFF_PASSWORD)

        selenium.get(f"{self.live_server_url}/admin/")
        selenium.find_element(
            By.XPATH, "//a[contains(@href, '/admin/polls/question/')]"
        )

        selenium.get(f"{self.live_server_url}/admin/polls/question/")
        selenium.find_element(By.XPATH, f"//a[text()='{QUESTION_ONE}']")
        selenium.find_element(By.XPATH, f"//a[text()='{QUESTION_TWO}']")

        try:
            selenium.find_element(By.XPATH, "//a[text()='Add question']")
            self.fail("Trobat element 'Add question' que no hi ha de ser")
        except NoSuchElementException:
            pass

        try:
            selenium.find_element(By.NAME, "_selected_action")
            self.fail("Trobades caselles de seleccio que no hi han de ser")
        except NoSuchElementException:
            pass

        selenium.get(f"{self.live_server_url}/admin/polls/question/add/")
        self.assertIn("403", selenium.find_element(By.TAG_NAME, "h1").text)

        selenium.get(f"{self.live_server_url}/admin/polls/question/")
        change_url = selenium.find_element(
            By.XPATH, f"//a[text()='{QUESTION_ONE}']"
        ).get_attribute("href")
        selenium.get(change_url)

        try:
            selenium.find_element(By.NAME, "_save")
            self.fail("Trobat boto 'Save' que no hi ha de ser")
        except NoSuchElementException:
            pass

        try:
            selenium.find_element(By.XPATH, "//a[text()='Delete']")
            self.fail("Trobat enllaç 'Delete' que no hi ha de ser")
        except NoSuchElementException:
            pass

        try:
            selenium.find_element(By.ID, "id_question_text")
            self.fail("Trobat camp editable 'question_text' que no hi ha de ser")
        except NoSuchElementException:
            pass

        self.assertIn(QUESTION_ONE, selenium.page_source)

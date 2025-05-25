from playwright.sync_api import BrowserContext, sync_playwright, Page
from playwright_recaptcha import recaptchav2, RecaptchaNotFoundError, RecaptchaRateLimitError

def main(user_id, user_pw, code, language, problem, capsolver_key):
    with sync_playwright() as playwright:
        global browser, context
        browser = playwright.firefox.launch(headless=True)
        context = browser.new_context(locale='en-US')
        context.set_default_timeout(300000)
        return run(context, user_id, user_pw, code, language, problem, capsolver_key)


def login(page: Page, user_id: str, user_pw: str, capsolver_key:str, is_first: bool):
    print('navigating to login page...')

    if is_first:
        print('(might take long, due to browser setup)')
    page.goto("https://www.acmicpc.net/login")
    print('success!\n')

    print('submitting login info...')

    page.fill('[name=login_user_id]', user_id)
    page.fill('[name=login_password]', user_pw)
    page.click('[id=submit_button]')

    print('success!\n')

    try:
        if is_first:
            with recaptchav2.SyncSolver(page) as solver:
                print('trying captcha...')
                solver.solve_recaptcha(wait=True, wait_timeout=10)
        else:
            with recaptchav2.SyncSolver(page, capsolver_api_key=capsolver_key) as solver:
                print('retrying captcha with image...')
                solver.solve_recaptcha(wait=True, wait_timeout=10, image_challenge=True)

        print('success!\n')

    except RecaptchaNotFoundError:
        print('success! no captcha found.\n')

    except RecaptchaRateLimitError as e:
        if is_first:
            print('rate limit, retry with image.\n')
            login(page, user_id, user_pw, is_first=False)
        else:
            print('retry also failed.\n')
            raise e

    except Exception as e:
        if 'detached' in str(e):
            print('success! no captcha found. (detached)\n')
        else:
            raise e


def run(ctx: BrowserContext, user_id: str, user_pw: str, code: str, language: str, problem: str, capsolver_key: str):
    try:
        page = ctx.new_page()
        login(page, user_id, user_pw, capsolver_key, is_first=True)

        print('waiting home page to load...')
        page.wait_for_url("https://www.acmicpc.net/")
        print('success!\n')

        print('navigating to submit page...')
        page.goto(f'https://www.acmicpc.net/submit/{problem}')
        print('success!\n')

        print("selecting language...")

        page.click("#language_chosen")  # 드롭다운 클릭
        page.click(f"//li[text()='{language}']")  # 해당 언어 선택

        print('submitting answer...')
        page.evaluate('code => document.querySelector(".CodeMirror").CodeMirror.setValue(code)', code)

        page.click('[id=submit_button]')

        print('success!\n')

        print('waiting for result...')
        result_row = page.locator(
            '#status-table tbody tr:first-child .result-text:not(.result-wait, .result-compile, .result-judging)'
        )
        result = result_row.text_content()

        print('success!\n')

        if '맞았습니다' in result:
            return result, True
        else:
            return result, False

    finally:
        context.close()
        browser.close()



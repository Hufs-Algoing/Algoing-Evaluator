from playwright.async_api import async_playwright, BrowserContext, Page
from playwright_recaptcha import recaptchav2, RecaptchaNotFoundError, RecaptchaRateLimitError

async def login(page: Page, user_id: str, user_pw: str, capsolver_key: str, is_first: bool):
    print('navigating to login page...')

    if is_first:
        print('(might take long, due to browser setup)')
    await page.goto("https://www.acmicpc.net/login")
    print('success!\n')

    print('submitting login info...')
    await page.fill('[name=login_user_id]', user_id)
    await page.fill('[name=login_password]', user_pw)
    await page.click('[id=submit_button]')
    print('success!\n')

    try:
        if is_first:
            async with recaptchav2.AsyncSolver(page) as solver:
                print('trying captcha...')
                await solver.solve_recaptcha(wait=True, wait_timeout=10)
        else:
            async with recaptchav2.AsyncSolver(page, capsolver_api_key=capsolver_key) as solver:
                print('retrying captcha with image...')
                await solver.solve_recaptcha(wait=True, wait_timeout=10, image_challenge=True)

        print('success!\n')

    except RecaptchaNotFoundError:
        print('success! no captcha found.\n')

    except RecaptchaRateLimitError as e:
        if is_first:
            print('rate limit, retry with image.\n')
            await login(page, user_id, user_pw, capsolver_key, is_first=False)
        else:
            print('retry also failed.\n')
            raise e

    except Exception as e:
        if 'detached' in str(e):
            print('success! no captcha found. (detached)\n')
        else:
            raise e


async def run(ctx: BrowserContext, user_id: str, user_pw: str, code: str, language: str, problem: int, capsolver_key: str):
    try:
        page = await ctx.new_page()
        await login(page, user_id, user_pw, capsolver_key, is_first=True)

        print('waiting home page to load...')
        await page.wait_for_url("https://www.acmicpc.net/")
        print('success!\n')

        print('navigating to submit page...')
        await page.goto(f'https://www.acmicpc.net/submit/{problem}')
        print('success!\n')

        print("selecting language...")
        await page.click("#language_chosen")
        await page.click(f"//li[text()='{language}']")

        print('submitting answer...')
        await page.evaluate('code => document.querySelector(".CodeMirror").CodeMirror.setValue(code)', code)
        await page.click('[id=submit_button]')
        print('success!\n')

        print('waiting for result...')
        result_row = page.locator(
        '#status-table tbody tr:first-child .result-text:not(.result-wait, .result-compile, .result-judging)'
        )
        await page.wait_for_selector(
        '#status-table tbody tr:first-child .result-text:not(.result-wait, .result-compile, .result-judging)',
        timeout=180000
        )
        result = await result_row.text_content()

        print('success!\n')

        if '맞았습니다' in result:
            return result, True
        else:
            return result, False

    finally:
        await ctx.close()


async def main(user_id, user_pw, code, language, problem, capsolver_key):
    async with async_playwright() as playwright:
        browser = await playwright.firefox.launch(headless=True)
        context = await browser.new_context(locale='en-US')

        try:
            result, correct = await run(context, user_id, user_pw, code, language, problem, capsolver_key)
            return result, correct
        finally:
            await browser.close()





from playwright.async_api import async_playwright, BrowserContext, Page
from playwright_recaptcha import recaptchav2, RecaptchaNotFoundError, RecaptchaRateLimitError

import time
from curl_cffi import requests
import asyncio

async def solve_turnstile_with_capsolver(page: Page, capsolver_key: str):
    print('Solving Cloudflare Turnstile with Capsolver...')
    website_key = await page.locator('div.cf-turnstile').get_attribute('data-sitekey')
    website_url = page.url

    def solvecf_sync(api_key, metadata_action=None):
        url = "https://api.capsolver.com/createTask"
        task = {
            "type": "AntiTurnstileTaskProxyLess",
            "websiteURL": website_url,
            "websiteKey": website_key,
            "metadata": {"type": "turnstile"}
        }
        if metadata_action:
            task["metadata"]["action"] = metadata_action
        data = {"clientKey": api_key, "task": task}
        response_data = requests.post(url, json=data).json()
        print(" createTask:", response_data)
        return response_data.get('taskId')

    def solutionGet_sync(api_key, taskId):
        url = "https://api.capsolver.com/getTaskResult"
        while True:
            data = {"clientKey": api_key, "taskId": taskId}
            response_data = requests.post(url, json=data).json()
            print(" getTaskResult:", response_data)
            if response_data.get('status') == 'ready':
                solution = response_data['solution']
                print(" Capsolver Solution:", solution)
                return solution.get('token'), solution.get('userAgent')
            elif response_data.get('status') == 'failed' or response_data.get('errorId'):
                print(" Turnstile solving failed:", response_data)
                return None, None
            time.sleep(2)

    task_id = solvecf_sync(capsolver_key, metadata_action='submit')
    if task_id:
        token, user_agent = await asyncio.to_thread(solutionGet_sync, capsolver_key, task_id)
        return token, user_agent
    return None, None

async def run(ctx: BrowserContext, user_id: str, user_pw: str, code: str, language: str, problem: int, capsolver_key: str):
    page = await ctx.new_page()

    try:
        # Login
        await login(page, user_id, user_pw, capsolver_key, is_first=True)
        await page.wait_for_url("https://www.acmicpc.net/")
        print(" Login successful.")

        # submit page
        await page.goto(f'https://www.acmicpc.net/submit/{problem}')
        print(f" Navigated to submit page for problem {problem}.")

        turnstile_token, user_agent_from_capsolver = None, None
        if await page.locator('div.cf-turnstile').count() > 0:
            turnstile_token, user_agent_from_capsolver = await solve_turnstile_with_capsolver(page, capsolver_key)
            if turnstile_token:
                print(" Turnstile solved by Capsolver.")
                await page.evaluate(f'''
                    document.querySelector('input[name="cf-turnstile-response"]').value = "{turnstile_token}";
                    if (typeof turnstile_callback === 'function') {{
                        turnstile_callback('{turnstile_token}');
                        console.log(" turnstile_callback called.");
                        // Trigger form submit after callback
                        setTimeout(() => {{
                            document.querySelector('#submit_form').submit();
                            console.log(" Form submitted.");
                        }}, 500); // Wait a bit for turnstile_done to be set
                    }} else {{
                        console.log(" turnstile_callback is not a function.");
                    }}
                ''')
                print(" Turnstile token injected and turnstile_callback (if exists) called. Attempting to submit form.")
                if user_agent_from_capsolver:
                    print(f" Received User-Agent from Capsolver: {user_agent_from_capsolver}")
                    await ctx.set_extra_http_headers({"User-Agent": user_agent_from_capsolver})
            else:
                print(" Failed to solve Turnstile by Capsolver.")

        # Submit code
        await page.click("#language_chosen")
        await page.click(f"//li[text()='{language}']")

        await page.evaluate(f'''
            () => {{
                const editor = document.querySelector('.CodeMirror').CodeMirror;
                editor.setValue({repr(code)});
            }}
        ''')

        await page.wait_for_timeout(2000)

        print(" Waiting for result...")
        result_row = page.locator('#status-table tbody tr:first-child .result-text:not(.result-wait, .result-compile, .result-judging)')
        await page.wait_for_selector('#status-table tbody tr:first-child .result-text:not(.result-wait, .result-compile, .result-judging)', timeout=180000)
        result = await result_row.text_content()

        print(f" Result: {result}")
        return result, '맞았습니다' in result

    except Exception as e:
        print(f"Exception occurred in run: {e}")
        await page.screenshot(path="error_screenshot.png")
        return None, False

    finally:
        await page.close()

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
            async with recaptchav2.AsyncSolver(page, capsolver_api_key=capsolver_key) as solver:
                print('trying captcha...')
                try:
                    await solver.solve_recaptcha(wait=True, wait_timeout=10)
                except Exception as e:
                    print(f"Initial captcha solve failed: {e}. Trying image challenge.")
                    await solver.solve_recaptcha(wait=True, wait_timeout=10, image_challenge=True)
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

async def main(user_id, user_pw, code, language, problem, capsolver_key):
    async with async_playwright() as playwright:
        browser = await playwright.firefox.launch(headless=True)
        context = await browser.new_context(locale='en-US', viewport={'width': 1920, 'height': 1080})
        page = await context.new_page()

        try:
            result, correct = await run(context, user_id, user_pw, code, language, problem, capsolver_key)
            return result, correct
        finally:
            await browser.close()











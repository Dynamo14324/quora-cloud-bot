# setup_auth.py - Run this ONCE locally to get your login cookies
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        # Launch HEADFUL browser so you can see and login
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()

        print("--- STEP 1: LOG IN TO QUORA ---")
        page = await context.new_page()
        await page.goto("https://www.quora.com/")
        input("Log in to Quora manually. Press ENTER here when done...")

        print("--- STEP 2: LOG IN TO CHATGPT ---")
        await page.goto("https://chatgpt.com/")
        input("Log in to ChatGPT manually. Press ENTER here when done...")

        # Save the "ID Card" (Cookies & Local Storage)
        await context.storage_state(path="auth.json")
        print("SUCCESS! 'auth.json' has been created. Upload this file content to GitHub.")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
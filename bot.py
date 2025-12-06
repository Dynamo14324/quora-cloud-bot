# bot.py - Runs on GitHub Actions
import asyncio
import random
import os
import json
from playwright.async_api import async_playwright

# --- CONFIGURATION ---
CHATGPT_PROJECT_URL = "https://chatgpt.com/g/g-p-6931532106348191a38a8d26078c0182-quora-rio/project" 
QUORA_FEED_URL = "https://www.quora.com/answer"

async def main():
    print(">>> STARTING CLOUD BOT CYCLE")
    
    # 1. Load Auth Cookies from Environment Variable
    auth_json_content = os.environ.get("AUTH_JSON")
    if not auth_json_content:
        print("[ERROR] AUTH_JSON secret is missing!")
        return

    # Save to file for Playwright to read
    with open("auth.json", "w") as f:
        f.write(auth_json_content)

    async with async_playwright() as p:
        # Launch HEADLESS browser (Invisible)
        browser = await p.chromium.launch(headless=True)
        
        # Load the saved login state
        try:
            context = await browser.new_context(storage_state="auth.json", user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")
        except Exception as e:
            print(f"[ERROR] Auth file invalid: {e}")
            return

        page = await context.new_page()

        # --- RANDOM START DELAY (Humanize) ---
        # Sleep 1-3 minutes so we don't run at exactly the same second every hour
        delay = random.randint(60, 180)
        print(f">>> Humanizing: Sleeping {delay}s before starting...")
        await asyncio.sleep(delay)

        # --- 1. FIND QUESTION ---
        try:
            print(f"[QUORA] Checking feed...")
            await page.goto(QUORA_FEED_URL)
            await page.wait_for_timeout(5000)
            
            # Simple logic: Click the first available question link
            # (You can paste your complex scraping logic here)
            # For demo, we just print the title
            title = await page.title()
            print(f"[QUORA] Current Page: {title}")
            
            # NOTE: Full scraping logic omitted for brevity, 
            # paste your 'process_new_cycle' logic here if needed.
            
        except Exception as e:
            print(f"[ERROR] Quora Step Failed: {e}")

        # --- 2. GENERATE ANSWER (ChatGPT) ---
        try:
            print(f"[AI] Checking ChatGPT Access...")
            await page.goto(CHATGPT_PROJECT_URL)
            await page.wait_for_timeout(5000)
            if "Login" in await page.title():
                 print("[CRITICAL] ChatGPT Login Lost! Update auth.json.")
            else:
                 print("[AI] ChatGPT Access OK.")
                 # Paste your 'get_chatgpt_answer' logic here
        except Exception as e:
             print(f"[ERROR] ChatGPT Step Failed: {e}")

        await browser.close()
        print(">>> CYCLE COMPLETE")

if __name__ == "__main__":
    asyncio.run(main())
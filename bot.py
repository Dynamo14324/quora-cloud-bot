import asyncio
import random
import os
import json
import gzip
import base64
import re
import time
from playwright.async_api import async_playwright

# --- CONFIGURATION ---
CHATGPT_PROJECT_URL = "https://chatgpt.com/g/g-p-6931532106348191a38a8d26078c0182-quora-rio/project" 
QUORA_FEED_URL = "https://www.quora.com/answer"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# --- HELPER FUNCTIONS ---
async def get_cookies():
    """Decodes the compressed key from GitHub Secrets"""
    raw_secret = os.environ.get("AUTH_JSON")
    if not raw_secret:
        print("[ERROR] AUTH_JSON secret is missing!")
        return None
    try:
        decoded = base64.b64decode(raw_secret)
        decompressed = gzip.decompress(decoded)
        return json.loads(decompressed)
    except Exception as e:
        try:
            return json.loads(raw_secret)
        except:
            print(f"[CRITICAL] Could not decode AUTH_JSON: {e}")
            return None

async def find_new_question(page):
    print(f"   [QUORA] Scanning feed...")
    try:
        await page.goto(QUORA_FEED_URL)
        await page.wait_for_load_state("domcontentloaded")
        
        links = page.locator("a[href]")
        count = await links.count()
        
        for i in range(min(count, 60)):
            link = links.nth(i)
            if not await link.is_visible(): continue
            
            href = await link.get_attribute("href")
            text = await link.inner_text()
            
            if not href or len(text) < 10: continue
            
            if "/unanswered/" in href or (href.count("-") > 3 and "/answer/" not in href and "/profile/" not in href):
                if href.startswith("/"): href = "https://www.quora.com" + href
                print(f"   [FOUND] Candidate: {text[:50]}...")
                return href, text.strip()
                
    except Exception as e:
        print(f"   [ERROR] Scan failed: {e}")
    return None, None

async def ask_chatgpt(context, question):
    print(f"   [AI] Asking ChatGPT...")
    page = await context.new_page()
    try:
        await page.goto(CHATGPT_PROJECT_URL)
        
        # DEBUG 1: Screenshot after loading the page
        await page.wait_for_timeout(5000)
        await page.screenshot(path="debug_01_loaded.png")
        print("   [DEBUG] Screenshot taken: debug_01_loaded.png")

        title = await page.title()
        if "Login" in title or "Just a moment" in title:
             print(f"   [CRITICAL] ChatGPT blocked or logged out. Title: '{title}'")
             await page.screenshot(path="debug_error_login.png")
             await page.close()
             return None

        # Wait for input box
        try:
            await page.wait_for_selector("#prompt-textarea", timeout=20000)
        except:
            print("   [ERROR] Input box not found.")
            await page.screenshot(path="debug_error_no_input.png")
            return None
        
        # Type Question
        await page.click("#prompt-textarea")
        await page.fill("#prompt-textarea", "")
        await page.type("#prompt-textarea", question, delay=15)
        
        # DEBUG 2: Screenshot after typing (Verify the question is written)
        await page.wait_for_timeout(1000)
        await page.screenshot(path="debug_02_typed.png")
        print("   [DEBUG] Screenshot taken: debug_02_typed.png")
        
        # Click Send
        send_button = page.locator('button[data-testid="send-button"]')
        if await send_button.is_visible():
            await send_button.click()
            print("   [AI] Clicked Send Button.")
        else:
            await page.keyboard.press("Enter")
            print("   [AI] Pressed Enter.")

        print("   [AI] Waiting for answer...")
        
        # Wait for "Send" to disappear (Processing)
        try:
            await page.wait_for_selector('button[data-testid="send-button"]', state="hidden", timeout=10000)
        except:
            print("   [WARN] Send button stuck.")
            await page.screenshot(path="debug_error_stuck_send.png")

        # Wait for answer to finish
        try:
            await page.wait_for_selector('button[data-testid="send-button"]', state="visible", timeout=180000)
            
            # DEBUG 3: Screenshot of the answer
            await page.screenshot(path="debug_03_result.png")
            print("   [DEBUG] Screenshot taken: debug_03_result.png")
            
        except:
             print("   [WARN] Timeout waiting for generation.")
             await page.screenshot(path="debug_error_timeout.png")

        # Scrape response
        responses = page.locator("div.markdown")
        if await responses.count() > 0:
            text = await responses.nth(await responses.count() - 1).inner_text()
            print("   [AI] Answer generated!")
            await page.close()
            return text
        else:
            print("   [WARN] No response found.")
            await page.screenshot(path="debug_error_no_text.png")
            
    except Exception as e:
        print(f"   [ERROR] ChatGPT failed: {e}")
        await page.screenshot(path="debug_crash.png")
        await page.close()
    return None
    
async def post_to_quora(context, url, answer):
    print(f"   [QUORA] Posting answer...")
    page = await context.new_page()
    try:
        await page.goto(url)
        
        try:
            await page.click("div.q-text:has-text('Answer')", timeout=5000)
        except:
            await page.click("button:has-text('Answer')")
            
        await page.wait_for_selector("div[role='textbox']", state="visible", timeout=10000)
        await page.click("div[role='textbox']")
        
        # Type safely
        safe_answer = answer[:3000] 
        for chunk in [safe_answer[i:i+50] for i in range(0, len(safe_answer), 50)]:
            await page.keyboard.insert_text(chunk)
            await page.wait_for_timeout(50)
            
        await page.wait_for_timeout(2000)
        
        if await page.is_visible("button:has-text('Post')"):
            # await page.click("button:has-text('Post')") # Uncomment to enable posting
            print("   [SUCCESS] Answer typed (Simulated Post).")
        else:
            print("   [WARN] Post button not found.")
        
    except Exception as e:
        print(f"   [ERROR] Posting failed: {e}")
    await page.close()

async def main():
    print(">>> STARTING CLOUD BOT")
    
    cookies = await get_cookies()
    if not cookies: return
    
    with open("auth.json", "w") as f: json.dump(cookies, f)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled", 
                "--no-sandbox", 
                "--disable-setuid-sandbox"
            ]
        )
        
        # Use Desktop Viewport
        context = await browser.new_context(
            storage_state="auth.json",
            user_agent=USER_AGENT,
            viewport={"width": 1920, "height": 1080} 
        )
        
        delay = random.randint(60, 300)
        print(f">>> Humanizing: Sleeping {delay}s...")
        await asyncio.sleep(delay)
        
        q_page = await context.new_page()
        q_url, q_text = await find_new_question(q_page)
        await q_page.close()
        
        if q_url and q_text:
            ai_answer = await ask_chatgpt(context, q_text)
            if ai_answer:
                await post_to_quora(context, q_url, ai_answer)
        else:
            print("   [INFO] No valid questions found.")

        await browser.close()
        print(">>> CYCLE COMPLETE")

if __name__ == "__main__":
    asyncio.run(main())


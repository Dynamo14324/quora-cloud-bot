import asyncio
import random
import os
import json
import gzip
import base64
import re
from playwright.async_api import async_playwright

# --- CONFIGURATION ---
CHATGPT_PROJECT_URL = "https://chatgpt.com/g/g-p-6931532106348191a38a8d26078c0182-quora-rio/project" 
QUORA_FEED_URL = "https://www.quora.com/answer"

# Your Specific User Agent (Pre-filled)
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"

# --- HELPER FUNCTIONS ---
async def get_cookies():
    """Decodes the compressed key from GitHub Secrets"""
    raw_secret = os.environ.get("AUTH_JSON")
    if not raw_secret:
        print("[ERROR] AUTH_JSON secret is missing!")
        return None
    try:
        # 1. Decode Base64
        decoded = base64.b64decode(raw_secret)
        # 2. Decompress Gzip
        decompressed = gzip.decompress(decoded)
        # 3. Load JSON
        return json.loads(decompressed)
    except Exception as e:
        # Fallback: Maybe it wasn't compressed? Try loading as plain JSON
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
        
        # Scan first 60 links
        for i in range(min(count, 60)):
            link = links.nth(i)
            if not await link.is_visible(): continue
            
            href = await link.get_attribute("href")
            text = await link.inner_text()
            
            if not href or len(text) < 10: continue
            
            # Smart Filter: Look for valid question links
            # Must be a question URL and NOT an answer link or topic link
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
        
        # Check for login issues
        await page.wait_for_timeout(3000)
        title = await page.title()
        if "Login" in title or "Just a moment" in title:
             print(f"   [CRITICAL] ChatGPT blocked or logged out. Title: '{title}'")
             await page.close()
             return None

        # Wait for input box
        await page.wait_for_selector("#prompt-textarea", timeout=20000)
        
        # Type and Send
        await page.fill("#prompt-textarea", "")
        await page.type("#prompt-textarea", question, delay=15)
        await page.wait_for_timeout(500)
        await page.click("button[data-testid='send-button']")
        
        print("   [AI] Waiting for answer...")
        # Wait for generation to finish (Send button reappears)
        await page.wait_for_timeout(5000) # Initial buffer
        for _ in range(90): # Max 90 seconds wait
            if await page.is_visible("button[data-testid='send-button']"):
                break
            await page.wait_for_timeout(1000)
            
        # Scrape last response
        responses = page.locator("div.markdown")
        if await responses.count() > 0:
            text = await responses.nth(await responses.count() - 1).inner_text()
            print("   [AI] Answer generated!")
            await page.close()
            return text
            
    except Exception as e:
        print(f"   [ERROR] ChatGPT failed: {e}")
        await page.close()
    return None

async def post_to_quora(context, url, answer):
    print(f"   [QUORA] Posting answer...")
    page = await context.new_page()
    try:
        await page.goto(url)
        
        # Click Answer
        try:
            await page.click("div.q-text:has-text('Answer')", timeout=5000)
        except:
            await page.click("button:has-text('Answer')")
            
        # Wait for Editor
        await page.wait_for_selector("div[role='textbox']", state="visible", timeout=10000)
        await page.click("div[role='textbox']")
        
        # Type Answer in chunks to simulate human typing
        # Only type first 2000 chars to avoid timeouts if answer is huge
        safe_answer = answer[:3000] 
        for chunk in [safe_answer[i:i+50] for i in range(0, len(safe_answer), 50)]:
            await page.keyboard.insert_text(chunk)
            await page.wait_for_timeout(50)
            
        await page.wait_for_timeout(2000)
        
        # --- FINAL POST SWITCH ---
        # 1. Verify "Post" button is visible
        if await page.is_visible("button:has-text('Post')"):
            # 2. UNCOMMENT THE NEXT LINE TO ENABLE REAL POSTING:
            # await page.click("button:has-text('Post')")
            print("   [SUCCESS] Answer typed (Simulated Post). Uncomment line 133 to go live.")
        else:
            print("   [WARN] Post button not found.")
        
    except Exception as e:
        print(f"   [ERROR] Posting failed: {e}")
    await page.close()

async def main():
    print(">>> STARTING CLOUD BOT")
    
    # 1. Prepare Keys
    cookies = await get_cookies()
    if not cookies: return
    
    # Save formatted keys to file
    with open("auth.json", "w") as f: json.dump(cookies, f)

    async with async_playwright() as p:
        # 2. Launch with YOUR User Agent and Stealth Args
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled", 
                "--no-sandbox",
                "--disable-setuid-sandbox"
            ]
        )
        
        # 3. Create Context (The Disguise)
        try:
            context = await browser.new_context(
                storage_state="auth.json",
                user_agent=USER_AGENT # <--- Uses the ID from your PC
            )
        except Exception as e:
            print(f"[CRITICAL] Context creation failed. Your 'auth.json' might be corrupted. {e}")
            await browser.close()
            return
        
        # 4. Humanize Delay (Random 1-5 mins)
        delay = random.randint(60, 300)
        print(f">>> Humanizing: Sleeping {delay}s...")
        await asyncio.sleep(delay)
        
        # 5. Run Cycle
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

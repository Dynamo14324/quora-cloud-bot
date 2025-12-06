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

# --- HELPER FUNCTIONS ---
def clean_question_text(text):
    text = text.replace(" - Quora", "")
    text = re.sub(r'^\(\d+\)\s*', '', text)
    return text.strip()

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
    except:
        # Fallback for uncompressed keys
        try:
            return json.loads(raw_secret)
        except:
            return None

async def find_new_question(page):
    """Scrapes the Quora Feed for a valid question"""
    print(f"   [QUORA] Scanning feed...")
    try:
        await page.goto(QUORA_FEED_URL)
        await page.wait_for_load_state("domcontentloaded")
        
        # Get all link candidates
        links = page.locator("a[href]")
        count = await links.count()
        
        for i in range(min(count, 60)):
            link = links.nth(i)
            if not await link.is_visible(): continue
            
            href = await link.get_attribute("href")
            text = await link.inner_text()
            
            if not href or len(text) < 10: continue
            
            # Filter for Question URLs
            if "/unanswered/" in href or (href.count("-") > 3 and "/answer/" not in href):
                # cleanup URL
                if href.startswith("/"): href = "https://www.quora.com" + href
                
                print(f"   [FOUND] Candidate: {text[:50]}...")
                return href, text
    except Exception as e:
        print(f"   [ERROR] Scan failed: {e}")
        
    return None, None

async def ask_chatgpt(context, question):
    """Sends question to ChatGPT and returns the answer"""
    print(f"   [AI] Asking ChatGPT...")
    try:
        page = await context.new_page()
        await page.goto(CHATGPT_PROJECT_URL)
        await page.wait_for_selector("#prompt-textarea", timeout=10000)
        
        # Type and Send
        await page.fill("#prompt-textarea", "")
        await page.type("#prompt-textarea", question, delay=10)
        await page.click("button[data-testid='send-button']")
        
        print("   [AI] Waiting for generation...")
        # Wait for the send button to reappear (signaling completion)
        await page.wait_for_timeout(5000) # Initial buffer
        for _ in range(60): # Wait up to 60s
            if await page.is_visible("button[data-testid='send-button']"):
                break
            await page.wait_for_timeout(1000)
            
        # Extract the last response
        responses = page.locator("div.markdown")
        count = await responses.count()
        if count > 0:
            # We grab plain text because 'Clipboard' is unstable in Headless Cloud
            text = await responses.nth(count - 1).inner_text()
            print("   [AI] Answer generated successfully.")
            await page.close()
            return text
            
    except Exception as e:
        print(f"   [ERROR] ChatGPT failed: {e}")
        await page.close()
        
    return None

async def post_answer(context, question_url, answer_text):
    """Posts the answer to Quora"""
    print(f"   [QUORA] Posting answer...")
    try:
        page = await context.new_page()
        await page.goto(question_url)
        
        # Click Answer Button
        try:
            await page.click("div.q-text:has-text('Answer')", timeout=5000)
        except:
            await page.click("button:has-text('Answer')")
            
        # Wait for Editor
        await page.wait_for_selector("div[role='textbox']", state="visible", timeout=8000)
        
        # Type Answer (Simulating human typing speed)
        await page.click("div[role='textbox']")
        # Chunking text to prevent timeout on long answers
        for chunk in [answer_text[i:i+100] for i in range(0, len(answer_text), 100)]:
            await page.keyboard.insert_text(chunk)
            await page.wait_for_timeout(100)
            
        await page.wait_for_timeout(2000)
        
        # Click POST (Uncomment the line below to enable actual posting)
        await page.click("button:has-text('Post')")
        print("   [SUCCESS] Answer typed into editor (Posting simulated).")
        print("   *** TO ENABLE REAL POSTING: Uncomment line 125 in bot.py ***")
        
        await page.close()
        
    except Exception as e:
        print(f"   [ERROR] Posting failed: {e}")

# --- MAIN ENGINE ---
async def main():
    print(">>> STARTING PRODUCTION CYCLE")
    
    # 1. Load Keys
    cookies = await get_cookies()
    if not cookies: return
    
    # Save to file
    with open("auth.json", "w") as f: json.dump(cookies, f)

    async with async_playwright() as p:
        # 2. Launch Stealth Browser
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        
        # 3. Create Context with Saved Login
        context = await browser.new_context(
            storage_state="auth.json",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        # 4. Humanize (Random Sleep 1-5 mins)
        delay = random.randint(60, 300)
        print(f">>> Humanizing: Sleeping {delay}s...")
        await asyncio.sleep(delay)
        
        # 5. Execute Workflow
        q_page = await context.new_page()
        q_url, q_text = await find_new_question(q_page)
        await q_page.close()
        
        if q_text and q_url:
            answer = await ask_chatgpt(context, q_text)
            if answer:
                await post_answer(context, q_url, answer)
        else:
            print("   [INFO] No interesting questions found this cycle.")

        await browser.close()
        print(">>> CYCLE COMPLETE")

if __name__ == "__main__":
    asyncio.run(main())


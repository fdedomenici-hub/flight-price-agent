import os
import json
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

HISTORY_FILE = "price_history.json"

def search_flights(origin, destination="FOR", departure_date="2026-11-07", 
                   return_date="2026-11-14", currency="USD"):
    params = {
        "engine": "google_flights",
        "departure_id": origin,
        "arrival_id": destination,
        "outbound_date": departure_date,
        "return_date": return_date,
        "currency": currency,
        "hl": "en",
        "api_key": SERPAPI_KEY,
        "type": "1"
    }
    
    try:
        response = requests.get("https://serpapi.com/search", params=params, timeout=30)
        data = response.json()
        
        if "error" in data:
            print(f"SerpAPI Error for {origin}:", data.get("error"))
            return None
        
        all_flights = data.get("best_flights", []) + data.get("other_flights", [])
        if not all_flights:
            return None
        
        good_flights = []
        for f in all_flights:
            price_str = str(f.get("price", "999999")).replace("$", "").replace(",", "").strip()
            try:
                price_num = float(price_str)
            except:
                continue
                
            segments = f.get("flights", [])
            stops = len(segments) - 1 if segments else 99
            
            if stops <= 1:
                good_flights.append({
                    "price": price_num,
                    "price_display": f.get("price"),
                    "stops": stops,
                    "duration": f.get("total_duration"),
                    "detail": segments,
                    "search_url": data.get("search_metadata", {}).get("google_flights_url", "")
                })
        
        if not good_flights:
            return None
        
        cheapest = min(good_flights, key=lambda x: x["price"])
        return {
            "origin": origin,
            "price": cheapest["price"],
            "price_display": cheapest["price_display"],
            "stops": cheapest["stops"],
            "duration": cheapest["duration"],
            "search_url": cheapest["search_url"],
            "checked_at": datetime.now().isoformat()
        }
    except Exception as e:
        print(f"Error searching {origin}:", str(e))
        return None

def load_history():
    try:
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)

def send_telegram_alert(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram not fully configured. Would have sent:\n", message)
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
        print("✅ Alert sent to Telegram!")
    except Exception as e:
        print("Failed to send Telegram:", e)

def check_and_alert():
    print("\n=== Checking EZE + AEP → FOR (Outbound Nov 7) ===")
    
    best_overall = None
    for origin in ["EZE", "AEP"]:
        result = search_flights(origin)
        if result and (best_overall is None or result["price"] < best_overall["price"]):
            best_overall = result
    
    if not best_overall:
        print("No suitable flights found.")
        return
    
    route_key = "EZE_AEP_FOR_2026-11-07"
    history = load_history()
    previous_best = history.get(route_key, {}).get("best_price")
    
    current_price = best_overall["price"]
    is_new_low = previous_best is None or current_price < previous_best
    under_target = current_price <= 600
    
    # Hand-crafted Google Flights link with your dates
    hand_crafted_link = (
        "https://www.google.com/travel/flights/search?tfs=CBwQAhoqEgoyMDI2LTExLTA3agwIAxIIL20vMGZmbXAaKBIKMjAyNi0xMS0xNHIMCAMSCC9tLzA0anBsQAFIAXABggELCP///////////wGYAQE&curr=USD"
    )
    
    if is_new_low or under_target:
        msg = f"🚨 <b>FLIGHT DEAL ALERT - Buenos Aires → Fortaleza</b> 🚨\n\n"
        msg += f"<b>Best from:</b> {best_overall['origin']}\n"
        msg += f"<b>Outbound:</b> 2026-11-07\n"
        msg += f"<b>Return:</b> 2026-11-14\n"
        msg += f"<b>Price:</b> {best_overall['price_display']} USD ({best_overall['stops']} stops)\n"
        msg += f"<b>Duration:</b> {best_overall['duration']}\n\n"
        
        if previous_best:
            msg += f"Previous best: ${previous_best} → New low!\n"
        if under_target:
            msg += f"✅ Under $600 target!\n"
        
        msg += f"\n🔗 <a href='{best_overall.get('search_url', hand_crafted_link)}'>View on Google Flights (SerpAPI link)</a>\n"
        msg += f"🔗 <a href='https://www.google.com/travel/flights'>Manual Search with your filters</a>\n"
        
        send_telegram_alert(msg)
        
        history[route_key] = {
            "best_price": current_price,
            "last_checked": best_overall["checked_at"],
            "search_url": hand_crafted_link
        }
        save_history(history)
        print(f"New best price: ${current_price}")
    else:
        print(f"No better deal. Current best: ${current_price}")

if __name__ == "__main__":
    check_and_alert()
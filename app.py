from flask import Flask, render_template, request
import requests
import time
import os

app = Flask(__name__)

IP_API_URL = "http://ip-api.com/batch"
FIELDS = "query,status,message,country,regionName,city,isp,org,as"

def parse_ips(raw_text: str):
    # Accept: one per line OR comma separated
    ips = []
    for line in raw_text.replace(",", "\n").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        ips.append(line)

    # Deduplicate (keep order)
    seen = set()
    clean = []
    for ip in ips:
        if ip not in seen:
            seen.add(ip)
            clean.append(ip)

    return clean

def chunk_list(lst, size=100):
    for i in range(0, len(lst), size):
        yield lst[i:i+size]

def lookup_ipapi_batch(ips):
    results = []
    # ip-api batch supports up to 100 per request
    for batch in chunk_list(ips, 100):
        payload = [{"query": ip, "fields": FIELDS} for ip in batch]
        r = requests.post(IP_API_URL, json=payload, timeout=30)
        r.raise_for_status()
        results.extend(r.json())
        time.sleep(1)  # avoid rate limit
    return results

@app.route("/", methods=["GET", "POST"])
def index():
    data = []
    error = ""
    raw_ips = ""

    if request.method == "POST":
        raw_ips = request.form.get("ips", "")
        ips = parse_ips(raw_ips)

        if not ips:
            error = "دخل شي IP واحد على الأقل."
        else:
            try:
                data = lookup_ipapi_batch(ips)
            except Exception as e:
                error = f"وقع مشكل فـ الطلب: {e}"

    return render_template("index.html", data=data, error=error, raw_ips=raw_ips)

# Railway needs host 0.0.0.0 and PORT env var
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
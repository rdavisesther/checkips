from flask import Flask, render_template, request, session, Response
import requests
import time
import os
import csv
import io

app = Flask(__name__)

# Needed for session (Railway: you can set SECRET_KEY as env var too)
app.secret_key = os.environ.get("SECRET_KEY", "change-me-please")

IP_API_URL = "http://ip-api.com/batch"
FIELDS = "query,status,message,country,regionName,city,isp,org,as"

def parse_ips(raw_text: str):
    ips = []
    for line in raw_text.replace(",", "\n").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        ips.append(line)

    # dedupe keep order
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
            error = "Please enter at least one IP address."
            session.pop("last_results", None)
        else:
            try:
                data = lookup_ipapi_batch(ips)
                session["last_results"] = data  # save for CSV download
            except Exception as e:
                error = f"Request error: {e}"
                session.pop("last_results", None)

    # If user refreshes GET, keep last results if exist
    if request.method == "GET":
        data = session.get("last_results", [])

    return render_template("index.html", data=data, error=error, raw_ips=raw_ips)

@app.route("/download", methods=["GET"])
def download_csv():
    data = session.get("last_results", [])
    if not data:
        # No results yet
        return Response("No results to download. Please run a check first.", mimetype="text/plain")

    output = io.StringIO()
    writer = csv.writer(output)

    header = ["IP", "Status", "ISP", "Organization", "ASN", "Country", "Region", "City", "Message"]
    writer.writerow(header)

    for r in data:
        writer.writerow([
            r.get("query", ""),
            r.get("status", ""),
            r.get("isp", ""),
            r.get("org", ""),
            r.get("as", ""),
            r.get("country", ""),
            r.get("regionName", ""),
            r.get("city", ""),
            r.get("message", ""),
        ])

    csv_text = output.getvalue()
    output.close()

    return Response(
        csv_text,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=ip_results.csv"}
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

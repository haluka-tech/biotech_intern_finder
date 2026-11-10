import os
import json
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# ---------------------------------------------------------
# GLOBAL CONFIGURATION
# ---------------------------------------------------------
INPUT_COMPANIES_FILE = "companies.json"
OUTPUT_HTML_FILE = "index.html"
# OpenRouter model endpoint (e.g., deepseek/deepseek-chat, anthropic/claude-3.5-sonnet, meta-llama/llama-3.3-70b-instruct)
OPENROUTER_MODEL = "deepseek/deepseek-chat"

GLOBAL_TARGET_KEYWORDS = [
    "intern",
    "internship",
    "co-op",
    "student",
    "biotechnology",
    "trainee",
    "research assistant",
    "oncology",
    "immunology",
    "bioinformatics"
]

# ---------------------------------------------------------
# STEP 1: LOAD TARGET COMPANIES
# ---------------------------------------------------------
def load_companies(filepath=INPUT_COMPANIES_FILE):
    """Loads target companies list from input JSON file."""
    if not os.path.exists(filepath):
        print(f"Error: Could not find {filepath}. Please create it first.")
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

# ---------------------------------------------------------
# STEP 2: SCRAPE CAREER PAGES
# ---------------------------------------------------------
def scrape_company_page(url):
    """Fetches text content from a company career page."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=12)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            # Remove scripts, styles, and headers/footers to clean output
            for tag in soup(["script", "style", "nav", "footer"]):
                tag.decompose()
            text = soup.get_text(separator=" ", strip=True)
            return text[:7000] # Cap text length to stay within token context limits
    except Exception as e:
        print(f"  [!] Failed to scrape {url}: {e}")
    return ""

# ---------------------------------------------------------
# STEP 3: PARSE VIA OPENROUTER API
# ---------------------------------------------------------
def parse_with_openrouter(company_name, country, apply_url, raw_text, keywords):
    """Calls OpenRouter API to identify and extract biotech internship postings."""
    if not OPENROUTER_API_KEY:
        print("Error: OPENROUTER_API_KEY is not set in environment or .env file.")
        return []

    keywords_str = ", ".join(keywords)
    system_prompt = (
        "You are an expert biotechnology job crawler assistant. "
        "Analyze career page text and extract relevant internship/student postings matching specified keywords. "
        "Always respond ONLY with valid JSON in the requested structure."
    )

    user_prompt = f"""
Analyze the following career page text for '{company_name}' ({country}).

Required Keywords to match: [{keywords_str}]

Task:
1. Identify any active internship, co-op, student, or entry-level research opportunities in biotechnology, pharmaceuticals, or life sciences.
2. Ensure the posting matches at least ONE of the required keywords.
3. Extract structured details.

Return a JSON object with this exact structure:
{{
  "is_match_found": true/false,
  "jobs": [
    {{
      "title": "Exact Job Title",
      "location": "City, Country or Remote",
      "matched_keywords": ["keyword1", "keyword2"],
      "summary": "2-sentence brief description of the role and eligibility.",
      "apply_url": "{apply_url}"
    }}
  ]
}}

If no matching internship positions exist on this page, set "is_match_found" to false and "jobs" to [].

Page Text:
{raw_text}
"""

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/biotech-intern-finder",
        "X-Title": "Biotech Intern Agent"
    }

    payload = {
        "model": OPENROUTER_MODEL,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.1
    }

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        if response.status_code == 200:
            res_data = response.json()
            content = res_data["choices"][0]["message"]["content"]
            parsed_json = json.loads(content)
            
            if parsed_json.get("is_match_found"):
                jobs = parsed_json.get("jobs", [])
                for j in jobs:
                    j["company"] = company_name
                    j["country"] = country
                return jobs
    except Exception as e:
        print(f"  [!] OpenRouter parsing error for {company_name}: {e}")

    return []

# ---------------------------------------------------------
# STEP 4: GENERATE HTML DASHBOARD
# ---------------------------------------------------------
def generate_html_report(all_jobs, output_path=OUTPUT_HTML_FILE):
    """Generates a responsive HTML dashboard displaying found job postings."""
    
    table_rows = ""
    if not all_jobs:
        table_rows = """
        <tr>
            <td colspan="6" style="text-align: center; padding: 40px; color: #94a3b8;">
                No active biotech internships matching target keywords were found in this run.
            </td>
        </tr>
        """
    else:
        for job in all_jobs:
            kw_tags = "".join([f'<span class="tag">{kw}</span>' for kw in job.get("matched_keywords", [])])
            table_rows += f"""
            <tr>
                <td><strong>{job.get("company", "N/A")}</strong><br><small style="color:#94a3b8;">{job.get("country", "")}</small></td>
                <td><span class="job-title">{job.get("title", "N/A")}</span></td>
                <td>{job.get("location", "N/A")}</td>
                <td>{kw_tags}</td>
                <td style="max-width: 350px; font-size: 0.88rem; color: #cbd5e1;">{job.get("summary", "")}</td>
                <td><a href="{job.get("apply_url", "#")}" target="_blank" class="apply-btn">Apply Now &rarr;</a></td>
            </tr>
            """

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Biotech Intern Finder | Automated Dashboard</title>
    <style>
        :root {{
            --bg-color: #0f172a;
            --card-bg: #1e293b;
            --accent-color: #0284c7;
            --text-color: #f8fafc;
            --border-color: #334155;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            margin: 0;
            padding: 2rem;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        header {{
            margin-bottom: 2rem;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 1rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        h1 {{
            font-size: 1.75rem;
            margin: 0;
            color: #38bdf8;
        }}
        .badge {{
            background: #0369a1;
            padding: 0.35rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.85rem;
        }}
        .table-container {{
            background: var(--card-bg);
            border-radius: 12px;
            border: 1px solid var(--border-color);
            overflow-x: auto;
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3);
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            text-align: left;
        }}
        th, td {{
            padding: 1rem 1.25rem;
            border-bottom: 1px solid var(--border-color);
        }}
        th {{
            background-color: #0f172a;
            color: #94a3b8;
            font-weight: 600;
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        tr:last-child td {{
            border-bottom: none;
        }}
        .job-title {{
            font-weight: 600;
            color: #ffffff;
        }}
        .tag {{
            display: inline-block;
            background: #0f172a;
            border: 1px solid #0284c7;
            color: #38bdf8;
            padding: 0.15rem 0.45rem;
            border-radius: 4px;
            font-size: 0.75rem;
            margin: 0.1rem;
        }}
        .apply-btn {{
            display: inline-block;
            background: var(--accent-color);
            color: white;
            padding: 0.45rem 0.85rem;
            border-radius: 6px;
            text-decoration: none;
            font-weight: 500;
            font-size: 0.85rem;
            transition: background 0.2s;
        }}
        .apply-btn:hover {{
            background: #0369a1;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1>🧫 Biotech Internship Finder</h1>
                <p style="color: #94a3b8; margin: 0.25rem 0 0 0; font-size: 0.9rem;">Automated target company scan powered by OpenRouter</p>
            </div>
            <div class="badge">Active Roles Found: {len(all_jobs)}</div>
        </header>

        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th>Company</th>
                        <th>Position Title</th>
                        <th>Location</th>
                        <th>Matched Keywords</th>
                        <th>Summary</th>
                        <th>Action</th>
                    </tr>
                </thead>
                <tbody>
                    {table_rows}
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"\n[+] Successfully generated dashboard at: {output_path}")

# ---------------------------------------------------------
# MAIN ORCHESTRATOR
# ---------------------------------------------------------
def main():
    print("=" * 60)
    print("  BIOTECH INTERNSHIP AGENT (OPENROUTER ENGINE)")
    print("=" * 60)
    
    companies = load_companies()
    if not companies:
        print("No target companies found. Exiting.")
        return

    print(f"Loaded {len(companies)} target companies from '{INPUT_COMPANIES_FILE}'.")
    print(f"Global Target Keywords: {GLOBAL_TARGET_KEYWORDS}\n")

    all_jobs = []

    for entry in companies:
        company_name = entry.get("company", "Unknown")
        country = entry.get("country", "")
        url = entry.get("careers_url", "")

        print(f"[*] Processing {company_name} ({country})...")
        raw_text = scrape_company_page(url)

        if raw_text:
            jobs = parse_with_openrouter(
                company_name=company_name,
                country=country,
                apply_url=url,
                raw_text=raw_text,
                keywords=GLOBAL_TARGET_KEYWORDS
            )
            if jobs:
                print(f"  [✓] Found {len(jobs)} matching position(s)!")
                all_jobs.extend(jobs)
            else:
                print("  [-] No matching internships found.")
        else:
            print("  [-] Skipped due to empty or unreadable text content.")

    # Output to HTML Dashboard
    generate_html_report(all_jobs)

if __name__ == "__main__":
    main()
# Public Profile Agent

An AI-powered application that builds a structured, source-cited public profile
report for any named person — e.g. `Satya Nadella`, `Sachin Tendulkar`, or
`Rachael, CTO of Microsoft` — using only publicly available web information.

Given a name, it:
1. **Scrapes** the open web (DuckDuckGo search + Wikipedia) for public information.
2. **Synthesizes** the raw, messy scraped text into a clean, schema-conformant
   profile using Claude (Anthropic API), grounded strictly in the retrieved
   sources — no invented facts.
3. **Renders** the result as both a Markdown report and a polished PDF.

If a piece of information isn't publicly available, the report says so
explicitly (`"Not publicly available"`) instead of guessing.

---

## Output sections

Every generated profile includes:

- Executive Summary
- Basic Details (full name, age/DOB, occupation, industry, current city, current country)
- Biography / Summary
- Career Timeline
- Interests
- Network (notable professional/personal connections)
- Recent News / Public Activity
- References / Source Links

## Sample output

See [`sample_output/Satya_Nadella/`](sample_output/Satya_Nadella/) for a full,
real run: `profile.json` (structured data), `profile.md` (Markdown report),
and `profile.pdf` (formatted PDF), generated from live public sources.

---

## Architecture

```
main.py                CLI entry point — orchestrates the 3-stage pipeline
src/
  scraper.py            Stage 1: free web scraping (DuckDuckGo HTML + Wikipedia API)
  synthesizer.py         Stage 2: Claude turns raw scraped text into structured JSON
  schema.py              Shared JSON schema — single source of truth for both stages
  report.py              Stage 3: renders the JSON into Markdown + PDF
```

**Why this design:**
- **Scraping first, AI second.** The AI model never invents information — it
  only reorganizes and summarizes text that was actually retrieved from the
  web, with every source URL preserved for the references section. This
  keeps the report grounded and auditable (`raw_sources.json` is saved
  alongside every run so you can see exactly what the AI was given).
- **No paid search API required.** DuckDuckGo's HTML endpoint and Wikipedia's
  public REST API are both free and keyless, so the only credential you need
  is an Anthropic API key for the synthesis step.
- **Schema-first.** `schema.py` defines the exact JSON shape once; the AI
  step is forced (via Claude's tool-calling / forced `tool_choice`) to return
  data matching that schema, and the renderer trusts that shape completely.
  This means Markdown and PDF outputs can never disagree with each other.
- **Graceful degradation.** Every network call (search, page fetch, Wikipedia,
  the Claude call itself) is wrapped in error handling. If Claude synthesis
  fails or no API key is set, the app still completes the run using a
  transparent offline fallback rather than crashing.

---

## Setup

### 1. Requirements
- Python 3.10+
- An [Anthropic API key](https://console.anthropic.com/) (for the synthesis step)

### 2. Install

```bash
git clone <this-repo-url>
cd public-profile-agent
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure

```bash
cp .env.example .env
# then edit .env and paste in your ANTHROPIC_API_KEY
```

### 4. Run

```bash
python main.py "Satya Nadella"
python main.py "Sachin Tendulkar"
python main.py "Rachael, CTO of Microsoft"
```

Optional flags:

```bash
python main.py "Satya Nadella" --outdir my_reports   # custom output folder
python main.py "Satya Nadella" --no-pdf              # skip PDF, JSON+Markdown only
```

### 5. Output

Each run creates `output/<Person_Name>/` containing:

| File               | Contents                                              |
|--------------------|--------------------------------------------------------|
| `raw_sources.json` | Every scraped source (title, URL, extracted text)      |
| `profile.json`     | The structured profile Claude produced                 |
| `profile.md`       | Human-readable Markdown report                          |
| `profile.pdf`      | Polished, shareable PDF report                          |

---

## Notes & limitations

- Scraping quality depends on what's publicly indexed and how common the
  name is — very common or ambiguous names (e.g. "Rachael" with no surname)
  will return sparser, noisier results, and the report will correctly mark
  more fields as `"Not publicly available"` rather than guessing which
  "Rachael" was meant.
- DuckDuckGo's HTML endpoint and third-party sites can rate-limit or change
  their markup over time; `scraper.py` is defensive but not indestructible.
- This tool is intended for building profiles from information the subject
  has already made public (news coverage, official bios, public social
  posts, Wikipedia, etc.). It does not access private data, paywalled
  content, or anything requiring login.

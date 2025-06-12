from textwrap import dedent

DEFAULT_SYSTEM_PROMPT = dedent("""
    Summarize high-quality content for a senior executive with limited time and high cognitive demands.
    You goal is to make complex ideas accessible without oversimplifying.

    You MUST provide output in **Markdown** format.
    You MUST follow the specified output structure exactly; you MUST NOT add or omit sections.

    You MUST be very concise and avoid fluff in your language.
    You MUST NOT refer to 'the article' or similar phrases.
    You MUST NOT refer to 'the reader' (e.g., 'you').

    You MUST keep the tone professional, engaging, authoritative, and neutral.
    You MUST avoid opinion unless part of the original argument or counterpoint.

    ---

    Structure the response as follows:

    💡 Argument: One-sentence summary of the article’s main stance. It MUST NOT exceed 200 characters.

    🔍 Counterpoint: One-sentence critique or counterargument. It MUST NOT exceed 200 characters.

    ### Key Statements
    You MUST list between 3–5 critical points or content highlights as bullets.
    Each bullet MUST have a matching leading emoji (e.g., 🔑, 🚨, 📉).
    You MUST bold the most relevant parts using Markdown.
    You MUST NOT use introductory phrases or subheadings.

    ### Quick Facts
    You MUST list between 2–5 essential stats, dates, and names as bullets.
    Each bullet MUST have a matching leading emoji (e.g., 🔑, 🚨, 📉).

    ### Key Terms and Abbreviations
    You MUST list between 2-3 relevant terms or acronyms in simple language as bullets.
    Each bullet MUST have a matching leading emoji (e.g., 🔑, 🚨, 📉).
    You MUST include a short example for each bullet if applicable.

    ---

    Example response:

    💡 **Argument:** Lip-Bu Tan, Intel’s new CEO, is applying his proven turnaround expertise to rescue the
    company from years of strategic and technological decline.

    🔍 **Counterpoint:** But Intel’s deep structural challenges, reliance on government support, and tough
    competition in AI and chip fabrication make a successful revival far from guaranteed.

    ### Key Statements
    - 🔑 **Lip-Bu Tan brings a strong track record** from revitalizing Cadence Design Systems, where he
      tripled revenues and led a 48-fold stock rise
    - 📉 **The company’s revenue plunged** from $79bn in 2021 to $53bn in 2024, while its market cap shrank
      to $90bn—far behind rivals like Nvidia and TSMC
    - 🛠️ **Tan is pushing for deeper cost cuts** and a “big startup” culture to restore agility
    - ⚖️ **He insists on keeping design and manufacturing together**, a risky choice as Intel competes on
      two demanding fronts simultaneously
    - 🌐 **Intel faces geopolitical risks**, especially in China, which accounts for nearly a third of its
      revenue

    ### Quick Facts
    - 🌎 Intel Revenue Decline: $79bn (2021) → $53bn (2024)
    - 📉 Market Cap: ~$90bn (2025), down more than 50% in one year
    - 🧠 Cadence Turnaround: Stock rose 48× under Tan (2009–2021)
    - 📍 CEO Appointment: Lip-Bu Tan became CEO in March 2025
    - 🏭 Workforce Cut: 15% reduction already implemented under predecessor

    ### Key Terms and Abbreviations
    - 🏗️ **Foundry:** A facility that manufactures semiconductor chips designed by other companies, e.g.,
      TSMC for Apple or Nvidia
    - 🧠 **AI Chips:** Specialized processors optimized for artificial intelligence tasks; Nvidia dominates
      this fast-growing segment
    - 📊 **Philadelphia Semiconductor Index (SOX):** A key stock index tracking the performance of major
      U.S. semiconductor companies

""")
WATERMARK = "*Summarized by minigist* ([GitHub](https://github.com/eikendev/minigist))"
WATERMARK_DETECTOR = "Summarized by minigist"
MARKDOWN_CONTENT_WITH_WATERMARK = "{summary_content}\n\n" + WATERMARK + "\n\n---\n\n{original_article_content}"
MAX_RETRIES_PER_ENTRY = 3  # Max number of retries for processing a single entry (e.g., download, summarize)
RETRY_DELAY_SECONDS = 5  # Delay in seconds between retries for a single entry
FAILED_ENTRIES_ABORT_THRESHOLD = 10  # Abort if this many entries fail
MINIGIST_ENV_PREFIX = "MINIGIST"
DEFAULT_FETCH_LIMIT = 50  # Default number of entries to fetch per feed if not specified

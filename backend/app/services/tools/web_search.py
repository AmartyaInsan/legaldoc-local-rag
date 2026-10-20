import re
import socket
import logging
import urllib.parse
import base64
from typing import List, Dict, Any, Optional
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Learning Note:
# This optional Web Search tool (Module 7) lets the agent look up external information when a user
# explicitly asks to search the internet. It uses DuckDuckGo and Bing HTML scraping so no paid API key is needed.

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

# Known stable DuckDuckGo IP fallbacks (to bypass local ISP DNS poisoning like Kominfo TrustPositif)
FALLBACK_DDG_IPS = ["20.43.161.105", "52.149.246.39", "40.89.244.238"]
_DOH_CACHE: Dict[str, str] = {}
_REAL_GETADDRINFO = socket.getaddrinfo


def _is_poisoned_ip(ip: str) -> bool:
    """Detect common ISP block/poisoning IPs in Indonesia and other regions."""
    if not ip:
        return True
    poison_prefixes = ("202.169.", "118.98.", "10.", "127.", "0.", "192.168.", "36.86.")
    return ip.startswith(poison_prefixes)


def _resolve_doh_sync(hostname: str) -> Optional[str]:
    """Resolve clean IP via DNS-over-HTTPS (DoH) using Cloudflare or Google."""
    if hostname in _DOH_CACHE:
        return _DOH_CACHE[hostname]

    doh_endpoints = [
        f"https://cloudflare-dns.com/dns-query?name={hostname}&type=A",
        f"https://dns.google/resolve?name={hostname}&type=A",
    ]
    for url in doh_endpoints:
        try:
            with httpx.Client(timeout=3.0, headers={"accept": "application/dns-json"}) as client:
                resp = client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    for ans in data.get("Answer", []):
                        if ans.get("type") == 1:  # Type A record
                            ip = ans.get("data")
                            if ip and not _is_poisoned_ip(ip):
                                _DOH_CACHE[hostname] = ip
                                return ip
        except Exception:
            continue

    fallback = FALLBACK_DDG_IPS[0]
    _DOH_CACHE[hostname] = fallback
    return fallback


def _custom_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    """Intercept DNS queries for duckduckgo to bypass local ISP DNS poisoning."""
    host_str = str(host)
    if "duckduckgo.com" in host_str:
        clean_ip = _DOH_CACHE.get(host_str) or _resolve_doh_sync(host_str) or FALLBACK_DDG_IPS[0]
        return _REAL_GETADDRINFO(clean_ip, port, family, type, proto, flags)
    return _REAL_GETADDRINFO(host, port, family, type, proto, flags)


# Patch socket getaddrinfo globally for DuckDuckGo
socket.getaddrinfo = _custom_getaddrinfo


def clean_search_query(query: str) -> str:
    """
    Strip conversational filler in Indonesian & English so search engines receive high-signal keywords.
    E.g. 'Tolong cari di web apa ada update ollama terbaru ?' -> 'update ollama terbaru'
    """
    cleaned = query.strip()
    patterns = [
        r"^(?:tolong\s+)?(?:coba\s+)?(?:bisakah\s+)?(?:cari(?:kan)?|searching)\s+(?:di|lewat|melalui)\s+(?:web|internet|google|bing|duckduckgo)(?:\s+tentang|\s+mengenai|\s+soal|\s+apakah|\s+apa ada|\s+apa)?\s*",
        r"^(?:tolong\s+)?(?:coba\s+)?(?:cari(?:kan)?|temukan)\s+(?:info(?:rmasi)?|update|berita)?\s+(?:tentang|soal|mengenai)?\s*",
        r"^(?:please\s+)?(?:can you\s+)?search\s+(?:the\s+)?(?:web|internet|online)\s+(?:for|about)?\s*",
        r"^(?:what(?:'s|\s+is)\s+the\s+latest\s+on\s+)",
        r"^(?:apa\s+(?:ada\s+)?update\s+terbaru\s+(?:dari|tentang)\s+)",
        r"^(?:apakah\s+ada\s+update\s+terbaru\s+(?:dari|tentang)\s+)",
    ]
    for pat in patterns:
        cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE).strip()

    # Strip conversational question marks or quotes
    cleaned = re.sub(r"^[?\"'.,\s]+|[?\"'.,\s]+$", "", cleaned).strip()
    return cleaned if len(cleaned) >= 2 else query.strip()


def extract_targeted_web_query(query: str) -> str:
    """
    Extract high-signal search terms from composite or conversational prompts.
    Strips document-processing instructions (e.g. 'cek dokumen', 'bandingkan file')
    so search engines don't return PDF comparison utilities like iLovePDF or poyo.ai.
    """
    q = query.strip()
    if not q:
        return ""

    # 1. Match explicit web search clause anywhere in the sentence
    pattern = (
        r"(?:dan\s+|serta\s+)?(?:tolong\s+|coba\s+|bisakah\s+)?"
        r"(?:cari(?:kan)?|searching|search)\s+(?:di|lewat|melalui|the|on)\s+"
        r"(?:web|internet|google|bing|duckduckgo|online)\s*"
        r"(?:tentang|mengenai|soal|apakah ada|apa ada|apakah|apa|for|about)?\s*([^?!\n]+)"
    )
    m = re.search(pattern, q, re.IGNORECASE)
    if m:
        target = m.group(1).strip()
    else:
        target = q

    # 2. Remove conversational greetings & endings
    target = re.sub(r"(?i)\b(?:thanks|terima kasih|makasih|tolong ya|please|halo|hai)\b", "", target)

    # 3. Strip document-related commands from web search query
    target = re.sub(
        r"(?i)\b(?:cek|analisis|bandingkan|baca|telaah)\s+(?:semua\s+)?(?:dokumen|file|laporan)(?:\s+(?:ini|yang ada|yang aku berikan))?\b",
        "",
        target,
    )
    target = re.sub(
        r"(?i)\b(?:berikan|buatkan)\s+(?:detail\s+)?(?:inti|perbandingan|tabel|matriks)(?:\s+saja)?(?:\s+untuk\s+tiap\s+dokumen)?\b",
        "",
        target,
    )

    # Clean leading/trailing punctuation & conversational filler
    target = clean_search_query(target)
    target = re.sub(r"^[,\-–\s.]+|[,\-–\s.]+$", "", target).strip()

    # If query is about Indonesian regulations, ensure 'indonesia' is included for authoritative results
    if re.search(r"\b(?:peraturan|uu|undang-undang|merek|paten|hak cipta|desain industri|permenkum|permenkumham)\b", target, re.IGNORECASE) and not re.search(
        r"\bindonesia\b", target, re.IGNORECASE
    ):
        target = f"{target} indonesia"

    return target if len(target) >= 3 else query.strip()


# Strictly blocked untrusted domains (user-uploaded document dumps, homework sites, blogs, PDF utilities)
BLOCKED_WEB_DOMAINS = (
    "scribd.com",
    "academia.edu",
    "studocu.com",
    "coursehero.com",
    "slideshare.net",
    "dokumen.tips",
    "123dok.com",
    "pdfcoffee.com",
    "kupdf.net",
    "adoc.pub",
    "fdokumen.com",
    "researchgate.net",
    "brainly.co.id",
    "brainly.com",
    "quora.com",
    "reddit.com",
    "wikipedia.org",
    "blogspot.com",
    "wordpress.com",
    "medium.com",
    "kompasiana.com",
    "kaskus.co.id",
    "ilovepdf.com",
    "smallpdf.com",
    "poyo.ai",
    "sodapdf.com",
    "pdf24.org",
    "sejda.com",
    "camscanner.com",
    "canva.com",
    "facebook.com",
    "instagram.com",
    "tiktok.com",
    "twitter.com",
    "x.com",
    "youtube.com",
    "pinterest.com",
    "linkedin.com",
    "shopee.co.id",
    "tokopedia.com",
    "bukalapak.com",
    "blibli.com",
)

# Verified legal portals, IP law firms, and authoritative news/tech domains
TRUSTED_LEGAL_AND_NEWS_DOMAINS = (
    "hukumonline.com",
    "ambadar.com",
    "skclaw.id",
    "affa.co.id",
    "ssplaw.co.id",
    "sip-law.com",
    "makarim.com",
    "ahp.id",
    "abnrlaw.com",
    "antaranews.com",
    "kompas.com",
    "tempo.co",
    "bisnis.com",
    "kontan.co.id",
    "cnbcindonesia.com",
    "cnnindonesia.com",
    "detik.com",
    "katadata.co.id",
    "ollama.com",
    "github.com",
)


def is_legitimate_web_url(url: str) -> bool:
    """
    Validate that a URL comes from a legitimate external source and NOT from
    user-uploaded document dumps (like Scribd, Studocu, Academia) or PDF utility sites.
    """
    if not url or not url.startswith(("http://", "https://")):
        return False

    try:
        parsed = urllib.parse.urlparse(url)
        host = (parsed.netloc or "").lower().strip()
        if host.startswith("www."):
            host = host[4:]

        if not host:
            return False

        # Reject search engine root pages
        if host in ("google.com", "google.co.id", "bing.com", "duckduckgo.com", "yahoo.com"):
            return False

        # Reject any blocked domain or subdomain (e.g. id.scribd.com)
        for blocked in BLOCKED_WEB_DOMAINS:
            if host == blocked or host.endswith("." + blocked):
                logger.info(f"Filtered out untrusted web domain: {host} ({url})")
                return False

        return True
    except Exception:
        return False


def score_web_source_authority(url: str) -> tuple[int, str]:
    """
    Score a URL by its institutional legitimacy and return (score, badge_label).
    Prioritizes official Indonesian government (.go.id) and verified legal portals.
    """
    try:
        parsed = urllib.parse.urlparse(url)
        host = (parsed.netloc or "").lower().strip()
        if host.startswith("www."):
            host = host[4:]

        # Tier 1: Official Indonesian Government & Statutory Repositories (.go.id / .gov)
        if host.endswith(".go.id") or host.endswith(".gov") or host == "mkri.id":
            return 100, "Sumber Resmi Pemerintah (.go.id)"

        # Tier 2: Academic Institutions (.ac.id / .edu)
        if host.endswith(".ac.id") or host.endswith(".edu"):
            return 85, "Institusi Akademik Resmi (.ac.id)"

        # Tier 3: Reputable Legal Portals, Verified IP Consultants & National News
        for trusted in TRUSTED_LEGAL_AND_NEWS_DOMAINS:
            if host == trusted or host.endswith("." + trusted):
                return 75, f"Portal Hukum / Berita Terverifikasi ({trusted})"

        # Tier 4: Other non-blocked websites
        return 35, f"Sumber Web ({host})"
    except Exception:
        return 10, "Sumber Web"


class WebSearchService:
    """
    Robust, Zero-config Web Search Service with Legitimate Source Filtering:
    - Strictly blocks untrusted user-upload sites (Scribd, Academia, Studocu, CourseHero, Brainly, etc.)
    - Prioritizes official government domains (.go.id like peraturan.go.id, dgip.go.id, bpk.go.id)
      and verified legal portals (Hukumonline, verified IP law firms, national media).
    """

    def __init__(self):
        self.headers = {
            "User-Agent": USER_AGENT,
            "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

    async def search(self, query: str, max_results: int = 4) -> List[Dict[str, str]]:
        if not query or not query.strip():
            return []

        clean_query = extract_targeted_web_query(query)
        # Add search-engine level exclusion for Scribd & user-upload dumps on legal queries
        is_legal_query = bool(
            re.search(r"\b(?:peraturan|uu|undang-undang|merek|paten|hukum|permenkum|pasal)\b", clean_query, re.IGNORECASE)
        )
        engine_query = (
            f"{clean_query} -site:scribd.com -site:academia.edu -site:studocu.com"
            if is_legal_query
            else clean_query
        )

        logger.info(f"WebSearchService query cleaned: '{query}' -> '{clean_query}'")
        candidates: List[Dict[str, Any]] = []
        seen_urls: set[str] = set()

        def _add_candidate(title: str, url: str, snippet: str, source_type: str) -> None:
            if not title or not url or url.startswith("/"):
                return
            norm_url = url.strip()
            canonical_key = norm_url.split("?")[0].split("#")[0].rstrip("/").lower()
            if canonical_key in seen_urls:
                return
            if not is_legitimate_web_url(norm_url):
                return
            seen_urls.add(canonical_key)
            auth_score, badge = score_web_source_authority(norm_url)
            candidates.append({
                "title": title,
                "url": norm_url.split("?highlight=")[0],
                "snippet": snippet,
                "source_type": source_type,
                "authority_score": auth_score,
                "authority_badge": badge,
            })

        # 1. Tier 1: DuckDuckGo HTML Search (collect up to 12 candidates for authority filtering)
        try:
            async with httpx.AsyncClient(timeout=7.0, headers=self.headers, follow_redirects=True) as client:
                resp = await client.post(
                    "https://html.duckduckgo.com/html/",
                    data={"q": engine_query},
                )

                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    result_divs = soup.find_all("div", class_=re.compile(r"result\s+results_links"))

                    for div in result_divs[:12]:
                        title_elem = div.find("a", class_="result__a")
                        snippet_elem = div.find("a", class_="result__snippet")

                        if not title_elem:
                            continue

                        title = title_elem.get_text(strip=True)
                        raw_url = title_elem.get("href", "")

                        url_match = re.search(r"uddg=([^&]+)", raw_url)
                        if url_match:
                            url = urllib.parse.unquote(url_match.group(1))
                        else:
                            url = raw_url

                        snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""
                        _add_candidate(title, url, snippet, "web (duckduckgo)")
        except Exception as e:
            logger.warning(f"DuckDuckGo HTML search error: {e}")

        # 2. Tier 2: Bing Web Search (runs if DDG returned fewer than max_results legitimate results)
        if len(candidates) < max_results:
            logger.info("Fetching additional legitimate sources via Bing Web Search...")
            try:
                async with httpx.AsyncClient(timeout=6.0, headers=self.headers, follow_redirects=True) as client:
                    resp = await client.get(f"https://www.bing.com/search?q={urllib.parse.quote(engine_query)}")
                    if resp.status_code == 200:
                        soup = BeautifulSoup(resp.text, "html.parser")
                        for item in soup.select("li.b_algo")[:12]:
                            a = item.select_one("h2 a")
                            snippet_elem = item.select_one(".b_caption p, .b_algoSlug, p")
                            if a:
                                href = a.get("href", "")
                                if "bing.com/ck/a" in href:
                                    m = re.search(r"u=a1([a-zA-Z0-9_\-]+)", href)
                                    if m:
                                        try:
                                            padded = m.group(1) + "=" * ((4 - len(m.group(1)) % 4) % 4)
                                            href = base64.urlsafe_b64decode(padded.encode()).decode("utf-8", "ignore")
                                        except Exception:
                                            pass

                                title = a.get_text(strip=True)
                                snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""
                                _add_candidate(title, href, snippet, "web (bing)")
            except Exception as e:
                logger.warning(f"Bing Web Search fallback error: {e}")

        # 3. Tier 3: DuckDuckGo Instant Answer API fallback (only if still 0 results)
        if not candidates:
            try:
                async with httpx.AsyncClient(timeout=5.0, headers=self.headers, follow_redirects=True) as client:
                    resp = await client.get(
                        "https://api.duckduckgo.com/",
                        params={"q": clean_query, "format": "json", "no_html": 1, "skip_disambig": 1},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        abstract = data.get("AbstractText", "")
                        abstract_source = data.get("AbstractSource", "DuckDuckGo")
                        abstract_url = data.get("AbstractURL", "")
                        if abstract and is_legitimate_web_url(abstract_url):
                            _add_candidate(
                                f"{abstract_source} Overview: {clean_query}",
                                abstract_url,
                                abstract,
                                "web (duckduckgo)",
                            )
            except Exception as e:
                logger.warning(f"DuckDuckGo Instant Answer fallback error: {e}")

        # Sort candidates by authority score descending (preserving search rank order within same tier)
        candidates.sort(key=lambda x: x.get("authority_score", 0), reverse=True)
        final_results = candidates[:max_results]

        logger.info(
            f"Web search for '{clean_query}' returned {len(final_results)} legitimate results "
            f"(from {len(candidates)} filtered candidates)."
        )
        return final_results

    def format_web_context(self, results: List[Dict[str, str]]) -> str:
        """Format verified web search results into a clean context block with authority badges."""
        if not results:
            return ""

        lines = [
            "### HASIL PENCARIAN WEB TERVERIFIKASI (Sumber Eksternal Resmi & Kredibel)",
            "INSTRUKSI PENTING: Pengguna meminta informasi/pembaruan eksternal dari web. Gunakan hasil pencarian web yang telah difilter dari sumber kredibel di bawah ini untuk menjawab secara akurat.",
            "- WAJIB cantumkan kutipan tautan sumber dengan format [Judul Sumber](URL).",
            "- DILARANG KERAS mengutip situs unggahan pengguna yang tidak terverifikasi (seperti Scribd, Studocu, Academia, dsb.).",
            "- DILARANG mengarang nomor undang-undang/peraturan yang tidak disebutkan di dalam sumber di bawah ini.",
            "---",
        ]
        for idx, item in enumerate(results, 1):
            title = item.get("title", "Web Page")
            url = item.get("url", "")
            snippet = item.get("snippet", "")
            badge = item.get("authority_badge", "Sumber Web Terverifikasi")
            lines.append(f"[Web Source {idx} ({badge}): {title} | URL: {url}]")
            lines.append(snippet)
            lines.append("---")

        return "\n".join(lines)


web_search_service = WebSearchService()

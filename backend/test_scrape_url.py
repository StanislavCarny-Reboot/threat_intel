"""Quick manual test for _do_scrape. Run with: uv run test_scrape_url.py"""

from workflows.new_flows.get_link_content import _do_scrape

url = "https://phys.org/news/2026-02-elusive-lithium-ion-anode-binder.html"

text = _do_scrape(url)
print(f"URL: {url}")
print(f"Text length: {len(text)} chars")
print(f"\n--- First 1000 chars ---\n{text[:1000]}")

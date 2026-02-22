ATTACK_CLASSIFICATION_PROMPT = """
# Role: Cybersecurity Article Classifier
**Task:** Analyze the provided article text and determine if it belongs to any of the three categories below. Use the specific "True/False" criteria to make your decision.


## 1. Cyber Attack Campaign
*Definition: Is this a description of an active malicious operation against real targets?*

**Mark TRUE if:**
* **Recency:** The article describes activity as "ongoing," "current," or "recently observed" (within days or weeks). 
* **Real Targeting:** It mentions specific victims, such as a named company, a specific industry sector, or a geographic region.
* **Adversary Behavior:** It details actual attacker actions (e.g., how they gained access, lateral movement, data exfiltration, or ransomware deployment).

**Mark FALSE if:**
* **Historical:** It is a post-mortem or retrospective look at an old attack with no signs of current activity.
* **Hypothetical:** It only talks about "potential" risks or "could-be" targets.
* **Defensive Only:** The focus is purely on vendor marketing, policy, or general security advice without an active threat.

---

## 2. Common Vulnerabilities and Exposures (CVE)
*Definition: Does the article meaningfully discuss specific technical flaws?*

**Mark TRUE if:**
* **Explicit Identifiers:** The article explicitly names one or more CVE IDs (e.g., CVE-2025-12345).
* **Technical Focus:** It provides a deep dive into a specific vulnerability, including affected software versions, technical impact, or patch details.
* **Exploitation:** It discusses the "in the wild" exploitation of a specific known bug.

**Mark FALSE if:**
* **Vague Mentions:** It uses generic terms like "zero-day" or "vulnerability" without identifying a specific flaw.
* **Passing Mention:** A CVE is mentioned only in passing or as background context without detail.

---

## 3. Digest
*Definition: Is this a multi-topic roundup that includes at least one active threat?*

**Mark TRUE only if ALL of the following apply:**
1. **Aggregated Format:** It is a summary or roundup (e.g., "Weekly News Recap" or "Daily Briefing").
2. **Multiple Items:** It covers several independent topics, such as different threat actors, multiple malware families, or various news incidents.
3. **Active Campaign Included:** At least one of the items in the roundup must meet the criteria for a **Cyber Attack Campaign** (active/recent malicious activity).

**Mark FALSE if:**
* **Single Topic:** It focuses deeply on one main event, even if it mentions others briefly.
* **Non-Operational:** The roundup only contains policy, business funding, or general trends with no active attacks.



## 4. Uncertainty (Not Sure)
**Use "Not Sure" if:**
* The article is ambiguous about whether the attack is current or historical.
* There is not enough information to satisfy the criteria for a "True" label.
* **Principle:** Always be conservative. If it doesn't clearly hit the marks for "True," label it "Not Sure" or "False."


## 5. Redirect / Link-Only Article
Definition: Is this article primarily a pointer to another external post with little or no original content?

Mark TRUE if:
* **Minimal Content:** Only a very brief summary (e.g., 1–3 short paragraphs) with no meaningful technical or operational detail.
* **Primary Purpose is Redirection:** The main goal is to send the reader to another blog, report, or external site for the full story.
* **No Independent Intelligence Value:** The page itself does not provide enough information to assess a campaign or CVE.

Mark FALSE if:
* **Substantive Analysis:** The article contains substantive analysis or meaningful summaries, even if it includes external links.
* **Digest Qualification:** It qualifies as a Digest with multiple topics and standalone intelligence value.
* **Key Distinction:** A Redirect exists mainly to forward the reader elsewhere; a Digest provides meaningful content on its own.


## Required Output Format
For every article, provide the following:

* **Cyber Attack Campaign:** [True/False/Not Sure] | **Reasoning:** [1-2 sentence explanation]
* **CVE:** [True/False/Not Sure] | **Reasoning:** [1-2 sentence explanation]
* **Digest:** [True/False/Not Sure] | **Reasoning:** [1-2 sentence explanation]"""

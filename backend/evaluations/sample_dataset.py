"""Sample evaluation dataset for article classification."""

# Sample dataset matching the ArticleClassification schema
data = [
    {
        "inputs": {
            "article_text": """
            Ransomware Gang 'BlackCat' Targets Major Healthcare Provider

            A sophisticated ransomware group known as BlackCat has successfully breached
            a major healthcare provider, encrypting patient records and demanding a
            $5 million ransom. The attack utilized a zero-day vulnerability in the
            organization's VPN gateway. Security researchers have identified several
            indicators of compromise including file hashes and C2 server addresses.
            The gang has given the organization 72 hours to pay before threatening to
            release patient data on the dark web.
            """,
            "article_url": "https://example.com/blackcat-ransomware",
        },
        "expectations": {
            "active_campaign": "True",
            "cve": "False",
            "digest": "False",
        },
    },
    {
        "inputs": {
            "article_text": """
            Critical Vulnerability Discovered in Apache Log4j (CVE-2021-44228)

            A critical remote code execution vulnerability has been discovered in
            Apache Log4j, a widely used Java logging library. The vulnerability,
            tracked as CVE-2021-44228, allows attackers to execute arbitrary code
            by sending a specially crafted string that gets logged. This affects
            Log4j versions 2.0 to 2.14.1. Organizations using Log4j should
            immediately upgrade to version 2.15.0 or apply the recommended mitigations.
            CVSS score: 10.0 (Critical).
            """,
            "article_url": "https://example.com/log4j-cve",
        },
        "expectations": {
            "active_campaign": "False",
            "cve": "True",
            "digest": "False",
        },
    },
    {
        "inputs": {
            "article_text": """
            Weekly Security Digest: Top 5 Cybersecurity Stories This Week

            1. New ransomware variant discovered targeting SMBs
            2. Microsoft patches 75 vulnerabilities in monthly update
            3. FBI warns of increase in BEC attacks
            4. CISA releases new guidance on zero trust architecture
            5. Major cloud provider announces enhanced DDoS protection

            Stay tuned for our detailed coverage of each story throughout the week.
            """,
            "article_url": "https://example.com/weekly-digest",
        },
        "expectations": {
            "active_campaign": "False",
            "cve": "False",
            "digest": "True",
        },
    },
    {
        "inputs": {
            "article_text": """
            APT29 (Cozy Bear) Launches Sophisticated Phishing Campaign Against Government Agencies

            Russian-linked threat actor APT29 has been observed conducting a highly
            targeted spear-phishing campaign against government agencies in North America
            and Europe. The campaign, which began in early January, uses weaponized PDF
            documents exploiting CVE-2023-XXXX. The malware establishes persistence through
            scheduled tasks and exfiltrates data to attacker-controlled infrastructure.
            IOCs and YARA rules have been published by CISA.
            """,
            "article_url": "https://example.com/apt29-campaign",
        },
        "expectations": {
            "active_campaign": "True",
            "cve": "False",
            "digest": "False",
        },
    },
    {
        "inputs": {
            "article_text": """
            Security Researchers Disclose Multiple Vulnerabilities in Popular IoT Devices

            A team of security researchers has disclosed 12 critical vulnerabilities
            affecting popular IoT devices from three major manufacturers. The flaws
            include:
            - CVE-2025-0001: Remote code execution in smart camera firmware
            - CVE-2025-0002: Authentication bypass in smart lock API
            - CVE-2025-0003: SQL injection in home automation controller

            Patches are now available for all affected devices. Users should update
            immediately to prevent exploitation.
            """,
            "article_url": "https://example.com/iot-vulnerabilities",
        },
        "expectations": {
            "active_campaign": "False",
            "cve": "True",
            "digest": "False",
        },
    },
    {
        "inputs": {
            "article_text": """
            Phishing Activity Targeting Financial Sector Increases

            General statistics show a 40% increase in phishing emails targeting the
            financial sector over the past quarter. While no specific campaign has been
            identified, security analysts note common patterns including fake invoice
            notifications and urgent payment requests. Organizations are advised to
            enhance email security and user awareness training.
            """,
            "article_url": "https://example.com/phishing-trends",
        },
        "expectations": {
            "cyber_attack_campaign": "Not Sure",
            "common_vulnerabilities_and_exposures": False,
            "digest": False,
        },
    },
    {
        "inputs": {
            "article_text": """
            This Week in Cybersecurity: Vulnerabilities, Breaches, and Best Practices

            Our weekly roundup covers the latest security news including newly disclosed
            CVEs, ongoing attack campaigns, and recommended security practices. Featured
            stories include the SolarWinds supply chain attack analysis, new NIST
            cybersecurity framework updates, and emerging threats in the cloud security
            landscape. Subscribe for weekly updates delivered to your inbox.
            """,
            "article_url": "https://example.com/weekly-roundup",
        },
        "expectations": {
            "active_campaign": "False",
            "cve": "False",
            "digest": "True",
        },
    },
    {
        "inputs": {
            "article_text": """
            LockBit 3.0 Ransomware Deployment Linked to ProxyShell Exploitation

            Threat intelligence indicates that LockBit 3.0 ransomware operators are
            actively exploiting ProxyShell vulnerabilities (CVE-2021-34473, CVE-2021-34523,
            CVE-2021-31207) to gain initial access to Exchange servers. Once inside,
            attackers deploy Cobalt Strike beacons, perform lateral movement, and
            eventually encrypt systems with LockBit 3.0. The campaign has affected
            over 50 organizations globally in the past month.
            """,
            "article_url": "https://example.com/lockbit-proxyshell",
        },
        "expectations": {
            "active_campaign": "True",
            "cve": "False",
            "digest": "False",
        },
    },
    {
        "inputs": {
            "article_text": """
            Best Practices for Securing Your Home Network in 2025

            As remote work continues, securing your home network is essential. Here are
            five key recommendations: 1) Change default router passwords, 2) Enable WPA3
            encryption, 3) Use a VPN for sensitive work, 4) Keep firmware updated,
            5) Segment IoT devices. Following these practices can significantly reduce
            your risk of compromise. Educational content for general audience.
            """,
            "article_url": "https://example.com/home-security-tips",
        },
        "expectations": {
            "active_campaign": "False",
            "cve": "False",
            "digest": "False",
        },
    },
    {
        "inputs": {
            "article_text": """
            Microsoft Patch Tuesday: January 2025 Security Updates

            Microsoft has released security updates addressing 85 vulnerabilities across
            its product portfolio. Notable patches include:
            - CVE-2025-0010: Critical RCE in Windows MSHTML (CVSS 9.8)
            - CVE-2025-0011: Important elevation of privilege in Active Directory
            - CVE-2025-0012: Critical RCE in Exchange Server

            IT administrators should prioritize patching systems, especially internet-facing
            Exchange servers and domain controllers.
            """,
            "article_url": "https://example.com/patch-tuesday-jan2025",
        },
        "expectations": {
            "active_campaign": "False",
            "cve": "True",
            "digest": "False",
        },
    },
]

if __name__ == "__main__":
    print(f"Sample dataset contains {len(data)} evaluation examples")
    print("\nDistribution:")
    active_campaigns = sum(
        1 for d in data if d["expectations"]["active_campaign"] == "True"
    )
    cves = sum(1 for d in data if d["expectations"]["cve"] == "True")
    digests = sum(1 for d in data if d["expectations"]["digest"] == "True")
    print(f"  Active Campaigns: {active_campaigns}")
    print(f"  CVEs: {cves}")
    print(f"  Digests: {digests}")
    print(f"  Other/Mixed: {len(data) - active_campaigns - cves - digests}")

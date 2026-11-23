"""Title and location filters for blue-team roles in Pune / Mumbai / Bengaluru."""
import re

CORE = [
    (r"\bsoc\b|security operations? (cent(er|re)|analyst|engineer|lead|manager)|\bsecops\b|cyber ?defen[cs]e|fusion cent", "SOC / Security Operations"),
    (r"detection (engineer|&|and)|detection engineering|threat detection|\bdetections?\b.*engineer|use ?case (engineer|developer)", "Detection Engineering"),
    (r"threat (intel|intelligence|research|researcher|hunt|hunter|hunting|analyst)|\bcti\b|malware|reverse engineer", "Threat Intel / Research / Hunting"),
    (r"incident (response|responder|handler|management.*security)|\bdfir\b|forensic|\bcsirt\b|\bcert\b|\bpsirt\b", "Incident Response / DFIR"),
    (r"\bsiem\b|splunk|sentinel|qradar|chronicle|\bsoar\b|\bxdr\b|\bedr\b|\bmdr\b|\bxsiam\b|elastic security|cortex", "SIEM / SOAR / XDR Engineering"),
    (r"blue team|purple team|cyber ?security analyst|information security analyst|security analyst|security monitoring|cyber (security )?operations|security engineer.*(operations|monitoring|response)", "Blue Team / Security Analyst"),
]
ADJ = [
    (r"vulnerability (management|analyst|engineer)|threat (and|&) vulnerability|exposure management", "Vulnerability Management (adjacent)"),
    (r"cloud security|security engineer|cyber ?security engineer|cybersecurity specialist|information security engineer", "Security Engineering (adjacent)"),
]
EXCLUDE = re.compile(
    r"sales|account (executive|manager)|business development|presales|pre-sales|marketing|recruit|"
    r"physical security|security guard|social security|securities|customer success|partner|"
    r"\bintern\b|legal counsel|paralegal|payroll|finance|accountant", re.I)

CITY = [
    (r"bengaluru|bangalore|blr\b|whitefield|electronic city|manyata", "Bengaluru"),
    (r"\bpune\b|hinjewadi|kharadi|magarpatta|hadapsar|yerwada|baner", "Pune"),
    (r"mumbai|navi mumbai|thane|powai|airoli|bkc|goregaon|malad|andheri|vikhroli", "Mumbai"),
]


def classify_title(title):
    t = title or ""
    if EXCLUDE.search(t):
        return None
    low = t.lower()
    for pat, label in CORE:
        if re.search(pat, low):
            return label
    for pat, label in ADJ:
        if re.search(pat, low):
            return label
    return None


def match_city(loc):
    low = (loc or "").lower()
    found = [label for pat, label in CITY if re.search(pat, low)]
    return ", ".join(dict.fromkeys(found)) if found else None

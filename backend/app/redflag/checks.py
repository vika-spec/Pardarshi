"""The seven warning-sign checks, in one place.

Each check states, in plain words, what it looks for and the exact threshold.
These definitions are served by /api/methodology so the rules are public.

A red flag is a reason to look closer, never proof of wrongdoing.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Check:
    id: str
    kind: str  # "text" (LLM/regex judges wording) | "numeric" (Python computes from extracted figures)
    severity: str  # weight if flagged: "high" | "medium"
    title: dict[str, str]
    what: dict[str, str]  # what it means, plain language
    rule: str  # the exact rule, shown on the methodology page
    queries: list[str]
    fields: list[str] = field(default_factory=list)  # numeric fields the extractor must return
    flagged_text: dict[str, str] = field(default_factory=dict)
    passed_text: dict[str, str] = field(default_factory=dict)


CHECKS: list[Check] = [
    Check(
        id="auditor_opinion",
        kind="text",
        severity="high",
        title={"en": "Auditor raised concerns", "hi": "ऑडिटर ने आपत्ति जताई"},
        what={
            "en": "The outside accountant signs off on the books. A 'qualified' or 'adverse' opinion, or a going-concern warning, means they were not fully satisfied.",
            "hi": "बाहरी ऑडिटर कंपनी के खातों की जाँच करता है। 'क्वालिफ़ाइड' या 'एडवर्स' राय का मतलब है कि वह पूरी तरह संतुष्ट नहीं था।",
        },
        rule="Flag if the independent auditor's report contains a qualified, adverse or disclaimer of opinion, or a material uncertainty about going concern.",
        queries=["independent auditor's report opinion", "basis for qualified opinion", "material uncertainty related to going concern", "emphasis of matter"],
        flagged_text={"en": "The auditor's report is not clean.", "hi": "ऑडिटर की रिपोर्ट साफ़ नहीं है।"},
        passed_text={"en": "The auditor gave a clean (unmodified) opinion.", "hi": "ऑडिटर ने साफ़ राय दी।"},
    ),
    Check(
        id="auditor_change",
        kind="text",
        severity="high",
        title={"en": "Auditor resigned mid-term", "hi": "ऑडिटर ने बीच में इस्तीफ़ा दिया"},
        what={
            "en": "Auditors rarely quit early. A resignation, especially with vague reasons, has preceded several Indian collapses.",
            "hi": "ऑडिटर आमतौर पर बीच में इस्तीफ़ा नहीं देते। कई कंपनियों के डूबने से पहले ऐसा हुआ है।",
        },
        rule="Flag if the report mentions the statutory auditor resigning or a casual vacancy in the auditor's office during the year.",
        queries=["statutory auditor resigned", "resignation of statutory auditors", "casual vacancy auditor", "appointment of statutory auditors"],
        flagged_text={"en": "The auditor resigned during the year.", "hi": "ऑडिटर ने साल के दौरान इस्तीफ़ा दिया।"},
        passed_text={"en": "No auditor resignation is mentioned.", "hi": "ऑडिटर के इस्तीफ़े का कोई ज़िक्र नहीं है।"},
    ),
    Check(
        id="promoter_pledge",
        kind="numeric",
        severity="high",
        title={"en": "Owners borrowed against their shares", "hi": "मालिकों ने अपने शेयर गिरवी रखे"},
        what={
            "en": "When promoters pledge shares for loans and the price falls, lenders can sell those shares, pushing the price down further.",
            "hi": "प्रमोटर शेयर गिरवी रखकर कर्ज़ लेते हैं। दाम गिरने पर कर्ज़ देने वाले शेयर बेच सकते हैं।",
        },
        rule="Flag if more than 10% of the promoter group's shares are pledged or encumbered (high if above 25%).",
        queries=["shares pledged or encumbered promoter", "promoter shareholding pledged", "encumbrance promoter group"],
        fields=["pledged_pct_of_promoter_holding"],
        flagged_text={"en": "{pledged_pct_of_promoter_holding:.1f}% of the owners' shares are pledged.", "hi": "मालिकों के {pledged_pct_of_promoter_holding:.1f}% शेयर गिरवी हैं।"},
        passed_text={"en": "Only {pledged_pct_of_promoter_holding:.1f}% of the owners' shares are pledged.", "hi": "मालिकों के केवल {pledged_pct_of_promoter_holding:.1f}% शेयर गिरवी हैं।"},
    ),
    Check(
        id="related_party",
        kind="numeric",
        severity="medium",
        title={"en": "Large deals with the owner's own companies", "hi": "मालिक की अपनी कंपनियों से बड़े सौदे"},
        what={
            "en": "Buying from or lending to firms the promoter controls can move money out of the company. Not wrong by itself, but worth reading.",
            "hi": "प्रमोटर की अपनी कंपनियों से लेन-देन से पैसा बाहर जा सकता है। यह अपने आप में गलत नहीं, पर ध्यान देने लायक है।",
        },
        rule="Flag if related-party transactions exceed 10% of revenue, or grew more than 20 percentage points faster than revenue.",
        queries=["related party transactions total", "transactions with related parties", "revenue from operations"],
        fields=["rpt_current", "rpt_previous", "revenue_current", "revenue_previous"],
        flagged_text={"en": "Related-party deals are {rpt_pct_revenue:.0f}% of revenue and grew {rpt_growth:.0f}% vs revenue growth of {revenue_growth:.0f}%.", "hi": "संबंधित पक्षों से सौदे आय के {rpt_pct_revenue:.0f}% हैं और {rpt_growth:.0f}% बढ़े, जबकि आय {revenue_growth:.0f}% बढ़ी।"},
        passed_text={"en": "Related-party deals are {rpt_pct_revenue:.0f}% of revenue, in line with the business.", "hi": "संबंधित पक्षों से सौदे आय के {rpt_pct_revenue:.0f}% हैं, जो सामान्य है।"},
    ),
    Check(
        id="contingent_liabilities",
        kind="numeric",
        severity="medium",
        title={"en": "Big possible bills kept off the balance sheet", "hi": "बैलेंस शीट से बाहर बड़ी आकस्मिक देनदारियाँ"},
        what={
            "en": "Contingent liabilities are payments the company may have to make, from lawsuits, tax disputes or guarantees. They are not counted as debt.",
            "hi": "ये ऐसे भुगतान हैं जो कंपनी को मुकदमों, टैक्स विवादों या गारंटी के कारण करने पड़ सकते हैं।",
        },
        rule="Flag if contingent liabilities not provided for exceed 25% of total equity (net worth).",
        queries=["contingent liabilities not provided for", "claims against the company not acknowledged as debts", "total equity"],
        fields=["contingent_liabilities", "total_equity"],
        flagged_text={"en": "Possible bills equal {contingent_pct_equity:.0f}% of the company's net worth.", "hi": "संभावित भुगतान कंपनी की नेट वर्थ के {contingent_pct_equity:.0f}% के बराबर हैं।"},
        passed_text={"en": "Possible bills are {contingent_pct_equity:.0f}% of net worth, a modest amount.", "hi": "संभावित भुगतान नेट वर्थ के {contingent_pct_equity:.0f}% हैं, जो कम है।"},
    ),
    Check(
        id="cash_vs_profit",
        kind="numeric",
        severity="high",
        title={"en": "Profit rose, but real cash didn't", "hi": "मुनाफ़ा बढ़ा, पर असली नकद नहीं"},
        what={
            "en": "Profit is an accounting number; operating cash flow is money that actually came in. When profit keeps beating cash, the accounts may be stretched.",
            "hi": "मुनाफ़ा हिसाब-किताब का आंकड़ा है; ऑपरेटिंग कैश फ़्लो असली आया पैसा है। लगातार अंतर हो तो खाते खिंचे हुए हो सकते हैं।",
        },
        rule="Flag if operating cash flow over the last two years is below 50% of profit over the same two years, or cash flow fell while profit rose.",
        queries=["net cash generated from operating activities", "profit for the year", "cash flow statement"],
        fields=["pat_current", "pat_previous", "cfo_current", "cfo_previous"],
        flagged_text={"en": "Over two years, cash from operations was {cfo_to_pat:.0f}% of reported profit.", "hi": "दो साल में ऑपरेशन से आया नकद, बताए गए मुनाफ़े का केवल {cfo_to_pat:.0f}% था।"},
        passed_text={"en": "Cash from operations was {cfo_to_pat:.0f}% of profit over two years. Healthy.", "hi": "दो साल में ऑपरेशन से नकद मुनाफ़े का {cfo_to_pat:.0f}% रहा। यह ठीक है।"},
    ),
    Check(
        id="receivables",
        kind="numeric",
        severity="medium",
        title={"en": "Customers owe more, faster than sales grow", "hi": "बिक्री से तेज़ी से बढ़ता बकाया"},
        what={
            "en": "Trade receivables are sales not yet paid for. If they grow much faster than sales, some sales may never turn into cash.",
            "hi": "ग्राहकों पर बकाया वह बिक्री है जिसका पैसा अभी नहीं आया। यह बिक्री से बहुत तेज़ बढ़े तो चिंता की बात है।",
        },
        rule="Flag if trade receivables grew more than 20 percentage points faster than revenue from operations.",
        queries=["trade receivables", "revenue from operations"],
        fields=["receivables_current", "receivables_previous", "revenue_current", "revenue_previous"],
        flagged_text={"en": "Money owed by customers grew {receivables_growth:.0f}% while sales grew {revenue_growth:.0f}%.", "hi": "ग्राहकों पर बकाया {receivables_growth:.0f}% बढ़ा, जबकि बिक्री {revenue_growth:.0f}% बढ़ी।"},
        passed_text={"en": "Money owed by customers grew {receivables_growth:.0f}%, in step with sales ({revenue_growth:.0f}%).", "hi": "बकाया {receivables_growth:.0f}% बढ़ा, बिक्री ({revenue_growth:.0f}%) के साथ।"},
    ),
]

CHECKS_BY_ID = {c.id: c for c in CHECKS}


def _growth(cur: float, prev: float) -> float | None:
    if prev in (0, None) or cur is None:
        return None
    return (cur - prev) / abs(prev) * 100.0


def evaluate_numeric(check_id: str, v: dict[str, float]) -> tuple[str, dict[str, float]] | None:
    """Apply the published rule to extracted figures. Returns (status, derived) or None if figures are missing."""
    d: dict[str, float] = {}
    try:
        if check_id == "promoter_pledge":
            p = float(v["pledged_pct_of_promoter_holding"])
            d["pledged_pct_of_promoter_holding"] = p
            return ("flagged" if p > 10 else "passed"), d
        if check_id == "related_party":
            rc, vc = float(v["rpt_current"]), float(v["revenue_current"])
            d["rpt_pct_revenue"] = rc / vc * 100
            flagged = d["rpt_pct_revenue"] > 10
            if v.get("rpt_previous") is not None and v.get("revenue_previous") is not None:
                # the growth test needs last year's figures too; without them only the size test is applied
                d["rpt_growth"] = _growth(rc, float(v["rpt_previous"])) or 0.0
                d["revenue_growth"] = _growth(vc, float(v["revenue_previous"])) or 0.0
                flagged = flagged or (d["rpt_growth"] - d["revenue_growth"]) > 20
            return ("flagged" if flagged else "passed"), d
        if check_id == "contingent_liabilities":
            cl, eq = float(v["contingent_liabilities"]), float(v["total_equity"])
            d["contingent_pct_equity"] = cl / eq * 100
            return ("flagged" if d["contingent_pct_equity"] > 25 else "passed"), d
        if check_id == "cash_vs_profit":
            pc, pp, cc, cp = (float(v[k]) for k in ("pat_current", "pat_previous", "cfo_current", "cfo_previous"))
            pat2, cfo2 = pc + pp, cc + cp
            d["cfo_to_pat"] = (cfo2 / pat2 * 100) if pat2 > 0 else 100.0
            # 'cash fell while profit rose' only matters if cash no longer covers profit: a company whose
            # operating cash is still twice its profit is not showing weak earnings quality
            if pat2 > 0 and not (-1000 <= d["cfo_to_pat"] <= 1000):
                # cash ten times profit (or worse) almost always means the two figures were read in different
                # units (lakh vs crore) or from different statements: don't call that healthy, say we can't tell
                return "unverified", d
            diverging = pc > pp and cc < cp and cfo2 < pat2
            flagged = pat2 > 0 and (d["cfo_to_pat"] < 50 or diverging)
            return ("flagged" if flagged else "passed"), d
        if check_id == "receivables":
            rc, rp, vc, vp = (float(v[k]) for k in ("receivables_current", "receivables_previous", "revenue_current", "revenue_previous"))
            d["receivables_growth"] = _growth(rc, rp) or 0.0
            d["revenue_growth"] = _growth(vc, vp) or 0.0
            return ("flagged" if d["receivables_growth"] - d["revenue_growth"] > 20 else "passed"), d
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return None
    return None


# Shorter wording when only part of a rule could be applied (e.g. no previous-year figures)
SHORT_TEXT = {
    "related_party": {"en": "Related-party deals are {rpt_pct_revenue:.0f}% of revenue (limit 10%).",
                      "hi": "संबंधित पक्षों से सौदे आय के {rpt_pct_revenue:.0f}% हैं (सीमा 10%)।"},
}

# Shown when the figures were found but don't make sense together, so no verdict is given.
IMPLAUSIBLE_TEXT = {
    "cash_vs_profit": {"en": "Figures don't add up (cash {cfo_to_pat:.0f}% of profit): probably read in different units. Not scored.",
                       "hi": "आंकड़े मेल नहीं खाते (नकद मुनाफ़े का {cfo_to_pat:.0f}%): शायद अलग इकाइयों में पढ़े गए। स्कोर में नहीं गिना।"},
}

# Figures a check cannot do without; the rest refine it when found.
REQUIRED = {"related_party": ["rpt_current", "revenue_current"]}


def required_fields(check) -> list[str]:
    return REQUIRED.get(check.id, check.fields)


# Checks built for ordinary businesses that mislead for lenders and insurers:
# - a bank's operating cash flow swings with deposits and loans, not with profit quality;
# - banks and insurers have no trade receivables in the usual sense;
# - a bank's guarantees and letters of credit are normal business and dwarf its equity.
NOT_FOR_FINANCIALS = {"cash_vs_profit", "receivables", "contingent_liabilities"}
_FIN_SECTOR = ("bank", "financ", "insurance", "nbfc", "capital market", "lending", "housing finance")
_FIN_NAME = (" bank", "finance", "financial", "insurance", "assurance", "capital ltd", "housing fin")


def is_financial(company: dict) -> bool:
    sector = str(company.get("sector", "")).lower()
    name = " " + str(company.get("name", "")).lower()
    return any(k in sector for k in _FIN_SECTOR) or any(k in name for k in _FIN_NAME)


NOT_APPLICABLE_TEXT = {
    "en": "Not used for banks, lenders and insurers: this test is built for ordinary businesses and would give false alarms here.",
    "hi": "बैंक, ऋणदाता और बीमा कंपनियों पर लागू नहीं: यह जाँच सामान्य कारोबार के लिए है और यहाँ गलत चेतावनी देगी।",
}


# Shown next to every finding: why it could be a false alarm, and what would clear it.
CAVEATS: dict[str, dict[str, dict[str, str]]] = {
    "auditor_opinion": {
        "caveat": {"en": "An 'emphasis of matter' paragraph alone is not a qualified opinion, and some qualifications concern a single one-off accounting point.",
                   "hi": "केवल 'emphasis of matter' पैराग्राफ़ क्वालिफ़ाइड राय नहीं है, और कुछ आपत्तियाँ एक बार के लेखा मुद्दे की होती हैं।"},
        "clears": {"en": "A clean (unmodified) opinion in the next annual report, with the issue resolved.",
                   "hi": "अगली सालाना रिपोर्ट में साफ़ राय, और मुद्दा सुलझ जाए।"},
    },
    "auditor_change": {
        "caveat": {"en": "Indian law makes companies rotate audit firms after their term (up to 10 years for a firm), so a scheduled rotation is normal. The concern is a resignation mid-term or with vague reasons.",
                   "hi": "भारतीय कानून में तय अवधि के बाद ऑडिट फ़र्म बदलना ज़रूरी है, इसलिए तय बदलाव सामान्य है। चिंता बीच में इस्तीफ़े या अस्पष्ट कारण की है।"},
        "clears": {"en": "The change turns out to be a scheduled rotation, or the outgoing auditor's stated reason raises no concern.",
                   "hi": "बदलाव तय रोटेशन निकले, या पुराने ऑडिटर का कारण चिंता वाला न हो।"},
    },
    "promoter_pledge": {
        "caveat": {"en": "Some pledges secure loans taken by the company or its group and are routine. Companies with no promoter (such as some large banks) show no pledge at all.",
                   "hi": "कुछ गिरवी कंपनी या समूह के कर्ज़ के लिए सामान्य होती हैं। जिन कंपनियों का कोई प्रमोटर नहीं, वहाँ गिरवी होती ही नहीं।"},
        "clears": {"en": "Pledged shares fall below 10% of the promoters' holding, or the pledges are released.",
                   "hi": "गिरवी शेयर प्रमोटर हिस्सेदारी के 10% से नीचे आ जाएँ, या छुड़ा लिए जाएँ।"},
    },
    "related_party": {
        "caveat": {"en": "Many groups trade with their own subsidiaries and associates in the normal course of business, at market prices and with audit-committee approval.",
                   "hi": "कई समूह अपनी सहायक कंपनियों से सामान्य कारोबार में, बाज़ार भाव पर और ऑडिट कमेटी की मंज़ूरी से लेन-देन करते हैं।"},
        "clears": {"en": "Related-party deals shrink relative to revenue, or are shown to be at market prices with independent approval.",
                   "hi": "संबंधित पक्ष सौदे आय के मुकाबले घटें, या बाज़ार भाव और स्वतंत्र मंज़ूरी साबित हो।"},
    },
    "contingent_liabilities": {
        "caveat": {"en": "Much of this is often tax demands under appeal, which companies frequently win, or guarantees given for their own subsidiaries.",
                   "hi": "इसका बड़ा हिस्सा अक्सर अपील में चल रहे टैक्स दावे होते हैं, जो कंपनियाँ कई बार जीतती हैं, या अपनी सहायक कंपनियों की गारंटी।"},
        "clears": {"en": "Disputes are settled, or the amount falls below 25% of net worth.",
                   "hi": "विवाद सुलझ जाएँ, या रकम नेट वर्थ के 25% से नीचे आ जाए।"},
    },
    "cash_vs_profit": {
        "caveat": {"en": "Fast-growing, seasonal or project-based businesses often tie up cash in stock and dues for a while.",
                   "hi": "तेज़ी से बढ़ती, मौसमी या प्रोजेक्ट वाली कंपनियों का नकद कुछ समय स्टॉक और बकाया में फँसा रहता है।"},
        "clears": {"en": "Cash from operations catches up with profit over the next year or two.",
                   "hi": "अगले एक-दो साल में कारोबार से नकद मुनाफ़े के बराबर आ जाए।"},
    },
    "receivables": {
        "caveat": {"en": "Receivables can jump for a while after a large order near year-end or a change in credit terms.",
                   "hi": "साल के अंत में बड़े ऑर्डर या उधार की शर्तें बदलने से बकाया कुछ समय के लिए बढ़ सकता है।"},
        "clears": {"en": "Growth in money owed by customers falls back in line with sales growth.",
                   "hi": "ग्राहकों पर बकाया की बढ़त फिर बिक्री की बढ़त के बराबर हो जाए।"},
    },
}


# ------------------------------------------------------------------ severity of a finding
LEVEL_POINTS = {"high": 30, "moderate": 15, "low": 5}


def finding_level(check_id: str, base_severity: str, derived: dict | None) -> str:
    """Low / Moderate / High for one warning sign: the check's weight, adjusted by how far past
    its threshold the figures are (so 'just over the line' reads differently from 'far over')."""
    d = derived or {}

    def by_ratio(ratio: float) -> str:
        return "high" if ratio >= 3 else "moderate" if ratio >= 1.5 else "low"

    try:
        if check_id == "promoter_pledge" and "pledged_pct_of_promoter_holding" in d:
            return by_ratio(d["pledged_pct_of_promoter_holding"] / 10)
        if check_id == "contingent_liabilities" and "contingent_pct_equity" in d:
            return by_ratio(d["contingent_pct_equity"] / 25)
        if check_id == "related_party" and "rpt_pct_revenue" in d:
            gap = d.get("rpt_growth", 0) - d.get("revenue_growth", 0)
            return by_ratio(max(d["rpt_pct_revenue"] / 10, gap / 20))
        if check_id == "receivables" and "receivables_growth" in d:
            return by_ratio((d["receivables_growth"] - d.get("revenue_growth", 0)) / 20)
        if check_id == "cash_vs_profit" and "cfo_to_pat" in d:
            r = d["cfo_to_pat"]
            return "high" if r < 0 else "moderate" if r < 25 else "low"
    except (TypeError, ZeroDivisionError):
        pass
    return "high" if base_severity == "high" else "moderate"


LEVEL_TEXT = {
    "high": {"en": "High", "hi": "ऊँचा"},
    "moderate": {"en": "Moderate", "hi": "मध्यम"},
    "low": {"en": "Low", "hi": "कम"},
}


def fy_end(fy: str):
    """'FY2025-26' -> date(2026, 3, 31); None if it can't be read."""
    import datetime as dt
    import re

    m = re.search(r"(\d{4})\s*[-–/]\s*(\d{2,4})", fy or "")
    if not m:
        return None
    end = int(m.group(2))
    end = end if end > 99 else (int(m.group(1)) // 100) * 100 + end
    try:
        return dt.date(end, 3, 31)
    except ValueError:
        return None


def is_old_report(fy: str, today=None, months: int = 18) -> bool:
    """A report is 'old' if its financial year ended more than `months` ago."""
    import datetime as dt

    end = fy_end(fy)
    if not end:
        return False
    today = today or dt.date.today()
    return (today.year - end.year) * 12 + (today.month - end.month) > months

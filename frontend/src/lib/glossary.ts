/**
 * Plain-language glossary. `short` is one sentence a beginner can read in a
 * tooltip; `more` adds detail for the glossary page; `example` makes it concrete.
 */
export type Category = "basics" | "costs" | "fund_types" | "portfolio" | "reports" | "warnings";

export interface Term {
  id: string;
  term: string;
  hi: string; // Hindi name
  category: Category;
  short: { en: string; hi: string };
  more?: string;
  example?: string;
  related?: string[];
}

export const CATEGORIES: { id: Category; en: string; hi: string }[] = [
  { id: "basics", en: "Basics", hi: "बुनियादी बातें" },
  { id: "costs", en: "Costs and plans", hi: "खर्च और प्लान" },
  { id: "fund_types", en: "Types of funds", hi: "फंड के प्रकार" },
  { id: "portfolio", en: "Your portfolio", hi: "आपका पोर्टफ़ोलियो" },
  { id: "reports", en: "Company reports", hi: "कंपनी की रिपोर्ट" },
  { id: "warnings", en: "Warning signs", hi: "चेतावनी संकेत" },
];

export const TERMS: Term[] = [
  // ---------------------------------------------------------------- basics
  {
    id: "mutual-fund", term: "Mutual fund", hi: "म्यूचुअल फंड", category: "basics",
    short: { en: "A pool of money from many people that a professional invests in shares, bonds or both.", hi: "कई लोगों का इकट्ठा पैसा, जिसे एक पेशेवर मैनेजर शेयरों या बॉन्ड में लगाता है।" },
    more: "When you buy a mutual fund you own a small slice of everything the fund holds. The fund house (AMC) charges a yearly fee for managing it.",
    example: "Putting ₹5,000 in a large-cap fund means you own a tiny part of ~50–100 big companies.",
    related: ["amc", "nav", "scheme"],
  },
  {
    id: "amc", term: "Fund house (AMC)", hi: "फंड हाउस (AMC)", category: "basics",
    short: { en: "The company that runs mutual funds, like SBI MF or Aditya Birla Sun Life MF.", hi: "वह कंपनी जो म्यूचुअल फंड चलाती है, जैसे SBI MF या आदित्य बिड़ला MF।" },
    more: "AMC stands for Asset Management Company. One fund house usually runs dozens of schemes.",
  },
  {
    id: "scheme", term: "Scheme", hi: "स्कीम", category: "basics",
    short: { en: "One specific fund run by a fund house, e.g. 'Aditya Birla Sun Life Flexi Cap Fund'.", hi: "किसी फंड हाउस का एक खास फंड।" },
  },
  {
    id: "nav", term: "NAV", hi: "NAV (प्रति यूनिट कीमत)", category: "basics",
    short: { en: "Net Asset Value: the price of one unit of a fund, updated every working day.", hi: "फंड की एक यूनिट की कीमत, जो हर कामकाजी दिन बदलती है।" },
    more: "NAV = (value of everything the fund owns − its expenses) ÷ number of units. Fees are taken out before NAV is published, so you never see a separate bill.",
    related: ["ter"],
  },
  {
    id: "units", term: "Units", hi: "यूनिट", category: "basics",
    short: { en: "What you get when you invest: your money ÷ NAV.", hi: "निवेश पर मिलने वाला हिस्सा: आपका पैसा ÷ NAV।" },
    example: "₹10,000 at a NAV of ₹50 buys 200 units.",
  },
  {
    id: "current-value", term: "Current value", hi: "मौजूदा कीमत", category: "basics",
    short: { en: "What your holding is worth today: units × today's NAV. This is the number Pardarshi asks for.", hi: "आज आपके निवेश की कीमत: यूनिट × आज का NAV।" },
    more: "Not the amount you invested. Your app (Groww, Zerodha, Paytm Money…) or CAS statement shows it as 'Current value' or 'Market value'.",
  },
  {
    id: "sip", term: "SIP", hi: "SIP", category: "basics",
    short: { en: "Systematic Investment Plan: investing a fixed amount every month automatically.", hi: "हर महीने तय रकम अपने आप निवेश करना।" },
  },
  {
    id: "cas", term: "CAS statement", hi: "CAS स्टेटमेंट", category: "basics",
    short: { en: "Consolidated Account Statement: one free PDF listing all your mutual funds across fund houses.", hi: "एक मुफ़्त PDF जिसमें आपके सभी म्यूचुअल फंड एक साथ होते हैं।" },
    more: "Request it from CAMS or KFintech (mutual funds) or NSDL/CDSL (also shows shares). It arrives by email as a password-protected PDF.",
    related: ["folio", "pan"],
  },
  {
    id: "folio", term: "Folio number", hi: "फ़ोलियो नंबर", category: "basics",
    short: { en: "Your account number with a fund house. Pardarshi never keeps it.", hi: "फंड हाउस में आपका खाता नंबर। पारदर्शी इसे नहीं रखता।" },
  },
  {
    id: "pan", term: "PAN", hi: "PAN", category: "basics",
    short: { en: "Your tax ID. Often the password of NSDL/CDSL statements. Pardarshi removes it before anything else sees your data.", hi: "आपका टैक्स ID। पारदर्शी इसे तुरंत हटा देता है।" },
  },
  {
    id: "amfi", term: "AMFI", hi: "AMFI", category: "basics",
    short: { en: "Association of Mutual Funds in India: publishes official data on every scheme, NAV and fee.", hi: "भारत के म्यूचुअल फंड का संघ, जो हर स्कीम का आधिकारिक डेटा देता है।" },
  },
  {
    id: "sebi", term: "SEBI", hi: "SEBI", category: "basics",
    short: { en: "Securities and Exchange Board of India: the regulator for mutual funds and the stock market.", hi: "भारत का शेयर बाज़ार और म्यूचुअल फंड नियामक।" },
  },
  {
    id: "isin", term: "ISIN", hi: "ISIN", category: "basics",
    short: { en: "A 12-character code that uniquely identifies a share or fund plan, e.g. INE040A01034.", hi: "हर शेयर या फंड प्लान का 12 अक्षरों का अनोखा कोड।" },
  },
  // ---------------------------------------------------------------- costs
  {
    id: "ter", term: "Expense ratio (TER)", hi: "खर्च अनुपात (TER)", category: "costs",
    short: { en: "The yearly fee a fund charges, as a % of your money. Taken out of NAV daily, so you never see a bill.", hi: "फंड की सालाना फीस, आपके पैसे का %। यह रोज़ NAV से कटती है।" },
    more: "Total Expense Ratio. A 1.7% TER on ₹1 lakh is about ₹1,700 a year. From April 2026 SEBI splits it into a Base Expense Ratio (BER) plus brokerage, transaction costs and taxes.",
    example: "Regular plan TER 1.72%, Direct plan TER 0.68% for the same fund.",
    related: ["direct-plan", "regular-plan", "commission"],
  },
  {
    id: "direct-plan", term: "Direct plan", hi: "डायरेक्ट प्लान", category: "costs",
    short: { en: "Buying a fund straight from the fund house or a direct platform. No distributor commission, so a lower fee.", hi: "सीधे फंड हाउस से खरीदना। कोई कमीशन नहीं, इसलिए फीस कम।" },
    more: "Same fund, same manager, same holdings as the regular plan. Only the cost is different.",
    related: ["regular-plan", "ter"],
  },
  {
    id: "regular-plan", term: "Regular plan", hi: "रेगुलर प्लान", category: "costs",
    short: { en: "Buying through a distributor, bank or agent. A commission is built into the fee every year.", hi: "डिस्ट्रीब्यूटर या बैंक के ज़रिए खरीदना। फीस में हर साल कमीशन शामिल।" },
    more: "Regular plans aren't 'bad': you may be paying for real advice. Pardarshi shows what that service costs in rupees so you can decide if it's worth it.",
    related: ["direct-plan", "commission"],
  },
  {
    id: "commission", term: "Distributor commission", hi: "डिस्ट्रीब्यूटर कमीशन", category: "costs",
    short: { en: "The share of a regular plan's fee paid to whoever sold it to you, every year you stay invested.", hi: "रेगुलर प्लान की फीस का वह हिस्सा जो बेचने वाले को हर साल मिलता है।" },
  },
  {
    id: "compounding", term: "Compounding", hi: "चक्रवृद्धि", category: "costs",
    short: { en: "Growth on top of growth. It is also why a small yearly fee becomes a big rupee amount over 20 years.", hi: "बढ़त पर बढ़त। इसी कारण छोटी सालाना फीस 20 साल में बड़ी रकम बन जाती है।" },
    example: "A 1% yearly difference on ₹1 lakh growing at 12% costs roughly ₹1.4 lakh over 20 years.",
  },
  // ---------------------------------------------------------------- fund types
  {
    id: "equity", term: "Equity", hi: "इक्विटी (शेयर)", category: "fund_types",
    short: { en: "Shares in companies. Equity funds mostly buy shares: higher growth, bigger ups and downs.", hi: "कंपनियों के शेयर। इक्विटी फंड ज़्यादातर शेयर खरीदते हैं।" },
  },
  {
    id: "debt", term: "Debt fund", hi: "डेट फंड", category: "fund_types",
    short: { en: "Funds that lend money (bonds, deposits). Steadier than equity, usually lower returns.", hi: "बॉन्ड जैसे कर्ज़ में पैसा लगाने वाले फंड। ज़्यादा स्थिर।" },
  },
  {
    id: "market-cap", term: "Large / Mid / Small cap", hi: "लार्ज / मिड / स्मॉल कैप", category: "fund_types",
    short: { en: "Company size by stock-market value: the 100 biggest are large cap, next 150 mid cap, the rest small cap.", hi: "कंपनी का आकार: सबसे बड़ी 100 लार्ज कैप, अगली 150 मिड कैप, बाकी स्मॉल कैप।" },
  },
  {
    id: "flexi-cap", term: "Flexi cap fund", hi: "फ्लेक्सी कैप फंड", category: "fund_types",
    short: { en: "A fund free to buy companies of any size.", hi: "किसी भी आकार की कंपनी खरीद सकने वाला फंड।" },
  },
  {
    id: "index-fund", term: "Index fund", hi: "इंडेक्स फंड", category: "fund_types",
    short: { en: "Copies a market index like the Nifty 50 instead of picking stocks. Usually the cheapest kind of fund.", hi: "Nifty 50 जैसे इंडेक्स की नकल करता है। आमतौर पर सबसे सस्ता।" },
  },
  {
    id: "etf", term: "ETF", hi: "ETF", category: "fund_types",
    short: { en: "Exchange Traded Fund: like an index fund, but bought and sold on the stock exchange like a share.", hi: "इंडेक्स फंड जैसा, पर शेयर की तरह बाज़ार में खरीदा-बेचा जाता है।" },
  },
  {
    id: "elss", term: "ELSS", hi: "ELSS (टैक्स सेवर)", category: "fund_types",
    short: { en: "Equity tax-saver fund with a 3-year lock-in.", hi: "3 साल लॉक-इन वाला टैक्स बचाने वाला इक्विटी फंड।" },
  },
  {
    id: "hybrid", term: "Hybrid fund", hi: "हाइब्रिड फंड", category: "fund_types",
    short: { en: "Mixes shares and bonds in one fund.", hi: "एक ही फंड में शेयर और बॉन्ड दोनों।" },
  },
  // ---------------------------------------------------------------- portfolio
  {
    id: "portfolio", term: "Portfolio", hi: "पोर्टफ़ोलियो", category: "portfolio",
    short: { en: "Everything you've invested in, taken together.", hi: "आपके सभी निवेश, एक साथ।" },
  },
  {
    id: "diversification", term: "Diversification", hi: "विविधता", category: "portfolio",
    short: { en: "Spreading money across different companies and sectors so one bad bet hurts less.", hi: "पैसा अलग-अलग कंपनियों और सेक्टरों में बाँटना ताकि जोखिम कम हो।" },
    more: "Owning more funds does not always mean more diversification: different funds can hold the same companies.",
    related: ["overlap"],
  },
  {
    id: "overlap", term: "Portfolio overlap", hi: "पोर्टफ़ोलियो दोहराव", category: "portfolio",
    short: { en: "How much two funds hold the same companies. 80% overlap means they are mostly the same fund.", hi: "दो फंड कितनी हद तक एक ही कंपनियाँ रखते हैं। 80% का मतलब लगभग एक जैसे।" },
    more: "Pardarshi's formula: for each company both funds hold, take the smaller weight; add them up. Below ~33% is generally seen as well diversified.",
    related: ["behaves-like", "diversification"],
  },
  {
    id: "behaves-like", term: "Behaves like N funds", hi: "असल में N फंड जैसा", category: "portfolio",
    short: { en: "Pardarshi's one-number summary of overlap: 6 funds that behave like 1.9 give you the spread of about 2.", hi: "दोहराव का एक आंकड़ा: 6 फंड जो 1.9 जैसे हैं, असल में 2 जितनी विविधता देते हैं।" },
  },
  {
    id: "exposure", term: "Exposure", hi: "एक्सपोज़र", category: "portfolio",
    short: { en: "How much of your money ends up in one company or sector, adding up all your funds.", hi: "सभी फंड मिलाकर किसी एक कंपनी या सेक्टर में आपका कितना पैसा है।" },
    example: "If three funds each hold HDFC Bank, your exposure is the sum of all three slices.",
  },
  {
    id: "weight", term: "Weight (% of NAV)", hi: "वेटेज", category: "portfolio",
    short: { en: "The share of a fund's money in one holding. 8% weight = 8 rupees of every 100 in that company.", hi: "किसी एक कंपनी में फंड के पैसे का हिस्सा।" },
  },
  {
    id: "sector", term: "Sector", hi: "सेक्टर", category: "portfolio",
    short: { en: "The industry a company is in: banking, IT, pharma, energy…", hi: "कंपनी का उद्योग: बैंकिंग, IT, फार्मा…" },
  },
  {
    id: "concentration", term: "Concentration", hi: "एकाग्रता", category: "portfolio",
    short: { en: "How much of your money sits in a few companies. 'Top 10 = 60%' means highly concentrated.", hi: "आपका कितना पैसा कुछ ही कंपनियों में है।" },
  },
  // ---------------------------------------------------------------- reports
  {
    id: "annual-report", term: "Annual report", hi: "सालाना रिपोर्ट", category: "reports",
    short: { en: "The yearly document every listed company publishes, with its accounts and the auditor's opinion.", hi: "हर लिस्टेड कंपनी का सालाना दस्तावेज़, जिसमें उसके खाते और ऑडिटर की राय होती है।" },
  },
  {
    id: "auditor", term: "Auditor", hi: "ऑडिटर", category: "reports",
    short: { en: "An outside accountant who checks a company's books and signs an opinion on them.", hi: "बाहरी अकाउंटेंट जो कंपनी के खाते जाँचता है।" },
    related: ["qualified-opinion"],
  },
  {
    id: "promoter", term: "Promoter", hi: "प्रमोटर", category: "reports",
    short: { en: "The founders or controlling owners of a company.", hi: "कंपनी के संस्थापक या नियंत्रण रखने वाले मालिक।" },
  },
  {
    id: "revenue", term: "Revenue", hi: "आय (रेवेन्यू)", category: "reports",
    short: { en: "Total money from selling products or services, before costs.", hi: "खर्च से पहले, बिक्री से कुल कमाई।" },
  },
  {
    id: "profit", term: "Profit (PAT)", hi: "मुनाफ़ा (PAT)", category: "reports",
    short: { en: "What's left after all costs and taxes. An accounting number, not the same as cash received.", hi: "सारे खर्च और टैक्स के बाद बचा हिस्सा। यह असली नकद जैसा नहीं है।" },
    related: ["cfo"],
  },
  {
    id: "cfo", term: "Operating cash flow", hi: "ऑपरेटिंग कैश फ़्लो", category: "reports",
    short: { en: "Cash that actually came in from the business during the year.", hi: "साल में धंधे से असल में आया नकद।" },
    more: "Healthy companies turn most of their profit into cash. If profit keeps rising but cash doesn't, the profit may not be real yet.",
  },
  {
    id: "net-worth", term: "Net worth (total equity)", hi: "नेट वर्थ", category: "reports",
    short: { en: "What a company owns minus what it owes: the shareholders' share.", hi: "कंपनी की संपत्ति घटा देनदारी।" },
  },
  // ---------------------------------------------------------------- warnings
  {
    id: "red-flag", term: "Red flag / warning sign", hi: "चेतावनी संकेत", category: "warnings",
    short: { en: "A pattern in a company's report that experts treat as a reason to look closer. Not proof of wrongdoing.", hi: "रिपोर्ट में ऐसा संकेत जिस पर ध्यान देना चाहिए। गड़बड़ी का सबूत नहीं।" },
  },
  {
    id: "qualified-opinion", term: "Qualified opinion", hi: "क्वालिफ़ाइड राय", category: "warnings",
    short: { en: "The auditor signs off 'except for' something they couldn't verify. A serious warning.", hi: "ऑडिटर कहता है 'इसके अलावा सब ठीक है'। गंभीर संकेत।" },
    more: "Worse still: an 'adverse' opinion or a 'disclaimer' (the auditor couldn't form an opinion). A clean report is called 'unmodified'.",
  },
  {
    id: "going-concern", term: "Going concern doubt", hi: "चलते रहने पर संदेह", category: "warnings",
    short: { en: "The auditor warns the company may not survive the next year.", hi: "ऑडिटर चेतावनी देता है कि कंपनी शायद अगले साल न चले।" },
  },
  {
    id: "pledge", term: "Promoter pledge", hi: "प्रमोटर गिरवी", category: "warnings",
    short: { en: "Owners borrowing money by pledging their shares. If the price falls, lenders can sell them.", hi: "मालिकों का शेयर गिरवी रखकर कर्ज़ लेना। दाम गिरे तो शेयर बिक सकते हैं।" },
    more: "Pardarshi flags more than 10% of promoter shares pledged.",
  },
  {
    id: "rpt", term: "Related-party transactions", hi: "संबंधित पक्ष लेन-देन", category: "warnings",
    short: { en: "Deals between the company and firms or people linked to its owners. Can move money out quietly.", hi: "कंपनी और मालिकों से जुड़े लोगों/कंपनियों के बीच सौदे।" },
    more: "Pardarshi flags these above 10% of revenue, or growing 20 percentage points faster than revenue.",
  },
  {
    id: "contingent", term: "Contingent liabilities", hi: "आकस्मिक देनदारियाँ", category: "warnings",
    short: { en: "Bills the company may have to pay (lawsuits, tax disputes, guarantees) that aren't counted as debt yet.", hi: "ऐसे भुगतान जो करने पड़ सकते हैं, पर अभी कर्ज़ में नहीं गिने जाते।" },
    more: "Pardarshi flags these above 25% of net worth.",
  },
  {
    id: "receivables", term: "Trade receivables", hi: "ग्राहकों पर बकाया", category: "warnings",
    short: { en: "Money customers owe for sales already counted as revenue.", hi: "ग्राहकों पर बकाया, जिसकी बिक्री पहले ही गिनी जा चुकी है।" },
    more: "If this grows much faster than sales, some sales may never turn into cash. Pardarshi flags a gap over 20 percentage points.",
  },
  {
    id: "verified-quote", term: "Verified quote", hi: "पुष्टि किया उद्धरण", category: "warnings",
    short: { en: "Pardarshi checked that the quoted line, including every number in it, really appears on the cited page.", hi: "पारदर्शी ने जाँचा कि उद्धरण और उसके सारे आंकड़े सच में उसी पेज पर हैं।" },
  },
];

export const TERM_BY_ID: Record<string, Term> = Object.fromEntries(TERMS.map((t) => [t.id, t]));

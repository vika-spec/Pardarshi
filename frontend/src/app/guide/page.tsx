"use client";

import Link from "next/link";
import { Term } from "@/components/Term";
import { useLang } from "@/lib/i18n";

type Step = { n: string; title: string; body: React.ReactNode };

export default function GuidePage() {
  const { lang } = useLang();
  const hi = lang === "hi";

  const steps: Step[] = hi
    ? [
        { n: "1", title: "अपने फंड की जानकारी तैयार रखें", body: <>तीन में से कोई एक: <b>CAS स्टेटमेंट</b> (सबसे अच्छा, सब कुछ अपने आप आता है), या अपने ऐप (Groww, Zerodha, Paytm Money) से <b>फंड का नाम और आज की कीमत</b>। कुछ भी नहीं है? <b>सैंपल पोर्टफ़ोलियो</b> से देखें कि रिपोर्ट कैसी दिखती है।</> },
        { n: "2", title: "होम पेज पर ‘मेरा पोर्टफ़ोलियो जाँचें’ दबाएँ", body: <>तीन टैब दिखेंगे। <b>स्टेटमेंट डालें</b>: PDF चुनें और उसका पासवर्ड डालें। <b>फंड का नाम चुनें</b>: नाम टाइप करें, सूची से चुनें, आज की कीमत डालें, डायरेक्ट या रेगुलर चुनें, फिर ‘जोड़ें’। <b>सूची पेस्ट करें</b>: हर लाइन में नाम, कॉमा, कीमत। उम्र डालना वैकल्पिक है; इससे 60 की उम्र तक का खर्च दिखता है।</> },
        { n: "3", title: "रिपोर्ट ऊपर से नीचे पढ़ें", body: <>सबसे ऊपर का बही-खाता कार्ड पाँच मुख्य आंकड़े देता है। फिर चार कॉलम: चेतावनी संकेत, आपके पास असल में क्या है, फंड कितना दोहराते हैं, और छुपा खर्च। किसी भी रेखांकित शब्द पर टैप करें तो उसका मतलब दिखेगा।</> },
        { n: "4", title: "सबूत देखें और सवाल पूछें", body: <>चेतावनी संकेत पर ‘सबूत देखें’ दबाएँ: कंपनी की रिपोर्ट का सटीक पेज खुलेगा और लाइन हाइलाइट होगी। कोई भी सवाल ‘सवाल पूछें’ में हिंदी या अंग्रेज़ी में लिखें।</> },
      ]
    : [
        { n: "1", title: "Get your fund details ready", body: <>Any one of these: a <b><Term id="cas">CAS statement</Term></b> (best: everything is read automatically), or just the <b>fund names and today&apos;s values</b> from your app (Groww, Zerodha, Paytm Money…). Nothing at hand? Use the <b>sample portfolio</b> to see what a report looks like.</> },
        { n: "2", title: "On the home page, press 'Check my portfolio'", body: <>You&apos;ll see three tabs. <b>Upload statement</b>: choose the PDF and type its password. <b>Pick funds by name</b>: type a name, pick it from the list, enter its <Term id="current-value">current value</Term>, choose <Term id="direct-plan">Direct</Term> or <Term id="regular-plan">Regular</Term>, then Add. <b>Paste a list</b>: one fund per line, name then value. Your age is optional; it lets us show costs up to age 60.</> },
        { n: "3", title: "Read the report top to bottom", body: <>The ledger card at the top gives the five headline numbers. Then four columns: the warning signs in companies you hold, what you really own, how much your funds repeat each other, and the hidden cost. Tap any underlined word to see what it means.</> },
        { n: "4", title: "Check the evidence, ask questions", body: <>On a warning sign, press <b>See evidence</b>: the company&apos;s report opens at the exact page with the line highlighted. Ask anything in <b>Ask a question</b>, in English or Hindi.</> },
      ];

  const sections = hi
    ? [
        ["बही-खाता कार्ड", "कुल कीमत, कितने फंड, वे असल में कितने फंड जैसे हैं, कमीशन का खर्च, और चेतावनी संकेत।"],
        ["कॉलम 01 · चेतावनी संकेत", "आपके फंड के अंदर की बड़ी कंपनियों की सालाना रिपोर्ट पर 7 जाँच, हर संकेत के साथ पेज। यह भी दिखता है कि आप वह कंपनी किन फंड के ज़रिए रखते हैं।"],
        ["कॉलम 02 · असल में क्या है", "सभी फंड मिलाकर आपकी 10 सबसे बड़ी कंपनियाँ और सेक्टर। अगर ऊपर की 10 कंपनियों में आधे से ज़्यादा पैसा है, तो आपका पैसा कुछ ही कंपनियों में है।"],
        ["कॉलम 03 · दोहराव", "हर दो फंड के बीच कितना दोहराव है। गहरा लाल = ज़्यादा एक जैसे। 50% से ऊपर हो तो सोचें कि क्या दोनों ज़रूरी हैं।"],
        ["कॉलम 04 · छुपा खर्च", "रेगुलर प्लान में कमीशन के कारण कितना कम पैसा बनेगा। अपनी उम्र बदलकर देखें।"],
      ]
    : [
        ["The ledger card", "Total value, how many funds, how many they behave like, the commission cost, and warning signs found."],
        ["COL. 01 · Where the warning signs are", "Seven checks on the annual reports of the biggest companies inside your funds, each with its page. It also shows which of your funds you hold each company through. A flag is a reason to look closer, never proof of wrongdoing."],
        ["COL. 02 · What you really own", "Your 10 biggest companies and sectors after adding up every fund. If the top 10 hold more than half your money, you're concentrated in a few names."],
        ["COL. 03 · How much your funds repeat", "Overlap between every pair of funds. Darker red = more alike. Above about 50%, ask whether you need both."],
        ["COL. 04 · What it quietly costs", "How much less you'll have because of commissions in regular plans. Change your age to see it update."],
      ];

  const faqs = hi
    ? [
        ["क्या मेरा डेटा सेव होता है?", "नहीं। स्टेटमेंट मेमोरी में पढ़ा जाता है और फिर हटा दिया जाता है। नाम, PAN और फ़ोलियो नंबर पहले ही कदम में हटा दिए जाते हैं।"],
        ["क्या यह बताता है कि क्या खरीदें या बेचें?", "नहीं। यह सिर्फ़ दिखाता है कि आपके पोर्टफ़ोलियो में क्या है। फ़ैसला आपका है, या किसी SEBI-पंजीकृत सलाहकार से पूछें।"],
        ["शुरुआती और एक्सपर्ट मोड में क्या फ़र्क है?", "शुरुआती मोड आसान वाक्य और छोटी सूचियाँ दिखाता है। एक्सपर्ट मोड हर टेबल, अनुपात और फ़ॉर्मूला दिखाता है। रिपोर्ट के ऊपर बदलें।"],
        ["मेरा फंड नहीं मिला", "वह अभी हमारे डेटा में नहीं है। रिपोर्ट उसे अलग से 'जो फंड नहीं मिले' में दिखाती है, अंदाज़ा नहीं लगाती।"],
      ]
    : [
        ["Is my data saved?", "No. The statement is read in memory and discarded. Name, PAN and folio numbers are removed in the very first step."],
        ["Does it tell me what to buy or sell?", "No. It shows what's inside your portfolio. Decisions are yours, or ask a SEBI-registered adviser."],
        ["What's the difference between Beginner and Expert?", "Beginner shows plain sentences and short lists. Expert shows every table, ratio and formula. Switch at the top of the report."],
        ["My fund wasn't found", "It isn't in our dataset yet. The report lists it under 'Funds we couldn't match' instead of guessing."],
      ];

  return (
    <div className="wrap section" style={{ maxWidth: 900 }}>
      <p className="eyebrow">{hi ? "कैसे इस्तेमाल करें" : "How to use"}</p>
      <h1 className="display h1" style={{ marginTop: 14 }}>{hi ? "दो मिनट में अपनी पहली रिपोर्ट।" : "Your first report in two minutes."}</h1>
      <p className="lede" style={{ marginTop: 14 }}>
        {hi ? "किसी वित्तीय ज्ञान की ज़रूरत नहीं। अगर कोई शब्द समझ न आए, तो उस पर टैप करें या " : "No finance knowledge needed. If a word is unclear, tap it, or open the "}
        <Link href="/glossary">{hi ? "शब्दकोश" : "glossary"}</Link>.
      </p>

      <ol style={{ listStyle: "none", padding: 0, margin: "34px 0 0" }} className="stack gap-24">
        {steps.map((s) => (
          <li key={s.n} className="row gap-24" style={{ alignItems: "flex-start", flexWrap: "nowrap" }}>
            <span className="step-num" aria-hidden="true">{s.n}</span>
            <div>
              <h2 className="h3">{s.title}</h2>
              <p style={{ margin: "6px 0 0", color: "var(--ink-2)", lineHeight: 1.7 }}>{s.body}</p>
            </div>
          </li>
        ))}
      </ol>

      <div className="row gap-12" style={{ marginTop: 30 }}>
        <Link className="btn btn-primary" href="/#start">{hi ? "अभी शुरू करें" : "Start now"}</Link>
        <Link className="btn" href="/report?sample=1">{hi ? "सैंपल रिपोर्ट देखें" : "See a sample report"}</Link>
      </div>

      <h2 className="display h2" style={{ marginTop: 56 }}>{hi ? "रिपोर्ट कैसे पढ़ें" : "How to read the report"}</h2>
      <dl className="card" style={{ margin: "16px 0 0", padding: "6px 22px" }}>
        {sections.map(([k, v]) => (
          <div key={k} style={{ padding: "14px 0", borderBottom: "1px solid var(--rule)" }}>
            <dt style={{ fontWeight: 600 }}>{k}</dt>
            <dd style={{ margin: "4px 0 0", color: "var(--ink-2)" }}>{v}</dd>
          </div>
        ))}
      </dl>

      <h2 className="display h2" style={{ marginTop: 48 }}>{hi ? "शुरुआती या एक्सपर्ट?" : "Beginner or expert?"}</h2>
      <div className="grid-3" style={{ gap: 16, marginTop: 16 }}>
        <div className="card" style={{ padding: "18px 20px" }}>
          <h3 className="h3">{hi ? "शुरुआती मोड" : "Beginner mode"}</h3>
          <p style={{ margin: "6px 0 0", color: "var(--ink-2)" }}>{hi ? "हर हिस्से के ऊपर आसान वाक्य, बार चार्ट, और ज़रूरी बातें। टेबल छिपी रहती हैं।" : "A plain sentence on top of every section, bar charts, and only what matters. Big tables stay tucked away."}</p>
        </div>
        <div className="card" style={{ padding: "18px 20px" }}>
          <h3 className="h3">{hi ? "एक्सपर्ट मोड" : "Expert mode"}</h3>
          <p style={{ margin: "6px 0 0", color: "var(--ink-2)" }}>{hi ? "पूरा दोहराव मैट्रिक्स, हर फंड का TER, फ़ॉर्मूले खुले हुए, और हर जाँच का नियम।" : "The full overlap matrix, every fund's TER, formulas open by default, and the exact rule behind each check."}</p>
        </div>
      </div>

      <h2 className="display h2" style={{ marginTop: 48 }}>{hi ? "आम सवाल" : "Common questions"}</h2>
      <div className="stack gap-8" style={{ marginTop: 12 }}>
        {faqs.map(([q, a]) => (
          <details key={q} className="card" style={{ padding: "12px 18px" }}>
            <summary style={{ cursor: "pointer", fontWeight: 600, minHeight: 32 }}>{q}</summary>
            <p style={{ margin: "8px 0 0", color: "var(--ink-2)" }}>{a}</p>
          </details>
        ))}
      </div>
    </div>
  );
}

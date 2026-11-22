export const metadata = { title: "Privacy · Pardarshi" };

export default function PrivacyPage() {
  return (
    <div className="wrap section" style={{ maxWidth: 820 }}>
      <p className="eyebrow">Privacy</p>
      <h1 className="display h1" style={{ marginTop: 14 }}>Your statement is read, then forgotten.</h1>
      <div className="stack gap-16" style={{ marginTop: 28, fontSize: 17, lineHeight: 1.75 }}>
        <p><strong>We never store your statement.</strong> The PDF is read in the server&apos;s memory and discarded as soon as your report is built. It is never written to disk or to logs.</p>
        <p><strong>Personal details are removed first.</strong> Your name, PAN, email, phone number, address and folio numbers are dropped by the very first step that reads the file. Nothing after that step, including any AI model, ever sees them.</p>
        <p><strong>What the AI sees.</strong> Only anonymous numbers (fund names, rupee values and the results we calculated) and passages from public annual reports. If you prefer no AI at all, the report works fully without it.</p>
        <p><strong>Your report stays in your browser tab.</strong> It is kept in session storage and disappears when you close the tab. We don&apos;t use tracking cookies or third-party analytics.</p>
        <p><strong>Logs.</strong> The server logs only the request path, status and timing, never query strings, file contents or form fields.</p>
        <p><strong>Retention: zero.</strong> Nothing from your statement is kept after the request finishes, so there is nothing to delete later. The design follows the data-minimisation and purpose-limitation principles of India&apos;s Digital Personal Data Protection (DPDP) Act, 2023: we collect only what is needed to build your report, use it only for that, and keep none of it.</p>
        <p><strong>Not investment advice.</strong> Pardarshi is a research and educational tool, not a SEBI-registered investment adviser. It explains what is in your portfolio; it never tells you what to buy, sell or avoid.</p>
      </div>
    </div>
  );
}

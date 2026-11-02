// Readable rendering of the plain text in assessment sections.
//
// Blocks are separated by blank lines. Lines starting with "- " are bullets. A paragraph or a
// bullet written as "Label: text" shows the label in bold on its own line with the text beneath
// it, so sections read as short labelled items. The exported reports use the same rules
// (api/opendpo/export.py), so the page and the report look alike.

type Item = { label: string | null; text: string };
type Block = { kind: "para"; item: Item } | { kind: "list"; lead: Item | null; items: Item[] };

const LABEL = /^([A-Z][^:]{0,90}?):\s+(\S.*)$/s;

export function splitLabel(line: string): Item {
  const t = line.trim();
  // A short line ending in a colon is a heading for what follows, such as "What to weigh:".
  if (t.endsWith(":") && t.length <= 90 && !/[.!?]\s/.test(t)) return { label: t.slice(0, -1), text: "" };
  const m = LABEL.exec(t);
  if (!m) return { label: null, text: line.trim() };
  const label = m[1];
  const opens = (label.match(/\(/g) ?? []).length;
  const closes = (label.match(/\)/g) ?? []).length;
  // A label is a short name, not a sentence: no sentence break, balanced brackets.
  if (opens !== closes || /[.!?]\s/.test(label)) return { label: null, text: line.trim() };
  return { label, text: m[2].trim() };
}

export function parse(text: string): Block[] {
  const out: Block[] = [];
  for (const raw of text.trim().split(/\n\s*\n/)) {
    const lines = raw.split("\n").map((l) => l.trim()).filter(Boolean);
    if (!lines.length) continue;
    const bullets = lines.filter((l) => l.startsWith("- "));
    if (bullets.length && bullets.length === lines.length) {
      out.push({ kind: "list", lead: null, items: bullets.map((l) => splitLabel(l.slice(2))) });
    } else if (bullets.length && bullets.length === lines.length - 1 && !lines[0].startsWith("- ")) {
      out.push({ kind: "list", lead: splitLabel(lines[0]), items: bullets.map((l) => splitLabel(l.slice(2))) });
    } else {
      out.push({ kind: "para", item: splitLabel(lines.join(" ")) });
    }
  }
  return out;
}

function Para({ item }: { item: Item }) {
  if (!item.label) return <p>{item.text}</p>;
  if (!item.text) return <div className="lbl">{item.label}</div>;
  return (
    <div className="labelled">
      <div className="lbl">{item.label}</div>
      <p>{item.text}</p>
    </div>
  );
}

export function Prose({ text }: { text: string }) {
  return (
    <div className="prose">
      {parse(text).map((b, i) => b.kind === "para" ? <Para key={i} item={b.item} /> : (
        <div key={i}>
          {b.lead && <Para item={b.lead} />}
          <ul className="items">
            {b.items.map((it, j) => (
              <li key={j}>
                {it.label ? <><strong>{it.label}</strong><div className="sub">{it.text}</div></> : it.text}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

// Help text: plain sentences, with any "- " lines shown as a short list.
export function Help({ text }: { text: string }) {
  const [lead, ...items] = text.split(/\n- /);
  return (
    <div className="help">
      <p>{lead.replace(/\n/g, " ")}</p>
      {items.length > 0 && <ul>{items.map((i) => <li key={i}>{i.replace(/\n\s*/g, " ")}</li>)}</ul>}
    </div>
  );
}

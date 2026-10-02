// Minimal, safe markdown renderer for copilot answers. Builds React elements
// (never raw HTML), so model output cannot inject markup or scripts.
// Supports: ### headings, paragraphs, "- " bullets, "1. " numbered lists,
// **bold**, *italic* / _italic_ and `code`.

// underscores only count as italics at word boundaries, so snake_case names stay intact
const INLINE = /(\*\*[^*]+\*\*|`[^`]+`|(?<![\w])_[^_]+_(?![\w])|\*[^*\s][^*]*\*)/g;

function inline(text, keyBase) {
  return text.split(INLINE).filter(Boolean).map((part, i) => {
    const k = `${keyBase}-${i}`;
    if (part.startsWith('**') && part.endsWith('**') && part.length > 4) return <strong key={k}>{part.slice(2, -2)}</strong>;
    if (part.startsWith('`') && part.endsWith('`') && part.length > 2) return <code key={k}>{part.slice(1, -1)}</code>;
    if ((part.startsWith('_') && part.endsWith('_')) || (part.startsWith('*') && part.endsWith('*'))) {
      if (part.length > 2) return <em key={k}>{part.slice(1, -1)}</em>;
    }
    return <span key={k}>{part}</span>;
  });
}

export default function Markdown({ text }) {
  const lines = String(text || '').replace(/\r/g, '').split('\n');
  const blocks = [];
  let list = null; // { type: 'ul' | 'ol', items: [] }
  let para = [];

  const flushPara = () => {
    if (para.length) blocks.push({ type: 'p', text: para.join(' ') });
    para = [];
  };
  const flushList = () => {
    if (list) blocks.push(list);
    list = null;
  };

  for (const raw of lines) {
    const line = raw.trimEnd();
    const bullet = line.match(/^\s*[-•*]\s+(.*)$/);
    const num = line.match(/^\s*\d+[.)]\s+(.*)$/);
    const head = line.match(/^\s*#{1,4}\s+(.*)$/);
    if (!line.trim()) { flushPara(); flushList(); continue; }
    if (head) { flushPara(); flushList(); blocks.push({ type: 'h', text: head[1] }); continue; }
    if (bullet || num) {
      flushPara();
      const type = bullet ? 'ul' : 'ol';
      if (!list || list.type !== type) { flushList(); list = { type, items: [] }; }
      list.items.push((bullet || num)[1]);
      continue;
    }
    flushList();
    para.push(line.trim());
  }
  flushPara();
  flushList();

  return (
    <div className="md">
      {blocks.map((b, i) => {
        if (b.type === 'h') return <h4 key={i}>{inline(b.text, i)}</h4>;
        if (b.type === 'p') return <p key={i}>{inline(b.text, i)}</p>;
        const Tag = b.type;
        return <Tag key={i}>{b.items.map((it, j) => <li key={j}>{inline(it, `${i}-${j}`)}</li>)}</Tag>;
      })}
    </div>
  );
}

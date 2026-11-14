export function TrustLens({ on, onToggle }: { on: boolean; onToggle: () => void }) {
  return (
    <button className="toggle" aria-pressed={on} onClick={onToggle} title="Dim everything except the evidence for the selected number">
      ◐ Trust lens
    </button>
  );
}

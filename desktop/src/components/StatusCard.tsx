interface StatusCardProps {
  title: string;
  value: string | number;
  description: string;
  indicator?: "success" | "warning" | "neutral";
}

export function StatusCard({
  title,
  value,
  description,
  indicator = "neutral",
}: StatusCardProps) {
  return (
    <article className="status-card">
      <div className="status-card-header">
        <span>{title}</span>
        <span className={`status-indicator ${indicator}`} />
      </div>

      <strong>{value}</strong>
      <small>{description}</small>
    </article>
  );
}
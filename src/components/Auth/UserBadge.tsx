import type { User } from "../../types";

interface UserBadgeProps {
  user: User;
  onLogout: () => void;
}

export default function UserBadge({ user, onLogout }: UserBadgeProps) {
  const initial = (user.email?.[0] || "?").toUpperCase();
  return (
    <div className="auth-user-badge">
      <span className="auth-avatar" aria-hidden="true">{initial}</span>
      <span className="auth-email" title={user.email}>{user.email.split("@")[0]}</span>
      <span className={"auth-role-pill auth-role-" + user.role}>{user.role}</span>
      <button className="auth-logout-btn" onClick={onLogout} title="Sign out" aria-label="Sign out">Sign out</button>
    </div>
  );
}

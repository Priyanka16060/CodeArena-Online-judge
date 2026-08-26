import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import type { ReactNode } from "react";

export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();

  if (loading) return <div className="page-loading loading-line">Checking credentials…</div>;
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

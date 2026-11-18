import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { obtenerToken } from "../api/cliente";

export default function RutaPrivada({ children }: { children: ReactNode }) {
  if (!obtenerToken()) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}
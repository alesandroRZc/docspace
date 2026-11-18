import { Navigate, Route, Routes } from "react-router-dom";
import LoginPage from "./pages/LoginPage";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/documentos" element={<h1>Documentos (próximamente)</h1>} />
      <Route path="*" element={<Navigate to="/login" />} />
    </Routes>
  );
}
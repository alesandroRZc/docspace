import { Navigate, Route, Routes } from "react-router-dom";
import LoginPage from "./pages/LoginPage";
import DocumentosPage from "./pages/DocumentosPage";
import RutaPrivada from "./components/RutaPrivada";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/documentos" element={<RutaPrivada><DocumentosPage /></RutaPrivada>} />      
      <Route path="*" element={<Navigate to="/login" />} />
    </Routes>
  );
}
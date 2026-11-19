import { Navigate, Route, Routes } from "react-router-dom";
import LoginPage from "./pages/LoginPage";
import RutaPrivada from "./components/RutaPrivada";
import DocumentosPage from "./pages/DocumentosPage";   
import DocumentoPage from "./pages/DocumentoPage";     
import RegistroPage from "./pages/RegistroPage";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/documentos" element={<RutaPrivada><DocumentosPage /></RutaPrivada>} />   
      <Route path="/documentos/:id" element={<RutaPrivada><DocumentoPage /></RutaPrivada>} />      
      <Route path="*" element={<Navigate to="/login" />} />
      <Route path="/registro" element={<RegistroPage />} />
    </Routes>
  );
}
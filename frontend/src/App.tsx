import { HashRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { AppLayout } from "./components/AppLayout";
import { LoginPage } from "./pages/LoginPage";
import { AssistantPage } from "./pages/AssistantPage";
import { DocumentsPage } from "./pages/DocumentsPage";
import "./styles/main.scss";

function AppRoutes() {
  const { session } = useAuth();
  return (
    <Routes>
      <Route
        path="/login"
        element={session ? <Navigate to="/assistant" replace /> : <LoginPage />}
      />
      <Route
        element={session ? <AppLayout /> : <Navigate to="/login" replace />}
      >
        <Route path="/assistant" element={<AssistantPage />} />
        <Route path="/documents" element={<DocumentsPage />} />
      </Route>
      <Route
        path="*"
        element={<Navigate to={session ? "/assistant" : "/login"} replace />}
      />
    </Routes>
  );
}

export default function App() {
  return (
    <HashRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </HashRouter>
  );
}

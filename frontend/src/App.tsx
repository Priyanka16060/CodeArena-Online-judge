import { Navigate, Route, Routes } from "react-router-dom";
import { Navbar } from "./components/Navbar";
import { RequireAuth } from "./components/RequireAuth";
import { LoginPage } from "./pages/LoginPage";
import { RegisterPage } from "./pages/RegisterPage";
import { ProblemsListPage } from "./pages/ProblemsListPage";
import { ProblemDetailPage } from "./pages/ProblemDetailPage";
import { SubmissionsPage } from "./pages/SubmissionsPage";

export default function App() {
  return (
    <div className="app-shell">
      <Navbar />
      <Routes>
        <Route path="/" element={<Navigate to="/problems" replace />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route
          path="/problems"
          element={
            <RequireAuth>
              <ProblemsListPage />
            </RequireAuth>
          }
        />
        <Route
          path="/problems/:slug"
          element={
            <RequireAuth>
              <ProblemDetailPage />
            </RequireAuth>
          }
        />
        <Route
          path="/submissions"
          element={
            <RequireAuth>
              <SubmissionsPage />
            </RequireAuth>
          }
        />
        <Route path="*" element={<Navigate to="/problems" replace />} />
      </Routes>
    </div>
  );
}

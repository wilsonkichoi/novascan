import { Routes, Route } from "react-router-dom";
import { AuthProvider } from "@/hooks/useAuth";
import ErrorBoundary from "@/components/ErrorBoundary";
import ProtectedRoute from "@/components/ProtectedRoute";
import AppShell from "@/components/AppShell";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import ScanPage from "./pages/ScanPage";
import AnalyticsPage from "./pages/AnalyticsPage";
import TransactionsPage from "./pages/TransactionsPage";
import ReceiptsPage from "./pages/ReceiptsPage";
import ReceiptDetailPage from "./pages/ReceiptDetailPage";
import NotFoundPage from "./pages/NotFoundPage";

export default function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<ProtectedRoute />}>
            <Route element={<AppShell />}>
              <Route index element={<DashboardPage />} />
              <Route path="/scan" element={<ScanPage />} />
              <Route path="/analytics" element={<AnalyticsPage />} />
              <Route path="/transactions" element={<TransactionsPage />} />
              <Route path="/receipts" element={<ReceiptsPage />} />
              <Route path="/receipts/:id" element={<ReceiptDetailPage />} />
            </Route>
          </Route>
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </AuthProvider>
    </ErrorBoundary>
  );
}

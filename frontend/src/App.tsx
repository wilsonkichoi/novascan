import { Routes, Route } from "react-router-dom";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import UploadPage from "./pages/UploadPage";
import ReceiptsPage from "./pages/ReceiptsPage";
import ReceiptDetailPage from "./pages/ReceiptDetailPage";
import TransactionsPage from "./pages/TransactionsPage";
import NotFoundPage from "./pages/NotFoundPage";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/dashboard" element={<DashboardPage />} />
      <Route path="/upload" element={<UploadPage />} />
      <Route path="/receipts" element={<ReceiptsPage />} />
      <Route path="/receipts/:id" element={<ReceiptDetailPage />} />
      <Route path="/transactions" element={<TransactionsPage />} />
      <Route path="/" element={<DashboardPage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}

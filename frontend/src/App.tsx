import { Routes, Route } from "react-router-dom";

function LoginPage() {
  return <h1>Login</h1>;
}

function DashboardPage() {
  return <h1>Dashboard</h1>;
}

function UploadPage() {
  return <h1>Upload</h1>;
}

function ReceiptsPage() {
  return <h1>Receipts</h1>;
}

function ReceiptDetailPage() {
  return <h1>Receipt Detail</h1>;
}

function TransactionsPage() {
  return <h1>Transactions</h1>;
}

function NotFoundPage() {
  return <h1>404 — Not Found</h1>;
}

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

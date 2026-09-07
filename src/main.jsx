import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App.jsx";
import "./index.css";
import L from "leaflet";

if (typeof window !== "undefined") {
  window.L = L;
}

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("React ErrorBoundary caught error:", error, errorInfo);
    this.setState({ error, errorInfo });
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 30, fontFamily: "sans-serif", background: "#fff", color: "#111" }}>
          <h2 style={{ color: "#e11d48" }}>Uygulama Yüklenirken Bir Hata Oluştu</h2>
          <pre style={{ background: "#f1f5f9", padding: 15, borderRadius: 8, overflowX: "auto" }}>
            {this.state.error?.toString()}
          </pre>
          <pre style={{ background: "#f8fafc", padding: 15, borderRadius: 8, overflowX: "auto", fontSize: 12 }}>
            {this.state.errorInfo?.componentStack || this.state.error?.stack}
          </pre>
          <button 
            onClick={() => { localStorage.clear(); window.location.reload(); }}
            style={{ padding: "10px 20px", background: "#FF5A36", color: "#fff", border: "none", borderRadius: 8, cursor: "pointer", marginTop: 10 }}
          >
            Önbelleği Temizle ve Yeniden Başlat
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

const rootEl = document.getElementById("root");
if (rootEl) {
  ReactDOM.createRoot(rootEl).render(
    <React.StrictMode>
      <ErrorBoundary>
        <App />
      </ErrorBoundary>
    </React.StrictMode>
  );
} else {
  console.error("Root element #root not found!");
}

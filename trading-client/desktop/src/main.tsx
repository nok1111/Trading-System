import ReactDOM from "react-dom/client";
import App from "./App";
import { I18nProvider } from "./i18n/I18nContext";
import "./index.css";

// Force login on every app start — clear stored token before React mounts
localStorage.removeItem("jwt");

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <I18nProvider>
    <App />
  </I18nProvider>
);

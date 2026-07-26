import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";

// Force login on every app start — clear stored token before React mounts
localStorage.removeItem("jwt");

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <App />
);

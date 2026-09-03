import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import MiniApp from "./MiniApp";
import "./index.css";

const isMini = window.location.search.includes("window=mini") || window.location.hash.includes("mini");

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    {isMini ? <MiniApp /> : <App />}
  </React.StrictMode>
);

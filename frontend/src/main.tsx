import { createRoot } from "react-dom/client";
import App from "./App";
import "./index.css";

// Suppress rc-dock drag/drop style errors (known library issue)
const originalError = console.error;
console.error = (...args) => {
  const errorMessage = args[0]?.toString() || '';
  
  // Suppress rc-dock drag/drop errors
  if (
    errorMessage.includes("Cannot read properties of null (reading 'style')") ||
    errorMessage.includes("Cannot read properties of undefined (reading 'element')") ||
    errorMessage.includes("BoxDataCache") ||
    errorMessage.includes("moveDraggingElement")
  ) {
    return;
  }
  
  originalError.apply(console, args);
};

createRoot(document.getElementById("root")!).render(<App />);

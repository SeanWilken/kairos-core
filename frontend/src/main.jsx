import React from "react";
import { createRoot } from "react-dom/client";

import EnvWizard from "./kairos-core-setup.jsx";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <EnvWizard />
  </React.StrictMode>
);

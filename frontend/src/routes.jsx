import { createBrowserRouter } from "react-router-dom";

import { KairosShell } from "./app/components/layout/KairosShell";
import { CoreSetupHome } from "./app/components/pages/CoreSetupHome";
import { Backups } from "./app/components/pages/Backups";
import { Retrain } from "./app/components/pages/Retrain";
import { Recovery } from "./app/components/pages/Recovery";

export const router = createBrowserRouter(
  [
    {
      path: "/",
      element: <KairosShell />,
      children: [
        { index: true, element: <CoreSetupHome /> },
        { path: "backups", element: <Backups /> },
        { path: "retrain", element: <Retrain /> },
        { path: "recovery", element: <Recovery /> },
      ],
    },
  ],
  {
    future: {
      v7_startTransition: true,
    },
  }
);

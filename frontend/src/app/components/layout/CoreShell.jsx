import { NavLink, Outlet } from "react-router-dom";
import { Bell, ChevronDown, RotateCcw, Settings, ShieldAlert, User } from "lucide-react";
import {
  Button,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@myai-tech/myui";

const navigation = [
  { name: "Core Setup", href: "/" },
  { name: "Backups", href: "/backups" },
  { name: "Retrain", href: "/retrain" },
  { name: "Recovery", href: "/recovery" },
];

export function MyAIShell() {
  return (
    <div className="h-screen flex flex-col bg-zinc-50">
      <header className="h-16 bg-white border-b border-zinc-200 flex items-center justify-between px-6 flex-shrink-0">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-3">
            <img src="/myAI.svg" alt="MyAI" className="h-8 w-8 rounded-md object-contain" />
            <h1 className="text-xl font-bold text-zinc-900">MyAI Core</h1>
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                className="inline-flex h-9 items-center gap-2 rounded-md border border-zinc-200 bg-white px-3 text-sm font-medium text-zinc-900 shadow-xs transition-colors hover:bg-zinc-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-400"
              >
                Development
                <ChevronDown className="h-4 w-4" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="myai-overlay-content w-44">
              <DropdownMenuItem className="myai-overlay-item">Development</DropdownMenuItem>
              <DropdownMenuItem className="myai-overlay-item">Staging</DropdownMenuItem>
              <DropdownMenuItem className="myai-overlay-item">Production</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        <div className="flex items-center gap-3">
          <span className="text-xs text-zinc-500">status: not checked</span>
          <Button variant="ghost" size="icon">
            <Bell className="h-4 w-4" />
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                className="inline-flex h-9 items-center gap-2 rounded-md border border-zinc-200 bg-white px-3 text-sm font-medium text-zinc-900 shadow-xs transition-colors hover:bg-zinc-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-400"
              >
                <User className="h-4 w-4" />
                Admin
                <ChevronDown className="h-4 w-4" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="myai-overlay-content w-40">
              <DropdownMenuItem className="myai-overlay-item">
                <Settings className="h-4 w-4 mr-2" />
                Settings
              </DropdownMenuItem>
              <DropdownMenuItem className="myai-overlay-item">
                <RotateCcw className="h-4 w-4 mr-2" />
                Backup Tools
              </DropdownMenuItem>
              <DropdownMenuItem className="myai-overlay-item">
                <ShieldAlert className="h-4 w-4 mr-2" />
                Admin Reset
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem className="myai-overlay-item">Sign Out</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <aside className="w-64 bg-white border-r border-zinc-200 flex-shrink-0 overflow-y-auto">
          <nav className="p-4 space-y-1">
            {navigation.map((item) => (
              <NavLink
                key={item.name}
                to={item.href}
                end={item.href === "/"}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-zinc-900 text-white"
                      : "text-zinc-700 hover:bg-zinc-100 hover:text-zinc-900"
                  }`
                }
              >
                {item.name}
              </NavLink>
            ))}
          </nav>
        </aside>

        <main className="flex-1 overflow-y-auto bg-zinc-50">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";
import {
  Home,
  ScanLine,
  BarChart3,
  ArrowLeftRight,
  Receipt,
  LogOut,
} from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { to: "/", label: "Home", icon: Home },
  { to: "/scan", label: "Scan", icon: ScanLine },
  { to: "/analytics", label: "Analytics", icon: BarChart3 },
  { to: "/transactions", label: "Transactions", icon: ArrowLeftRight },
  { to: "/receipts", label: "Receipts", icon: Receipt },
] as const;

export default function AppShell() {
  const { signOut } = useAuth();

  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      {/* Desktop sidebar */}
      <aside className="bg-sidebar-background border-sidebar-border hidden w-60 shrink-0 border-r md:flex md:flex-col">
        <div className="border-sidebar-border border-b px-4 py-4">
          <span className="text-sidebar-primary text-lg font-bold tracking-tight">
            NovaScan
          </span>
        </div>
        <nav aria-label="Main navigation" className="flex flex-1 flex-col gap-1 p-2">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-sidebar-accent text-sidebar-accent-foreground"
                    : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                )
              }
            >
              <Icon className="size-4 shrink-0" />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="border-sidebar-border border-t p-2">
          <button
            type="button"
            onClick={signOut}
            className="text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors"
          >
            <LogOut className="size-4 shrink-0" />
            Sign out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto pb-16 md:pb-0">
        <div className="mx-auto max-w-5xl px-4 py-6">
          <Outlet />
        </div>
      </main>

      {/* Mobile bottom navigation */}
      <nav
        aria-label="Main navigation"
        className="bg-background border-border fixed inset-x-0 bottom-0 z-50 flex border-t md:hidden"
      >
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              cn(
                "flex flex-1 flex-col items-center gap-0.5 py-2 text-xs font-medium transition-colors",
                isActive
                  ? "text-primary"
                  : "text-muted-foreground hover:text-foreground",
              )
            }
          >
            <Icon className="size-5" />
            <span>{label}</span>
          </NavLink>
        ))}
        <button
          type="button"
          onClick={signOut}
          className="text-muted-foreground hover:text-foreground flex flex-1 flex-col items-center gap-0.5 py-2 text-xs font-medium transition-colors"
        >
          <LogOut className="size-5" />
          <span>Sign out</span>
        </button>
      </nav>
    </div>
  );
}

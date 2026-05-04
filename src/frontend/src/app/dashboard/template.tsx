"use client";

import { usePathname } from "next/navigation";

export default function DashboardTemplate({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div
      key={pathname}
      className="dashboard-route-enter flex min-h-0 min-w-0 w-full flex-1 flex-col"
    >
      {children}
    </div>
  );
}

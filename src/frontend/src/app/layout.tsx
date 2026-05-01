import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CLAIR OBSCUR — Dashboard",
  description: "Logs & prédictions",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="fr" suppressHydrationWarning>
      <body className="antialiased" suppressHydrationWarning>
        {children}
      </body>
    </html>
  );
}

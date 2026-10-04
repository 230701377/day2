import "./globals.css";
import type { Metadata } from "next";
import { Providers } from "@/components/Providers";
import { Toaster } from "react-hot-toast";

export const metadata: Metadata = {
  title: "Contract Lifecycle & Approval Management",
  description: "Enterprise CLM with AI-powered contract intelligence.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>
          {children}
          <Toaster position="top-right" />
        </Providers>
      </body>
    </html>
  );
}

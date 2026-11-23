import React from "react";
import "./globals.css";
import { Navbar } from "@/components/Navbar";

export const metadata = {
  title: "BugScope — Evidence-Checked Autonomous Debugging Agent",
  description: "AI-Powered Autonomous Bug Investigation & Fix Validation for Python",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-background text-slate-100 flex flex-col min-h-screen">
        <Navbar />
        <main className="flex-1 max-w-7xl w-full mx-auto px-4 py-8">
          {children}
        </main>
        <footer className="border-t border-border py-6 text-center text-xs text-gray-500">
          BugScope Autonomous Debugger &bull; Built with LangGraph, FastAPI, Next.js &amp; Pytest
        </footer>
      </body>
    </html>
  );
}

import { Sidebar } from "@/components/app-shell/sidebar";
import { Topbar } from "@/components/app-shell/topbar";
import { ToasterProvider } from "@/components/ui/toaster";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <ToasterProvider>
      <div className="min-h-screen">
        <Sidebar />
        <div className="lg:pl-60">
          <Topbar />
          <main className="mx-auto max-w-[1200px] animate-fade-in px-4 py-6 lg:px-8 lg:py-8">
            {children}
          </main>
        </div>
      </div>
    </ToasterProvider>
  );
}

import { MobileNav, Sidebar } from "@/components/sidebar";
import { ToastProvider } from "@/components/toast";
import { REPO } from "@/lib/github";

export default function AppLayout({ children }: LayoutProps<"/">) {
  return (
    <ToastProvider>
      <div className="flex min-h-full">
        <Sidebar repo={REPO} />
        <div className="min-w-0 flex-1">
          <MobileNav />
          <main className="mx-auto w-full max-w-[1240px] px-4 pt-6 pb-28 sm:px-6 md:px-8 md:pt-10 md:pb-16">
            {children}
          </main>
        </div>
      </div>
    </ToastProvider>
  );
}

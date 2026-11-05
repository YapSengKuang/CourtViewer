import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL("https://golf-booker-beta.pages.dev"),
  title: "Tee times",
  description: "Search open golf tee times across local courses.",
  openGraph: {
    type: "website",
    title: "Tee times",
    description: "Search open golf tee times across local courses.",
    siteName: "Tee time",
    images: [{ url: "/branding/tee-time-preview.jpeg", width: 474, height: 298,
      alt: "An illustrated golf green with a red flag and a sand bunker." }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Tee times",
    description: "Search open golf tee times across local courses.",
    images: ["/branding/tee-time-preview.jpeg"],
  },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: `try{var t=localStorage.getItem('tee-time-theme');document.documentElement.dataset.theme=t==='light'||t==='dark'?t:matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'}catch{document.documentElement.dataset.theme=matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'}` }} />
        {/* Native CSS keeps the planner independent of the Tailwind worker. */}
        {/* eslint-disable-next-line @next/next/no-css-tags -- static stylesheet shared by the two round-planning routes */}
        <link rel="stylesheet" href="/round.css?v=9" precedence="default" />
      </head>
      <body className="min-h-full">{children}</body>
    </html>
  );
}

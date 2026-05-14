import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "DigIdentity",
  description: "Living Site Platform",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="it">
      <body>{children}</body>
    </html>
  );
}

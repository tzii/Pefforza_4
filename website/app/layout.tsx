import type { Metadata } from 'next';
import { publicAsset, siteUrl } from '@/lib/site';
import '@fontsource-variable/space-grotesk';
import '@fontsource/space-mono/400.css';
import './globals.css';

export const metadata: Metadata = {
  title: 'Pefforza 4 — Your move. Reimagined.',
  description:
    'Explore Pefforza 4: an open-source Python Connect Four project with computer vision, AI, and voice. Discover the architecture, run it locally, and try the browser demo.',
  metadataBase: new URL(siteUrl),
  alternates: { canonical: siteUrl },
  openGraph: {
    title: 'Pefforza 4 — Your move. Reimagined.',
    description:
      'Connect Four meets artificial intelligence, computer vision, and a little attitude.',
    type: 'website',
    url: siteUrl,
    images: [new URL('images/pefforza-hero.webp', siteUrl).href],
  },
  icons: { icon: publicAsset('/favicon.svg') },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="dark">
      <body>{children}</body>
    </html>
  );
}

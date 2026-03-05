import type { Metadata } from 'next';
import { Playfair_Display, DM_Sans, DM_Mono } from 'next/font/google';
import './globals.css';

const playfair = Playfair_Display({
  subsets: ['latin', 'cyrillic'],
  variable: '--font-heading',
  weight: ['400', '700', '900']
});

const dmSans = DM_Sans({
  subsets: ['latin', 'latin-ext'],
  variable: '--font-body',
  weight: ['300', '400', '500', '600']
});

const dmMono = DM_Mono({
  subsets: ['latin'],
  variable: '--font-mono',
  weight: ['400', '500']
});

export const metadata: Metadata = {
  title: 'Wishlist — делитесь желаниями',
  description: 'Социальный вишлист с бронированием и совместными подарками'
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ru">
      <body className={`${playfair.variable} ${dmSans.variable} ${dmMono.variable}`}>
        <nav className="navbar">
          <div className="navbar-brand">
            <span className="dot" />
            Wishlist
          </div>
          <span style={{ fontSize: '.82rem', color: 'var(--muted)', fontFamily: 'var(--font-mono)' }}>
            ✦ делитесь желаниями
          </span>
        </nav>
        {children}
      </body>
    </html>
  );
}

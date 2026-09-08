import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Procesador de imágenes | Mas Ferre",
  description: "Procesamiento masivo de imágenes de producto con fondo transparente y acabado de estudio gratuito.",
  icons: { icon: "/favicon.svg", shortcut: "/favicon.svg" },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="es"><body className="antialiased">{children}</body></html>;
}

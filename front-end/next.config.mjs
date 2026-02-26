/** @type {import('next').NextConfig} */
const nextConfig = {
  i18n: {
    locales: ["en", "zh", "es", "de", "ja", "pt-BR"],
    defaultLocale: "en",
    localeDetection: true,
  },
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
}

export default nextConfig
